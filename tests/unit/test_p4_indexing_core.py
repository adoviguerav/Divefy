"""Andamiaje del implementador para las funciones puras de Fase 4 (indexing).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Fixtures hechas a mano (no jsonl reales) por velocidad y determinismo, mismo estilo
que test_p2_chunking_core.py / test_p3_enrich_core.py."""

import pytest

from divefy.pipeline.p4_indexing import build_rows

CHUNKS = [
    {"id": "a1", "corpus": "apuntes", "texto": "texto a1", "tipo": "prosa"},
    {"id": "a2", "corpus": "apuntes", "texto": "texto a2", "tipo": "prosa"},
    {"id": "m1", "corpus": "manual", "texto": "texto m1", "tipo": "prosa"},
    {"id": "m2", "corpus": "manual", "texto": "texto m2", "tipo": "puntero_tabla"},
]

# Todo chunk de prosa tiene su entrada — un chunk de prosa sin enrich es un fallo de
# Fase 3 a medio correr, no un caso normal (build_rows lo rechaza, ver test más abajo).
ENRICH = [
    {"id": "a1", "contexto": "contexto a1", "preguntas": ["p1", "p2"]},
    {"id": "a2", "contexto": "contexto a2", "preguntas": ["p1"]},
    {"id": "m1", "contexto": "contexto m1", "preguntas": ["p1", "p2", "p3"]},
]


def test_base_incluye_todos_los_chunks_del_corpus_filtrado():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    assert {r["id"] for r in rows["base"]} == {"a1", "a2"}


def test_base_excluye_punteros_de_tabla():
    rows = build_rows(CHUNKS, ENRICH, "manual")
    assert {r["id"] for r in rows["base"]} == {"m1"}


def test_combined_no_filtra_por_corpus():
    rows = build_rows(CHUNKS, ENRICH, "combined")
    assert {r["id"] for r in rows["base"]} == {"a1", "a2", "m1"}


def test_contextual_incluye_todos_los_chunks_prosa_del_corpus():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    assert {r["id"] for r in rows["contextual"]} == {"a1", "a2"}


def test_build_rows_lanza_si_falta_enrich_de_un_chunk_prosa():
    chunks_incompletos = [
        {"id": "a1", "corpus": "apuntes", "texto": "texto a1", "tipo": "prosa"},
        {"id": "a2", "corpus": "apuntes", "texto": "texto a2", "tipo": "prosa"},
    ]
    enrich_incompleto = [{"id": "a1", "contexto": "contexto a1", "preguntas": ["p1"]}]  # falta a2
    with pytest.raises(ValueError, match="a2"):
        build_rows(chunks_incompletos, enrich_incompleto, "apuntes")


def test_contextual_document_es_texto_crudo_y_embed_text_va_fusionado():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    fila = rows["contextual"][0]
    assert fila["document"] == "texto a1"
    assert fila["embed_text"] == "contexto a1\n\ntexto a1"


def test_hype_incluye_las_filas_de_contextual_mas_una_por_pregunta():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    total_preguntas = sum(len(e["preguntas"]) for e in ENRICH if e["id"] in {"a1", "a2"})
    esperado = len(rows["contextual"]) + total_preguntas
    assert len(rows["hype"]) == esperado


def test_hype_id_de_pregunta_y_parent_chunk_id():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    preguntas = [r for r in rows["hype"] if r["metadata"]["entry_type"] == "hype"]
    assert {r["id"] for r in preguntas} == {"a1::hype::0", "a1::hype::1", "a2::hype::0"}
    assert all(r["metadata"]["parent_chunk_id"] in {"a1", "a2"} for r in preguntas)


def test_hype_pregunta_no_se_fusiona_con_el_chunk():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    pregunta = next(r for r in rows["hype"] if r["id"] == "a1::hype::0")
    assert pregunta["document"] == "p1"
    assert pregunta["embed_text"] == "p1"


def test_ninguna_fila_usa_la_clave_de_metadato_tipo():
    rows = build_rows(CHUNKS, ENRICH, "combined")
    for extras_rows in rows.values():
        for fila in extras_rows:
            assert "tipo" not in fila["metadata"]
