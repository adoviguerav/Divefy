"""Andamiaje del implementador para el corrector v1 (T-05, Fase 5).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Fixture sintético mini con etiquetas y recuperados conocidos a mano: cada valor
del resumen está calculado en el comentario, no copiado de la salida."""

import json

import pytest

from divefy.evals.corrector import evaluate, extract_numbers, serialize, write_result

# --- fixture mini: 4 chunks, 3 preguntas ---

ROWS = {
    "ca": {"section_ids": ["A#s1"], "corpus": "apuntes", "n_tokens": 10,
           "texto": "subir a 18 m/min como máximo"},
    "cb": {"section_ids": ["A#s2"], "corpus": "apuntes", "n_tokens": 20,
           "texto": "el chaleco controla la flotabilidad"},
    "cm": {"section_ids": ["9-1"], "corpus": "manual", "n_tokens": 30,
           "texto": "ascend at 30 fsw per minute"},
    "cn": {"section_ids": ["9-2"], "corpus": "manual", "n_tokens": 40,
           "texto": "nitrogen absorption increases with depth"},
}

GOLDEN = [
    {"id": "q1", "pregunta": "¿A qué velocidad subo?", "respuesta_esperada": ["A 18 m/min máximo"]},
    {"id": "q2", "pregunta": "¿Qué controla el chaleco?", "respuesta_esperada": ["La flotabilidad"]},
    {"id": "q3", "pregunta": "¿Hay tiburones domésticos?", "respuesta_esperada": ["No hay soporte"]},
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
    return evaluate(GOLDEN, LABELS, RETRIEVED, ROWS)


def test_resumen_del_fixture_calculado_a_mano():
    resumen, _ = _resultado()
    # con etiqueta: q1, q2 → q1 acierta (cm cubre 9-1), q2 no → recall 1/2
    assert resumen["recall_at_k"] == 0.5
    # apuntes: q1 y q2 tienen secciones de apuntes; acierta solo q1 (ca cubre A#s1)
    assert resumen["recall_apuntes"] == 0.5
    # manual: solo q1 tiene secciones de manual; acierta → 1.0
    assert resumen["recall_manual"] == 1.0
    # mrr: q1 rank 1 (cm), q2 sin acierto → (1/1 + 0) / 2
    assert resumen["mrr"] == 0.5
    # tokens: q1=30+10, q2=30+40, q3=10 → (40+70+10)/3
    assert resumen["tokens_recuperados_media"] == 40.0
    # numérica: solo q1 lleva número (18); "18" está en el texto de ca → 1.0
    assert resumen["match_numerico"] == 1.0
    assert resumen["n_preguntas"] == 3


def test_detalle_marca_rank_y_aciertos_por_corpus():
    _, detalle = _resultado()
    d1 = next(d for d in detalle if d["id"] == "q1")
    assert d1["recuperados"] == ["cm", "ca"]
    assert d1["acierto"] is True
    assert d1["rank"] == 1
    assert d1["acierto_apuntes"] is True
    assert d1["acierto_manual"] is True

    d2 = next(d for d in detalle if d["id"] == "q2")
    assert d2["acierto"] is False
    assert d2["rank"] is None
    assert d2["acierto_apuntes"] is False
    assert d2["acierto_manual"] is None  # su etiqueta no tiene secciones de manual


def test_sin_respuesta_queda_fuera_de_recall_pero_dentro_del_detalle():
    resumen, detalle = _resultado()
    d3 = next(d for d in detalle if d["id"] == "q3")
    assert d3["sin_respuesta"] is True
    assert d3["acierto"] is None  # no hay sección correcta que recuperar
    assert d3["recuperados"] == ["ca"]  # insumo de abstención para F7
    # el denominador de recall/mrr es 2, no 3 (ya cubierto arriba: 0.5 con 1/2)
    assert resumen["n_preguntas"] == 3


def test_extract_numbers_normaliza_coma_decimal():
    assert extract_numbers("parada a 1,5 bar y 18 m") == {1.5, 18.0}
    assert extract_numbers("safety stop at 1.5 bar") == {1.5}
    assert extract_numbers("sin cifras") == set()


def test_match_numerico_exige_todos_los_numeros():
    golden = [{"id": "q1", "pregunta": "¿?", "respuesta_esperada": ["12 h simples y 18 h sucesivas"]}]
    labels = {"q1": {"id": "q1", "secciones_apuntes": ["A#s1"], "secciones_manual": [],
                     "sin_respuesta": False, "notas": None}}
    # el texto recuperado (ca) contiene 18 pero no 12 → False
    _, detalle = evaluate(golden, labels, {"q1": ["ca"]}, ROWS)
    assert detalle[0]["match_numerico"] is False


def test_evaluate_es_determinista():
    assert serialize(_resultado()) == serialize(_resultado())


# --- política nunca-se-sobreescribe ---


def test_write_result_es_no_op_si_la_fila_es_identica(tmp_path):
    data = {"config": {"k": 5}, "resumen": {"recall_at_k": 0.5}, "detalle": []}
    path = tmp_path / "run.json"
    assert write_result(data, path) == "escrita"
    assert write_result(data, path) == "identica"  # no-op OK
    assert path.read_text(encoding="utf-8") == serialize(data)


def test_write_result_lanza_error_con_diff_si_la_fila_difiere(tmp_path):
    path = tmp_path / "run.json"
    write_result({"config": {"k": 5}, "resumen": {"recall_at_k": 0.5}, "detalle": []}, path)
    with pytest.raises(FileExistsError, match="recall_at_k"):
        write_result({"config": {"k": 5}, "resumen": {"recall_at_k": 0.7}, "detalle": []}, path)
