"""Fase 5 — Retrieval: denso, BM25 y fusión RRF; dedup HyPE a trozo padre."""

import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from rank_bm25 import BM25Okapi

from divefy.config import RetrievalConfig
from divefy.pipeline import p4_vectorstore
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


def rrf_fuse(rankings: list[list[str]], k_rrf: int = K_RRF) -> list[str]:
    """Reciprocal Rank Fusion: score = Σ 1/(k_rrf + rank), rank 1-based.
    Desempate determinista: score desc, chunk_id asc."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k_rrf + rank)
    return sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))


def dedup_to_chunk_ids(hits) -> list[str]:
    """Regla HyPE→padre: cada hit hype se resuelve a su parent_chunk_id (la fila
    es autocontenida, sin get extra — D3); se conserva la mejor posición."""
    seen: set[str] = set()
    chunk_ids: list[str] = []
    for hit in hits:
        metadata = hit.metadata
        chunk_id = metadata["parent_chunk_id"] if metadata.get("entry_type") == "hype" else hit.id
        if chunk_id not in seen:
            seen.add(chunk_id)
            chunk_ids.append(chunk_id)
    return chunk_ids


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


# ponytail: caché global por nombre de colección — el corrector llama a retrieve
# 84 veces por pasada y reconstruir BM25 (tokenizar 723 chunks) en cada query
# sería puro desperdicio; invalidación innecesaria: las colecciones son
# inmutables entre indexados y el proceso del corrector es efímero.
_BM25_CACHE: dict[str, Bm25Index] = {}


def retrieve(
    config: RetrievalConfig, query: str, query_vector: list[float] | None = None
) -> list[str]:
    """k chunk ids únicos para una query, según la config (denso o híbrido)."""
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

    n_dense = OVERSAMPLE * config.k if config.extras == "hype" else config.k
    hits = collection.similarity_search_by_vector(query_vector, k=n_dense)
    dense_ids = dedup_to_chunk_ids(hits)[: config.k]
    if config.search == "densa":
        if len(dense_ids) < config.k:
            # el dedup HyPE→padre puede colapsar los 4·k hits a menos de k padres;
            # hoy no ocurre (medido), pero el fallo sería silencio (review #4)
            warnings.warn(
                f"{name}: {len(dense_ids)} de k={config.k} chunks tras el dedup "
                f"HyPE→padre para {query!r}"
            )
        return dense_ids

    if name not in _BM25_CACHE:
        _BM25_CACHE[name] = build_bm25(collection)
    lexical_ids = _BM25_CACHE[name].top(query, OVERSAMPLE * config.k)
    return rrf_fuse([dense_ids, lexical_ids])[: config.k]
