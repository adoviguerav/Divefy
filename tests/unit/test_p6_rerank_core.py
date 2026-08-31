"""Unit — p6_rerank con modelo falso inyectado: orden, desempate, corte y determinismo puros."""

from divefy.pipeline import p6_rerank

QUERY = "¿da igual? el fake no la mira"


class FakeModel:
    """Devuelve un score fijo por texto — el orden lo decide la tabla, no un modelo."""

    def __init__(self, scores_by_text):
        self.scores_by_text = scores_by_text

    def predict(self, pairs, batch_size=None):
        return [self.scores_by_text[texto] for _query, texto in pairs]


def _patch(monkeypatch, scores_by_text):
    monkeypatch.setattr(p6_rerank, "_model", lambda: FakeModel(scores_by_text))


def test_orders_by_score_desc_and_cuts_k(monkeypatch):
    _patch(monkeypatch, {"ta": 0.1, "tb": 0.9, "tc": 0.5})
    candidates = [("a", "ta"), ("b", "tb"), ("c", "tc")]
    assert p6_rerank.rerank(QUERY, candidates, k=3) == ["b", "c", "a"]
    assert p6_rerank.rerank(QUERY, candidates, k=2) == ["b", "c"]


def test_tie_breaks_by_chunk_id_asc(monkeypatch):
    _patch(monkeypatch, {"tz": 0.5, "ta": 0.5, "tm": 0.5})
    candidates = [("z", "tz"), ("a", "ta"), ("m", "tm")]
    assert p6_rerank.rerank(QUERY, candidates, k=3) == ["a", "m", "z"]


def test_output_is_subset_and_input_order_irrelevant(monkeypatch):
    scores = {"t1": 0.3, "t2": 0.8, "t3": 0.6, "t4": 0.1}
    _patch(monkeypatch, scores)
    candidates = [("c1", "t1"), ("c2", "t2"), ("c3", "t3"), ("c4", "t4")]
    reversed_result = p6_rerank.rerank(QUERY, list(reversed(candidates)), k=4)
    assert p6_rerank.rerank(QUERY, candidates, k=4) == reversed_result == ["c2", "c3", "c1", "c4"]
    assert set(p6_rerank.rerank(QUERY, candidates, k=2)) <= {c[0] for c in candidates}


def test_retrieve_widens_to_n_candidates_when_rerank_on(monkeypatch, tmp_path):
    """review H-2: sin este test, `n = config.k` en vez de N_CANDIDATES pasaría
    toda la suite — la fase degeneraría a reordenar los k que ya tenías."""
    from types import SimpleNamespace

    from divefy.config import RetrievalConfig
    from divefy.pipeline import p4_vectorstore, p5_retrieve

    hits = [
        SimpleNamespace(id=f"c{i:02d}", metadata={"entry_type": "chunk"})
        for i in range(p6_rerank.N_CANDIDATES + 10)
    ]

    class FakeCollection:
        def similarity_search_by_vector(self, vector, k):
            return hits[:k]

        def get(self, ids=None):
            return {"ids": list(ids), "documents": [f"text {i}" for i in ids]}

    config = RetrievalConfig(
        corpus="apuntes", extras="base", embedding="bgem3",
        search="densa", k=5, rerank=True,
    )
    (tmp_path / f"{config.collection}.complete").touch()
    monkeypatch.setattr(p4_vectorstore, "chroma_directory", lambda: tmp_path)
    monkeypatch.setattr(p4_vectorstore, "get_collection", lambda name, emb: FakeCollection())
    monkeypatch.setattr(p5_retrieve, "MODELS", {"bgem3": None})

    captured = {}

    def fake_rerank(query, candidates, k):
        captured["n_candidates"] = len(candidates)
        return [chunk_id for chunk_id, _ in candidates[:k]]

    monkeypatch.setattr(p5_retrieve.p6_rerank, "rerank", fake_rerank)

    result = p5_retrieve.retrieve(config, "q", query_vector=[0.0])
    assert captured["n_candidates"] == p6_rerank.N_CANDIDATES
    assert len(result) == config.k