"""Acceptance tests for Fase 6 — reranking (bge-reranker-v2-m3).

Scope:
  1. Config surface: `RetrievalConfig.rerank` field and its `-rerank` run_id suffix.
  2. retrieve() public contract with rerank=True on a real hybrid store.
  3. rerank() order semantics via the public API: permutation, prefix-stability,
     determinism, subset guarantee.
  4. End-to-end determinism of retrieval_evaluator.run() with rerank=True.

These tests are written BEFORE the implementation exists: on first run they must
fail RED with ImportError/AttributeError (or TypeError for the new kwarg) raised
inside the tests — imports of the code under test live inside fixtures/tests,
never at module level.

Heavy artifacts (Chroma store, chunks.jsonl, golden/labels, HF reranker cache)
are required via skip-with-hint; tests never write to data/, results/ or
data/chroma/ (retrieval_evaluator.run() is pure; main() is never called).
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
GOLDEN_PATH = ROOT / "data" / "eval" / "golden.jsonl"
LABELS_PATH = ROOT / "data" / "eval" / "labels.jsonl"
CHROMA_DIR = ROOT / "data" / "chroma"
RERANKER_CACHE = (
    Path.home() / ".cache" / "huggingface" / "hub" / "models--BAAI--bge-reranker-v2-m3"
)

# Cheap arm used for all store-backed tests.
COLLECTION = "combined-512-contextual-bgem3"

# Fresh plain-Spanish diving questions — written for these tests, NEVER taken
# from the golden dataset (the exam must not leak into fixtures).
RETRIEVE_QUERY = (
    "¿Qué debe hacer un buceador si nota que le queda poco aire durante una inmersión?"
)
RERANK_QUERY = (
    "¿Por qué nunca se debe contener la respiración mientras se asciende con botella?"
)


def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _require(path, hint):
    if not Path(path).exists():
        pytest.skip(f"missing {path} — {hint}")


def _require_marker(collection_name):
    marker = CHROMA_DIR / f"{collection_name}.complete"
    if not marker.exists():
        pytest.skip(f"missing {marker} — run p4 indexing for {collection_name} first")


def _require_reranker_cache():
    _require(RERANKER_CACHE, "first use downloads ~2.1GB (BAAI/bge-reranker-v2-m3)")


def _make_config(k, rerank=True):
    from divefy.config import RetrievalConfig

    return RetrievalConfig(
        corpus="combined",
        extras="contextual",
        embedding="bgem3",
        search="hibrida",
        k=k,
        cap=512,
        rerank=rerank,
    )


# ---------------------------------------------------------------------------
# Criterion 1 — config surface (always runs, no heavy artifacts)
# ---------------------------------------------------------------------------


class TestConfigSurface:
    def test_rerank_true_appends_suffix_to_run_id(self):
        cfg = _make_config(k=5, rerank=True)
        # Expected value built from the config's own fields, not hardcoded.
        assert cfg.run_id == f"{cfg.collection}-{cfg.search}-k{cfg.k}-rerank"
        assert cfg.run_id.endswith("-rerank")

    def test_rerank_false_keeps_f5_run_id_format(self):
        cfg = _make_config(k=5, rerank=False)
        assert cfg.run_id == f"{cfg.collection}-{cfg.search}-k{cfg.k}"
        assert not cfg.run_id.endswith("-rerank")

    def test_rerank_defaults_to_false_when_omitted(self):
        from divefy.config import RetrievalConfig

        cfg = RetrievalConfig(
            corpus="combined",
            extras="contextual",
            embedding="bgem3",
            search="hibrida",
            k=5,
            cap=512,
        )
        assert cfg.rerank is False
        assert cfg.run_id == f"{cfg.collection}-{cfg.search}-k{cfg.k}"

    def test_n_candidates_constant_exposed(self):
        from divefy.pipeline.p6_rerank import N_CANDIDATES

        assert N_CANDIDATES == 20


# ---------------------------------------------------------------------------
# Criterion 2 — retrieve() contract with rerank on (real store + real model)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def store_context():
    """Skips if heavy artifacts are absent; pre-embeds the query once."""
    _require(CHUNKS_PATH, "run p1/p2 ingest+chunking first")
    _require(CHROMA_DIR, "run p4 indexing first")
    _require_marker(COLLECTION)
    _require_reranker_cache()

    from divefy.pipeline.p4_indexing import MODELS

    query_vector = MODELS["bgem3"].embed_query(RETRIEVE_QUERY)
    prosa_ids = {row["id"] for row in _read_jsonl(CHUNKS_PATH) if row["tipo"] == "prosa"}
    return {"query_vector": query_vector, "prosa_ids": prosa_ids}


class TestRetrieveWithRerank:
    @pytest.mark.parametrize("k", [3, 5, 10])
    def test_returns_exactly_k_unique_prosa_ids(self, store_context, k):
        from divefy.pipeline.p5_retrieve import retrieve

        cfg = _make_config(k=k, rerank=True)
        result = retrieve(cfg, RETRIEVE_QUERY, query_vector=store_context["query_vector"])

        assert isinstance(result, list)
        assert len(result) == cfg.k
        assert len(set(result)) == cfg.k, "ids must be unique"
        assert set(result) <= store_context["prosa_ids"], (
            "every returned id must be a tipo=='prosa' chunk id from chunks.jsonl"
        )
        assert not any("::hype::" in chunk_id for chunk_id in result)


# ---------------------------------------------------------------------------
# Criteria 3 & 4 — rerank() order semantics (real model, no store needed)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rerank_candidates():
    """First ~10 prosa chunks from chunks.jsonl as (chunk_id, texto) candidates."""
    _require(CHUNKS_PATH, "run p1/p2 ingest+chunking first")
    _require_reranker_cache()

    prosa_rows = [row for row in _read_jsonl(CHUNKS_PATH) if row["tipo"] == "prosa"][:10]
    assert len(prosa_rows) >= 5, "chunks.jsonl too small for rerank semantics tests"
    return [(row["id"], row["texto"]) for row in prosa_rows]


@pytest.fixture(scope="module")
def full_ranking(rerank_candidates):
    """One full-length rerank call, shared across the semantics tests."""
    from divefy.pipeline.p6_rerank import rerank

    return rerank(RERANK_QUERY, rerank_candidates, k=len(rerank_candidates))


class TestRerankSemantics:
    def test_full_length_result_is_permutation_of_candidates(
        self, rerank_candidates, full_ranking
    ):
        candidate_ids = [chunk_id for chunk_id, _ in rerank_candidates]
        assert sorted(full_ranking) == sorted(candidate_ids)

    @pytest.mark.parametrize("k", [3, 5])
    def test_top_k_is_prefix_of_full_ranking(self, rerank_candidates, full_ranking, k):
        from divefy.pipeline.p6_rerank import rerank

        result = rerank(RERANK_QUERY, rerank_candidates, k=k)
        assert len(result) == k
        assert result == full_ranking[:k], (
            "top-k by score desc (tie-break id asc) must be prefix-stable"
        )
        # Criterion 4 — subset guarantee.
        assert set(result) <= {chunk_id for chunk_id, _ in rerank_candidates}

    def test_rerank_is_deterministic(self, rerank_candidates, full_ranking):
        from divefy.pipeline.p6_rerank import rerank

        again = rerank(RERANK_QUERY, rerank_candidates, k=len(rerank_candidates))
        assert again == full_ranking


# ---------------------------------------------------------------------------
# Criterion 5 — end-to-end determinism of the retrieval_evaluator with rerank on
# ---------------------------------------------------------------------------


class TestCorrectorDeterminismWithRerank:
    def test_run_twice_serializes_byte_identical(self):
        # Slow (~1.5s/query x 84 queries x 2 + one-time model load), but this
        # is the exam — do not skip when the artifacts exist.
        _require(CHUNKS_PATH, "run p1/p2 ingest+chunking first")
        _require(GOLDEN_PATH, "golden dataset missing (never indexed, only read by retrieval_evaluator)")
        _require(LABELS_PATH, "run labeling first")
        _require(CHROMA_DIR, "run p4 indexing first")
        _require_marker(COLLECTION)
        _require_reranker_cache()

        from divefy.evals.retrieval_evaluator import run, serialize

        cfg = _make_config(k=5, rerank=True)
        assert cfg.run_id.endswith("-rerank")

        first = run(cfg)
        # Reuse the first result for shape assertions before paying for run #2.
        assert set(first) >= {"config", "resumen", "detalle"}

        second = run(cfg)
        assert serialize(first) == serialize(second), (
            "retrieval_evaluator.run() with rerank=True must be byte-stable across runs"
        )
