"""Acceptance tests for Fase 5 — retrieval over the real Chroma collections.

Blind-written from the phase plan BEFORE the implementation exists: a
ModuleNotFoundError raised inside a test (divefy.config, p5_retrieve or the
retrieval_evaluator) is the expected RED today, not a broken suite. Imports of the code
under test therefore live inside fixtures/tests, never at module level.

Scope — only the criteria whose checker says "acceptance":
  * retrieve() against the real persisted store returns exactly k unique
    prosa chunk ids that exist in chunks.jsonl, never a raw hype-question
    row id (the hype -> parent dedup is exercised on a real hype collection).
  * End-to-end determinism: the retrieval_evaluator's run() with the base config
    serializes byte-for-byte identically across two runs.
  * Completion-marker refusal: a collection without its `.complete` sidecar
    must raise a noisy error, never return silent results. Real markers must
    never be deleted, so here we can only point the config at a collection
    name Fase 4 never builds; the stricter exists-in-Chroma-but-unmarked
    variant needs a synthetic store and is left to the unit tests.

Conventions honored: missing heavy artifacts => pytest.skip naming the
artifact and the command/task that generates it; expected counts derived from
the source files at test time, never hardcoded; nothing is ever written to
the real data/, results/ or data/chroma/ (run() returns a dict, main() is
never called).
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
GOLDEN_PATH = ROOT / "data" / "eval" / "golden.jsonl"
CHROMA_DIR = ROOT / "data" / "chroma"
LABELS_PATH = ROOT / "data" / "eval" / "labels.jsonl"
QUERY_CACHE_PATH = ROOT / "data" / "eval" / "query-embeddings-bgem3.json"

# Plain-Spanish diving questions in the golden style — deliberately NOT taken
# from the golden file, so the exam never leaks into test inputs.
QUERIES = (
    "¿Por qué aumenta la presión sobre el cuerpo al descender bajo el agua?",
    "¿Por qué se ven los colores apagados a 12 metros de profundidad?",
    "¿A qué velocidad hay que ascender para bucear con seguridad?",
)

# Cheapest fully-local arm; the fixed baseline every test derives from.
BASE = dict(corpus="apuntes", cap=512, extras="base", embedding="bgem3", search="densa", k=5)


def _read_jsonl(path):
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _require(path, hint):
    if not path.exists():
        pytest.skip(f"missing {path} — {hint}")


def _require_marker(collection_name):
    _require(
        CHROMA_DIR / f"{collection_name}.complete",
        "completion marker for a Fase 4 collection; rebuild with "
        "`uv run python -m divefy.pipeline.p4_indexing`",
    )


def _make_config(**overrides):
    from divefy.config import RetrievalConfig

    return RetrievalConfig(**{**BASE, **overrides})


def _assert_retrieval_contract(config, query_vectors, prosa_chunk_ids):
    """The full retrieve() guarantee for one config, over every test query:
    exactly k results, all unique, all real prosa chunk ids, no hype row ids."""
    from divefy.pipeline.p5_retrieve import retrieve

    for query, vector in query_vectors.items():
        result = retrieve(config, query, query_vector=vector)
        assert len(result) == config.k, (
            f"{config.collection}/{config.search}: expected exactly k={config.k} "
            f"ids for {query!r}, got {len(result)}: {result}"
        )
        assert len(set(result)) == len(result), (
            f"{config.collection}: duplicated chunk ids for {query!r}: {result}"
        )
        hype_ids = [chunk_id for chunk_id in result if "::hype::" in chunk_id]
        assert not hype_ids, (
            f"{config.collection}: raw hype row ids leaked for {query!r}: {hype_ids}"
        )
        unknown = set(result) - prosa_chunk_ids
        assert not unknown, (
            f"{config.collection}: ids absent from chunks.jsonl prosa chunks "
            f"for {query!r}: {sorted(unknown)}"
        )


@pytest.fixture(scope="module")
def prosa_chunk_ids():
    """Ids of the indexable (tipo=='prosa') chunks — the only ids retrieve()
    may ever return. Derived from chunks.jsonl at test time."""
    _require(CHUNKS_PATH, "regenerate with the ingest/chunking pipeline (Fases 1-2)")
    return {row["id"] for row in _read_jsonl(CHUNKS_PATH) if row["tipo"] == "prosa"}


@pytest.fixture(scope="module")
def eval_question_count():
    """Number of uso=='eval' golden questions, derived from the file itself,
    never hardcoded."""
    _require(GOLDEN_PATH, "the golden dataset is a tracked source file and should always be present")
    return sum(1 for row in _read_jsonl(GOLDEN_PATH) if row.get("uso") == "eval")


@pytest.fixture(scope="module")
def query_vectors():
    """One bgem3 vector per test query, embedded once with the same embeddings
    instance Fase 4 indexes with, reused read-only by every test below.
    Checked for the store first so a missing store skips before the model loads."""
    _require(CHROMA_DIR, "build the collections with `uv run python -m divefy.pipeline.p4_indexing`")
    from divefy.pipeline.p4_indexing import MODELS

    embeddings = MODELS["bgem3"]
    return {query: embeddings.embed_query(query) for query in QUERIES}


@pytest.mark.parametrize("k", (3, 5, 10))
def test_retrieve_on_real_base_collection_returns_exactly_k_unique_prosa_chunk_ids(
    prosa_chunk_ids, query_vectors, k
):
    """Dense retrieval over the real apuntes-512-base-bgem3 collection honors
    the contract for every k in the grid (3, 5, 10)."""
    config = _make_config(k=k)
    _require_marker(config.collection)
    _assert_retrieval_contract(config, query_vectors, prosa_chunk_ids)


def test_retrieve_on_real_hype_collection_dedups_hype_rows_to_unique_parent_chunks(
    prosa_chunk_ids, query_vectors
):
    """extras='hype' collections hold extra rows with ids like
    '{parent_chunk_id}::hype::{i}'; retrieval must fold those hits into their
    parent chunk and still fill exactly k unique real chunk ids. k=10 to
    stress the dedup path hardest."""
    config = _make_config(extras="hype", k=10)
    _require_marker(config.collection)
    _assert_retrieval_contract(config, query_vectors, prosa_chunk_ids)


def test_running_the_retrieval_evaluator_twice_with_the_base_config_is_byte_for_byte_identical(
    eval_question_count,
):
    """Same config in, same bytes out — no timestamp, no random tie-breaking,
    no ordering drift. Compared on run()'s returned dict serialized as the
    retrieval_evaluator would write it, so the real results/ directory is never touched.
    Skips (rather than writes to real data/) if the query-vector cache is not
    built yet."""
    _require(CHROMA_DIR, "build the collections with `uv run python -m divefy.pipeline.p4_indexing`")
    _require(LABELS_PATH, "produced by the separate Fase 5 labeling task")
    _require(
        QUERY_CACHE_PATH,
        "query-vector cache built by the retrieval_evaluator on first use; run "
        "`uv run python -m divefy.evals.retrieval_evaluator` once outside the tests",
    )
    config = _make_config()
    _require_marker(config.collection)
    from divefy.evals.retrieval_evaluator import run

    first = run(config)
    second = run(config)

    first_bytes = json.dumps(first, ensure_ascii=False).encode("utf-8")
    second_bytes = json.dumps(second, ensure_ascii=False).encode("utf-8")
    assert first_bytes == second_bytes, (
        "retrieval_evaluator run() is not deterministic for the base config: two runs "
        "serialized to different bytes"
    )
    assert len(first["detalle"]) == eval_question_count, (
        "detalle must carry exactly one row per uso=='eval' golden question"
    )


def test_retrieve_raises_a_noisy_error_for_a_collection_without_completion_marker(
    query_vectors,
):
    """A collection whose `.complete` sidecar is absent must be refused with an
    error, never silent 0 results. We point the config at a collection name
    Fase 4 never builds (cap=1024) so no real marker is touched; the
    exists-in-Chroma-but-unmarked variant needs a synthetic store and belongs
    to the unit tests."""
    config = _make_config(cap=1024)
    marker = CHROMA_DIR / f"{config.collection}.complete"
    if marker.exists():
        pytest.skip(
            f"test premise broken: {marker} exists for a collection this suite "
            "assumes was never built"
        )
    from divefy.pipeline.p5_retrieve import retrieve

    query = QUERIES[0]
    with pytest.raises(Exception):
        retrieve(config, query, query_vector=query_vectors[query])
