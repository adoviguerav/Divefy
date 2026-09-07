"""Fase 7 — Juez de generación: G-Eval (deepeval) con rúbrica versionada.

Solo evaluación, jamás runtime ni hardware: el juez necesita la respuesta
esperada, que solo existe en el examen (decisión 12 del plan). Modelo fijo de
familia fuera de la ablación, temperatura la fija deepeval (G-Eval determinista
por diseño con strict_mode). La rúbrica vive en `prompts/judge_v1.txt` y su
versión se estampa en cada fila (`prompt_version_juez`).
"""

import json
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
JUDGE_PROMPT_PATH = PROMPTS_DIR / "judge_v1.txt"
PROMPT_VERSION = JUDGE_PROMPT_PATH.stem  # se estampa en la fila del eval

# Confirmado contra la referencia vigente de OpenAI (2026-09-07) y decidido por
# Adolfo: Luna ($0.20/$1.20 por millón) con esfuerzo de razonamiento alto —
# juez barato pensando mucho; la calibración dirá si basta. Fuera de la familia
# de los 4 concursantes. Los modelos razonadores rechazan `temperature`, por
# eso no se pasa.
JUDGE_MODEL = "gpt-5.6-luna"
JUDGE_EFFORT = "xhigh"

APROBADO = "aprobado"
SUSPENSO = "suspenso"

# Última medición del juez real (score fino + razón); la costura grade() sigue
# devolviendo solo el veredicto (contrato de los tests congelados) y el
# llm_evaluator lee esto con getattr — un fake que no lo rellene deja None.
last: dict | None = None

CALIBRATION_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "eval" / "judge-calibration.jsonl"
)


def _metric():
    """G-Eval perezoso (patrón de la casa): deepeval solo se importa/paga en la
    primera llamada real — los tests con `grade` parcheado nunca llegan aquí."""
    if not hasattr(_metric, "_cache"):
        load_dotenv()
        from deepeval.metrics import GEval
        from deepeval.models import OpenAIModel
        from deepeval.test_case import LLMTestCaseParams

        _metric._cache = GEval(
            name="correctness-divefy",
            criteria=JUDGE_PROMPT_PATH.read_text(encoding="utf-8"),
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
            model=OpenAIModel(
                model=JUDGE_MODEL,
                generation_kwargs={"reasoning_effort": JUDGE_EFFORT},
            ),
            # Score continuo 0-1 (ponderado por logprobs, paper G-Eval) + umbral
            # (decisión de Adolfo 2026-09-07): el veredicto sigue siendo binario
            # vía is_successful(), pero el score fino queda en la fila.
            strict_mode=False,
            threshold=0.5,
            async_mode=False,
            verbose_mode=False,
        )
    return _metric._cache


def grade(pregunta: str, respuesta: str, esperada: str) -> str:
    """aprobado/suspenso comparando la respuesta con la esperada del golden."""
    from deepeval.test_case import LLMTestCase

    global last
    metric = _metric()
    metric.measure(
        LLMTestCase(input=pregunta, actual_output=respuesta, expected_output=esperada)
    )
    last = {"score": round(metric.score, 4), "reason": metric.reason}
    logger.debug("[judge] %s", json.dumps(
        {"pregunta": pregunta, **last}, ensure_ascii=False,
    ))
    return APROBADO if metric.is_successful() else SUSPENSO


def calibrate(path: Path = CALIBRATION_PATH) -> dict:
    """Acuerdo juez↔Adolfo sobre sus 20-30 etiquetas (respuestas mezcladas de los
    4 modelos). ≥90% → juez válido; menos → ajustar rúbrica y repetir. Filas del
    fichero: {id, pregunta, respuesta, esperada, etiqueta} con etiqueta en
    {aprobado, suspenso}."""
    with path.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    if not rows:
        raise ValueError(f"{path} vacío — etiquetar 20-30 respuestas primero")
    desacuerdos = []
    for row in rows:
        veredicto = grade(row["pregunta"], row["respuesta"], row["esperada"])
        if veredicto != row["etiqueta"]:
            desacuerdos.append({**row, "veredicto_juez": veredicto})
    acuerdo = 1 - len(desacuerdos) / len(rows)
    return {"n": len(rows), "acuerdo": round(acuerdo, 4), "desacuerdos": desacuerdos}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    resultado = calibrate()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print("JUEZ VÁLIDO" if resultado["acuerdo"] >= 0.9 else "AJUSTAR RÚBRICA Y REPETIR")
