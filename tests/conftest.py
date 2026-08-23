"""Fixtures compartidos de la Fase 1 (ingesta).

Nada se fabrica: el "mini manual" que usan los tests de integración son páginas
REALES recortadas del manual con pymupdf, con un outline que imita el del
original. Si falta `data/raw/navy-diving-manual-rev7.pdf`, todo se salta.

El parseo con Docling es lento (~5 s/página en CPU), así que se cachea a disco:
el test lento de `tests/acceptance/test_p1_pipeline.py` escribe la caché y los
tests rápidos de tablas la leen. Sin caché, esos tests se saltan con el comando
que la genera en el mensaje.
"""

from pathlib import Path

import pymupdf
import pytest
from docling_core.types.doc import DoclingDocument

from divefy.pipeline.p1_ingest import PDF, build_records

FIXTURES = Path(__file__).parent / "fixtures"
MINI_MANUAL = FIXTURES / "mini-manual.pdf"
MINI_PARSED = FIXTURES / "mini-manual-subset.docling.json"

# Páginas físicas reales del manual que forman el mini manual (1-based, inclusive).
# Del cap 9 se cogen las 4 páginas de tablas: 9-7 (18 columnas), 9-8 (que Docling
# no detecta), y la 9-9 PARTIDA entre dos páginas con caption "(Continued)".
MINI_CHAPTER_PAGES = {9: (493, 496), 14: (697, 702)}
# Centinela: sin una división de nivel 3 detrás, el último capítulo no tiene final.
MINI_APPENDIX_PAGE = 547
# Página del manual original de la que sale cada página del mini manual (índice 0).
MINI_SOURCE_PAGES = [
    page for first, last in MINI_CHAPTER_PAGES.values() for page in range(first, last + 1)
] + [MINI_APPENDIX_PAGE]
# Rangos que el mini manual debe producir, en páginas del propio mini manual.
MINI_EXPECTED_RANGES = {9: (1, 4), 14: (5, 10)}


def alnum(text: str) -> str:
    """Solo letras y dígitos en minúscula. El PDF usa guion U+2011, tabuladores y
    caracteres de control que Docling normaliza de otra forma; comparar el texto
    en crudo daría falsos negativos que no son un fallo de la ingesta."""
    return "".join(c for c in text.lower() if c.isalnum())


@pytest.fixture
def manual():
    """El manual real, abierto de cero en cada test.

    A propósito no es de sesión: `pymupdf.Document.select()` muta el documento in
    place, así que si `build_subset` lo usara sobre el doc recibido, un doc
    compartido dejaría a los demás tests corriendo sobre un manual destrozado y el
    fallo aparecería lejos de su causa.
    """
    if not PDF.exists():
        pytest.skip(f"falta el manual real en {PDF}")
    with pymupdf.open(PDF) as doc:
        yield doc


@pytest.fixture(scope="session")
def mini_manual() -> Path:
    """PDF pequeño con páginas reales de 2 capítulos + la primera de un apéndice.

    El outline se reconstruye con los títulos literales del manual original (el
    mini manual aplana los volúmenes: el cap 9 es del vol 2 y el 14 del vol 3).
    """
    if MINI_MANUAL.exists():
        return MINI_MANUAL
    if not PDF.exists():
        pytest.skip(f"falta el manual real en {PDF}, no se puede recortar el fixture")

    FIXTURES.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(PDF) as source, pymupdf.open() as mini:
        for first, last in MINI_CHAPTER_PAGES.values():
            mini.insert_pdf(source, from_page=first - 1, to_page=last - 1)
        mini.insert_pdf(
            source, from_page=MINI_APPENDIX_PAGE - 1, to_page=MINI_APPENDIX_PAGE - 1
        )
        mini.set_toc(
            [
                [1, "U.S. Navy Diving Manual", 1],
                [2, "Volume 2 - Air Diving Operations", 1],
                [3, "CHAPTER 9 Air Decompression ", 1],
                [3, "CHAPTER 14\r Breathing Gas Mixing Procedures ", 5],
                [3, "APPENDIX 2A Optional Shallow Water Diving Tables", 11],
            ]
        )
        mini.save(MINI_MANUAL)
    return MINI_MANUAL


@pytest.fixture(scope="session")
def parsed_subset() -> DoclingDocument:
    """El DoclingDocument del subset del mini manual, cacheado en disco."""
    if not MINI_PARSED.exists():
        pytest.skip(
            f"falta la caché del parseo ({MINI_PARSED}). "
            "La genera: uv run pytest tests/ -m slow"
        )
    return DoclingDocument.load_from_json(MINI_PARSED)


@pytest.fixture(scope="session")
def subset_records(parsed_subset) -> list:
    """Las secciones que produce el paso 7, que es quien trocea de verdad.

    El mini manual lleva dos capítulos en un solo subset, así que el capítulo se
    pasa como etiqueta y no se asserta sobre él: la pertenencia real va en el
    `section_id` (`9-7`, `14-1`).
    """
    page_map = {i + 1: page for i, page in enumerate(MINI_SOURCE_PAGES)}
    return build_records(parsed_subset, page_map, 0)
