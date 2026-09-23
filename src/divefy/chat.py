"""Fase 8 (recorte) — Chat CLI: bucle de conversación mínimo sobre p7_generate.answer().

Memoria de 3 pares vía condensador (p8_condense.condense). Resto de Fase 8 (Textual,
modo buceo/dev, comandos /fuentes /config /reset, streaming, trazas LangSmith) queda
pendiente — ver `.claude/plans/phase-8-chat-cli/plan.md`.
"""

import argparse

from rich.console import Console
from rich.panel import Panel

import divefy.llm as llm
from divefy.config import RECETA_GANADORA
from divefy.pipeline import p7_generate, p8_condense

SALIR = {"/salir", "/exit", "/quit"}


def run_turn(
    historial: list[tuple[str, str]], model: str, pregunta: str
) -> tuple[str, list[tuple[str, str]]]:
    """Un turno de chat: condensa la pregunta contra el historial, genera la
    respuesta, y devuelve (respuesta, historial_actualizado) sin mutar el
    historial que recibió."""
    query = p8_condense.condense(historial, pregunta)
    resultado = p7_generate.answer(RECETA_GANADORA, model, query)
    return resultado.respuesta, historial + [(pregunta, resultado.respuesta)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Divefy — chat CLI")
    parser.add_argument(
        "--model",
        choices=sorted(llm.API_MODELS) + sorted(llm.MLX_MODELS),
        required=True,
    )
    args = parser.parse_args()

    console = Console()
    historial: list[tuple[str, str]] = []
    console.print("[bold cyan]Divefy[/] — escribe tu pregunta ([dim]/salir para terminar[/])")

    while True:
        try:
            pregunta = console.input("[bold green]tú >[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not pregunta:
            continue
        if pregunta.lower() in SALIR:
            break
        respuesta, historial = run_turn(historial, args.model, pregunta)
        console.print(Panel(respuesta, title="Divefy", border_style="cyan"))


if __name__ == "__main__":
    main()
