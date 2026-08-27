"""Andamiaje del implementador para las funciones puras de Fase 4 (indexing).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Fixtures hechas a mano (no jsonl reales) por velocidad y determinismo, mismo estilo
que test_p2_chunking_core.py / test_p3_enrich_core.py. Esquema de chunk = el real de
chunks.jsonl (contrato en docs/modelo-datos.md), incluido n_tokens."""

import json

import pytest

from divefy.pipeline.p4_indexing import build_rows

CHUNKS = [
    {
        "id": "a1",
        "corpus": "apuntes",
        "section_ids": ["Física#a1"],
        "titulo": "A1",
        "tipo": "prosa",
        "texto": "texto a1",
        "fichero": "Física",
        "capitulo": None,
        "pagina": None,
        "pagina_fin": None,
        "n_tokens": 3,
    },
    {
        "id": "a2",
        "corpus": "apuntes",
        "section_ids": ["Física#a2"],
        "titulo": "A2",
        "tipo": "prosa",
        "texto": "texto a2",
        "fichero": "Física",
        "capitulo": None,
        "pagina": None,
        "pagina_fin": None,
        "n_tokens": 3,
    },
    {
        "id": "m1",
        "corpus": "manual",
        "section_ids": ["9-1", "9-2"],
        "titulo": "M1",
        "tipo": "prosa",
        "texto": "texto m1",
        "fichero": None,
        "capitulo": 9,
        "pagina": 100,
        "pagina_fin": 101,
        "n_tokens": 3,
    },
    {
        "id": "m2",
        "corpus": "manual",
        "section_ids": ["9-3"],
        "titulo": "M2",
        "tipo": "puntero_tabla",
        "texto": "texto m2",
        "fichero": None,
        "capitulo": 9,
        "pagina": 102,
        "pagina_fin": 102,
        "n_tokens": 3,
    },
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
    chunks_incompletos = [c for c in CHUNKS if c["id"] in {"a1", "a2"}]
    enrich_incompleto = [e for e in ENRICH if e["id"] == "a1"]  # falta a2
    with pytest.raises(ValueError, match="a2"):
        build_rows(chunks_incompletos, enrich_incompleto, "apuntes")


def test_contextual_document_es_texto_crudo_y_embed_text_va_fusionado():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    fila = rows["contextual"][0]
    assert fila["document"] == "texto a1"
    assert fila["embed_text"] == "contexto a1\n\ntexto a1"


def test_metadata_de_fila_chunk_cumple_el_contrato():
    rows = build_rows(CHUNKS, ENRICH, "combined")

    meta = next(r for r in rows["base"] if r["id"] == "a1")["metadata"]
    assert meta["entry_type"] == "chunk"
    assert meta["corpus"] == "apuntes"
    assert json.loads(meta["section_ids"]) == ["Física#a1"]
    assert meta["titulo"] == "A1"
    assert meta["n_tokens"] == 3
    assert meta["fichero"] == "Física"
    for clave in ("capitulo", "pagina", "pagina_fin"):
        assert clave not in meta  # None se omite, nunca se escribe null

    meta_m = next(r for r in rows["base"] if r["id"] == "m1")["metadata"]
    assert (meta_m["capitulo"], meta_m["pagina"], meta_m["pagina_fin"]) == (9, 100, 101)
    assert "fichero" not in meta_m
    assert json.loads(meta_m["section_ids"]) == ["9-1", "9-2"]


def test_contextual_anade_contexto_a_la_metadata_completa_del_chunk():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    meta = next(r for r in rows["contextual"] if r["id"] == "a1")["metadata"]
    assert meta["contexto"] == "contexto a1"
    assert meta["entry_type"] == "chunk"
    assert json.loads(meta["section_ids"]) == ["Física#a1"]


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


def test_hype_pregunta_es_autocontenida():
    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    pregunta = next(r for r in rows["hype"] if r["id"] == "a1::hype::0")
    assert pregunta["document"] == "texto a1"  # el texto del padre, no la pregunta
    assert pregunta["embed_text"] == "p1"  # lo embebido sigue siendo la pregunta
    meta = pregunta["metadata"]
    assert meta["entry_type"] == "hype"
    assert meta["parent_chunk_id"] == "a1"
    assert meta["pregunta"] == "p1"
    assert meta["contexto"] == "contexto a1"
    assert json.loads(meta["section_ids"]) == ["Física#a1"]


def test_ninguna_fila_usa_la_clave_de_metadato_tipo():
    rows = build_rows(CHUNKS, ENRICH, "combined")
    for extras_rows in rows.values():
        for fila in extras_rows:
            assert "tipo" not in fila["metadata"]


# --- Fixes de la review 2026-08-28 (hallazgos 1, 2, 4) ---


class _OkEmbeddings:
    def embed_documents(self, texts):
        return [[0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [0.0, 0.0]


class _FlakyEmbeddings(_OkEmbeddings):
    """Falla la primera llamada y luego funciona — un 429 o un tosido de Ollama."""

    def __init__(self):
        self.calls = 0

    def embed_documents(self, texts):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("fallo transitorio")
        return super().embed_documents(texts)


def test_index_model_valida_cap_contra_n_tokens(tmp_path, monkeypatch):
    """Hallazgo 1: cap no puede ser solo texto del nombre — si un chunk lo supera,
    error ruidoso antes de tocar Chroma o embeber nada. El monkeypatch no sobra
    aunque el guard salte antes de Chroma: si el guard regresa, este test escribiría
    colecciones cap=2 en el data/chroma REAL (pasó en su primera pasada en RED)."""
    from divefy.pipeline import p4_indexing, p4_vectorstore

    monkeypatch.setattr(p4_vectorstore, "chroma_directory", lambda: tmp_path)

    rows = build_rows(CHUNKS, ENRICH, "apuntes")  # n_tokens=3 en las fixtures
    with pytest.raises(ValueError, match="cap"):
        p4_indexing.index_model("bgem3", _OkEmbeddings(), rows, corpus="apuntes", cap=2)


def test_index_model_reintenta_ante_fallo_transitorio(tmp_path, monkeypatch):
    """Hallazgo 4: un fallo puntual del backend no tira la pasada — se reintenta."""
    from divefy.pipeline import p4_indexing, p4_vectorstore

    monkeypatch.setattr(p4_vectorstore, "chroma_directory", lambda: tmp_path)
    monkeypatch.setattr(p4_indexing.time, "sleep", lambda s: None)

    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    flaky = _FlakyEmbeddings()
    p4_indexing.index_model("bgem3", flaky, rows, corpus="apuntes", cap=512)
    assert flaky.calls >= 2  # falló una vez y la pasada sobrevivió


def test_index_model_deja_marcador_complete_al_terminar(tmp_path, monkeypatch):
    """Hallazgo 2: una colección solo es válida con su marcador `{nombre}.complete`
    junto a ella en data/chroma/ — una interrumpida entre reset y escritura no lo
    lleva (se borra antes del reset, se crea al terminar). No va en la metadata de
    colección porque `modify` la reemplaza entera y langchain lee `hnsw:space` de ahí."""
    from divefy.pipeline import p4_indexing, p4_vectorstore

    monkeypatch.setattr(p4_vectorstore, "chroma_directory", lambda: tmp_path)

    rows = build_rows(CHUNKS, ENRICH, "apuntes")
    p4_indexing.index_model("bgem3", _OkEmbeddings(), rows, corpus="apuntes", cap=512)

    for extras in ("base", "contextual", "hype"):
        name = p4_vectorstore.canonical_name("apuntes", 512, extras, "bgem3")
        assert (tmp_path / f"{name}.complete").exists(), extras
