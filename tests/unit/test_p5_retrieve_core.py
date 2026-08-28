"""Andamiaje del implementador para las partes puras de Fase 5 (retrieval).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Datos sintéticos, sin Chroma ni modelos (la colección es un fake con .get())."""

import pytest

from divefy.config import RetrievalConfig
from divefy.pipeline.p5_retrieve import build_bm25, rrf_fuse


class FakeCollection:
    """Imita lo único que build_bm25 usa de langchain Chroma: .get()."""

    def __init__(self, rows):
        self._rows = rows

    def get(self):
        return {
            "ids": [r[0] for r in self._rows],
            "documents": [r[1] for r in self._rows],
            "metadatas": [r[2] for r in self._rows],
        }


CHUNK_ROWS = [
    ("a1", "la presión aumenta con la profundidad", {"entry_type": "chunk"}),
    ("a2", "el chaleco controla la flotabilidad", {"entry_type": "chunk"}),
    ("a3", "los colores se apagan al descender", {"entry_type": "chunk"}),
]
HYPE_ROWS = CHUNK_ROWS + [
    ("a1::hype::0", "la presión aumenta con la profundidad",
     {"entry_type": "hype", "parent_chunk_id": "a1", "pregunta": "¿sube la presión?"}),
    ("a2::hype::0", "el chaleco controla la flotabilidad",
     {"entry_type": "hype", "parent_chunk_id": "a2", "pregunta": "¿qué controla el chaleco?"}),
]


# --- rrf_fuse ---


def test_rrf_reproduce_el_orden_calculado_a_mano():
    # b: 1/62 + 1/61 · a: 1/61 + 1/63 · c: 1/63 + 1/62 → b > a > c
    fused = rrf_fuse([["a", "b", "c"], ["b", "c", "a"]])
    assert fused == ["b", "a", "c"]


def test_rrf_desempata_por_id_ascendente():
    # a y b: 1/61 cada uno — empate exacto, gana el id menor
    assert rrf_fuse([["b"], ["a"]]) == ["a", "b"]


def test_rrf_k_rrf_cambia_el_peso_de_los_primeros_puestos():
    # x: un 1º (1/(k+1)) · y: dos 3º (2/(k+3)). Con k=60 ganan los dos terceros
    # (0.0317 > 0.0164); con k=0 gana el primer puesto (1.0 > 0.67).
    rankings = [["x", "b", "y"], ["c", "d", "y"]]
    con_60 = rrf_fuse(rankings)
    assert con_60.index("y") < con_60.index("x")
    con_0 = rrf_fuse(rankings, k_rrf=0)
    assert con_0.index("x") < con_0.index("y")


def test_rrf_un_solo_ranking_se_devuelve_tal_cual():
    assert rrf_fuse([["c", "a", "b"]]) == ["c", "a", "b"]


# --- build_bm25 (Decision 8: solo filas entry_type=="chunk" de la colección) ---


def test_bm25_prefiere_el_chunk_con_los_terminos_de_la_query():
    index = build_bm25(FakeCollection(CHUNK_ROWS))
    assert index.top("presión profundidad", 3)[0] == "a1"
    assert index.top("flotabilidad chaleco", 3)[0] == "a2"


def test_bm25_ignora_las_filas_hype_el_lado_lexico_es_identico_en_todos_los_brazos():
    """Criterio de aceptación: el ranking BM25 para una query es el mismo con
    extras base y hype — las preguntas HyPE no entran en el índice léxico."""
    base = build_bm25(FakeCollection(CHUNK_ROWS))
    hype = build_bm25(FakeCollection(HYPE_ROWS))
    for query in ("presión", "flotabilidad chaleco", "colores"):
        assert base.top(query, 3) == hype.top(query, 3)


def test_bm25_tokeniza_minusculas_y_acentos():
    index = build_bm25(FakeCollection(CHUNK_ROWS))
    assert index.top("PRESIÓN", 3) == index.top("presión", 3)


def test_bm25_desempata_por_chunk_id_ascendente():
    # query sin ningún término del corpus: todos los scores empatan a 0
    index = build_bm25(FakeCollection(CHUNK_ROWS))
    assert index.top("xyz", 3) == ["a1", "a2", "a3"]


def test_bm25_es_determinista_ante_orden_de_filas_distinto():
    """Chroma no garantiza el orden de .get(); el índice debe ordenarse solo."""
    index_a = build_bm25(FakeCollection(CHUNK_ROWS))
    index_b = build_bm25(FakeCollection(list(reversed(CHUNK_ROWS))))
    for query in ("presión", "chaleco", "xyz"):
        assert index_a.top(query, 3) == index_b.top(query, 3)


# --- dedup HyPE→padre ---


def test_dedup_resuelve_hype_a_padre_conservando_la_mejor_posicion():
    from divefy.pipeline.p5_retrieve import dedup_to_chunk_ids

    class Doc:
        def __init__(self, id, metadata):
            self.id = id
            self.metadata = metadata

    hits = [
        Doc("a2::hype::0", {"entry_type": "hype", "parent_chunk_id": "a2"}),
        Doc("a1", {"entry_type": "chunk"}),
        Doc("a2", {"entry_type": "chunk"}),  # duplicado del padre de la posición 0
        Doc("a1::hype::0", {"entry_type": "hype", "parent_chunk_id": "a1"}),  # dup
        Doc("a3", {"entry_type": "chunk"}),
    ]
    assert dedup_to_chunk_ids(hits) == ["a2", "a1", "a3"]


# --- marcador .complete (invariante 6): error ruidoso antes de tocar Chroma ---


def test_retrieve_rechaza_coleccion_sin_marcador_complete(tmp_path, monkeypatch):
    from divefy.pipeline import p4_vectorstore, p5_retrieve

    monkeypatch.setattr(p4_vectorstore, "chroma_directory", lambda: tmp_path)

    config = RetrievalConfig(
        corpus="apuntes", extras="base", embedding="bgem3", search="densa", k=5
    )
    with pytest.raises(RuntimeError, match="complete"):
        p5_retrieve.retrieve(config, "¿sube la presión?", query_vector=[0.0])
