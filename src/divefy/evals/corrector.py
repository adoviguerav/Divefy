"""Fases 5 y 7 — El corrector: config -> fila de métricas versionada (recall@k, MRR, numérica, juez, abstención, latencia, coste)."""

import argparse
import difflib
import json
import re
from pathlib import Path

from divefy.config import RetrievalConfig
from divefy.pipeline import p4_vectorstore, p5_retrieve

GOLDEN_PATH = Path("data/eval/golden.jsonl")
LABELS_PATH = Path("data/eval/labels.jsonl")
RESULTS_DIR = Path("results")

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> set[float]:
    """Números del texto con coma decimal normalizada a punto (Decision 7)."""
    return {float(match.replace(",", ".")) for match in _NUMBER_RE.findall(text)}


def evaluate(golden, labels_by_id, retrieved_by_id, rows_by_chunk_id):
    """Métricas puras sobre datos ya recuperados: (resumen, detalle).

    Las preguntas sin_respuesta quedan fuera de recall/MRR (no hay sección
    correcta que recuperar) pero se listan en el detalle como insumo de
    abstención para F7 (Decision 6)."""
    detalle = []
    aciertos = mrr_total = con_etiqueta = 0
    aciertos_apuntes = con_apuntes = aciertos_manual = con_manual = 0
    matches_numericos = con_numeros = tokens_total = 0

    for pregunta in golden:
        qid = pregunta["id"]
        label = labels_by_id[qid]
        recuperados = retrieved_by_id[qid]
        filas = [rows_by_chunk_id[chunk_id] for chunk_id in recuperados]
        tokens = sum(fila["n_tokens"] for fila in filas)
        tokens_total += tokens

        etiquetadas_apuntes = set(label["secciones_apuntes"])
        etiquetadas_manual = set(label["secciones_manual"])
        etiquetadas = etiquetadas_apuntes | etiquetadas_manual

        if label["sin_respuesta"]:
            acierto = rank = acierto_apuntes = acierto_manual = None
        else:
            con_etiqueta += 1
            rank = next(
                (i for i, fila in enumerate(filas, start=1) if etiquetadas & set(fila["section_ids"])),
                None,
            )
            acierto = rank is not None
            aciertos += acierto
            mrr_total += 1 / rank if rank else 0
            acierto_apuntes = acierto_manual = None
            if etiquetadas_apuntes:
                con_apuntes += 1
                acierto_apuntes = any(etiquetadas_apuntes & set(f["section_ids"]) for f in filas)
                aciertos_apuntes += acierto_apuntes
            if etiquetadas_manual:
                con_manual += 1
                acierto_manual = any(etiquetadas_manual & set(f["section_ids"]) for f in filas)
                aciertos_manual += acierto_manual

        numeros = extract_numbers(" ".join(pregunta["respuesta_esperada"]))
        match_numerico = None
        if numeros:
            con_numeros += 1
            match_numerico = numeros <= extract_numbers(" ".join(f["texto"] for f in filas))
            matches_numericos += match_numerico

        detalle.append(
            {
                "id": qid,
                "recuperados": recuperados,
                "acierto": acierto,
                "rank": rank,
                "acierto_apuntes": acierto_apuntes,
                "acierto_manual": acierto_manual,
                "tokens": tokens,
                "match_numerico": match_numerico,
                "sin_respuesta": label["sin_respuesta"],
            }
        )

    resumen = {
        "recall_at_k": round(aciertos / con_etiqueta, 4) if con_etiqueta else None,
        "recall_apuntes": round(aciertos_apuntes / con_apuntes, 4) if con_apuntes else None,
        "recall_manual": round(aciertos_manual / con_manual, 4) if con_manual else None,
        "mrr": round(mrr_total / con_etiqueta, 4) if con_etiqueta else None,
        "tokens_recuperados_media": round(tokens_total / len(golden), 2),
        "match_numerico": round(matches_numericos / con_numeros, 4) if con_numeros else None,
        "n_preguntas": len(golden),
    }
    return resumen, detalle


def serialize(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_result(data: dict, path: Path) -> str:
    """Política nunca-se-sobreescribe (Decision 6): idéntica → no-op; distinta →
    error con el diff (borrado manual si el cambio es intencionado)."""
    payload = serialize(data)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == payload:
            return "identica"
        diff = "\n".join(
            difflib.unified_diff(
                existing.splitlines(), payload.splitlines(),
                fromfile=str(path), tofile="fila nueva", lineterm="", n=1,
            )
        )
        raise FileExistsError(
            f"{path} ya existe con una fila DISTINTA — results/ nunca se "
            f"sobreescribe; borra el fichero a mano si el cambio es intencionado.\n{diff}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return "escrita"


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run(config: RetrievalConfig) -> dict:
    """Una config → {"config", "resumen", "detalle"}. Lee solo Chroma en runtime
    (Decision 8): section_ids/corpus/n_tokens salen de la metadata de las filas
    recuperadas, sin join contra chunks.jsonl."""
    golden = [g for g in _read_jsonl(GOLDEN_PATH) if g.get("uso") == "eval"]
    labels_by_id = {row["id"]: row for row in _read_jsonl(LABELS_PATH)}
    if [g["id"] for g in golden] != list(labels_by_id):
        raise ValueError(
            "labels.jsonl no cuadra con las preguntas uso=eval del golden — "
            "regenera las etiquetas (T-03) antes de corregir."
        )

    vectors = p5_retrieve.ensure_query_vectors(config.embedding, [g["pregunta"] for g in golden])
    retrieved_by_id = {
        g["id"]: p5_retrieve.retrieve(config, g["pregunta"], vectors[g["pregunta"]])
        for g in golden
    }

    from divefy.pipeline.p4_indexing import MODELS  # perezoso: solo por la firma de get_collection

    collection = p4_vectorstore.get_collection(config.collection, MODELS[config.embedding])
    chunk_ids = sorted({cid for ids in retrieved_by_id.values() for cid in ids})
    data = collection.get(ids=chunk_ids)
    rows_by_chunk_id = {
        row_id: {
            "section_ids": json.loads(metadata["section_ids"]),
            "corpus": metadata["corpus"],
            "n_tokens": metadata["n_tokens"],
            "texto": document,
        }
        for row_id, document, metadata in zip(data["ids"], data["documents"], data["metadatas"])
    }

    resumen, detalle = evaluate(golden, labels_by_id, retrieved_by_id, rows_by_chunk_id)
    config_dict = {
        "corpus": config.corpus, "cap": config.cap, "extras": config.extras,
        "embedding": config.embedding, "search": config.search, "k": config.k,
        "collection": config.collection, "run_id": config.run_id,
    }
    return {"config": config_dict, "resumen": resumen, "detalle": detalle}


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrector v1: config → results/{run_id}.json")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--extras", required=True)
    parser.add_argument("--embedding", required=True)
    parser.add_argument("--search", required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--cap", type=int, default=512)
    args = parser.parse_args()

    config = RetrievalConfig(
        corpus=args.corpus, extras=args.extras, embedding=args.embedding,
        search=args.search, k=args.k, cap=args.cap,
    )
    data = run(config)
    path = RESULTS_DIR / f"{config.run_id}.json"
    estado = write_result(data, path)
    print(f"[{estado}] {path}")
    print(json.dumps(data["resumen"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
