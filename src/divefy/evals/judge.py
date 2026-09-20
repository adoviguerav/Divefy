"""Fase 7 — Juez de generación: G-Eval (deepeval) con rúbrica versionada.

Solo evaluación, jamás runtime ni hardware: el juez necesita la respuesta
esperada, que solo existe en el examen (decisión 12 del plan). Modelo fijo de
familia fuera de la ablación, temperatura la fija deepeval (G-Eval determinista
por diseño con strict_mode). La rúbrica vive en `prompts/judge_v3.txt` y su
versión se estampa en cada fila (`prompt_version_juez`).

v3 (2026-09-20, decisión de Adolfo: "el mayor control posible sobre el
prompt"): pasamos `evaluation_steps` en vez de `criteria`. Con `criteria`,
deepeval hace una llamada extra al LLM que TRADUCE nuestra rúbrica a sus
propios pasos de evaluación — el juez obedece esa traducción, no lo que
escribimos. Con `evaluation_steps` (una línea del .txt = un paso), esa
traducción desaparece: el juez recibe nuestras frases literales, sin
intermediario. El envoltorio de deepeval (pedir nota+razón en JSON) se
mantiene — es mecánica de puntuación, no criterio de juicio.

Council (2026-09-20): sin `temperature` en ningún proveedor (retirado en toda
la generación actual — Anthropic, OpenAI, Google), un solo juez tiene ruido de
muestreo real cerca del umbral (caso h04 de la calibración: mismo texto,
0.6 y 0.4 en corridas distintas). En vez de repetir el MISMO juez (que repite
también su propio ruido), 3 jueces de 3 proveedores distintos votan por
mayoría — el desacuerdo entre ellos es una señal más honesta que la varianza
de uno solo consigo mismo, y de paso diversifica el sesgo de cada modelo.
"""

import json
import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
# v3 (2026-09-20): sobre v2 (mata la "lista blanca" de números; endurece
# claims que enturbian una conclusión de seguridad o avisos omitidos), añade
# la regla de ORDEN (calibración con Adolfo, casos h03/h08: alterar el orden o
# la prioridad de acciones de la esperada es fallo aunque estén todos los
# elementos) — y pasa a `evaluation_steps` (ver docstring del módulo).
JUDGE_PROMPT_PATH = PROMPTS_DIR / "judge_v3.txt"
PROMPT_VERSION = JUDGE_PROMPT_PATH.stem  # se estampa en la fila del eval


def _evaluation_steps() -> list[str]:
    """Una línea no vacía del .txt = un paso — nuestras frases literales,
    sin que deepeval las traduzca (ver docstring del módulo)."""
    return [
        linea.strip()
        for linea in JUDGE_PROMPT_PATH.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]

# Decisión 2026-09-20 (Adolfo): council de 3 proveedores en vez de un juez
# solo (ver docstring del módulo). Cada entrada: (nombre, clase deepeval,
# kwargs del constructor). Precios y disponibilidad verificados 2026-09-20
# contra la API real — gemini-2.5-flash devolvió 404 (retirado para cuentas
# nuevas); gemini-3.1-flash-lite confirmado con una llamada real ($0.25/$1.50
# por millón, la más barata de las probadas).
COUNCIL = [
    ("sonnet45", "AnthropicModel", {"model": "claude-sonnet-4-5"}),
    ("gemini31flashlite", "GeminiModel", {"model": "gemini-3.1-flash-lite"}),
    ("gpt41mini", "OpenAIModel", {"model": "gpt-4.1-mini", "temperature": 0}),
]

APROBADO = "aprobado"
SUSPENSO = "suspenso"

# Última medición del council: score/reason medios de los votos ganadores,
# más el detalle voto a voto en "jueces". La costura grade() sigue
# devolviendo solo el veredicto (contrato de los tests congelados) y el
# llm_evaluator lee esto con getattr — un fake que no lo rellene deja None.
last: dict | None = None

CALIBRATION_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "eval" / "judge-calibration.jsonl"
)


def _metrics() -> dict:
    """Una GEval perezosa por juez del council — mismos evaluation_steps para
    los 3, solo cambia el modelo detrás. Se construyen una vez por proceso."""
    if not hasattr(_metrics, "_cache"):
        import os

        load_dotenv()
        from deepeval import models as deepeval_models
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCaseParams

        # deepeval espera GOOGLE_API_KEY; nuestro .env usa GEMINI_API_KEY (el
        # nombre de la variable de Google AI Studio) — se lo pasamos explícito
        # en vez de duplicar la clave con dos nombres.
        extra = {"GeminiModel": {"api_key": os.environ.get("GEMINI_API_KEY")}}

        steps = _evaluation_steps()
        _metrics._cache = {
            nombre: GEval(
                name=f"correctness-divefy-{nombre}",
                evaluation_steps=steps,
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                    LLMTestCaseParams.EXPECTED_OUTPUT,
                ],
                model=getattr(deepeval_models, clase)(**kwargs, **extra.get(clase, {})),
                # Score continuo 0-1 (ponderado por logprobs, paper G-Eval) +
                # umbral (decisión de Adolfo 2026-09-07): is_successful() da
                # el voto binario de este juez; el council decide por mayoría.
                strict_mode=False,
                threshold=0.5,
                async_mode=False,
                verbose_mode=False,
            )
            for nombre, clase, kwargs in COUNCIL
        }
    return _metrics._cache


def grade(pregunta: str, respuesta: str, esperada: str) -> str:
    """aprobado/suspenso por mayoría de los 3 jueces del council (2 de 3)."""
    from deepeval.test_case import LLMTestCase

    global last
    caso = LLMTestCase(input=pregunta, actual_output=respuesta, expected_output=esperada)
    votos = {}
    for nombre, metric in _metrics().items():
        metric.measure(caso)
        votos[nombre] = {
            "veredicto": APROBADO if metric.is_successful() else SUSPENSO,
            "score": round(metric.score, 4),
            "reason": metric.reason,
        }

    aprobados = [v for v in votos.values() if v["veredicto"] == APROBADO]
    veredicto = APROBADO if len(aprobados) >= 2 else SUSPENSO
    scores = [v["score"] for v in votos.values()]
    last = {
        "veredicto": veredicto,
        "score": round(sum(scores) / len(scores), 4),
        "reason": " | ".join(f"{n}: {v['reason']}" for n, v in votos.items()),
        "jueces": votos,
    }
    logger.debug("[judge] %s", json.dumps(
        {"pregunta": pregunta, **last}, ensure_ascii=False,
    ))
    return veredicto


def calibrate(path: Path = CALIBRATION_PATH) -> dict:
    """Acuerdo juez↔Adolfo sobre sus 20-30 etiquetas (respuestas mezcladas de los
    4 modelos). ≥90% → juez válido; menos → ajustar rúbrica y repetir. Filas del
    fichero: {id, pregunta, respuesta, esperada, etiqueta} con etiqueta en
    {aprobado, suspenso}."""
    with path.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    # Solo las etiquetadas: una fila sin etiqueta está pendiente, no en desacuerdo.
    rows = [r for r in rows if r.get("etiqueta")]
    if not rows:
        raise ValueError(f"{path} sin filas etiquetadas — etiquetar 20-30 respuestas primero")
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
