"""Tests de aceptación de la Fase 2 (chunking): corren contra los artefactos generados
por `python -m divefy.pipeline.p2_chunking` en data/processed/chunks.jsonl (tope 512,
tokenizador BGE-M3 real). Hasta que ese artefacto exista, las pruebas fallan con
FileNotFoundError — es el RED esperado."""

import json
from pathlib import Path

import pytest

PROCESSED_DIR = Path("data/processed")
CORPUS_PATH = PROCESSED_DIR / "corpus.jsonl"
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"

TOPE = 512


@pytest.fixture(scope="module")
def corpus_records():
    with CORPUS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def chunk_records():
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def contar_tokens():
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
    return lambda texto: len(tokenizer.tokenize(texto))


# --- 1. Ningún trozo vacío ni sobre el tope; nada se pierde en el camino -----------


def test_ningun_trozo_vacio(chunk_records):
    assert chunk_records
    for c in chunk_records:
        assert c["texto"].strip(), c["section_ids"]


def test_ningun_trozo_prosa_sobre_el_tope(chunk_records, contar_tokens):
    prosa = [c for c in chunk_records if c["tipo"] == "prosa"]
    assert prosa
    for c in prosa:
        assert contar_tokens(c["texto"]) <= TOPE, (c["section_ids"], contar_tokens(c["texto"]))


def test_ningun_trozo_se_pierde_por_el_camino(corpus_records, chunk_records):
    secciones_prosa = [r for r in corpus_records if r["tipo"] == "prosa"]
    trozos_prosa = [c for c in chunk_records if c["tipo"] == "prosa"]
    assert len(trozos_prosa) >= len(secciones_prosa)

    punteros_in = [r for r in corpus_records if r["tipo"] == "puntero_tabla"]
    punteros_out = [c for c in chunk_records if c["tipo"] == "puntero_tabla"]
    assert len(punteros_out) == len(punteros_in)


# --- 2. Metadatos bien formados -----------------------------------------------------


def test_trozos_bien_formados(chunk_records):
    for c in chunk_records:
        assert c["corpus"] in ("apuntes", "manual")
        assert c["tipo"] in ("prosa", "puntero_tabla")
        assert c["section_ids"], c
        assert c["titulo"]
        if c["corpus"] == "apuntes":
            assert c["fichero"]
            assert c["capitulo"] is None
        else:
            assert c["capitulo"] is not None
            assert c["pagina"] is not None


def test_todas_las_secciones_de_origen_aparecen_en_algun_trozo(corpus_records, chunk_records):
    section_ids_entrada = {r["section_id"] for r in corpus_records if r["tipo"] == "prosa"}
    section_ids_salida = {sid for c in chunk_records if c["tipo"] == "prosa" for sid in c["section_ids"]}
    assert section_ids_entrada <= section_ids_salida


# --- 3. Punteros de tabla sin tocar --------------------------------------------------


def test_punteros_de_tabla_identicos_a_fase_1(corpus_records, chunk_records):
    punteros_in = {r["section_id"]: r["texto"] for r in corpus_records if r["tipo"] == "puntero_tabla"}
    for c in chunk_records:
        if c["tipo"] == "puntero_tabla":
            assert len(c["section_ids"]) == 1
            assert c["texto"] == punteros_in[c["section_ids"][0]]
