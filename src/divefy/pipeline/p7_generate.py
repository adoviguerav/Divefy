"""Fase 7 — Generación: monta el estado, llama al LLM y aplica el guardarraíl.

`answer()` es la única puerta: retrieval determinista → prompt versionado →
`llm.generate()` (costura única, decisión 1) → guardarraíl numérico con
reintento-una-vez (decisión 16) → `Answer` inmutable. Los logs DEBUG enseñan el
estado JSON tras cada etapa (decisión 17).
"""

import json
import logging
from dataclasses import asdict, dataclass

import divefy.llm as llm
from divefy.config import RetrievalConfig
from divefy.pipeline import p4_vectorstore, p5_retrieve, p7_guardrail
from divefy.pipeline.p4_indexing import MODELS

logger = logging.getLogger(__name__)

from pathlib import Path

# Dentro del paquete (veto de Adolfo a la decisión 13, 2026-09-07): los prompts
# son parte de divefy, viajan con él.
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
# v2 (2026-09-16, decisión de Adolfo): voz hablada de instructor y sin citar
# fuentes — el usuario ya asume material fiable — SALVO en conflictos
# PADI/Navy, donde nombrarlas es parte de la respuesta.
GENERATION_PROMPT_PATH = PROMPTS_DIR / "generation_v2.txt"
PROMPT_VERSION = GENERATION_PROMPT_PATH.stem  # se estampa en la fila del eval (T-05)
CONSTANTES_PATH = p4_vectorstore.REPO_ROOT / "data" / "guardrail" / "constantes.jsonl"

# Plantilla fija de abstención (regla inmutable 4): el modelo la emite EXACTA o
# no hay respuesta. Fuente única aquí; el prompt la recibe interpolada.
# La palabra que el MODELO emite para abstenerse (decisión 2026-09-17): el
# código la sustituye por la plantilla — el LLM nunca copia texto sagrado.
ABSTENTION_SENTINEL = "ABSTENER"

# Sin nombrar fuentes (decisión 2026-09-17): las referencias viven en el estado
# del RAG (chunks + metadata), jamás en la prosa ni en la plantilla.
ABSTENTION_TEMPLATE = (
    "No tengo información suficiente para responderte con seguridad. Consulta el "
    "material oficial de tu curso o pregunta a tu instructor; para cálculos de "
    "planificación usa tu eRDPML u ordenador de buceo."
)

_AVISO_REINTENTO = (
    "\n\nAVISO: tu respuesta anterior contenía al menos un número que no aparece "
    "textual en el contexto. Reescríbela usando SOLO números copiados literalmente "
    "del contexto, en sus unidades originales — o emite la plantilla de abstención."
)


@dataclass(frozen=True)
class Answer:
    pregunta: str
    chunks: tuple[dict, ...]  # id, texto, metadata — deterministas, del retrieval
    respuesta: str
    abstencion: bool


def _system_prompt() -> str:
    return GENERATION_PROMPT_PATH.read_text(encoding="utf-8")


def _constantes() -> list[dict]:
    if not hasattr(_constantes, "_cache"):
        with CONSTANTES_PATH.open(encoding="utf-8") as fh:
            _constantes._cache = [json.loads(line) for line in fh if line.strip()]
    return _constantes._cache


def _fetch_chunks(config: RetrievalConfig, pregunta: str) -> tuple[dict, ...]:
    """k chunks con texto, metadata y score (tipo según la config), en el orden
    que dejó el retrieval."""
    scored = p5_retrieve.retrieve_scored(config, pregunta)
    ids = [chunk_id for chunk_id, _ in scored]
    kind = p5_retrieve.score_kind(config)
    collection = p4_vectorstore.get_collection(config.collection, MODELS[config.embedding])
    rows = collection.get(ids=ids)
    by_id = {
        row_id: {"id": row_id, "texto": documento, "metadata": metadata}
        for row_id, documento, metadata in zip(rows["ids"], rows["documents"], rows["metadatas"])
    }
    return tuple(
        {**by_id[chunk_id], "score": score, "score_kind": kind} for chunk_id, score in scored
    )


def _user_prompt(chunks: tuple[dict, ...], pregunta: str) -> str:
    contexto = "\n\n".join(
        f"[{chunk['metadata'].get('corpus', '?')} · {chunk['metadata'].get('titulo', chunk['id'])}]\n{chunk['texto']}"
        for chunk in chunks
    )
    return f"Context:\n{contexto}\n\nQuestion: {pregunta}\n\nAnswer:"


def _log_estado(etapa: str, estado: dict) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("[%s] %s", etapa, json.dumps(estado, ensure_ascii=False))


def answer(retrieval_config: RetrievalConfig, model, pregunta: str) -> Answer:
    """Estado completo de una respuesta: pregunta + chunks + respuesta verificada.

    Política del guardarraíl (decisión 16 + PRD): primer número no verificado →
    UN reintento avisando al modelo; si la segunda también falla, la respuesta
    entera se sustituye por la plantilla de abstención — jamás se emite una
    cifra sin verificar.
    """
    chunks = _fetch_chunks(retrieval_config, pregunta)
    _log_estado("retrieval", {"pregunta": pregunta, "chunks": [c["id"] for c in chunks]})

    system = _system_prompt()
    user = _user_prompt(chunks, pregunta)

    respuesta = llm.generate(model, system, user)
    verdict = p7_guardrail.verify(respuesta, _constantes())
    if verdict != "ok":
        respuesta = llm.generate(model, system, user + _AVISO_REINTENTO)
        verdict = p7_guardrail.verify(respuesta, _constantes())
        if verdict != "ok":
            respuesta = ABSTENTION_TEMPLATE  # abstener_cifra: reincidió

    # El modelo se abstiene con la palabra centinela; se acepta también la
    # plantilla literal (contrato de los tests congelados y del guardarraíl,
    # que abstiene poniendo la plantilla directamente).
    if respuesta.strip() in (ABSTENTION_SENTINEL, ABSTENTION_TEMPLATE):
        respuesta = ABSTENTION_TEMPLATE
        abstencion = True
    else:
        abstencion = False

    _log_estado("generate", {"respuesta": respuesta, "abstencion": abstencion, "verdict": verdict})

    resultado = Answer(pregunta=pregunta, chunks=chunks, respuesta=respuesta, abstencion=abstencion)
    _log_estado("answer", asdict(resultado))
    return resultado
