"""Fase 4 — Conexión Chroma compartida por indexing y retrieve: mismo cliente, misma colección canónica por config."""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

# Raíz del repo anclada a este fichero (src/divefy/pipeline/ → 3 niveles arriba):
# las rutas de datos funcionan desde cualquier CWD (review 2026-08-30, #9).
REPO_ROOT = Path(__file__).resolve().parents[3]


def canonical_name(corpus: str, cap: int, extras: str, model: str) -> str:
    return f"{corpus}-{cap}-{extras}-{model}"


def chroma_directory() -> Path:
    return REPO_ROOT / "data" / "chroma"


def get_collection(name: str, embeddings: Embeddings) -> Chroma:
    return Chroma(
        collection_name=name,
        embedding_function=embeddings,
        persist_directory=str(chroma_directory()),
        collection_metadata={"hnsw:space": "cosine"},
    )
