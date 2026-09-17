"""Etiquetado interactivo del fichero de calibración del juez (F7).

`uv run python -m divefy.evals.label_calibration [ruta.jsonl]` — enseña cada
muestra sin etiqueta (pregunta, esperada, respuesta) y pide una tecla:
a=aprobado, s=suspenso, enter=saltar, q=salir. Guarda el fichero tras CADA
etiqueta, así que se puede interrumpir y continuar. Reutilizable para
recalibraciones (rúbrica v2, doble pasada de estabilidad...).
"""

import json
import sys
import textwrap
from pathlib import Path

from divefy.evals.judge import APROBADO, CALIBRATION_PATH, SUSPENSO

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


def _bloque(titulo: str, texto: str) -> str:
    cuerpo = textwrap.fill(texto, width=100)
    return f"{BOLD}{titulo}{RESET}\n{cuerpo}\n"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CALIBRATION_PATH
    rows = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
    pendientes = [r for r in rows if not r.get("etiqueta")]
    print(f"{len(rows)} muestras, {len(pendientes)} sin etiquetar — a=aprobado, "
          "s=suspenso, enter=saltar, q=salir\n")

    for r in rows:
        if r.get("etiqueta"):
            continue
        hechas = sum(1 for x in rows if x.get("etiqueta"))
        print(f"{DIM}── {r['id']} · {hechas}/{len(rows)} etiquetadas ──{RESET}")
        print(_bloque("PREGUNTA", r["pregunta"]))
        print(_bloque("ESPERADA (golden)", r["esperada"]))
        print(_bloque("RESPUESTA (¿la apruebas?)", r["respuesta"]))
        tecla = input("[a/s/enter/q] > ").strip().lower()
        if tecla == "q":
            break
        if tecla in ("a", "s"):
            r["etiqueta"] = APROBADO if tecla == "a" else SUSPENSO
            # Nota libre opcional: el porqué de tu etiqueta — en los desacuerdos
            # es la materia prima de la rúbrica v2.
            nota = input("nota (enter = ninguna) > ").strip()
            if nota:
                r["nota"] = nota
            with path.open("w", encoding="utf-8") as fh:
                for x in rows:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")
        print()

    hechas = sum(1 for x in rows if x.get("etiqueta"))
    print(f"\n{hechas}/{len(rows)} etiquetadas. "
          + ("Listo: uv run python -m divefy.evals.judge" if hechas == len(rows)
             else "Relanza este script para continuar."))


if __name__ == "__main__":
    main()
