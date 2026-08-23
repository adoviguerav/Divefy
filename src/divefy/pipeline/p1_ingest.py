"""Fase 1 — Ingesta del manual Navy y de los apuntes PADI".

Pasos 1-4 y 6 del pipeline (ver .claude/plans/phase-1-ingesta/planB.md):
localizar capítulos → cortar subset → Docling → markdown para revisar → guardar crudo.

Uso:
    uv run python -m divefy.pipeline.p1_ingest 9      # solo el capítulo 9
    uv run python -m divefy.pipeline.p1_ingest        # los 10 curados
"""

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import pymupdf

RAW = Path("data/raw")
PDF = RAW / "navy-diving-manual-rev7.pdf"
NOTES = RAW / "apuntes-buceo.md"   # documento madre del curso PADI
PROCESSED = Path("data/processed")
REVIEW = PROCESSED / "review"   # lo que lee Adolfo, generado DESDE el corpus
WORK = PROCESSED / "work"       # intermedios: subsets y crudo de Docling. Borrable.

CURATED_CHAPTERS = [2, 3, 4, 6, 7, 9, 10, 11, 14, 17]

# El outline marca en nivel 3 todas las divisiones del manual: capítulos,
# apéndices y front matter de cada volumen. El \r se cuela dentro de los títulos
# ("CHAPTER 14\r Breathing Gas..."), por eso se limpia antes de casar.
CHAPTER_ENTRY = re.compile(r"^CHAPTER\s+(\d+)\b")
DIVISION_LEVEL = 3


def chapter_page_ranges(doc: pymupdf.Document) -> dict[int, tuple[int, int]]:
    """Paso 1. Rango de páginas físicas de cada capítulo, según el outline embebido.

    Un capítulo llega hasta la página anterior a la siguiente división del manual,
    sea otro capítulo, un apéndice o el front matter del volumen siguiente. Cortar
    por "el capítulo siguiente" mete los apéndices dentro (el 11 se comía 68
    páginas de APPENDIX 2A-2D).
    """
    divisions = sorted(
        (page, title.replace("\r", " ").replace("\n", " ").strip())
        for level, title, page in doc.get_toc()
        if level == DIVISION_LEVEL
    )

    ranges = {}
    for i, (first, title) in enumerate(divisions):
        match = CHAPTER_ENTRY.match(title)
        if not match:
            continue
        last = divisions[i + 1][0] - 1 if i + 1 < len(divisions) else doc.page_count
        ranges[int(match.group(1))] = (first, last)
    return ranges


def build_subset(doc: pymupdf.Document, chapters: list[int], dest: Path) -> dict[int, int]:
    """Paso 2. PDF con solo esos capítulos, y el mapa que traduce de vuelta.

    Al cortar, las páginas se renumeran. El mapa {página_subset: página_original}
    es lo único que permite que el corpus cite la página real del manual.
    """
    ranges = chapter_page_ranges(doc)
    subset = pymupdf.open()
    page_map: dict[int, int] = {}
    for chapter in sorted(chapters):
        first, last = ranges[chapter]
        subset.insert_pdf(doc, from_page=first - 1, to_page=last - 1)
        for original in range(first, last + 1):
            page_map[len(page_map) + 1] = original
    subset.save(str(dest))
    return page_map


def make_converter():
    """Paso 3. Docling configurado para este documento.

    `do_ocr=False`: el PDF es nativo, el texto ya está dentro. Con OCR activado
    RapidOCR corre sobre cada página para nada y avisa de que no encuentra nada.

    `do_formula_enrichment` queda EN FALSE, con motivo. Sin él las fórmulas del
    manual se pierden ("The formula for expressing Dalton's law is:" seguido de
    nada), pero cuesta ~30x de tiempo (cap 2: 19 s -> más de 10 min) y ninguna de
    las 84 preguntas de eval del golden necesita una fórmula. Las que sí importan
    para un buceador recreativo (arrastre, pérdida de calor) ya están en los
    apuntes PADI en texto plano, sin modelo de por medio.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(do_ocr=False)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def parse(subset_path: Path):
    """Paso 3. Docling sobre un subset, con la configuración de arriba."""
    return make_converter().convert(str(subset_path)).document


# Una cabecera o pie corriente es el mismo texto repetido en muchas páginas. Se
# detecta por repetición, no por coordenadas mágicas.
RUNNING_HEADER_PAGES = 5


def ordered_items(parsed) -> list:
    """Los items en orden de lectura real, sin cabeceras de página.

    Docling NO respeta el orden de lectura dentro de una página: en la 121 entrega
    `2-2 PHYSICS` y salta a `2-3 MATTER`, y el cuerpo de 2-2 llega siete items más
    tarde. Sus 682 caracteres se perdían. La geometría del PDF sí dice la verdad,
    así que se ordena por posición vertical (origen abajo-izquierda: más `top` =
    más arriba en la página). Entre páginas Docling sí acierta — medidas 0
    inversiones en 4.211 items.
    """
    from docling_core.types.doc import TextItem

    placed = [item for item in parsed.iterate_items() if getattr(item[0], "prov", None)]

    seen_on: dict[str, set[int]] = {}
    for item, _level in placed:
        if isinstance(item, TextItem):
            seen_on.setdefault(item.text.strip(), set()).add(item.prov[0].page_no)
    running = {text for text, pages in seen_on.items() if len(pages) >= RUNNING_HEADER_PAGES}

    ordered = sorted(placed, key=lambda pair: (pair[0].prov[0].page_no, -pair[0].prov[0].bbox.t))
    return [
        item
        for item, _level in ordered
        if not (isinstance(item, TextItem) and item.text.strip() in running)
    ]


# El caption va escrito en el texto del PDF, lo detecte Docling o no. Ojo: el
# guion es U+2011 (non-breaking), no el guion normal.
TABLE_CAPTION = re.compile(r"^Table\s+(\d+)[‑-]\s*(\d+)\.", re.M)


def captions_in_pdf_text(doc: pymupdf.Document, first: int, last: int) -> set[str]:
    """Los ids de tabla que el manual dice tener, leídos del texto crudo.

    Es la lista de verdad contra la que se contrasta lo que Docling detecte:
    un caption aquí sin tabla en Docling es una tabla que se ha perdido en
    silencio, que es el fallo que nadie ve si solo miras lo que salió.
    """
    found = set()
    for page in range(first, last + 1):
        text = "\n".join(doc[page - 1].get_text().splitlines()[2:])
        for match in TABLE_CAPTION.finditer(text):
            found.add(f"{match.group(1)}-{match.group(2)}")
    return found


def captions_in_docling(parsed) -> set[str]:
    """Los ids de tabla que Docling sí detectó, de sus propios captions."""
    from docling_core.types.doc import TableItem

    found = set()
    for item, _level in parsed.iterate_items():
        if not isinstance(item, TableItem):
            continue
        match = re.search(r"Table\s+(\d+)[‑-]\s*(\d+)", item.caption_text(parsed) or "")
        if match:
            found.add(f"{match.group(1)}-{match.group(2)}")
    return found


# ---------------------------------------------------------------- paso 7 ---
# Del crudo de Docling al contrato que consume la Fase 2.


@dataclass(frozen=True)
class Record:
    """Una línea de corpus.jsonl. Los nombres del contrato no cambian: el
    recall@k de la Fase 5 depende de `section_id`."""

    corpus: Literal["apuntes", "manual"]
    section_id: str
    titulo: str
    tipo: Literal["prosa", "puntero_tabla"]
    texto: str
    fichero: str | None
    capitulo: int | None
    pagina: int | None
    pagina_fin: int | None


# El id abre sección cuando ENCABEZA el texto de un item. El label de Docling no
# se mira: solo 32 de las 88 secciones del cap 9 llevan `section_header`.
SECTION_START = re.compile(r"^(\d+-\d+(?:\.\d+)*)\s")
# Título = lo que va tras el id hasta el primer punto de frase. Si no lo hay, el
# resto entero es el título (encabezado sin cuerpo propio).
TITLE_SPLIT = re.compile(r"(?<=[A-Za-z]{3})\.\s+(?=[A-Z])")


def clean(text: str) -> str:
    """Colapsa el espaciado del texto justificado y quita guiones suaves. Los
    dígitos no se tocan nunca (regla 3 del CLAUDE.md: números de seguridad)."""
    text = text.replace("­", "")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))


def fold_to_unit(section_id: str) -> str:
    """La unidad es `N-M.K`: los sub-sub-apartados se pliegan en su apartado.

    9-8.2.1 -> 9-8.2 · 9-12.10.1 -> 9-12.10 · 9-8.2 -> 9-8.2 · 9-2 -> 9-2
    """
    parts = section_id.split(".")
    return ".".join(parts[:2])


def split_title(rest: str) -> str:
    """El título de la sección. Nunca decide qué es el cuerpo: `texto` se queda
    con todo igualmente, así que un título mal cortado es un título feo, no
    contenido perdido (el fallo que documenta docs/aprendizajes-parseo-pdf.md)."""
    head = TITLE_SPLIT.split(rest, maxsplit=1)[0].strip()
    return head if head and len(head.split()) <= 15 else rest.strip()[:120]


def build_records(parsed, page_map: dict[int, int], chapter: int) -> list[Record]:
    """Recorre los items en orden y arma un registro por sección, más un
    puntero por tabla. Las rejillas no entran: son ruido para el RAG."""
    from docling_core.types.doc import TableItem, TextItem

    records: list[Record] = []
    tables: dict[str, dict] = {}
    unit = title = None
    body: list[str] = []
    first_page: int | None = None

    def real_page(item) -> int | None:
        return page_map.get(item.prov[0].page_no) if item.prov else None

    def close() -> None:
        if unit is None:
            return
        text = "\n".join(body).strip()
        # Un contenedor cuyo cuerpo son sus hijas (`9-1 INTRODUCTION`) no emite
        # registro: sería un chunk que es solo un título, sin nada que recuperar.
        if not text or not text.replace(f"{unit} {title}", "", 1).strip():
            return
        records.append(
            Record("manual", unit, clean(title or unit), "prosa", clean(text),
                   None, chapter, first_page, None)
        )

    for item in ordered_items(parsed):
        if isinstance(item, TableItem):
            caption = (item.caption_text(parsed) or "").strip()
            match = re.search(r"Table\s+(\d+)[‑-]\s*(\d+)", caption)
            if not match:
                continue  # figura, o fragmento que perdió su caption
            table_id = f"table-{match.group(1)}-{match.group(2)}"
            page = real_page(item)
            seen = tables.setdefault(
                table_id,
                {"titulo": TABLE_CAPTION.sub("", caption).strip() or caption,
                 "pagina": page, "pagina_fin": page},
            )
            if page is not None:
                seen["pagina"] = min(seen["pagina"] or page, page)
                seen["pagina_fin"] = max(seen["pagina_fin"] or page, page)
            continue

        if not isinstance(item, TextItem):
            continue

        text = item.text.strip()
        match = SECTION_START.match(text)
        if not match:
            body.append(text)  # prosa suelta, bullet, o caja WARNING de la sección abierta
            continue

        found = match.group(1)
        target = fold_to_unit(found)
        if target == unit:
            body.append(text)  # sub-sub-apartado: se pliega en la sección abierta
            continue

        close()
        unit = target
        first_page = real_page(item)
        rest = text[len(found):].strip()
        title = split_title(rest) if rest else found
        body = [text]

    close()

    for table_id, seen in tables.items():
        caption = f"{table_id.replace('table-', 'Table ')}. {seen['titulo']}"
        records.append(
            Record("manual", table_id, seen["titulo"], "puntero_tabla", caption,
                   None, chapter, seen["pagina"], seen["pagina_fin"])
        )
    return records


def load_notes(path: Path) -> list[Record]:
    """Los apuntes PADI, del documento madre: `#` es el tema, `##` la sección.

    Markdown, sin modelo de por medio. Es a propósito: las fórmulas de los
    apuntes (`F = ½ · ρ · Cd · A · v²`) se leen literales, mientras que las del
    manual pasan por un extractor que a veces se las come.

    El preámbulo (título e índice, antes del primer `#`) se ignora solo: no hay
    tema abierto todavía.
    """
    text = path.read_text(encoding="utf-8")
    blocks = list(re.finditer(r"^(#{1,2}) (.+)$", text, flags=re.MULTILINE))

    records, topic = [], None
    for i, block in enumerate(blocks):
        level, heading = len(block.group(1)), block.group(2).strip()
        if level == 1:
            topic = heading
            continue
        if topic is None or heading == "Índice":
            continue
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(text)
        records.append(
            Record("apuntes", f"{topic}#{heading}", heading, "prosa",
                   text[block.end():end].strip(), topic, None, None, None)
        )
    return records


PEOR_PAGINA = 3  # cuántas páginas dudosas se listan por capítulo


def confidence_report(result, page_map: dict[int, int]) -> dict:
    """Lo que Docling dice de su propia confianza. Es la señal más barata que
    existe para saber dónde mirar: en vez de leer 386 páginas de markdown, se
    revisan las que el propio parser marca como dudosas.

    Cuatro scores 0-1: `parse` (extracción de texto), `layout` (estructura de la
    página), `table` (rejillas) y `ocr`. Las páginas se traducen a la numeración
    del manual, que es la que Adolfo puede abrir.
    """
    confidence = getattr(result, "confidence", None)
    if confidence is None:
        return {}

    def scores_of(item) -> dict:
        return {
            name: round(value, 3)
            for name in ("parse_score", "layout_score", "table_score", "ocr_score")
            if isinstance(value := getattr(item, name, None), float) and value == value
        }

    by_page = {
        page_map.get(page_no, page_no): scores_of(page_scores)
        for page_no, page_scores in (getattr(confidence, "pages", {}) or {}).items()
    }
    worst = sorted(
        (p for p, s in by_page.items() if s),
        key=lambda p: min(by_page[p].values()),
    )[:PEOR_PAGINA]

    return {
        "capitulo": scores_of(confidence),
        "nota": str(getattr(confidence, "mean_grade", "")),
        "PAGINAS_A_REVISAR": {str(p): by_page[p] for p in worst},
    }


def write_review(records: list[Record], chapter: int, report: dict) -> None:
    """El markdown que revisa Adolfo, generado DESDE el corpus y no desde la
    salida cruda de Docling.

    Es la diferencia entre revisar lo que entra al índice y revisar lo que el
    parser escupió: en el crudo salen tablas, figuras y WARNING como titulares
    que el paso 7 ya filtra, y eso hace perder el tiempo persiguiendo fallos que
    no existen. Lo que aquí se vea mal, está mal de verdad.
    """
    REVIEW.mkdir(parents=True, exist_ok=True)
    prose = [r for r in records if r.tipo == "prosa"]
    tables = [r for r in records if r.tipo == "puntero_tabla"]

    lines = [
        f"# Capítulo {chapter} — lo que entra al corpus",
        "",
        "<!-- DERIVADO de corpus.jsonl. No editar: se regenera con la ingesta. -->",
        "",
        f"- {len(prose)} secciones · {len(tables)} tablas referenciadas",
        f"- páginas {report['paginas'][0]}-{report['paginas'][1]}",
    ]
    if report["TABLAS_PERDIDAS"]:
        lines.append(
            f"- ⚠️ **tablas que el manual dice tener y Docling no detectó: "
            f"{', '.join(report['TABLAS_PERDIDAS'])}**"
        )
    dudosas = list(report.get("confianza", {}).get("PAGINAS_A_REVISAR", {}))
    if dudosas:
        lines.append(f"- páginas que Docling marca como dudosas: {', '.join(dudosas)}")
    lines += ["", "---", ""]

    for record in prose:
        lines += [f"## {record.section_id} · {record.titulo}", "", f"*pág {record.pagina}*", "",
                  record.texto, ""]
    if tables:
        lines += ["---", "", "## Tablas referenciadas (la rejilla no entra al corpus)", ""]
        lines += [f"- `{t.section_id}` pág {t.pagina}-{t.pagina_fin} — {t.titulo}" for t in tables]
    (REVIEW / f"cap-{chapter:02d}.md").write_text("\n".join(lines), encoding="utf-8")


def write_notes_review(records: list[Record]) -> None:
    """Los apuntes también se revisan desde el corpus, igual que el manual. Antes
    su calidad no la miraba nadie porque entran por otro camino."""
    REVIEW.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Apuntes PADI — lo que entra al corpus",
        "",
        "<!-- DERIVADO de corpus.jsonl. No editar: se regenera con la ingesta. -->",
        "",
        f"- {len(records)} secciones",
        "",
        "---",
        "",
    ]
    for record in records:
        lines += [f"## {record.section_id}", "", record.texto, ""]
    (REVIEW / "apuntes.md").write_text("\n".join(lines), encoding="utf-8")


def ingest_chapter(doc, chapter: int, converter) -> tuple[list[Record], dict]:
    """Pasos 2-4, 6 y 7 sobre un capítulo. Devuelve sus registros y su parte del
    manifiesto (incluidas las tablas que el manual dice tener y Docling no vio)."""
    first, last = chapter_page_ranges(doc)[chapter]

    WORK.mkdir(parents=True, exist_ok=True)
    subset_path = WORK / f"subset-cap{chapter}.pdf"
    page_map = build_subset(doc, [chapter], subset_path)

    started = time.time()
    result = converter.convert(str(subset_path))
    parsed = result.document
    elapsed = time.time() - started

    parsed.save_as_json(WORK / f"parsed-cap{chapter}.json")

    records = build_records(parsed, page_map, chapter)
    claimed = captions_in_pdf_text(doc, first, last)
    detected = captions_in_docling(parsed)

    report = {
        "paginas": [first, last],
        "segundos": round(elapsed, 1),
        "secciones": sum(1 for r in records if r.tipo == "prosa"),
        "punteros_tabla": sum(1 for r in records if r.tipo == "puntero_tabla"),
        "tablas_que_dice_el_manual": len(claimed),
        "TABLAS_PERDIDAS": sorted(claimed - detected),
        "confianza": confidence_report(result, page_map),
    }
    write_review(records, chapter, report)
    return records, report


def main() -> None:
    chapters = [int(arg) for arg in sys.argv[1:]] or CURATED_CHAPTERS
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if not PDF.exists():
        raise FileNotFoundError(f"PDF no encontrado: {PDF}")

    converter = make_converter()
    doc = pymupdf.open(PDF)

    records = load_notes(NOTES)
    write_notes_review(records)
    print(f"apuntes PADI: {len(records)} secciones")

    manifest = {}
    for chapter in sorted(chapters):
        chapter_records, report = ingest_chapter(doc, chapter, converter)
        records.extend(chapter_records)
        manifest[str(chapter)] = report
        perdidas = report["TABLAS_PERDIDAS"]
        print(
            f"cap {chapter:2d} | {report['segundos']:6.0f}s | "
            f"{report['secciones']:3d} secciones | {report['punteros_tabla']:2d} tablas | "
            f"PIERDE {len(perdidas)} {perdidas if perdidas else ''}",
            flush=True,
        )

    corpus_path = PROCESSED / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    (PROCESSED / "manifiesto.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n{corpus_path}: {len(records)} registros")


if __name__ == "__main__":
    main()
