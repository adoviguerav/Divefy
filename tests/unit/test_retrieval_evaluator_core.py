"""Andamiaje del implementador para el retrieval_evaluator (T-05 + revisión de métricas).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Fixture sintético mini con etiquetas y recuperados conocidos a mano: cada valor
del resumen está calculado en el comentario, no copiado de la salida.
Métricas: ranx (hit_rate/recall/precision/mrr) — ver metricas-framework.md."""

import json

import pytest

from divefy.evals.retrieval_evaluator import evaluate, serialize, write_result

# --- fixture mini: 4 chunks, 3 preguntas, k=2 ---

CHUNK_SECTIONS = {
    "ca": {"A#s1"},
    "cb": {"A#s2"},
    "cm": {"9-1"},
    "cn": {"9-2"},
}
CHUNK_TOKENS = {"ca": 10, "cb": 20, "cm": 30, "cn": 40}

GOLDEN = [
    {"id": "q1", "pregunta": "¿A qué velocidad subo?"},
    {"id": "q2", "pregunta": "¿Qué controla el chaleco?"},
    {"id": "q3", "pregunta": "¿Hay tiburones domésticos?"},
]

LABELS = {
    "q1": {"id": "q1", "secciones_apuntes": ["A#s1"], "secciones_manual": ["9-1"],
           "sin_respuesta": False, "notas": None},
    "q2": {"id": "q2", "secciones_apuntes": ["A#s2"], "secciones_manual": [],
           "sin_respuesta": False, "notas": None},
    "q3": {"id": "q3", "secciones_apuntes": [], "secciones_manual": [],
           "sin_respuesta": True, "notas": "fuera del corpus"},
}

RETRIEVED = {"q1": ["cm", "ca"], "q2": ["cm", "cn"], "q3": ["ca"]}


def _resultado():
    return evaluate(GOLDEN, LABELS, RETRIEVED, CHUNK_SECTIONS, CHUNK_TOKENS, k=2)


def test_resumen_del_fixture_calculado_a_mano():
    resumen, _ = _resultado()
    # q1: recuperados [cm, ca] — cm toca 9-1 y ca toca A#s1 → ambos relevantes.
    # q2: recuperados [cm, cn] — su etiqueta es {A#s2}, ninguno la toca.
    # q3: sin_respuesta → fuera de los agregados de ranking.
    assert resumen["hit_rate"] == 0.5        # q1 sí, q2 no → 1/2
    assert resumen["precision"] == 0.5       # q1: 2/2 · q2: 0/2 → media 0.5
    assert resumen["mrr"] == 0.5             # q1: 1º relevante en puesto 1 · q2: 0
    assert resumen["recall"] == 0.5          # q1: cubre 2 de 2 etiquetadas · q2: 0 de 1
    assert resumen["tokens_recuperados_media"] == 40.0  # (40 + 70 + 10) / 3
    assert resumen["n_preguntas"] == 3
    assert resumen["n_puntuadas"] == 2  # q3 sin_respuesta no puntúa (review #7)


def test_desglose_por_corpus_sigue_la_etiqueta_de_cada_corpus():
    resumen, _ = _resultado()
    # apuntes: q1 (A#s1, la trae ca) y q2 (A#s2, no viene) → 1/2
    assert resumen["hit_rate_apuntes"] == 0.5
    # manual: solo q1 tiene etiqueta de manual (9-1, la trae cm) → 1/1
    assert resumen["hit_rate_manual"] == 1.0


def test_detalle_es_crudo_una_entrada_por_pregunta():
    _, detalle = _resultado()
    assert [d["id"] for d in detalle] == ["q1", "q2", "q3"]
    for d in detalle:
        assert set(d) == {"id", "recuperados", "tokens", "sin_respuesta"}
    d3 = detalle[2]
    assert d3["sin_respuesta"] is True
    assert d3["recuperados"] == ["ca"]  # insumo de abstención: presente aunque no puntúe
    assert d3["tokens"] == 10


def test_etiqueta_entera_en_otro_corpus_cuenta_como_fallo_no_como_crash():
    """Caso borde decidido (metricas-framework.md): q140 solo-manual evaluada
    sobre una colección de apuntes — ningún chunk puede ser relevante; la
    pregunta puntúa 0 (es lo que la ablación de corpus mide), no se excluye."""
    golden = [{"id": "qx", "pregunta": "¿?"}]
    labels = {"qx": {"id": "qx", "secciones_apuntes": [], "secciones_manual": ["9-9"],
                     "sin_respuesta": False, "notas": None}}
    solo_apuntes = {"ca": {"A#s1"}}
    resumen, _ = evaluate(golden, labels, {"qx": ["ca"]}, solo_apuntes, {"ca": 10}, k=1)
    assert resumen["hit_rate"] == 0.0
    assert resumen["recall"] == 0.0
    assert resumen["mrr"] == 0.0
    assert resumen["hit_rate_manual"] == 0.0
    assert resumen["hit_rate_apuntes"] is None  # ninguna pregunta con etiqueta de apuntes
    assert resumen["n_puntuadas"] == 1


def test_evaluate_es_determinista():
    resumen_a, detalle_a = _resultado()
    resumen_b, detalle_b = _resultado()
    assert serialize({"resumen": resumen_a, "detalle": detalle_a}) == serialize(
        {"resumen": resumen_b, "detalle": detalle_b}
    )


# --- fixes de la review 2026-08-30 (hallazgos 3 y 9) ---


def test_golden_sin_preguntas_eval_lanza_error_claro(tmp_path, monkeypatch):
    """Hallazgo 3: golden truncado o campo renombrado → error que lo dice, no
    ZeroDivisionError tres capas más abajo."""
    from divefy.config import RetrievalConfig
    from divefy.evals import retrieval_evaluator

    golden = tmp_path / "golden.jsonl"
    golden.write_text(
        json.dumps({"id": "q1", "pregunta": "¿?", "uso": "repaso"}) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(retrieval_evaluator, "GOLDEN_PATH", golden)
    monkeypatch.setattr(retrieval_evaluator, "LABELS_PATH", tmp_path / "labels.jsonl")

    config = RetrievalConfig(corpus="apuntes", extras="base", embedding="bgem3", search="densa", k=5)
    with pytest.raises(ValueError, match="uso=eval"):
        retrieval_evaluator.run(config)


def test_rutas_ancladas_al_repo_no_al_cwd(tmp_path, monkeypatch):
    """Hallazgo 9: el retrieval_evaluator funciona desde cualquier directorio."""
    from divefy.evals import retrieval_evaluator

    monkeypatch.chdir(tmp_path)
    assert retrieval_evaluator.GOLDEN_PATH.is_absolute()
    assert retrieval_evaluator.GOLDEN_PATH.exists()
    assert retrieval_evaluator.LABELS_PATH.exists()


# --- política nunca-se-sobreescribe (sin cambios en la revisión de métricas) ---


def test_write_result_es_no_op_si_la_fila_es_identica(tmp_path):
    data = {"config": {"k": 5}, "resumen": {"hit_rate": 0.5}, "detalle": []}
    path = tmp_path / "run.json"
    assert write_result(data, path) == "escrita"
    assert write_result(data, path) == "identica"  # no-op OK
    assert path.read_text(encoding="utf-8") == serialize(data)


def test_write_result_lanza_error_con_diff_si_la_fila_difiere(tmp_path):
    path = tmp_path / "run.json"
    write_result({"config": {"k": 5}, "resumen": {"hit_rate": 0.5}, "detalle": []}, path)
    with pytest.raises(FileExistsError, match="hit_rate"):
        write_result({"config": {"k": 5}, "resumen": {"hit_rate": 0.7}, "detalle": []}, path)
