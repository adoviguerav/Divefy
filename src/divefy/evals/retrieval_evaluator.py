"""Fase 5 — Evaluador de retrieval: config -> fila de métricas versionada (hit_rate, recall, precision, MRR, tokens). La generación (F7) se evalúa en llm_evaluator."""

import argparse
import difflib
import json
from pathlib import Path

from ranx import Qrels, Run
from ranx import evaluate as ranx_evaluate

from divefy.config import RetrievalConfig
from divefy.pipeline import p4_vectorstore, p5_retrieve
from divefy.pipeline.p4_indexing import MODELS

# Rutas ancladas a la raíz del repo — el evaluador funciona desde cualquier CWD
# (review 2026-08-30, #9).
GOLDEN_PATH = p4_vectorstore.REPO_ROOT / "data" / "eval" / "golden.jsonl"
LABELS_PATH = p4_vectorstore.REPO_ROOT / "data" / "eval" / "labels.jsonl"
RESULTS_DIR = p4_vectorstore.REPO_ROOT / "results"


def evaluate(golden, labels_by_id, retrieved_by_id, chunk_sections, chunk_tokens, k):
    """Métricas puras sobre datos ya recuperados: (resumen, detalle).

    La métrica sigue la etiqueta (metricas-framework.md): un chunk cuenta si su
    procedencia toca la etiqueta; el denominador del recall es lo que la etiqueta
    lista. Agregados SOLO de ranx — una única fuente de cálculo. Las preguntas
    sin_respuesta quedan fuera de los agregados de ranking pero en el detalle,
    como insumo de abstención para F7."""
    detalle = []
    tokens_total = 0
    # espacios chunk (hit_rate/precision/mrr): global + desglose por corpus
    spaces = {name: ({}, {}) for name in ("global", "apuntes", "manual")}
    qrels_secciones, run_secciones = {}, {}

    for pregunta in golden:
        qid = pregunta["id"]
        label = labels_by_id[qid]
        recuperados = retrieved_by_id[qid]
        tokens = sum(chunk_tokens[cid] for cid in recuperados)
        tokens_total += tokens
        detalle.append(
            {"id": qid, "recuperados": recuperados, "tokens": tokens,
             "sin_respuesta": label["sin_respuesta"]}
        )

        etiquetas = {
            "global": set(label["secciones_apuntes"]) | set(label["secciones_manual"]),
            "apuntes": set(label["secciones_apuntes"]),
            "manual": set(label["secciones_manual"]),
        }
        if not etiquetas["global"]:
            continue

        ranking = {cid: 1.0 / rank for rank, cid in enumerate(recuperados, start=1)}
        for name, etiquetadas in etiquetas.items():
            if not etiquetadas:
                continue
            qrels, run = spaces[name]
            relevantes = {cid: 1 for cid, secs in chunk_sections.items() if secs & etiquetadas}
            # etiqueta entera fuera de esta colección (p.ej. solo-manual sobre
            # apuntes): centinela para que la pregunta cuente como fallo, no crashee
            qrels[qid] = relevantes or {"__sin_cobertura__": 1}
            run[qid] = ranking

        qrels_secciones[qid] = {sid: 1 for sid in etiquetas["global"]}
        cubiertas = {}
        for rank, cid in enumerate(recuperados, start=1):
            for sid in chunk_sections.get(cid, ()):
                cubiertas.setdefault(sid, 1.0 / rank)  # mejor posición
        run_secciones[qid] = cubiertas

    def hit_rate(name):
        qrels, run = spaces[name]
        if not qrels:
            return None
        return round(ranx_evaluate(Qrels(qrels), Run(run), f"hit_rate@{k}"), 4)

    qrels_global, run_global = spaces["global"]
    if qrels_global:
        scores = ranx_evaluate(
            Qrels(qrels_global), Run(run_global),
            [f"hit_rate@{k}", f"precision@{k}", f"mrr@{k}"],
        )
        recall = ranx_evaluate(Qrels(qrels_secciones), Run(run_secciones), "recall")
    else:  # todas sin_respuesta: sin métricas de ranking definibles
        scores, recall = {}, None

    resumen = {
        "hit_rate": round(scores[f"hit_rate@{k}"], 4) if scores else None,
        "recall": round(recall, 4) if recall is not None else None,
        "precision": round(scores[f"precision@{k}"], 4) if scores else None,
        "mrr": round(scores[f"mrr@{k}"], 4) if scores else None,
        "hit_rate_apuntes": hit_rate("apuntes"),
        "hit_rate_manual": hit_rate("manual"),
        "tokens_recuperados_media": round(tokens_total / len(golden), 2),
        "n_preguntas": len(golden),
        # cuántas puntuaron de verdad en los agregados de ranking — sin esto, dos
        # filas de tandas de etiquetado distintas serían incomparables en silencio
        "n_puntuadas": len(qrels_global),
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
    (Decision 8): la procedencia y n_tokens salen de la metadata de las filas
    chunk de la colección, sin join contra chunks.jsonl."""
    golden = [g for g in _read_jsonl(GOLDEN_PATH) if g.get("uso") == "eval"]
    if not golden:
        raise ValueError(
            f"{GOLDEN_PATH} no tiene ninguna fila uso=eval — fichero truncado o "
            "campo renombrado; el examen son 84 preguntas."
        )
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

    collection = p4_vectorstore.get_collection(config.collection, MODELS[config.embedding])
    data = collection.get()
    chunk_sections, chunk_tokens = {}, {}
    for row_id, metadata in zip(data["ids"], data["metadatas"]):
        if metadata["entry_type"] == "chunk":
            chunk_sections[row_id] = set(json.loads(metadata["section_ids"]))
            chunk_tokens[row_id] = metadata["n_tokens"]

    resumen, detalle = evaluate(
        golden, labels_by_id, retrieved_by_id, chunk_sections, chunk_tokens, config.k
    )
    config_dict = {
        "corpus": config.corpus, "cap": config.cap, "extras": config.extras,
        "embedding": config.embedding, "search": config.search, "k": config.k,
        "rerank": config.rerank, "collection": config.collection, "run_id": config.run_id,
    }
    return {"config": config_dict, "resumen": resumen, "detalle": detalle}


def _run_and_write(config: RetrievalConfig) -> dict:
    data = run(config)
    estado = write_result(data, RESULTS_DIR / f"{config.run_id}.json")
    return {"estado": estado, "resumen": data["resumen"]}


def paso0() -> None:
    """T-07: cruce denso corpus×extras×modelo — 36 pasadas k=5, una fila cada una.
    Reanudable: filas ya escritas salen como [identica] y la caché de vectores
    persiste tras cada embedding."""
    import time

    from divefy.config import CORPUS_VALUES, EMBEDDING_VALUES, EXTRAS_VALUES

    queries = [g["pregunta"] for g in _read_jsonl(GOLDEN_PATH) if g.get("uso") == "eval"]
    total = len(EMBEDDING_VALUES) * len(CORPUS_VALUES) * len(EXTRAS_VALUES)
    pasada = 0
    for model in EMBEDDING_VALUES:
        t = time.time()
        p5_retrieve.ensure_query_vectors(model, queries)
        if hasattr(MODELS[model], "release"):
            MODELS[model].release()
        print(f"[cache] {model}: {len(queries)} vectores listos en {time.time() - t:.1f}s", flush=True)
        for corpus in CORPUS_VALUES:
            for extras in EXTRAS_VALUES:
                pasada += 1
                config = RetrievalConfig(
                    corpus=corpus, extras=extras, embedding=model, search="densa", k=5
                )
                t = time.time()
                salida = _run_and_write(config)
                r = salida["resumen"]
                print(
                    f"[{pasada:2}/{total}] [{salida['estado']}] {config.run_id}: "
                    f"hit_rate={r['hit_rate']} recall={r['recall']} "
                    f"precision={r['precision']} mrr={r['mrr']} "
                    f"apuntes={r['hit_rate_apuntes']} manual={r['hit_rate_manual']} "
                    f"tokens={r['tokens_recuperados_media']} ({time.time() - t:.1f}s)",
                    flush=True,
                )
    print("PASO 0 COMPLETO", flush=True)


def tabla() -> None:
    """`results/RESUMEN.html`: una fila por run con sus métricas (sin detalle),
    con filtros y ordenación. Vista derivada y regenerable — la única pieza de
    results/ que SÍ se sobreescribe, porque no es record, es vista."""
    filas = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(RESULTS_DIR.glob("*.json"))
    ]
    if not filas:
        print(f"{RESULTS_DIR} vacío — nada que resumir")
        return
    # Unión de claves preservando orden: results/ mezcla filas de retrieval y de
    # generación (F7) con resúmenes distintos; una fila sin una clave pinta "—".
    claves = list(dict.fromkeys(k for fila in filas for k in fila["resumen"]))
    html = RESULTS_DIR / "RESUMEN.html"
    html.write_text(_tabla_html(filas, claves), encoding="utf-8")
    print(f"{html}: {len(filas)} runs — abrir con `open {html}`")


_CONFIG_COLS = ("corpus", "extras", "embedding", "search", "k", "cap", "rerank")


def _tabla_html(filas: list[dict], claves: list[str]) -> str:
    """Vista HTML autocontenida: un desplegable de filtro por columna de config y
    ordenación clicando la cabecera de cualquier métrica."""
    datos = [
        # .get: las filas anteriores a F6 no llevan la clave "rerank" (= off)
        {**{c: fila["config"].get(c, False) for c in _CONFIG_COLS},
         **{k: fila["resumen"].get(k) for k in claves}}
        for fila in filas
    ]
    columnas = list(_CONFIG_COLS) + claves
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>results — resumen</title>
<style>
body{{font-family:ui-monospace,monospace;font-size:13px;margin:16px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:3px 7px;text-align:right;white-space:nowrap}}
th{{background:#f0f0f0;cursor:pointer;position:sticky;top:0}}
td:nth-child(-n+7),th:nth-child(-n+7){{text-align:left}}
tr:hover{{background:#fffbe6}} select{{margin:0 6px 10px 0}}
.max{{background:#d7f5d7;font-weight:bold}}
</style></head><body>
<h3>results/ — {len(datos)} runs (vista derivada; regenerar con --tabla)</h3>
<div id="filtros"></div><table id="t"><thead><tr></tr></thead><tbody></tbody></table>
<script>
const COLS={json.dumps(columnas)},CONFIG={json.dumps(list(_CONFIG_COLS))},DATA={json.dumps(datos, ensure_ascii=False)};
let orden=null,desc=true;
const filtros={{}};
CONFIG.forEach(c=>{{
  const vals=[...new Set(DATA.map(d=>String(d[c])))].sort();
  const s=document.createElement('select');
  s.innerHTML=`<option value="">${{c}}: todos</option>`+vals.map(v=>`<option>${{v}}</option>`).join('');
  s.onchange=()=>{{filtros[c]=s.value;pinta()}};
  document.getElementById('filtros').appendChild(s);
}});
document.querySelector('thead tr').innerHTML=COLS.map(c=>`<th onclick="ordenar('${{c}}')">${{c}}</th>`).join('');
function ordenar(c){{desc=(orden===c)?!desc:true;orden=c;pinta()}}
function pinta(){{
  let rows=DATA.filter(d=>CONFIG.every(c=>!filtros[c]||String(d[c])===filtros[c]));
  if(orden)rows=[...rows].sort((a,b)=>(a[orden]>b[orden]?1:-1)*(desc?-1:1));
  const maxs={{}};
  COLS.slice(CONFIG.length).forEach(c=>maxs[c]=Math.max(...rows.map(r=>r[c]??-Infinity)));
  document.querySelector('tbody').innerHTML=rows.map(r=>'<tr>'+COLS.map(c=>
    `<td class="${{typeof r[c]==='number'&&r[c]===maxs[c]?'max':''}}">${{r[c]??'—'}}</td>`).join('')+'</tr>').join('');
}}
pinta();
</script></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluator: config → results/{run_id}.json")
    parser.add_argument("--paso0", action="store_true",
                        help="las 36 pasadas densas k=5 del cruce corpus×extras×modelo (T-07)")
    parser.add_argument("--tabla", action="store_true",
                        help="regenera results/RESUMEN.html (métricas de cada run, con filtros)")
    parser.add_argument("--corpus")
    parser.add_argument("--extras")
    parser.add_argument("--embedding")
    parser.add_argument("--search")
    parser.add_argument("--k", type=int)
    parser.add_argument("--cap", type=int, default=512)
    parser.add_argument("--rerank", action="store_true",
                        help="rerank con bge-reranker-v2-m3 (N=20 → k); run_id lleva sufijo -rerank")
    args = parser.parse_args()

    if args.paso0:
        paso0()
        tabla()
        return
    if args.tabla:
        tabla()
        return
    if not all((args.corpus, args.extras, args.embedding, args.search, args.k)):
        parser.error("o --paso0, o la config completa: --corpus --extras --embedding --search --k")

    config = RetrievalConfig(
        corpus=args.corpus, extras=args.extras, embedding=args.embedding,
        search=args.search, k=args.k, cap=args.cap, rerank=args.rerank,
    )
    salida = _run_and_write(config)
    print(f"[{salida['estado']}] {RESULTS_DIR / (config.run_id + '.json')}")
    print(json.dumps(salida["resumen"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
