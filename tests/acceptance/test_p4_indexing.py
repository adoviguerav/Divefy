"""Acceptance tests for Fase 4 (indexing): run against the Chroma collections built
by `python -m divefy.pipeline.p4_indexing` under data/chroma/, from the real
data/processed/chunks.jsonl and data/processed/enrich.jsonl artifacts. Collections
span 3 corpus values ("apuntes", "manual", "combined" — the last a sentinel meaning
"every row, no corpus filter") x 3 extras levels x N embedding models. Until the
pipeline module exists and has actually been run, these tests fail with
ModuleNotFoundError / FileNotFoundError / collection-not-found errors — that is the
expected RED right now.

Note: acceptance criterion "manual search returns chunks about ascent" (item 9 in
the phase plan) is a human-inspection step and is intentionally NOT automated here.
"""

import json
from pathlib import Path

import pytest

PROCESSED_DIR = Path("data/processed")
CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"
ENRICH_PATH = PROCESSED_DIR / "enrich.jsonl"

CORPUS_VALUES = ("apuntes", "manual", "combined")  # "combined" = no corpus filter, every row
EXTRAS_LEVELS = ("base", "contextual", "hype")
CAP = 512

# Chunk fields written to metadata only when not None in the source chunk (contract:
# None is omitted, never written as null/sentinel — apuntes rows lack capitulo/pagina/
# pagina_fin, manual rows lack fichero).
OPTIONAL_PROVENANCE_FIELDS = ("fichero", "capitulo", "pagina", "pagina_fin")


def _read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def chunk_records():
    return _read_jsonl(CHUNKS_PATH)


@pytest.fixture(scope="module")
def enrich_records():
    return _read_jsonl(ENRICH_PATH)


@pytest.fixture(scope="module")
def corpus_chunk_records(chunk_records):
    """{corpus_value: [chunk rows for that corpus, tipo=="prosa" only]}, "combined" being
    unfiltered on corpus. puntero_tabla chunks are never indexed in any collection
    (base included) — tables are out of scope for retrieval/generation (EXPERIMENTOS.md)."""
    prosa = [c for c in chunk_records if c["tipo"] == "prosa"]
    return {
        corpus: list(prosa) if corpus == "combined" else [c for c in prosa if c["corpus"] == corpus]
        for corpus in CORPUS_VALUES
    }



@pytest.fixture(scope="module")
def corpus_chunk_ids(corpus_chunk_records):
    return {corpus: {c["id"] for c in records} for corpus, records in corpus_chunk_records.items()}


@pytest.fixture(scope="module")
def corpus_chunks_by_id(corpus_chunk_records):
    return {corpus: {c["id"]: c for c in records} for corpus, records in corpus_chunk_records.items()}


@pytest.fixture(scope="module")
def corpus_enrich_records(enrich_records, corpus_chunk_ids):
    """{corpus_value: [enrich rows whose id belongs to that corpus's chunks]},
    "combined" being unfiltered."""
    return {
        corpus: (
            list(enrich_records)
            if corpus == "combined"
            else [r for r in enrich_records if r["id"] in corpus_chunk_ids[corpus]]
        )
        for corpus in CORPUS_VALUES
    }


@pytest.fixture(scope="module")
def corpus_contexto_by_id(corpus_enrich_records):
    return {
        corpus: {r["id"]: r["contexto"] for r in records}
        for corpus, records in corpus_enrich_records.items()
    }


@pytest.fixture(scope="module")
def models():
    from divefy.pipeline.p4_indexing import MODELS

    return MODELS

@pytest.fixture(scope="module")
def all_collections(models):
    """Builds and queries every corpus x extras x model collection once, reused
    read-only by every test below. Existence is checked against the real persisted
    store first — chromadb.PersistentClient.get_collection() raises if `main()` never
    built it. get_collection() alone can't tell "built" from "never ran": it creates
    an empty collection on miss by default."""
    import chromadb

    from divefy.pipeline.p4_vectorstore import canonical_name, chroma_directory, get_collection

    client = chromadb.PersistentClient(path=str(chroma_directory()))

    collections = {}
    for corpus in CORPUS_VALUES:
        for extras in EXTRAS_LEVELS:
            for model_name, embeddings in models.items():
                name = canonical_name(corpus, CAP, extras, model_name)
                client.get_collection(name)  # raises if this collection was never built
                collection = get_collection(name, embeddings)
                collections[(corpus, extras, model_name)] = collection.get()
    return collections


def test_all_collections_exist_and_are_queryable(all_collections, models):
    expected_count = len(CORPUS_VALUES) * len(EXTRAS_LEVELS) * len(models)
    assert len(all_collections) == expected_count, all_collections.keys()
    for key, result in all_collections.items():
        assert result is not None, key
        assert "ids" in result, key
        assert "documents" in result, key
        assert "metadatas" in result, key


def test_each_base_collection_has_one_row_per_chunk_of_its_corpus(all_collections, corpus_chunk_records):
    for (corpus, extras, model_name), result in all_collections.items():
        if extras != "base":
            continue
        expected = len(corpus_chunk_records[corpus])
        assert len(result["ids"]) == expected, (corpus, model_name)


def test_each_contextual_collection_has_one_row_per_prosa_chunk_of_its_corpus(
    all_collections, corpus_chunk_records
):
    """Invariant 2 (docs/modelo-datos.md): |contextual| == prosa chunk count of the
    corpus, always derived from chunks.jsonl at test time, never hardcoded."""
    for (corpus, extras, model_name), result in all_collections.items():
        if extras != "contextual":
            continue
        expected = len(corpus_chunk_records[corpus])
        assert len(result["ids"]) == expected, (corpus, model_name)


def test_each_hype_collection_has_prosa_chunk_count_plus_dynamically_computed_question_count_rows(
    all_collections, corpus_chunk_records, corpus_enrich_records
):
    """Invariant 2 (docs/modelo-datos.md): |hype| == prosa chunk count + Σ preguntas."""
    for (corpus, extras, model_name), result in all_collections.items():
        if extras != "hype":
            continue
        expected = len(corpus_chunk_records[corpus]) + sum(
            len(r["preguntas"]) for r in corpus_enrich_records[corpus]
        )
        assert len(result["ids"]) == expected, (corpus, model_name, expected)


def test_every_hype_question_row_references_a_real_parent_chunk_id(all_collections, corpus_chunk_ids):
    for (corpus, extras, model_name), result in all_collections.items():
        if extras != "hype":
            continue
        for row_id, metadata in zip(result["ids"], result["metadatas"]):
            if metadata.get("entry_type") != "hype":
                continue
            parent_id = metadata.get("parent_chunk_id")
            assert parent_id in corpus_chunk_ids[corpus], (corpus, model_name, row_id, parent_id)
            assert row_id.startswith(f"{parent_id}::hype::"), (corpus, model_name, row_id, parent_id)


def test_no_row_in_any_collection_uses_a_metadata_key_called_tipo(all_collections):
    for key, result in all_collections.items():
        for metadata in result["metadatas"]:
            assert "tipo" not in metadata, key


def test_every_chunk_row_metadata_matches_the_contract(
    all_collections, corpus_chunks_by_id, corpus_contexto_by_id
):
    """Contract (docs/modelo-datos.md): every chunk row carries entry_type="chunk",
    corpus, section_ids (JSON string decoding to a non-empty list — invariant 3),
    titulo, n_tokens (int), provenance fields only when not None in the source chunk,
    and contexto only in contextual/hype collections."""
    for (corpus, extras, model_name), result in all_collections.items():
        chunk_by_id = corpus_chunks_by_id[corpus]
        contexto_by_id = corpus_contexto_by_id[corpus]
        for row_id, metadata in zip(result["ids"], result["metadatas"]):
            key = (corpus, extras, model_name, row_id)
            assert metadata.get("entry_type") in ("chunk", "hype"), key
            if metadata["entry_type"] != "chunk":
                continue
            chunk = chunk_by_id[row_id]
            assert metadata["corpus"] == chunk["corpus"], key
            section_ids = json.loads(metadata["section_ids"])
            assert isinstance(section_ids, list) and section_ids, key
            assert section_ids == chunk["section_ids"], key
            assert metadata["titulo"] == chunk["titulo"], key
            assert isinstance(metadata["n_tokens"], int), key
            assert metadata["n_tokens"] == chunk["n_tokens"], key
            for field in OPTIONAL_PROVENANCE_FIELDS:
                if chunk[field] is None:
                    assert field not in metadata, (key, field)
                else:
                    assert metadata[field] == chunk[field], (key, field)
            if extras == "base":
                assert "contexto" not in metadata, key
            else:
                assert metadata["contexto"] == contexto_by_id[row_id], key


def test_hype_question_rows_are_self_contained_copies_of_their_parent_chunk_row(
    all_collections, corpus_chunks_by_id, corpus_enrich_records
):
    """D3 (docs/modelo-datos.md): a hype question row's document is the raw text of its
    PARENT chunk (the question is never shown to anyone), and its metadata is the parent
    chunk row's metadata in that same collection (contexto included) plus exactly
    entry_type="hype", parent_chunk_id and pregunta (the question that was embedded)."""
    for (corpus, extras, model_name), result in all_collections.items():
        if extras != "hype":
            continue
        chunk_by_id = corpus_chunks_by_id[corpus]
        preguntas_by_id = {r["id"]: r["preguntas"] for r in corpus_enrich_records[corpus]}
        metadata_by_row_id = dict(zip(result["ids"], result["metadatas"]))
        for row_id, document, metadata in zip(result["ids"], result["documents"], result["metadatas"]):
            if metadata.get("entry_type") != "hype":
                continue
            key = (corpus, model_name, row_id)
            parent_id = metadata["parent_chunk_id"]
            assert document == chunk_by_id[parent_id]["texto"], key
            assert metadata["pregunta"] in preguntas_by_id[parent_id], key
            own_fields = {"entry_type", "parent_chunk_id", "pregunta"}
            inherited = {k: v for k, v in metadata.items() if k not in own_fields}
            parent_metadata = metadata_by_row_id[parent_id]
            expected = {k: v for k, v in parent_metadata.items() if k != "entry_type"}
            assert inherited == expected, key


def test_contextual_and_hype_documents_are_always_the_raw_chunk_text_never_fused_with_contexto(
    all_collections, corpus_chunks_by_id, corpus_contexto_by_id
):
    for (corpus, extras, model_name), result in all_collections.items():
        if extras not in ("contextual", "hype"):
            continue
        chunk_by_id = corpus_chunks_by_id[corpus]
        contexto_by_id = corpus_contexto_by_id[corpus]
        for row_id, document, metadata in zip(result["ids"], result["documents"], result["metadatas"]):
            # hype question rows are self-contained (D3): their document is the raw
            # text of the PARENT chunk, never the question itself
            source_id = metadata.get("parent_chunk_id", row_id)
            expected_text = chunk_by_id[source_id]["texto"]
            assert document == expected_text, (corpus, model_name, extras, row_id)
            contexto = contexto_by_id.get(source_id)
            if contexto is not None:
                fused = contexto + "\n\n" + expected_text
                assert document != fused, (corpus, model_name, extras, row_id)
                assert not document.startswith(contexto), (corpus, model_name, extras, row_id)


# --- Sample data for the pure build_rows/index_model unit-style test below ---
# Real rows from data/processed/chunks.jsonl and data/processed/enrich.jsonl (corpus="apuntes").

SAMPLE_CHUNKS = [
    {
        "id": "Física#Densidad y compresibilidad del agua frente al aire",
        "corpus": "apuntes",
        "section_ids": ["Física#Densidad y compresibilidad del agua frente al aire"],
        "titulo": "Densidad y compresibilidad del agua frente al aire",
        "tipo": "prosa",
        "texto": (
            "**Densidad**: el agua es unas 800 veces más densa que el aire. Por eso la presión sube tan\n"
            "rápido con la profundidad (1 atm cada 10 m) y por eso existe el empuje que te hace flotar.\n\n"
            "**Compresibilidad**: el aire se comprime con facilidad (Ley de Boyle), el agua prácticamente\n"
            "no. Por eso los espacios con aire — BCD, máscara, pulmones — cambian de volumen con la\n"
            "presión, pero la botella (metal rígido, sin aire libre dentro) no se ve afectada."
        ),
        "fichero": "Física",
        "capitulo": None,
        "pagina": None,
        "pagina_fin": None,
        "n_tokens": 118,
    },
    {
        "id": "Física#Resistencia al avance (por qué cuesta el cuádruple de energía al doblar velocidad)",
        "corpus": "apuntes",
        "section_ids": [
            "Física#Resistencia al avance (por qué cuesta el cuádruple de energía al doblar velocidad)"
        ],
        "titulo": "Resistencia al avance (por qué cuesta el cuádruple de energía al doblar velocidad)",
        "tipo": "prosa",
        "texto": "Fuerza de arrastre en un fluido: **F = ½ · ρ · Cd · A · v²**...",
        "fichero": "Física",
        "capitulo": None,
        "pagina": None,
        "pagina_fin": None,
        "n_tokens": 24,
    },
    {
        "id": "Física#Pérdida de calor en el agua",
        "corpus": "apuntes",
        "section_ids": ["Física#Pérdida de calor en el agua"],
        "titulo": "Pérdida de calor en el agua",
        "tipo": "prosa",
        "texto": "Dos propiedades distintas, no una sola:...",
        "fichero": "Física",
        "capitulo": None,
        "pagina": None,
        "pagina_fin": None,
        "n_tokens": 12,
    },
]

SAMPLE_ENRICH = [
    {
        "id": "Física#Densidad y compresibilidad del agua frente al aire",
        "fingerprint": "bfd5b3b0d590a772",
        "contexto": (
            "This chunk introduces fundamental physical properties of water—specifically density "
            "and compressibility—that explain why pressure changes with depth and how it affects "
            "air-filled spaces in scuba diving equipment."
        ),
        "preguntas": [
            "¿Por qué aumenta la presión tan rápido a medida que un buceador desciende en el agua?",
            "¿Cómo afecta la compresibilidad del aire a los diferentes elementos del equipo de buceo?",
            "¿Por qué el volumen del aire dentro de una máscara o los pulmones cambia con la profundidad "
            "mientras que el de una botella de metal no?",
            "¿Qué relación existe entre la densidad del agua y la flotabilidad del buceador?",
        ],
    },
    {
        "id": "Física#Pérdida de calor en el agua",
        "fingerprint": "f1f4b95ab224dfe7",
        "contexto": "Este fragmento explica por qué el cuerpo pierde calor más rápido en el agua que en el aire.",
        "preguntas": [
            "¿Por qué el cuerpo pierde calor más rápido en el agua que en el aire?",
            "¿Qué diferencia existe entre la capacidad calorífica y la conductividad térmica respecto a "
            "la pérdida de calor?",
            "¿Cuál es la razón física por la que el agua sigue enfriando el cuerpo mientras que el aire "
            "deja de hacerlo?",
        ],
    },
        {
        "id": "Física#Resistencia al avance (por qué cuesta el cuádruple de energía al doblar velocidad)",
        "fingerprint": "c2a917f0b3d64e21",
        "contexto": (
            "This chunk explains drag force in fluids and why doubling swimming speed "
            "requires four times the energy, relevant to a diver's air consumption planning."
        ),
        "preguntas": [
            "¿Por qué cuesta el cuádruple de energía nadar al doble de velocidad bajo el agua?",
            "¿Qué papel juega la fórmula de arrastre F = ½·ρ·Cd·A·v² en el consumo de aire?",
            "¿Cómo afecta la resistencia al avance a la planificación de una inmersión?",
        ],
    },
]


class RecordingEmbeddings:
    """Fake Embeddings that records every text it is ever asked to embed."""

    def __init__(self):
        self.embedded_texts = []

    def embed_documents(self, texts):
        self.embedded_texts.extend(texts)
        return [[0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [0.0, 0.0, 0.0]


def test_index_model_never_embeds_the_same_text_twice_for_one_model(tmp_path, monkeypatch):
    from divefy.pipeline import p4_indexing, p4_vectorstore

    monkeypatch.setattr(p4_vectorstore, "chroma_directory", lambda: tmp_path)

    rows = p4_indexing.build_rows(SAMPLE_CHUNKS, SAMPLE_ENRICH, "apuntes")

    fake_embeddings = RecordingEmbeddings()
    p4_indexing.index_model("bgem3", fake_embeddings, rows, corpus="apuntes", cap=CAP)

    assert len(fake_embeddings.embedded_texts) == len(set(fake_embeddings.embedded_texts)), (
        fake_embeddings.embedded_texts
    )




class LengthEmbeddings:
    """Fake Embeddings whose vector encodes the length of whatever text it embedded —
    lets a test tell which text (document vs embed_text) was actually embedded."""

    def embed_documents(self, texts):
        return [[float(len(t)), 0.0, 0.0] for t in texts]

    def embed_query(self, text):
        return [0.0, 0.0, 0.0]


def test_index_model_stores_the_embed_text_vector_not_the_document_vector(tmp_path, monkeypatch):
    """Guards the exact bug Decision #20 exists to prevent: Chroma.add_texts silently
    re-embeds `document` itself and ignores any precomputed vector, so a regression
    back to add_texts would still pass every other test in this file. This one checks
    the stored vector reflects `embed_text`, not the document: contexto fusionado vs
    raw chunk text in contextual rows, the question vs parent chunk text in
    hype question rows (D3)."""
    from divefy.pipeline import p4_indexing, p4_vectorstore

    monkeypatch.setattr(p4_vectorstore, "chroma_directory", lambda: tmp_path)

    rows = p4_indexing.build_rows(SAMPLE_CHUNKS, SAMPLE_ENRICH, "apuntes")
    fake_embeddings = LengthEmbeddings()
    p4_indexing.index_model("bgem3", fake_embeddings, rows, corpus="apuntes", cap=CAP)

    name = p4_vectorstore.canonical_name("apuntes", CAP, "contextual", "bgem3")
    collection = p4_vectorstore.get_collection(name, fake_embeddings)
    contextual_row = rows["contextual"][0]
    stored = collection._collection.get(ids=[contextual_row["id"]], include=["embeddings", "documents"])

    stored_vector_length = stored["embeddings"][0][0]
    document_length = len(stored["documents"][0])
    assert stored_vector_length != document_length
    assert stored_vector_length == len(contextual_row["embed_text"])

    hype_name = p4_vectorstore.canonical_name("apuntes", CAP, "hype", "bgem3")
    hype_collection = p4_vectorstore.get_collection(hype_name, fake_embeddings)
    question_row = next(r for r in rows["hype"] if "::hype::" in r["id"])
    stored_question = hype_collection._collection.get(
        ids=[question_row["id"]], include=["embeddings", "documents"]
    )

    stored_question_vector_length = stored_question["embeddings"][0][0]
    assert stored_question_vector_length == len(question_row["embed_text"])
    assert stored_question_vector_length != len(stored_question["documents"][0])
