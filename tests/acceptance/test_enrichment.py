"""Tests de aceptación de la Fase 3 (enriquecimiento): corren contra el artefacto
generado por `python -m divefy.pipeline.p3_enrich` en data/processed/enrich.jsonl, a
partir de data/processed/chunks.jsonl. Hasta que ese artefacto exista, las pruebas
fallan con FileNotFoundError — es el RED esperado."""

import json
from pathlib import Path

import pytest

PROCESSED_DIR = Path("data/processed")
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"
ENRICH_PATH = PROCESSED_DIR / "enrich.jsonl"

TOPE_CONTEXTO = 100


def _leer_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def chunk_records():
    return _leer_jsonl(CHUNKS_PATH)


@pytest.fixture(scope="module")
def enrich_records():
    return _leer_jsonl(ENRICH_PATH)


@pytest.fixture(scope="module")
def contar_tokens():
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
    return lambda texto: len(tokenizer.tokenize(texto))


# --- 1. Todo chunk de prosa tiene contexto no vacío y bajo el tope de 100 tokens --


def test_todo_chunk_prosa_tiene_contexto_no_vacio_bajo_el_tope(
    chunk_records, enrich_records, contar_tokens
):
    prosa_ids = {c["id"] for c in chunk_records if c["tipo"] == "prosa"}
    contexto_por_id = {r["id"]: r["contexto"] for r in enrich_records}

    assert prosa_ids
    for chunk_id in prosa_ids:
        assert chunk_id in contexto_por_id, chunk_id
        texto = contexto_por_id[chunk_id]
        assert texto.strip(), chunk_id
        assert contar_tokens(texto) <= TOPE_CONTEXTO, (chunk_id, contar_tokens(texto))


# --- 2. Ningún puntero_tabla aparece en enrich.jsonl ------------------------------


def test_ningun_puntero_tabla_en_enrich(chunk_records, enrich_records):
    puntero_ids = {c["id"] for c in chunk_records if c["tipo"] == "puntero_tabla"}
    ids_en_enrich = {r["id"] for r in enrich_records}

    assert puntero_ids
    assert not (puntero_ids & ids_en_enrich)


# --- 3. Todo chunk de prosa tiene entre 3 y 5 preguntas no vacías y distintas -----


def test_todo_chunk_prosa_tiene_de_3_a_5_preguntas_distintas(chunk_records, enrich_records):
    prosa_ids = {c["id"] for c in chunk_records if c["tipo"] == "prosa"}
    preguntas_por_id = {r["id"]: r["preguntas"] for r in enrich_records}

    assert prosa_ids
    for chunk_id in prosa_ids:
        assert chunk_id in preguntas_por_id, chunk_id
        preguntas = preguntas_por_id[chunk_id]
        assert 3 <= len(preguntas) <= 5, (chunk_id, len(preguntas))
        for pregunta in preguntas:
            assert pregunta.strip(), chunk_id
        assert len(set(preguntas)) == len(preguntas), chunk_id


# --- 4. Todo id referenciado en enrich.jsonl existe en chunks.jsonl --------------


def test_todo_id_referenciado_existe_en_chunks(chunk_records, enrich_records):
    ids_validos = {c["id"] for c in chunk_records}

    for r in enrich_records:
        assert r["id"] in ids_validos, r["id"]


# --- 5. Determinismo con caché: re-ejecutar no repite llamadas ni cambia el fichero


def test_enriquecer_es_determinista_con_cache(tmp_path, monkeypatch):
    from divefy.pipeline import p3_enrich

    filas = [
        {
            "id": 0,
            "corpus": "apuntes",
            "section_ids": ["Física#Densidad y compresibilidad del agua frente al aire"],
            "titulo": "Densidad y compresibilidad del agua frente al aire",
            "tipo": "prosa",
            "texto": "**Densidad**: el agua es unas 800 veces más densa que el aire.",
            "fichero": "Física",
            "capitulo": None,
            "pagina": None,
            "pagina_fin": None,
        },
        {
            "id": 187,
            "corpus": "manual",
            "section_ids": ["2-1.1", "2-1.2"],
            "titulo": "Purpose",
            "tipo": "prosa",
            "texto": "2-1.1 Purpose. This chapter describes the laws of physics as they affect humans in the water.",
            "fichero": None,
            "capitulo": 2,
            "pagina": 121,
            "pagina_fin": None,
        },
        {
            "id": 250,
            "corpus": "manual",
            "section_ids": ["table-2-1"],
            "titulo": "Pressure Chart.",
            "tipo": "puntero_tabla",
            "texto": "Table 2-1. Pressure Chart.",
            "fichero": None,
            "capitulo": 2,
            "pagina": 133,
            "pagina_fin": 133,
        },
    ]

    chunks_path = tmp_path / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    llamadas_contexto = []
    llamadas_hype = []

    def fake_generar_contexto(documento, chunk_texto, cliente):
        llamadas_contexto.append(chunk_texto)
        return "contexto fijo de prueba"

    def fake_generar_preguntas_hype(chunk_contextualizado, cliente):
        llamadas_hype.append(chunk_contextualizado)
        return ["¿pregunta uno?", "¿pregunta dos?", "¿pregunta tres?"]

    monkeypatch.setattr(p3_enrich, "generar_contexto", fake_generar_contexto)
    monkeypatch.setattr(p3_enrich, "generar_preguntas_hype", fake_generar_preguntas_hype)

    p3_enrich.enriquecer(chunks_path, tmp_path)

    enrich_path = tmp_path / "enrich.jsonl"

    # Solo los 2 chunks de tipo prosa disparan llamadas; el puntero_tabla se salta.
    assert (len(llamadas_contexto), len(llamadas_hype)) == (2, 2)

    bytes_primera = enrich_path.read_bytes()

    p3_enrich.enriquecer(chunks_path, tmp_path)

    assert (len(llamadas_contexto), len(llamadas_hype)) == (2, 2)
    assert enrich_path.read_bytes() == bytes_primera
