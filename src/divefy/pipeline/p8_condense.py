"""Fase 8 — Condensador: resuelve follow-ups del chat en una query autónoma de retrieval.

Ventana de 3 pares (PRD Fase 8): solo los últimos 3 turnos viajan al condensador — el
resto de la conversación se considera ya cerrado, sin memoria larga. Modelo fijo fuera
de la ablación: gemini-3.1-flash-lite, el mismo ya probado y barato del enriquecedor de
Fase 3 (`p3_enrich.py`).
"""

from pathlib import Path

from dotenv import load_dotenv
from google import genai

VENTANA = 3
MODELO_CONDENSADOR = "gemini-3.1-flash-lite"

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
CONDENSE_PROMPT_PATH = PROMPTS_DIR / "condense_v1.txt"
PROMPT_VERSION = CONDENSE_PROMPT_PATH.stem

# Cliente perezoso (patrón de p3_enrich.py): se construye la primera vez que hace
# falta de verdad, nunca al importar — los tests con fakes no necesitan GEMINI_API_KEY.
_cliente_gemini: genai.Client | None = None


def _cliente() -> genai.Client:
    global _cliente_gemini
    if _cliente_gemini is None:
        load_dotenv()
        _cliente_gemini = genai.Client()
    return _cliente_gemini


def _formatear_historial(pares: list[tuple[str, str]]) -> str:
    return "\n".join(f"Q: {pregunta}\nA: {respuesta}" for pregunta, respuesta in pares)


def condense(historial: list[tuple[str, str]], pregunta: str) -> str:
    """Últimos hasta-3 pares (pregunta, respuesta) + pregunta nueva -> query
    autónoma de retrieval."""
    ventana = historial[-VENTANA:]
    prompt = CONDENSE_PROMPT_PATH.read_text(encoding="utf-8").format(
        historial=_formatear_historial(ventana), pregunta=pregunta,
    )
    respuesta = _cliente().models.generate_content(model=MODELO_CONDENSADOR, contents=prompt)
    return (respuesta.text or "").strip()
