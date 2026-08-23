"""Invariantes sobre el corpus realmente generado (`data/processed/corpus.jsonl`).

No comprueba que el parser no se caiga: comprueba que lo que salió tiene sentido.
Es la lección de `docs/aprendizajes-parseo-pdf.md`, donde 48 tests pasaron en
verde con el parseo roto porque solo miraban la forma ("¿existe el campo?") y no
el contenido ("¿ese campo dice algo?").

Se salta entero si no se ha corrido la ingesta:
    uv run python -m divefy.pipeline.p1_ingest
"""

import json
import re

import pytest

from divefy.pipeline.p1_ingest import CURATED_CHAPTERS, PROCESSED, chapter_page_ranges

CORPUS = PROCESSED / "corpus.jsonl"
MANIFEST = PROCESSED / "manifiesto.json"


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    if not CORPUS.exists():
        pytest.skip(f"falta {CORPUS}. La genera: uv run python -m divefy.pipeline.p1_ingest")
    return [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture(scope="module")
def prose(corpus) -> list[dict]:
    return [record for record in corpus if record["tipo"] == "prosa"]


def test_every_record_carries_a_section_id(corpus):
    """`section_id` es el metadato del que depende el recall@k de la Fase 5."""
    missing = [r for r in corpus if not r["section_id"].strip()]
    assert not missing, f"{len(missing)} registros sin section_id"


def test_section_ids_are_unique(corpus):
    ids = [r["section_id"] for r in corpus]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"section_id repetidos: {sorted(duplicates)[:10]}"


def test_no_record_is_empty(corpus):
    empty = [r["section_id"] for r in corpus if not r["texto"].strip()]
    assert not empty, f"registros con texto vacío: {empty[:10]}"


def test_no_record_is_only_a_heading(prose):
    """El fallo concreto que hay que vigilar: una sección cuyo texto es su propio
    título y nada más. No es un chunk, es un chunk vacío con nombre."""
    barren = [
        r["section_id"]
        for r in prose
        if r["texto"].strip() == f"{r['section_id']} {r['titulo']}".strip()
    ]
    assert not barren, f"secciones que son solo su encabezado: {barren[:10]}"


def test_manual_sections_fold_to_the_agreed_granularity(prose):
    """La unidad es `N-M.K`: ningún sub-sub-apartado (`9-8.2.1`) es sección propia."""
    too_deep = [
        r["section_id"]
        for r in prose
        if r["corpus"] == "manual" and r["section_id"].count(".") > 1
    ]
    assert not too_deep, f"sub-sub-apartados sin plegar: {too_deep[:10]}"


def test_manual_pages_fall_inside_their_chapter(prose, request):
    """La red del remapeo del subset: una página fuera del rango de su capítulo
    significa que el mapa {página_subset: página_original} está desplazado."""
    import pymupdf

    from divefy.pipeline.p1_ingest import PDF

    if not PDF.exists():
        pytest.skip(f"falta el manual real en {PDF}")
    with pymupdf.open(PDF) as doc:
        ranges = chapter_page_ranges(doc)

    wrong = [
        (r["section_id"], r["pagina"], ranges[r["capitulo"]])
        for r in prose
        if r["corpus"] == "manual"
        and not (ranges[r["capitulo"]][0] <= r["pagina"] <= ranges[r["capitulo"]][1])
    ]
    assert not wrong, f"páginas fuera del rango de su capítulo: {wrong[:5]}"


def test_every_curated_chapter_produced_sections(prose):
    by_chapter = {r["capitulo"] for r in prose if r["corpus"] == "manual"}
    assert by_chapter == set(CURATED_CHAPTERS), (
        f"faltan capítulos en el corpus: {sorted(set(CURATED_CHAPTERS) - by_chapter)}"
    )


def test_the_padi_notes_are_in_the_corpus(corpus):
    notes = [r for r in corpus if r["corpus"] == "apuntes"]
    assert len(notes) >= 80, f"solo {len(notes)} secciones de apuntes"
    assert all(r["fichero"] for r in notes), "apuntes sin fichero de origen"


def test_no_table_row_leaked_into_the_prose(prose):
    """Contaminación: una línea que es mayoría de tokens numéricos es una fila de
    rejilla que se ha colado. Las rejillas no van al corpus."""
    token = re.compile(r"[\d:./-]*\d[\d:./-]*")
    offenders = []
    for record in prose:
        for line in record["texto"].split("\n"):
            words = line.split()
            if len(words) < 4:
                continue
            numeric = sum(1 for w in words if token.fullmatch(w))
            if numeric >= 4 and numeric > len(words) / 2:
                offenders.append((record["section_id"], line[:60]))
    assert not offenders, f"{len(offenders)} filas de tabla en la prosa: {offenders[:5]}"


def test_the_manifest_reports_every_lost_table(prose):
    """Una tabla que el manual dice tener y Docling no detectó tiene que quedar
    anotada. Perderla es aceptable; perderla en silencio no."""
    if not MANIFEST.exists():
        pytest.skip(f"falta {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert set(manifest) == {str(c) for c in CURATED_CHAPTERS}
    for chapter, report in manifest.items():
        assert "TABLAS_PERDIDAS" in report, f"cap {chapter} sin informe de tablas perdidas"
        assert report["secciones"] > 0, f"cap {chapter} no produjo ninguna sección"
