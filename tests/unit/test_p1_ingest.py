"""El manual verifica solos los rangos de capítulo: cada página lleva impreso
"capítulo-página" en la cabecera, así que la última página de un capítulo de N
páginas tiene que decir "cap-N". Si el rango se pasa de largo (apéndices dentro)
o se queda corto, el número deja de cuadrar.
"""

import re

import pymupdf
import pytest

from divefy.pipeline.p1_ingest import CURATED_CHAPTERS, PDF, chapter_page_ranges


@pytest.fixture(scope="module")
def doc():
    if not PDF.exists():
        pytest.skip(f"falta el PDF en {PDF}")
    return pymupdf.open(PDF)


def printed_page_number(doc, page: int, chapter: int) -> int | None:
    """El "9-86" de la cabecera. Está en las 2 primeras líneas, alternando
    posición entre páginas pares e impares."""
    header = " ".join(doc[page - 1].get_text().splitlines()[:2])
    match = re.search(rf"\b{chapter}-(\d+)\b", header)
    return int(match.group(1)) if match else None


@pytest.mark.parametrize("chapter", CURATED_CHAPTERS)
def test_chapter_range_matches_printed_numbering(doc, chapter):
    first, last = chapter_page_ranges(doc)[chapter]

    # las páginas finales pueden ser "PAGE LEFT BLANK", se retrocede hasta una con número
    for page in range(last, first - 1, -1):
        printed = printed_page_number(doc, page, chapter)
        if printed is not None:
            assert printed == page - first + 1, (
                f"cap {chapter}: la página {page} dice ser la {chapter}-{printed} "
                f"pero el rango {first}-{last} la sitúa como la {page - first + 1}"
            )
            return
    pytest.fail(f"cap {chapter}: ninguna página del rango {first}-{last} lleva número impreso")
