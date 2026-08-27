"""Fase 4 — Conexión Chroma compartida por indexing y retrieve: mismo cliente, misma colección canónica por config."""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings


def canonical_name(corpus: str, cap: int, extras: str, model: str) -> str:
    return f"{corpus}-{cap}-{extras}-{model}"


def chroma_directory() -> Path:
    return Path("data/chroma")


def get_collection(name: str, embeddings: Embeddings) -> Chroma:
    return Chroma(
        collection_name=name,
        embedding_function=embeddings,
        persist_directory=str(chroma_directory()),
        collection_metadata={"hnsw:space": "cosine"},
    )
