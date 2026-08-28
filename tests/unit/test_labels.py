"""Check de etiquetas (T-03, Fase 5): invariantes de data/eval/labels.jsonl.
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
labels.jsonl es un artefacto versionado (una pasada + auditoría de Adolfo): si
falta, es un fallo real del repo, no un artefacto pesado opcional — no se skipea."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LABELS_PATH = ROOT / "data" / "eval" / "labels.jsonl"
GOLDEN_PATH = ROOT / "data" / "eval" / "golden.jsonl"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"

CLAVES = {"id", "pregunta", "secciones_apuntes", "secciones_manual", "sin_respuesta", "notas"}


def _read_jsonl(path):
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@pytest.fixture(scope="module")
def golden_eval():
    return [g for g in _read_jsonl(GOLDEN_PATH) if g.get("uso") == "eval"]


@pytest.fixture(scope="module")
def labels():
    assert LABELS_PATH.exists(), (
        f"falta {LABELS_PATH} — la produce la sesión de etiquetado "
        "(.claude/plans/phase-5-retrieval/etiquetado-prompt.md)"
    )
    return _read_jsonl(LABELS_PATH)


@pytest.fixture(scope="module")
def secciones_alcanzables():
    """section_ids presentes en algún chunk de prosa — los únicos que el
    retriever puede devolver; una etiqueta fuera de este conjunto sería
    irrecuperable por construcción."""
    alcanzables = set()
    for c in _read_jsonl(CHUNKS_PATH):
        if c["tipo"] == "prosa":
            alcanzables.update(c["section_ids"])
    return alcanzables


def test_una_fila_por_pregunta_eval_en_el_orden_del_golden(labels, golden_eval):
    assert [l["id"] for l in labels] == [g["id"] for g in golden_eval]


def test_la_pregunta_es_la_literal_del_golden(labels, golden_eval):
    golden_by_id = {g["id"]: g for g in golden_eval}
    for fila in labels:
        assert fila["pregunta"] == golden_by_id[fila["id"]]["pregunta"], fila["id"]


def test_esquema_exacto_de_cada_fila(labels):
    for fila in labels:
        assert set(fila) == CLAVES, fila["id"]
        assert isinstance(fila["secciones_apuntes"], list), fila["id"]
        assert isinstance(fila["secciones_manual"], list), fila["id"]
        assert all(isinstance(s, str) for s in fila["secciones_apuntes"]), fila["id"]
        assert all(isinstance(s, str) for s in fila["secciones_manual"]), fila["id"]
        assert isinstance(fila["sin_respuesta"], bool), fila["id"]
        assert fila["notas"] is None or isinstance(fila["notas"], str), fila["id"]


def test_toda_seccion_etiquetada_existe_y_es_alcanzable(labels, secciones_alcanzables):
    for fila in labels:
        for section_id in fila["secciones_apuntes"] + fila["secciones_manual"]:
            assert section_id in secciones_alcanzables, (fila["id"], section_id)


def test_sin_respuesta_equivale_a_listas_vacias(labels):
    for fila in labels:
        vacia = not fila["secciones_apuntes"] and not fila["secciones_manual"]
        assert fila["sin_respuesta"] == vacia, fila["id"]


def test_sin_duplicados_dentro_de_cada_lista(labels):
    for fila in labels:
        for clave in ("secciones_apuntes", "secciones_manual"):
            assert len(fila[clave]) == len(set(fila[clave])), (fila["id"], clave)


def test_secciones_en_la_lista_de_su_corpus(labels):
    """Las secciones de apuntes son `fichero#sección`; las del manual, `9-3.2`.
    Una sección en la lista equivocada rompería el recall por corpus."""
    for fila in labels:
        assert all("#" in s for s in fila["secciones_apuntes"]), fila["id"]
        assert all("#" not in s for s in fila["secciones_manual"]), fila["id"]


def test_la_pregunta_requiere_tool_esta_marcada_coherentemente(labels, golden_eval):
    """Contrato de aceptación: la pregunta con requiere_tool=true va con
    sin_respuesta o etiquetada, pero siempre con el motivo en notas."""
    requiere_tool = {g["id"] for g in golden_eval if g.get("requiere_tool")}
    for fila in labels:
        if fila["id"] in requiere_tool:
            assert fila["notas"], fila["id"]
