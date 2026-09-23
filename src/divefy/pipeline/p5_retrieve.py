"""Fase 5 — Retrieval: denso, BM25 y fusión RRF; dedup HyPE a trozo padre."""

import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from rank_bm25 import BM25Okapi

from divefy.config import RetrievalConfig
from divefy.pipeline import p4_vectorstore, p6_rerank
from divefy.pipeline.p4_indexing import MODELS

K_RRF = 60  # constante k de la fórmula RRF: score = Σ 1/(k + rank). No es de BM25.

# Sobremuestreo antes de dedup/fusión (Decision 7): 4*k a Chroma en colecciones
# hype y 4*k al lado BM25 de la híbrida.
OVERSAMPLE = 4 

_TOKEN_RE = re.compile(r"\w+", re.UNICODE) #define what is a "word" for BM25


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class Bm25Index:
    chunk_ids: tuple[str, ...]
    bm25: BM25Okapi = field(repr=False)

    def top(self, query: str, n: int) -> list[str]:
        scores = self.bm25.get_scores(_tokenize(query))
        # desempate determinista: score desc, chunk_id asc (chunk_ids ya va ordenado)
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], self.chunk_ids[i]))
        return [self.chunk_ids[i] for i in order[:n]]


def build_bm25(collection) -> Bm25Index:
    """Índice léxico desde las filas `entry_type=="chunk"` de la colección
    (Decision 8): mismo conjunto recuperable que el lado denso, idéntico en todos
    los brazos de extras. Orden estable por chunk_id — Chroma no garantiza el
    orden de .get() y el check de determinismo depende de esto."""
    data = collection.get()
    rows = sorted(
        (row_id, document)
        for row_id, document, metadata in zip(data["ids"], data["documents"], data["metadatas"])
        if metadata["entry_type"] == "chunk"
    )
    return Bm25Index(
        chunk_ids=tuple(row_id for row_id, _ in rows),
        bm25=BM25Okapi([_tokenize(document) for _, document in rows]),
    )


def rrf_fuse_scored(rankings: list[list[str]], k_rrf: int = K_RRF) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score = Σ 1/(k_rrf + rank), rank 1-based.
    Desempate determinista: score desc, chunk_id asc."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k_rrf + rank)
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    return [(chunk_id, scores[chunk_id]) for chunk_id in ordered]


def rrf_fuse(rankings: list[list[str]], k_rrf: int = K_RRF) -> list[str]:
    return [chunk_id for chunk_id, _ in rrf_fuse_scored(rankings, k_rrf)]


def _parent_id(hit) -> str:
    """Regla HyPE→padre: cada hit hype se resuelve a su parent_chunk_id (la fila
    es autocontenida, sin get extra — D3)."""
    metadata = hit.metadata
    return metadata["parent_chunk_id"] if metadata.get("entry_type") == "hype" else hit.id


def dedup_scored(hits_with_scores) -> list[tuple[str, float]]:
    """Dedup HyPE→padre conservando la mejor posición (la primera vista) y su score."""
    seen: set[str] = set()
    out: list[tuple[str, float]] = []
    for hit, score in hits_with_scores:
        chunk_id = _parent_id(hit)
        if chunk_id not in seen:
            seen.add(chunk_id)
            out.append((chunk_id, float(score)))
    return out


def dedup_to_chunk_ids(hits) -> list[str]:
    """Regla HyPE→padre; se conserva la mejor posición."""
    return [chunk_id for chunk_id, _ in dedup_scored((hit, 0.0) for hit in hits)]


def score_kind(config: RetrievalConfig) -> str:
    """Qué significa el score de retrieve_scored según la config: cross-encoder
    (más alto = mejor), RRF (más alto = mejor, máx ≈ 2/61) o distancia de Chroma
    (más bajo = mejor)."""
    if config.rerank:
        return "rerank"
    return "rrf" if config.search == "hibrida" else "distancia"


def query_cache_path(model: str) -> Path:
    return p4_vectorstore.REPO_ROOT / "data" / "eval" / f"query-embeddings-{model}.json"


def _write_atomic(path: Path, cache: dict) -> None:
    """Escribir a .tmp y renombrar encima: un corte a mitad nunca deja el fichero
    corrupto ni pierde la copia anterior (review 2026-08-30, #1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def ensure_query_vectors(model: str, queries: list[str]) -> dict[str, list[float]]:
    """Caché de vectores de query por modelo: se construye una vez y da
    determinismo y coste cero a las pasadas siguientes (Decision 6). Se persiste
    tras CADA vector: si el backend muere en el 60 de 84, los 60 ya pagados
    quedan en disco y la siguiente pasada reanuda desde ahí."""
    path = query_cache_path(model)
    cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    missing = [q for q in queries if q not in cache]
    if missing:
        embeddings = MODELS[model]
        for query in missing:
            cache[query] = embeddings.embed_query(query)
            _write_atomic(path, cache)
    return cache


# ponytail: caché global por nombre de colección — el retrieval_evaluator llama a retrieve
# 84 veces por pasada y reconstruir BM25 (tokenizar 723 chunks) en cada query
# sería puro desperdicio; invalidación innecesaria: las colecciones son
# inmutables entre indexados y el proceso del retrieval_evaluator es efímero.
_BM25_CACHE: dict[str, Bm25Index] = {}


def retrieve(
    config: RetrievalConfig, query: str, query_vector: list[float] | None = None
) -> list[str]:
    """k chunk ids únicos para una query, según la config (denso o híbrido)."""
    return [chunk_id for chunk_id, _ in retrieve_scored(config, query, query_vector)]


def retrieve_scored(
    config: RetrievalConfig, query: str, query_vector: list[float] | None = None
) -> list[tuple[str, float]]:
    """k (chunk_id, score) únicos para una query; el tipo de score lo dice
    `score_kind(config)`. Mismo orden que `retrieve`, byte a byte."""
    name = config.collection
    marker = p4_vectorstore.chroma_directory() / f"{name}.complete"
    if not marker.exists():
        raise RuntimeError(
            f"colección {name} sin marcador {marker.name}: construcción interrumpida "
            "o nunca lanzada (invariante 6, docs/modelo-datos.md). "
            "Reindexa con `uv run python -m divefy.pipeline.p4_indexing`."
        )

    embeddings = MODELS[config.embedding]
    collection = p4_vectorstore.get_collection(name, embeddings)
    if query_vector is None:
        query_vector = embeddings.embed_query(query)

    # Con rerank on la misma tubería se ensancha a N candidatos; con off, n == k
    # y el flujo es byte a byte el de Fase 5.
    n = p6_rerank.N_CANDIDATES if config.rerank else config.k
    n_dense = OVERSAMPLE * n if config.extras == "hype" else n
    # Misma consulta que similarity_search_by_vector, con la distancia además.
    hits = collection.similarity_search_by_vector_with_relevance_scores(query_vector, k=n_dense)
    dense_scored = dedup_scored(hits)[:n]
    dense_ids = [chunk_id for chunk_id, _ in dense_scored]
    if config.search == "densa":
        if len(dense_ids) < config.k:
            # el dedup HyPE→padre puede colapsar los 4·k hits a menos de k padres;
            # hoy no ocurre (medido), pero el fallo sería silencio (review #4)
            warnings.warn(
                f"{name}: {len(dense_ids)} de k={config.k} chunks tras el dedup "
                f"HyPE→padre para {query!r}"
            )
        candidates = dense_scored
    else:
        if name not in _BM25_CACHE:
            _BM25_CACHE[name] = build_bm25(collection)
        lexical_ids = _BM25_CACHE[name].top(query, OVERSAMPLE * n)
        candidates = rrf_fuse_scored([dense_ids, lexical_ids])[:n]

    if not config.rerank:
        return candidates

    ids = [chunk_id for chunk_id, _ in candidates]
    rows = collection.get(ids=ids)
    text_by_id = dict(zip(rows["ids"], rows["documents"]))
    pairs = [(chunk_id, text_by_id[chunk_id]) for chunk_id in ids]
    return p6_rerank.rerank_scored(query, pairs, config.k)
