"""Fase 6 — Rerank opcional: bge-reranker-v2-m3 lee pregunta+chunk juntos y reordena los N candidatos."""

from functools import lru_cache

# Fijo por criterio (PRD F6), no dimensión del grid; sonda única a N=40 solo si el on/off da mejora.
N_CANDIDATES = 20

_MODEL_NAME = "BAAI/bge-reranker-v2-m3"
# Tamaño de lote de la sonda (2026-08-28, ~1.45s los 20 pares en el M5). Solo afecta
# a velocidad/memoria, nunca al orden: predict() re-ordena por longitud y lo deshace.
_BATCH_SIZE = 8


@lru_cache(maxsize=1)
def _model():
    # Import perezoso (excepción documentada de coding-style): torch + sentence-transformers
    # tardan ~36s en cargar el modelo — solo lo paga el proceso cuya config lleva rerank on.
    import torch
    from sentence_transformers import CrossEncoder

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    # Score crudo (Identity), no el default sigmoid de la librería: aquí solo importa
    # el orden, y sigmoid satura en float32 — dos chunks muy buenos empatarían en 1.0
    # y los ordenaría el desempate alfabético. Sigmoid volverá si llega el umbral (P1).
    return CrossEncoder(_MODEL_NAME, device=device, activation_fn=torch.nn.Identity())


def rerank_scored(query: str, candidates: list[tuple[str, str]], k: int) -> list[tuple[str, float]]:
    """k (chunk_id, score) por score del cross-encoder descendente; desempate determinista chunk_id asc."""
    scores = _model().predict(
        [(query, texto) for _, texto in candidates], batch_size=_BATCH_SIZE
    )
    ranked = sorted(
        zip(candidates, scores), key=lambda pair: (-float(pair[1]), pair[0][0])
    )
    return [(chunk_id, float(score)) for (chunk_id, _text), score in ranked[:k]]


def rerank(query: str, candidates: list[tuple[str, str]], k: int) -> list[str]:
    return [chunk_id for chunk_id, _ in rerank_scored(query, candidates, k)]
