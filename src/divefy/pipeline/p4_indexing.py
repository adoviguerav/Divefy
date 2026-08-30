"""Fase 4 — Embeddings e índice: BGE-M3 / Qwen3-Embedding-0.6B/8B / OpenAI text-embedding-3-large
sobre Chroma, tres colecciones canónicas (base/contextual/hype) por corpus y modelo."""

import json
import logging
import time
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

from divefy.config import CORPUS_VALUES  # config es la fuente única (review 2026-08-30, #5)
from divefy.pipeline import p4_vectorstore
from divefy.pipeline.p4_vectorstore import canonical_name, get_collection
BATCH_SIZE = 32  # 702 textos de golpe tumbó el servidor local de Ollama (plan Notas, T-06)
EMBED_RETRIES = 3  # un 429 o un tosido de Ollama no debe tirar una pasada de horas (review 2026-08-28, #4)

logger = logging.getLogger(__name__)


def _filter_by_corpus(records: list[dict], corpus: str) -> list[dict]:
    """"combined" es un centinela: sin filtro, todas las filas."""
    if corpus == "combined":
        return list(records)
    return [r for r in records if r["corpus"] == corpus]


def _chunk_metadata(c: dict) -> dict:
    """Metadata autocontenida de fila chunk según docs/modelo-datos.md — cada campo
    con consumidor nombrado. Chroma solo admite escalares: listas van como JSON
    string, y los campos a None (capitulo/pagina en apuntes, fichero en manual) se
    omiten en vez de escribirse como null."""
    metadata = {
        "entry_type": "chunk",
        "corpus": c["corpus"],
        "section_ids": json.dumps(c["section_ids"], ensure_ascii=False),
        "titulo": c["titulo"],
        "n_tokens": c["n_tokens"],
    }
    for key in ("fichero", "capitulo", "pagina", "pagina_fin"):
        if c[key] is not None:
            metadata[key] = c[key]
    return metadata


def build_rows(chunks: list[dict], enrich: list[dict], corpus: str) -> dict[str, list[dict]]:
    """{"base": [...], "contextual": [...], "hype": [...]}, filtrado a `corpus`.
    Pura — sin llamadas a modelo ni red. Cada fila trae `id`/`document`/`metadata`
    (lo que va a Chroma) y `embed_text` (lo que de verdad se embebe — distinto del
    document en contextual/hype, ver plan Decision 6). `document` es SIEMPRE texto
    crudo de chunk: en las filas de pregunta HyPE, el del chunk padre — la pregunta
    solo se embebe y queda en metadata (plan Decision 22). `enrich` no trae `corpus`
    propio: se une por pertenencia del id a los chunks ya filtrados. puntero_tabla
    nunca se indexa — solo tipo=="prosa" (tablas fuera de alcance, EXPERIMENTOS.md)."""
    corpus_chunks = [c for c in _filter_by_corpus(chunks, corpus) if c["tipo"] == "prosa"]
    chunk_ids = {c["id"] for c in corpus_chunks}
    chunk_by_id = {c["id"]: c for c in corpus_chunks}
    corpus_enrich = [r for r in enrich if r["id"] in chunk_ids]

    missing_enrich = chunk_ids - {r["id"] for r in corpus_enrich}
    if missing_enrich:
        raise ValueError(
            f"{len(missing_enrich)} chunks de prosa de corpus={corpus!r} sin entrada en "
            f"enrich.jsonl (¿Fase 3 no corrió, o se cortó a mitad?): "
            f"{sorted(missing_enrich)[:5]}"
        )

    base_rows = [
        {
            "id": c["id"],
            "document": c["texto"],
            "metadata": _chunk_metadata(c),
            "embed_text": c["texto"],
        }
        for c in corpus_chunks
    ]

    contextual_rows = [
        {
            "id": r["id"],
            "document": chunk_by_id[r["id"]]["texto"],
            "metadata": {**_chunk_metadata(chunk_by_id[r["id"]]), "contexto": r["contexto"]},
            "embed_text": f"{r['contexto']}\n\n{chunk_by_id[r['id']]['texto']}",
        }
        for r in corpus_enrich
    ]

    hype_rows = list(contextual_rows)
    for r in corpus_enrich:
        parent = chunk_by_id[r["id"]]
        for i, pregunta in enumerate(r["preguntas"]):
            hype_rows.append(
                {
                    "id": f"{r['id']}::hype::{i}",
                    "document": parent["texto"],
                    "metadata": {
                        **_chunk_metadata(parent),
                        "contexto": r["contexto"],
                        "entry_type": "hype",
                        "parent_chunk_id": r["id"],
                        "pregunta": pregunta,
                    },
                    "embed_text": pregunta,
                }
            )

    return {"base": base_rows, "contextual": contextual_rows, "hype": hype_rows}


class LazyEmbeddings(Embeddings):
    """Envuelve un `Embeddings` real, difiriendo su construcción (que puede implicar
    descargar/cargar un modelo entero, o validar una API key) hasta la primera
    llamada real — importar este módulo no debe pagar ese coste (plan Notas, T-04)."""

    def __init__(self, factory: Callable[[], Embeddings]):
        self._factory = factory
        self._real: Embeddings | None = None

    def _get(self) -> Embeddings:
        if self._real is None:
            self._real = self._factory()
        return self._real

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._get().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._get().embed_query(text)

    def release(self) -> None:
        """Suelta el backend real (review 2026-08-28, #3): sin esto, el preflight deja
        los ~GB de bgem3/qwen06b residentes en memoria durante toda la pasada aunque
        solo trabaje un modelo a la vez. La siguiente llamada real lo recarga."""
        self._real = None


def _openai_embeddings() -> Embeddings:
    load_dotenv()
    return OpenAIEmbeddings(model="text-embedding-3-large")


MODELS: dict[str, Embeddings] = {
    "bgem3": LazyEmbeddings(lambda: HuggingFaceEmbeddings(model_name="BAAI/bge-m3")),
    "qwen06b": LazyEmbeddings(lambda: HuggingFaceEmbeddings(model_name="Qwen/Qwen3-Embedding-0.6B")),
    # Q8_0 vía Ollama, no HuggingFaceEmbeddings: en fp16 pesa ~15GB, arriesgado en
    # 24GB de memoria unificada; Q8_0 (~8GB) es casi sin pérdida frente al 4-bit por
    # defecto de Ollama, que sí sesgaría la comparación con bgem3/qwen06b (plan Notas, T-04).
    "qwen8b": LazyEmbeddings(lambda: OllamaEmbeddings(model="qwen3-embedding:8b-q8_0")),
    "openai3large": LazyEmbeddings(_openai_embeddings),
}


def _batched(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _embed_with_retry(embeddings: Embeddings, texts: list[str]) -> list[list[float]]:
    """Reintenta con espera creciente antes de rendirse — un fallo transitorio del
    backend no debe descartar todo lo embebido hasta ahora (review 2026-08-28, #4)."""
    for attempt in range(1, EMBED_RETRIES + 1):
        try:
            return embeddings.embed_documents(texts)
        except Exception:
            if attempt == EMBED_RETRIES:
                raise
            wait = 5 * attempt
            logger.warning("embed_documents falló (intento %d/%d), reintento en %ds", attempt, EMBED_RETRIES, wait)
            time.sleep(wait)
    raise AssertionError("unreachable")


def index_model(
    model: str,
    embeddings: Embeddings,
    rows: dict[str, list[dict]],
    corpus: str,
    cap: int,
    cache: dict[str, list[float]] | None = None,
) -> None:
    """Puebla las 3 colecciones canónicas de (corpus, model) desde `rows` (salida de
    build_rows). Cada `embed_text` distinto se embebe una sola vez — contextual y hype
    comparten sus filas de chunk, así que sin este cache se re-embebería el mismo
    texto dos veces (plan Decision 1) — y en lotes de BATCH_SIZE, no todos de golpe.
    `cache` es opcional: si el llamador comparte el mismo dict entre varias pasadas de
    corpus para un modelo, "combined" (== apuntes ∪ manual) reutiliza los vectores ya
    calculados en vez de recomputarlos (plan Notas, T-06).

    Escribe con `collection._collection.upsert(...)`, NO `Chroma.add_texts` — add_texts
    siempre reembebe `texts` con `self._embedding_function` internamente e ignora
    cualquier `embeddings=` que se le pase (plan Notas, T-07: confirmado leyendo su
    código fuente). Con add_texts nunca se habría respetado embed_text (contexto
    fusionado en contextual/hype) — se habría embebido el document crudo siempre.

    Post-review 2026-08-28: valida cap contra n_tokens antes de tocar nada (#1),
    escribe por lotes según embebe en vez de todo al final (#4/#8 — decisión de
    Adolfo; de paso ningún upsert se acerca al máximo local de Chroma, 5461 filas),
    y deja un fichero marcador `{colección}.complete` junto a la colección al
    terminar (#2) — sin marcador, quedó a medias entre reset y escritura y NO es
    válida. Va en fichero y no en la metadata de colección porque `modify` la
    reemplaza entera y langchain lee `hnsw:space` de ahí (probado en vivo)."""
    cache = {} if cache is None else cache

    for extras_rows in rows.values():
        for row in extras_rows:
            if row["metadata"]["n_tokens"] > cap:
                raise ValueError(
                    f"{row['id']!r} mide {row['metadata']['n_tokens']} tokens > cap={cap}: "
                    f"la colección llevaría un tope falso en el nombre (review 2026-08-28, #1)"
                )

    for extras, extras_rows in rows.items():
        name = canonical_name(corpus, cap, extras, model)
        collection = get_collection(name, embeddings)
        marker = p4_vectorstore.chroma_directory() / f"{name}.complete"
        marker.unlink(missing_ok=True)
        collection.reset_collection()
        for batch in _batched(extras_rows, BATCH_SIZE):
            missing = list(dict.fromkeys(r["embed_text"] for r in batch if r["embed_text"] not in cache))
            if missing:
                for text, vector in zip(missing, _embed_with_retry(embeddings, missing)):
                    cache[text] = vector
            collection._collection.upsert(
                ids=[row["id"] for row in batch],
                embeddings=[cache[row["embed_text"]] for row in batch],
                documents=[row["document"] for row in batch],
                metadatas=[row["metadata"] for row in batch],
            )
        marker.touch()
        logger.info("[%s] %s: %d filas", corpus, name, len(extras_rows))


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(cap: int = 512) -> None:
    processed_dir = Path("data/processed")
    chunks = _read_jsonl(processed_dir / "chunks.jsonl")
    enrich = _read_jsonl(processed_dir / "enrich.jsonl")

    for model, embeddings in MODELS.items():
        logger.info("preflight %s...", model)
        embeddings.embed_query("prueba")
        embeddings.release()  # el preflight valida, no debe dejar los 4 modelos cargados (review #3)

    # Modelo por fuera, corpus por dentro: solo un cache de embeddings vive a la vez
    # (antes, con corpus por fuera, los 4 caches de los 4 modelos coexistían en
    # memoria durante toda la pasada — ~1.2GB de más en una máquina de 24GB, revisión
    # de código, T-07). "combined" es exactamente apuntes ∪ manual (mismo embed_text),
    # así que reutiliza los vectores ya calculados en las 2 pasadas anteriores de este
    # mismo modelo en vez de re-embeberlos (plan Notas, T-06).
    for model, embeddings in MODELS.items():
        cache: dict[str, list[float]] = {}
        for corpus in CORPUS_VALUES:
            rows = build_rows(chunks, enrich, corpus)
            logger.info("=== %s / %s ===", corpus, model)
            index_model(model, embeddings, rows, corpus=corpus, cap=cap, cache=cache)
        embeddings.release()  # suelta este modelo antes de cargar el siguiente (review #3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    main()
