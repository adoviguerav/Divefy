"""Pasos 1 y 2 del plan: localizar capítulos en el outline y recortar el subset.

Todo aquí corre sobre el PDF real y sin Docling, así que va en segundos.

`test_p1_ingest.py` ya verifica los rangos contra la numeración impresa en la
cabecera de cada página (el documento verificándose a sí mismo). Estos tests son
la otra mitad: fijan los rangos concretos que decidió el plan y comprueban que el
recorte no pierde ni mueve contenido.
"""

import re

import pymupdf
import pytest

from divefy.pipeline.p1_ingest import (
    CURATED_CHAPTERS,
    PDF,
    build_subset,
    chapter_page_ranges,
)

# Tabla de planB.md, verificada contra la numeración impresa del manual.
EXPECTED_RANGES = {
    2: (121, 158),
    3: (159, 222),
    4: (223, 240),
    6: (305, 338),
    7: (339, 390),
    9: (431, 516),
    10: (517, 530),
    11: (531, 546),
    14: (697, 708),
    17: (851, 902),
}
# El bug corregido: el cap 11 se comía APPENDIX 2A..2D, 68 páginas de más.
FIRST_APPENDIX_2A_PAGE = 547


def normalized(text: str) -> str:
    return " ".join(text.split())


def alnum_text(page) -> str:
    """Solo letras y dígitos: el espaciado de pymupdf no es estable entre copias
    de la misma página, el contenido sí."""
    return "".join(c for c in page.get_text().lower() if c.isalnum())


def test_curated_chapters_are_the_ten_of_the_plan():
    assert CURATED_CHAPTERS == [2, 3, 4, 6, 7, 9, 10, 11, 14, 17]


def test_toc_extrae_rango(manual):
    ranges = chapter_page_ranges(manual)

    curated = {chapter: ranges.get(chapter) for chapter in CURATED_CHAPTERS}
    assert curated == EXPECTED_RANGES


def test_chapter_ranges_do_not_overlap(manual):
    ranges = chapter_page_ranges(manual)

    ordered = sorted(ranges.items(), key=lambda item: item[1][0])
    for (chapter, (first, last)), (next_chapter, (next_first, _)) in zip(
        ordered, ordered[1:]
    ):
        assert first <= last, f"cap {chapter}: rango invertido ({first}, {last})"
        assert last < next_first, (
            f"cap {chapter} llega a la página {last} y el cap {next_chapter} "
            f"empieza en la {next_first}: los rangos se solapan"
        )


def test_chapter_11_stops_before_the_appendices(manual):
    """Regresión del bug documentado: 'hasta donde empieza el siguiente capítulo'
    es la regla equivocada, entre medias hay apéndices."""
    _, last = chapter_page_ranges(manual)[11]

    assert last < FIRST_APPENDIX_2A_PAGE, (
        f"el cap 11 llega a la página {last} y APPENDIX 2A empieza en la "
        f"{FIRST_APPENDIX_2A_PAGE}: se está tragando el apéndice"
    )


def test_chapter_ranges_stay_inside_the_document(manual):
    for chapter, (first, last) in chapter_page_ranges(manual).items():
        assert 1 <= first <= last <= manual.page_count, (
            f"cap {chapter}: rango ({first}, {last}) fuera de 1..{manual.page_count}"
        )


@pytest.mark.parametrize("chapter", CURATED_CHAPTERS)
def test_chapter_starts_on_its_own_title_page(manual, chapter):
    """Invariante de contenido: la primera página del rango es la portadilla del
    capítulo, y lo dice ella misma ('CHAPTER 9 — Air Decompression')."""
    first, _ = chapter_page_ranges(manual)[chapter]

    text = normalized(manual[first - 1].get_text())
    assert re.search(rf"CHAPTER {chapter}\b", text), (
        f"cap {chapter}: la página {first} no se anuncia como CHAPTER {chapter}; "
        f"empieza por {text[:80]!r}"
    )


def test_subset_paginas_correctas(manual, tmp_path):
    chapters = [10, 14]
    expected_pages = sum(
        last - first + 1 for first, last in (EXPECTED_RANGES[c] for c in chapters)
    )

    page_map = build_subset(manual, chapters, tmp_path / "subset.pdf")

    with pymupdf.open(tmp_path / "subset.pdf") as subset:
        assert subset.page_count == expected_pages
        assert len(page_map) == expected_pages
        assert page_map[1] == EXPECTED_RANGES[10][0], (
            "la primera página del subset tiene que ser la primera del primer capítulo"
        )
        first_page = normalized(subset[0].get_text())
        assert re.search(r"CHAPTER 10\b", first_page), (
            f"la primera página del subset no es la portadilla del cap 10: {first_page[:80]!r}"
        )


def test_subset_page_map_is_the_concatenation_of_the_ranges(manual, tmp_path):
    chapters = [10, 14]
    expected = [
        page
        for chapter in chapters
        for page in range(EXPECTED_RANGES[chapter][0], EXPECTED_RANGES[chapter][1] + 1)
    ]

    page_map = build_subset(manual, chapters, tmp_path / "subset.pdf")

    assert [page_map[i] for i in range(1, len(expected) + 1)] == expected


def test_subset_pages_keep_the_text_of_the_page_they_map_to(manual, tmp_path):
    """Invariante de contenido, no de forma: no basta con que el mapa tenga la
    longitud correcta. Cada página del subset tiene que llevar EL TEXTO de la
    página original que dice el mapa — un desplazamiento de uno pasaría cualquier
    comprobación de tamaño y rompería toda cita del corpus."""
    page_map = build_subset(manual, [10, 14], tmp_path / "subset.pdf")

    with pymupdf.open(PDF) as original, pymupdf.open(tmp_path / "subset.pdf") as subset:
        for subset_page, original_page in page_map.items():
            assert alnum_text(subset[subset_page - 1]) == alnum_text(
                original[original_page - 1]
            ), (
                f"la página {subset_page} del subset dice venir de la "
                f"{original_page} del original, pero su texto no coincide"
            )


def test_build_subset_does_not_destroy_the_document_it_receives(manual, tmp_path):
    """`doc.select()` muta el documento in place. Quien llama sigue teniendo la
    referencia: si `build_subset` recorta sobre ella, el manual se queda en 26
    páginas para todo el resto del proceso."""
    pages_before = manual.page_count

    build_subset(manual, [10, 14], tmp_path / "subset.pdf")

    assert manual.page_count == pages_before, (
        "build_subset ha recortado el documento del que se le pidió sacar un subset"
    )
    assert chapter_page_ranges(manual)[17] == EXPECTED_RANGES[17], (
        "tras build_subset el manual ya no tiene su outline original"
    )
