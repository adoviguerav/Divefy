"""Lo que el paso 7 tiene que garantizar por sección.

Rápido: lee la caché del parseo que deja el test lento de integración
(`uv run pytest tests/ -m slow`).

El fichero existe por `docs/aprendizajes-parseo-pdf.md`: 48 tests en verde con el
parseo roto porque solo miraban la forma. Aquí se mira el contenido.

Los tests van contra `build_records`, que es quien trocea. Antes iban contra
`HierarchicalChunker` de `docling_core` — un chunker que este pipeline no llama
nunca, así que podían seguir en verde con `build_records` roto.
"""

import re

import pytest
from conftest import MINI_CHAPTER_PAGES

# El manual imprime los captions con guion U+2011 y el outline mete \r dentro del
# id ("14\r-2.1"). Cualquier regex con "-" a secas no encuentra casi nada.
DASHES = "-‐‑‒–"


def outline_section_ids(manual) -> list[str]:
    """Los ids de sección ('14-2.1') que el outline sitúa en las páginas del
    fixture. Solo el id: los TÍTULOS del índice embebido están desactualizados
    (dice '9-15 RECOMPRESSION CHAMBER REQUIREMENTS', el cuerpo dice '9-15 DIVE
    COMPUTER'), así que contrastar títulos daría falsos fallos."""
    ids = []
    for level, title, page in manual.get_toc():
        if level < 4:
            continue
        if not any(first <= page <= last for first, last in MINI_CHAPTER_PAGES.values()):
            continue
        match = re.match(rf"(\d+)\s*[{DASHES}]\s*([\d.]+)", " ".join(title.split()))
        if match:
            ids.append(f"{match.group(1)}-{match.group(2)}")
    return ids


def test_outline_sections_survive_the_parse(manual, parsed_subset):
    """Ninguna sección se pierde en silencio. La lección de la fase: 37 secciones
    reales se fundieron con la anterior y los tests no se enteraron."""
    ids = outline_section_ids(manual)
    assert len(ids) >= 5, "el fixture debería cubrir varias secciones del cap 14"

    markdown = " ".join(parsed_subset.export_to_markdown().split())

    missing = [
        section_id
        for section_id in ids
        if not re.search(
            rf"\b{section_id.split('-')[0]}\s*[{DASHES}]\s*{re.escape(section_id.split('-')[1])}",
            markdown,
        )
    ]
    assert not missing, f"secciones del outline que no aparecen en el parseo: {missing}"


def test_seccion_tiene_pagina(subset_records):
    """Avisaría si algún día se migra a la API HTTP de Docling y los items llegan
    sin provenance resuelta: la sección existe, pero ya no sabe de dónde salió.

    La página es lo que permite citar la fuente en la respuesta del chat, así que
    una sección sin ella es una sección que no se puede usar."""
    assert subset_records

    for record in subset_records:
        assert record.pagina is not None, f"página nula: {record.section_id}"


def test_no_section_arrives_empty(subset_records):
    empty = [r.section_id for r in subset_records if not r.texto.strip()]

    assert not empty, f"{len(empty)} secciones sin texto, con página y todo: {empty[:5]}"


# Subsecciones del cap 14 dentro del recorte del fixture (págs 697-702). Docling
# solo etiqueta como encabezado `14-1` y `14-2`; estas llegan como `list_item` o
# `text`, así que solo aparecen si build_records mira el texto y no el label.
UNLABELLED_SUBSECTIONS = ["14-1.1", "14-1.2", "14-2.1", "14-2.2", "14-2.3"]


@pytest.mark.parametrize("section_id", UNLABELLED_SUBSECTIONS)
def test_records_cover_the_subsections_docling_never_labelled(subset_records, section_id):
    """Invariante de contenido, no de forma: si `build_records` volviera a fiarse
    del label de Docling en vez del texto, estas desaparecerían. Es el bug que
    documenta docs/aprendizajes-parseo-pdf.md, vigilado."""
    found = {r.section_id for r in subset_records}

    assert section_id in found, f"falta {section_id!r}; hay {sorted(found)}"
