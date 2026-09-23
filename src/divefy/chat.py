"""Fase 8 — Chat: la lógica de un turno (pura, testeable con fakes) y la precarga.

Solo librería: el arranque vive en `divefy/__main__.py` (`python -m divefy`). Este
módulo nunca se ejecuta como `__main__` a propósito — si se hiciera, Python lo cargaría
dos veces (como `__main__` y como `divefy.chat`), con dos copias de `LOCK`, y torch
(MPS) casca cuando dos hilos cargan modelos a la vez.

Memoria de 3 pares vía condensador (p8_condense.condense). Cada turno se traza en
LangSmith con `@traceable` (no-op si `LANGSMITH_TRACING` no está definida).
"""

import logging
import threading

from langsmith import traceable

import divefy.llm as llm
from divefy.config import RECETA_GANADORA, RetrievalConfig
from divefy.pipeline import p5_retrieve, p7_generate, p8_condense
from divefy.pipeline.p7_generate import Answer

logger = logging.getLogger(__name__)

# Todo lo que toca torch/MLX pasa por aquí, un hilo cada vez: la caché de shaders de
# MPS no es segura entre hilos (crash reproducido 2026-09-23, ver __main__.py).
LOCK = threading.Lock()
WARMUP_QUERY = "parada de seguridad"
DEFAULT_MODEL = "haiku45"


def warm_up(model: str, config: RetrievalConfig = RECETA_GANADORA) -> None:
    """Paga por adelantado lo que la primera pregunta pagaría: embedder, BM25 y
    reranker (vía un retrieve real) y el modelo local si `model` es MLX. Todo
    queda cacheado a nivel de proceso; la segunda llamada es gratis."""
    with LOCK:
        logger.info("precarga: retrieval %s", config.run_id)
        p5_retrieve.retrieve(config, WARMUP_QUERY)
        if model in llm.MLX_MODELS:
            logger.info("precarga: modelo %s", model)
            llm._mlx_load(model)


@traceable(name="divefy_turn")
def run_turn_full(
    historial: list[tuple[str, str]],
    model: str,
    pregunta: str,
    config: RetrievalConfig = RECETA_GANADORA,
) -> tuple[Answer, list[tuple[str, str]]]:
    """Un turno completo: condensa contra el historial, genera, y devuelve el
    Answer entero (chunks incluidos) más el historial actualizado, sin mutar el
    que recibió."""
    query = p8_condense.condense(historial, pregunta)
    resultado = p7_generate.answer(config, model, query)
    return resultado, historial + [(pregunta, resultado.respuesta)]


def run_turn(
    historial: list[tuple[str, str]],
    model: str,
    pregunta: str,
    config: RetrievalConfig = RECETA_GANADORA,
) -> tuple[str, list[tuple[str, str]]]:
    resultado, nuevo_historial = run_turn_full(historial, model, pregunta, config)
    return resultado.respuesta, nuevo_historial
