"""Fixes de la review 2026-08-30 que necesitan piezas reales (hallazgos 1 y 2).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
La híbrida usa el vector cacheado de bgem3 (sin cargar modelo) y el Chroma real
con skip si falta — el patrón de conftest para artefactos pesados."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = ROOT / "data" / "chroma"
CACHE_BGEM3 = ROOT / "data" / "eval" / "query-embeddings-bgem3.json"


class _MuereAlTercero:
    """Backend que embebe dos queries y muere en la tercera — un Ollama caído."""

    def __init__(self):
        self.calls = 0

    def embed_query(self, text):
        self.calls += 1
        if self.calls == 3:
            raise RuntimeError("backend caído")
        return [0.1, 0.2]


def test_cache_conserva_los_vectores_ya_pagados_si_el_backend_muere(tmp_path, monkeypatch):
    """Hallazgo 1: escritura incremental + atómica — morir en el vector 3 no
    pierde los 2 ya embebidos, y la reanudación solo embebe lo que falta."""
    from divefy.pipeline import p5_retrieve

    path = tmp_path / "cache.json"
    monkeypatch.setattr(p5_retrieve, "query_cache_path", lambda model: path)
    roto = _MuereAlTercero()
    monkeypatch.setitem(p5_retrieve.MODELS, "bgem3", roto)

    with pytest.raises(RuntimeError, match="backend caído"):
        p5_retrieve.ensure_query_vectors("bgem3", ["q1", "q2", "q3"])
    assert set(json.loads(path.read_text(encoding="utf-8"))) == {"q1", "q2"}

    # reanudación: el backend ya sano solo embebe la que falta
    sano = _MuereAlTercero()
    monkeypatch.setitem(p5_retrieve.MODELS, "bgem3", sano)
    cache = p5_retrieve.ensure_query_vectors("bgem3", ["q1", "q2", "q3"])
    assert set(cache) == {"q1", "q2", "q3"}
    assert sano.calls == 1


@pytest.mark.parametrize("extras", ("base", "hype"))
def test_hibrida_sobre_coleccion_real_cumple_el_contrato(extras):
    """Hallazgo 2: la híbrida (denso + BM25 + RRF) nunca se ejercía contra el
    Chroma real — solo la densa. Mismo contrato que el acceptance: k únicos,
    todos chunks, ningún señuelo hype. Vector desde la caché, sin cargar modelo."""
    from divefy.config import RetrievalConfig
    from divefy.pipeline.p5_retrieve import retrieve

    config = RetrievalConfig(
        corpus="apuntes", extras=extras, embedding="bgem3", search="hibrida", k=5
    )
    marker = CHROMA_DIR / f"{config.collection}.complete"
    if not marker.exists():
        pytest.skip(f"falta {marker} — construir con `uv run python -m divefy.pipeline.p4_indexing`")
    if not CACHE_BGEM3.exists():
        pytest.skip(f"falta {CACHE_BGEM3} — la construye el retrieval_evaluator en su primera pasada")

    cache = json.loads(CACHE_BGEM3.read_text(encoding="utf-8"))
    query, vector = next(iter(cache.items()))
    result = retrieve(config, query, query_vector=vector)

    assert len(result) == config.k
    assert len(set(result)) == config.k
    assert all("::hype::" not in chunk_id for chunk_id in result)
