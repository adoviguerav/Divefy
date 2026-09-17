"""Fase 7 — llm_evaluator: config + modelo → fila versionada (juez + abstención).

Corre el pipeline completo (retrieve → generar → guardarraíl → juez) sobre las
preguntas `uso=eval` del golden y escribe su propia fila en `results/`, con las
versiones de prompt estampadas. Molde: `retrieval_evaluator` (serialize/
write_result importados, no copiados — política nunca-sobreescribir intacta).
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import divefy.evals.judge as judge  # atributo de módulo: costura parcheable
from divefy.config import RetrievalConfig
from divefy.evals.retrieval_evaluator import (
    GOLDEN_PATH,
    RESULTS_DIR,
    _read_jsonl,
    serialize,
    write_result,
)
from divefy.pipeline import p7_generate

logger = logging.getLogger(__name__)

ABSTENCION = "abstención"


def run(retrieval_config: RetrievalConfig, model) -> dict:
    """Una config + un modelo → {"config", "resumen", "detalle"}. Las preguntas
    que acaban en plantilla de abstención NO pasan por el juez (hoy, con 0
    etiquetas sin_respuesta, toda abstención es falsa abstención — se ve en el
    resumen; los negativos reales llegan con el eval fresco, P1)."""
    golden = [g for g in _read_jsonl(GOLDEN_PATH) if g.get("uso") == "eval"]
    if not golden:
        raise ValueError(
            f"{GOLDEN_PATH} no tiene ninguna fila uso=eval — fichero truncado o "
            "campo renombrado; el examen son 84 preguntas."
        )

    detalle = []
    for i, g in enumerate(golden, start=1):
        respuesta = p7_generate.answer(retrieval_config, model, g["pregunta"])
        if respuesta.abstencion:
            veredicto, score = ABSTENCION, None
        else:
            # En el golden respuesta_esperada es lista (hoy siempre de 1); el
            # juez recibe texto plano — variantes futuras se unen como
            # alternativas explícitas.
            esperada = g["respuesta_esperada"]
            if isinstance(esperada, list):
                esperada = "\nO BIEN (alternativa igual de válida):\n".join(esperada)
            veredicto = judge.grade(g["pregunta"], respuesta.respuesta, esperada)
            # Score fino del juez real (None con un juez fake que no lo rellene).
            score = (getattr(judge, "last", None) or {}).get("score")
        detalle.append(
            {
                "id": g["id"],
                "pregunta": g["pregunta"],
                "respuesta": respuesta.respuesta,
                "veredicto": veredicto,
                "score": score,
            }
        )
        logger.info("[%d/%d] %s → %s", i, len(golden), g["id"], veredicto)

    n = len(detalle)
    aprobados = sum(1 for row in detalle if row["veredicto"] == judge.APROBADO)
    suspensos = sum(1 for row in detalle if row["veredicto"] == judge.SUSPENSO)
    abstenciones = n - aprobados - suspensos
    scores = [row["score"] for row in detalle if row["score"] is not None]
    resumen = {
        "n": n,
        "aprobado": aprobados,
        "suspenso": suspensos,
        "abstenciones": abstenciones,
        "tasa_aprobado": round(aprobados / n, 4),
        "score_medio": round(sum(scores) / len(scores), 4) if scores else None,
    }

    config_dict = {
        "corpus": retrieval_config.corpus, "cap": retrieval_config.cap,
        "extras": retrieval_config.extras, "embedding": retrieval_config.embedding,
        "search": retrieval_config.search, "k": retrieval_config.k,
        "rerank": retrieval_config.rerank, "collection": retrieval_config.collection,
        "model": str(model),
        "run_id": f"{retrieval_config.run_id}-{model}",
        "prompt_version_generacion": p7_generate.PROMPT_VERSION,
        "prompt_version_juez": judge.PROMPT_VERSION,
    }
    return {"config": config_dict, "resumen": resumen, "detalle": detalle}


def setup_logging(run_id: str) -> Path:
    """Consola limpia (INFO: progreso [i/84]) + fichero con TODO el detalle
    (DEBUG de divefy: estado JSON por etapa del pipeline —decisión 17— y
    score+razón del juez). Un fichero por pasada, timestamp para no pisar
    relanzamientos del mismo run_id (p. ej. tras rúbrica v2)."""
    log_path = Path("logs") / f"{run_id}-{datetime.now():%Y%m%d-%H%M%S}.log"
    log_path.parent.mkdir(exist_ok=True)
    consola = logging.StreamHandler()
    consola.setLevel(logging.INFO)
    consola.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    fichero = logging.FileHandler(log_path, encoding="utf-8")
    fichero.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    logging.basicConfig(level=logging.INFO, handlers=[consola, fichero])
    # Solo nuestro paquete baja a DEBUG; las librerías (httpx, openai…) se
    # quedan en INFO para no inundar el fichero.
    logging.getLogger("divefy").setLevel(logging.DEBUG)
    return log_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="llm_evaluator: config + modelo → results/{run_id}.json"
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--extras", required=True)
    parser.add_argument("--embedding", required=True)
    parser.add_argument("--search", required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--cap", type=int, default=512)
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--model", required=True,
                        help="clave del experimento: sonnet5 | haiku45 | qwen9b | qwen4b")
    args = parser.parse_args()

    config = RetrievalConfig(
        corpus=args.corpus, extras=args.extras, embedding=args.embedding,
        search=args.search, k=args.k, cap=args.cap, rerank=args.rerank,
    )
    log_path = setup_logging(f"{config.run_id}-{args.model}")
    logger.info("log completo de la pasada: %s", log_path)
    data = run(config, args.model)
    estado = write_result(data, RESULTS_DIR / f"{data['config']['run_id']}.json")
    print(f"[{estado}] {RESULTS_DIR / (data['config']['run_id'] + '.json')}")
    print(json.dumps(data["resumen"], ensure_ascii=False, indent=2))
    print(f"log: {log_path}")


if __name__ == "__main__":
    main()
