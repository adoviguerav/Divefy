"""Integración: la cadena entera sobre páginas reales del manual.

    outline -> rangos -> subset -> Docling -> ordered_items -> build_records

Sustituye a `test_p1_pipeline.py`, que medía los chunks de `HierarchicalChunker`
— un chunker de `docling_core` que **este pipeline no llama nunca**. El troceado
por sección lo hace `build_records` con un regex sobre el texto de los items, así
que aquellos tests podían seguir en verde con `build_records` roto.

Lento (invoca Docling): `uv run pytest tests/ -m slow`. Deja cacheado el parseo
del mini manual en `tests/fixtures/`.
"""

import pymupdf
import pytest
from conftest import MINI_EXPECTED_RANGES, MINI_PARSED, MINI_SOURCE_PAGES, alnum

from divefy.pipeline.p1_ingest import (
    build_records,
    build_subset,
    chapter_page_ranges,
    ordered_items,
    parse,
)

CHAPTERS = sorted(MINI_EXPECTED_RANGES)
SUBSET_PAGES = sum(last - first + 1 for first, last in MINI_EXPECTED_RANGES.values())

# El capítulo se pasa como etiqueta y aquí el subset lleva dos, así que no se
# asserta sobre el campo `capitulo`: la pertenencia real va en el section_id
# (`9-7`, `14-1`), y el etiquetado lo cubre test_p1_corpus.py sobre el corpus real.
LABEL = 0


@pytest.fixture(scope="module")
def chain(mini_manual, tmp_path_factory) -> dict:
    """Corre la cadena una sola vez y cachea el parseo."""
    dest = tmp_path_factory.mktemp("subset") / "subset.pdf"
    with pymupdf.open(mini_manual) as doc:
        ranges = chapter_page_ranges(doc)
        page_map = build_subset(doc, CHAPTERS, dest)

    document = parse(dest)
    MINI_PARSED.parent.mkdir(parents=True, exist_ok=True)
    document.save_as_json(MINI_PARSED)

    return {
        "ranges": ranges,
        "page_map": page_map,
        "subset": dest,
        "document": document,
        "records": build_records(document, page_map, LABEL),
    }


@pytest.mark.slow
def test_ranges_and_subset_on_the_mini_manual(chain):
    ranges = chain["ranges"]

    assert {c: ranges.get(c) for c in MINI_EXPECTED_RANGES} == MINI_EXPECTED_RANGES
    with pymupdf.open(chain["subset"]) as subset:
        assert subset.page_count == SUBSET_PAGES, (
            "el subset debería llevar solo las páginas de los capítulos, "
            "no la del apéndice que cierra el mini manual"
        )
    assert sorted(chain["page_map"]) == list(range(1, SUBSET_PAGES + 1))


@pytest.mark.slow
def test_every_subset_page_survives_our_own_filtering(chain):
    """`ordered_items` reordena y descarta cabeceras corrientes. Si de paso se
    lleva una página entera, se perdió en silencio."""
    seen = {item.prov[0].page_no for item in ordered_items(chain["document"]) if item.prov}

    assert seen == set(chain["page_map"]), (
        f"páginas sin contenido tras filtrar: {set(chain['page_map']) - seen}"
    )


@pytest.mark.slow
def test_records_claim_a_page_that_exists(chain):
    records = chain["records"]
    real_pages = set(chain["page_map"].values())

    assert records, "la cadena no ha producido ni un registro"
    for record in records:
        assert record.pagina is not None, f"registro sin página: {record.section_id}"
        assert record.pagina in real_pages, (
            f"{record.section_id} dice venir de la página {record.pagina}, "
            "que no está en el subset"
        )


@pytest.mark.slow
def test_record_text_really_comes_from_the_page_it_claims(chain, manual):
    """La invariante de contenido de toda la fase: la cadena
    subset -> Docling -> page_map -> manual original tiene que cerrar.

    Se comprueba contra el texto que pymupdf lee de la página original: si el
    mapa se desplaza una página, o Docling numera desde 0, o un item llega sin
    provenance resuelta, el texto deja de estar donde dice estar. Comprobar solo
    que el campo `pagina` existe no lo pillaría.

    Se ancla el ARRANQUE del texto porque una sección puede continuar en la
    página siguiente; `pagina` es donde empieza.
    """
    pages = {
        mini_page: alnum(manual[MINI_SOURCE_PAGES[mini_page - 1] - 1].get_text())
        for mini_page in chain["page_map"].values()
    }

    checked = 0
    for record in chain["records"]:
        if record.tipo != "prosa":
            continue
        start = alnum(record.texto)[:40]
        if len(start) < 20:
            continue
        checked += 1
        assert start in pages[record.pagina], (
            f"{record.section_id} dice empezar en la página {record.pagina} "
            f"del mini manual, pero ahí no está: {record.texto[:60]!r}"
        )
    assert checked >= 5, f"solo {checked} registros comprobados, el test no mira nada"


@pytest.mark.slow
def test_a_section_keeps_the_body_that_follows_its_heading(tmp_path):
    """Regresión del bug del orden de lectura.

    Docling no respeta el orden de lectura DENTRO de una página: en la 121
    entregaba `2-2 PHYSICS` y saltaba a `2-3 MATTER`, y el cuerpo de 2-2 llegaba
    siete items más tarde, ya dentro de `2-3.3`. Sus 682 caracteres se perdían
    sin que nada avisara. `ordered_items` lo arregla ordenando por la geometría
    del PDF, que es un hecho, en vez de por el orden que infiere el modelo.
    """
    from divefy.pipeline.p1_ingest import PDF

    if not PDF.exists():
        pytest.skip(f"falta el manual real en {PDF}")

    first, last = 121, 122  # el inicio del capítulo 2, donde estaba el fallo
    dest = tmp_path / "cap2-inicio.pdf"
    with pymupdf.open(PDF) as manual, pymupdf.open() as subset:
        subset.insert_pdf(manual, from_page=first - 1, to_page=last - 1)
        subset.save(dest)
    page_map = {i + 1: first + i for i in range(last - first + 1)}

    records = {r.section_id: r for r in build_records(parse(dest), page_map, 2)}

    assert "2-2" in records, (
        "la sección 2-2 no llegó al corpus: su cuerpo se ha vuelto a perder por "
        "el orden de lectura de Docling"
    )
    assert "Humans readily function" in records["2-2"].texto, (
        f"2-2 existe pero sin su cuerpo: {records['2-2'].texto[:120]!r}"
    )
