"""Unit — filtros de `p4_indexing.main` (instalación mínima: solo la colección ganadora).

Sin filtros construye el grid entero; con `--corpus/--extras/--embedding` solo lo que
casa, y el preflight solo toca los embedders seleccionados (nadie necesita la clave de
OpenAI ni Ollama para indexar con bgem3).
"""

import pytest


class _FakeEmbeddings:
    def __init__(self, name):
        self.name, self.preflights = name, 0

    def embed_query(self, _):
        self.preflights += 1
        return [0.0]

    def release(self):
        pass


@pytest.fixture
def indexing(monkeypatch):
    from divefy.pipeline import p4_indexing

    fakes = {m: _FakeEmbeddings(m) for m in ("bgem3", "qwen8b")}
    built = []
    monkeypatch.setattr(p4_indexing, "MODELS", fakes)
    monkeypatch.setattr(p4_indexing, "_read_jsonl", lambda path: [])
    monkeypatch.setattr(
        p4_indexing, "build_rows",
        lambda chunks, enrich, corpus: {"base": [], "contextual": [], "hype": []},
    )
    monkeypatch.setattr(
        p4_indexing, "index_model",
        lambda model, emb, rows, corpus, cap, cache=None: built.extend(
            (corpus, extras, model) for extras in rows
        ),
    )
    return p4_indexing, fakes, built


def test_sin_filtros_construye_todo(indexing):
    p4_indexing, fakes, built = indexing
    p4_indexing.main()
    assert len(built) == 3 * 3 * 2, built
    assert all(f.preflights == 1 for f in fakes.values())


def test_filtros_construyen_solo_la_ganadora(indexing):
    p4_indexing, fakes, built = indexing
    p4_indexing.main(corpus="combined", extras="contextual", embedding="qwen8b")
    assert built == [("combined", "contextual", "qwen8b")]
    assert fakes["bgem3"].preflights == 0, "un embedder no pedido no debe ni cargarse"


def test_filtro_imposible_falla_claro(indexing):
    p4_indexing, _, _ = indexing
    with pytest.raises(ValueError):
        p4_indexing.main(embedding="openai3large")  # no está en los MODELS falsos
