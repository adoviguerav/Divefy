"""Fase 1 — Ingesta: parsers (Docling/pdfplumber), loader de apuntes, tablas a JSON con procedencia."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

SOFT_HYPHEN = "­"
NON_BREAKING_HYPHEN = "‑"
CURLY_SINGLE = {"‘": "'", "’": "'"}
CURLY_DOUBLE = {"“": '"', "”": '"'}

CAPITULOS_CURADOS = {2, 3, 4, 6, 7, 9, 10, 11, 14, 17}

_FILA_TOKEN_RE = re.compile(r"[\d:.\-/]*\d[\d:.\-/]*")
_CONTINUED_SUFFIX_RE = re.compile(r"\s*\(Continued\)\.?\s*$")
_FOOTER_PAGINA_RE = re.compile(r"(\d+)-(\d+)(?!\d)")
_SECTION_ID_RE = re.compile(r"^\d+-\d+(?:\.\d+)*$")
_TABLE_CAPTION_RE = re.compile(r"Table\s+\d+-\d+")
_FIGURE_CAPTION_RE = re.compile(r"^Figure\s+\d+-\d+")
_WARNING_CELL_RE = re.compile(r"((?:WARNING|CAUTION)\b.*?)(?=(?:WARNING|CAUTION)\b|\Z)", re.DOTALL)
# Título/cuerpo pegados en el mismo list_item ("9-3.2 Descent Time. El cuerpo..."):
# solo se corta si delante del punto hay >=3 letras, para no partir abreviaturas
# cortas de la forma "U.S." / "No." / "vs.".
_TITULO_CUERPO_SPLIT_RE = re.compile(r"(?<=[A-Za-z]{3})\.\s+(?=[A-Z])")
_TABLA_HUECO_PAGINAS_MAX = 3


@dataclass(frozen=True)
class Registro:
    """Una sección de prosa o un puntero de tabla. Contrato de corpus.jsonl."""

    corpus: Literal["apuntes", "manual"]
    section_id: str          # apuntes: "fichero#sección" · manual: "9-3.2" · tabla: "table-9-9"
    titulo: str               # título de sección, o caption completo si es puntero
    tipo: Literal["prosa", "puntero_tabla"]
    texto: str                # normalizado, saltos de línea conservados
    fichero: str | None       # stem del .md (solo apuntes)
    capitulo: int | None      # nº de capítulo (solo manual)
    pagina: int | None        # pág PDF inicial (solo manual)
    pagina_fin: int | None    # pág final (punteros multipágina; si no, == pagina)


def normalizar(texto: str) -> str:
    """Limpia basura Unicode y colapsa espacios por línea. Los dígitos jamás se tocan."""
    # Guion suave que parte una palabra a través de un salto de línea: se quita
    # junto con el salto para reunir la palabra.
    texto = re.sub(rf"{SOFT_HYPHEN}[ \t]*\n[ \t]*", "", texto)
    # Guion suave dentro de la misma línea: se quita sin más.
    texto = texto.replace(SOFT_HYPHEN, "")
    texto = texto.replace(NON_BREAKING_HYPHEN, "-")
    for curly, straight in {**CURLY_SINGLE, **CURLY_DOUBLE}.items():
        texto = texto.replace(curly, straight)

    lineas = texto.split("\n")
    lineas = [re.sub(r"[ \t]+", " ", linea) for linea in lineas]
    return "\n".join(lineas)


def es_fila_distintiva(linea: str) -> bool:
    """El juez compartido ingesta/tests: ¿esta línea tiene pinta de fila de tabla colada?"""
    tokens = linea.split()
    if not tokens:
        return False
    numericos = sum(1 for t in tokens if _FILA_TOKEN_RE.fullmatch(t))
    return numericos >= 4 and numericos > len(tokens) / 2


def plegar_caption(caption: str) -> str:
    """"Table 9-9 Air Decompression Table (Continued)." -> "Table 9-9 Air Decompression
    Table". Pliega continuaciones en su tabla madre sin perder la descripción real."""
    caption = caption.strip()
    return _CONTINUED_SUFFIX_RE.sub("", caption).strip()


def cargar_apuntes(directorio: Path) -> list[Registro]:
    """Una sección de prosa por bloque `##` de cada fichero de apuntes, en orden. `###` no corta."""
    registros = []
    for fichero in sorted(directorio.glob("*.md")):
        texto = fichero.read_text(encoding="utf-8")
        secciones = list(re.finditer(r"^## (.+)$", texto, flags=re.MULTILINE))
        ids_vistos: set[str] = set()
        for i, match in enumerate(secciones):
            inicio = match.end()
            fin = secciones[i + 1].start() if i + 1 < len(secciones) else len(texto)
            titulo = normalizar(match.group(1).strip())
            cuerpo = normalizar(texto[inicio:fin].strip())
            section_id = f"{fichero.stem}#{titulo}"
            if section_id in ids_vistos:
                raise ValueError(f"section_id duplicado en {fichero.name}: {section_id!r}")
            ids_vistos.add(section_id)
            registros.append(
                Registro(
                    corpus="apuntes",
                    section_id=section_id,
                    titulo=titulo,
                    tipo="prosa",
                    texto=cuerpo,
                    fichero=fichero.stem,
                    capitulo=None,
                    pagina=None,
                    pagina_fin=None,
                )
            )
    return registros


def _mapa_paginas_por_capitulo(pdf: Path) -> dict[int, list[int]]:
    """Escanea el PDF entero con pdfplumber (rápido, sin modelo) y deriva del pie de
    página real qué páginas PDF (1-indexed) pertenecen a cada capítulo. No se fía de
    listas hardcodeadas: el pie manda."""
    import pdfplumber

    mapa: dict[int, list[int]] = {}
    with pdfplumber.open(pdf) as doc:
        for i, page in enumerate(doc.pages):
            texto = page.extract_text() or ""
            lineas = texto.splitlines()
            if not lineas:
                continue
            matches = list(_FOOTER_PAGINA_RE.finditer(lineas[-1]))
            if not matches:
                continue
            capitulo = int(matches[-1].group(1))
            mapa.setdefault(capitulo, []).append(i + 1)
    return mapa


def _rango_contiguo_mas_largo(paginas: list[int], tolerancia_hueco: int = 10) -> tuple[int, int]:
    """El rango real de un capítulo es su tramo contiguo más largo, no min/max bruto:
    una página aislada y lejana con el pie mal leído (ej. un apéndice con dos pies
    superpuestos) no debe disparar el rango completo hasta esa página suelta."""
    paginas = sorted(paginas)
    tramos = [[paginas[0]]]
    for p in paginas[1:]:
        if p - tramos[-1][-1] <= tolerancia_hueco:
            tramos[-1].append(p)
        else:
            tramos.append([p])
    mas_largo = max(tramos, key=len)
    return min(mas_largo), max(mas_largo)


def _buscar_caption_vecino(items: list, idx: int, patron: re.Pattern, radio: int = 8) -> str | None:
    """Gotcha de Docling: si TableItem.caption_text() viene vacío, busca en los
    TextItem vecinos en orden de lectura (puede haber una Picture de por medio) un
    patrón de caption ("Table X-Y." / "Figure X-Y."), el más cercano primero."""
    from docling_core.types.doc import TableItem, TextItem

    for distancia in range(1, radio + 1):
        for paso in (distancia, -distancia):
            j = idx + paso
            if 0 <= j < len(items):
                vecino, _nivel = items[j]
                if isinstance(vecino, TextItem) and not isinstance(vecino, TableItem):
                    match = patron.search(vecino.text)
                    if match:
                        return match.group(0)
    return None


def _chars_pdfplumber_rango(pdf: Path, rango: tuple[int, int]) -> int:
    """Cuenta de caracteres de entrada por una vía TOTALMENTE independiente de
    Docling (pdfplumber, sin modelo): la referencia real contra la que C2 valida
    chars_entrada. No tiene por qué coincidir exacto — pipelines de extracción
    distintos tratan cabeceras/pies/espacios distinto — pero sí quedarse cerca."""
    import pdfplumber

    total = 0
    with pdfplumber.open(pdf) as doc:
        for i in range(rango[0] - 1, rango[1]):
            total += len(doc.pages[i].extract_text() or "")
    return total


def _table_section_id(caption_plegado: str) -> str | None:
    match = re.match(r"Table\s+(\d+)-(\d+)", caption_plegado)
    if not match:
        return None
    return f"table-{match.group(1)}-{match.group(2)}"


def _parsear_capitulo(pdf: Path, capitulo: int, rango: tuple[int, int], converter) -> tuple[list[Registro], dict]:
    from docling_core.types.doc import ContentLayer, DocItemLabel, TableItem, TextItem

    result = converter.convert(pdf, page_range=rango)
    doc = result.document
    items = list(doc.iterate_items(included_content_layers=set(ContentLayer)))

    registros: list[Registro] = []
    chars_prosa = chars_tablas = chars_descartados = 0
    secciones_detectadas = 0

    seccion_actual_id: str | None = None
    seccion_actual_titulo = ""
    seccion_actual_texto: list[str] = []
    seccion_actual_pagina: int | None = None

    tablas_por_id: dict[str, dict] = {}  # section_id -> {titulo, pagina, pagina_fin, texto}
    ultima_tabla_id: str | None = None

    def _cerrar_seccion() -> None:
        if seccion_actual_id is None:
            return
        cuerpo = normalizar("\n".join(seccion_actual_texto).strip())
        registros.append(
            Registro(
                corpus="manual",
                section_id=seccion_actual_id,
                titulo=normalizar(seccion_actual_titulo),
                tipo="prosa",
                texto=cuerpo,
                fichero=None,
                capitulo=capitulo,
                pagina=seccion_actual_pagina,
                pagina_fin=None,
            )
        )

    for idx, (item, _nivel) in enumerate(items):
        if isinstance(item, TableItem):
            pagina = item.prov[0].page_no
            caption = item.caption_text(doc)
            if not caption:
                caption = _buscar_caption_vecino(items, idx, _TABLE_CAPTION_RE) or ""
                if not caption:
                    caption = _buscar_caption_vecino(items, idx, _FIGURE_CAPTION_RE) or ""
            # C3: caracteres de origen (celdas crudas), no del markdown renderizado
            # (que añade "|" y relleno de columnas y no guarda relación con el PDF).
            chars_item = len(caption) + sum(len(c.text) for c in item.data.table_cells)

            if _FIGURE_CAPTION_RE.match(caption):
                # figura/gráfico, no tabla de datos: fuera de alcance. Pero a veces
                # arrastra una o más cajas WARNING/CAUTION como fila de la rejilla (ej.
                # Figure 7-3) — esas sí se salvan como prosa de la sección abierta, el
                # resto se tira.
                markdown = item.export_to_markdown(doc)
                fragmentos = []
                for match_aviso in _WARNING_CELL_RE.finditer(markdown):
                    fragmento = re.sub(r"\s*\|\s*", " ", match_aviso.group(1)).strip()
                    fragmento = re.sub(r"\s+", " ", fragmento)
                    if fragmento:
                        fragmentos.append(fragmento)
                if fragmentos and seccion_actual_id is not None:
                    texto_avisos = "\n".join(fragmentos)
                    seccion_actual_texto.append(texto_avisos)
                    chars_prosa += len(texto_avisos)
                    chars_descartados += max(0, chars_item - len(texto_avisos))
                else:
                    chars_descartados += chars_item
                continue

            if not caption:
                ultima_tabla = tablas_por_id.get(ultima_tabla_id) if ultima_tabla_id else None
                if ultima_tabla is None or pagina - ultima_tabla["pagina_fin"] > _TABLA_HUECO_PAGINAS_MAX:
                    # fragmento huérfano: sin tabla previa a la que unirse, o demasiado
                    # lejos en páginas de la última tabla vista (probable tabla distinta
                    # que también perdió su caption) — se descarta en vez de fundirlo
                    chars_descartados += chars_item
                    continue
                section_id = ultima_tabla_id
            else:
                section_id = _table_section_id(plegar_caption(caption))
                if section_id is None:
                    # caption presente pero no tiene forma "Table N-M": no es una tabla
                    # de datos numerada (fuera de alcance), se descarta
                    chars_descartados += chars_item
                    continue

            chars_tablas += chars_item
            ultima_tabla_id = section_id
            if section_id in tablas_por_id:
                t = tablas_por_id[section_id]
                t["pagina"] = min(t["pagina"], pagina)
                t["pagina_fin"] = max(t["pagina_fin"], pagina)
            else:
                tablas_por_id[section_id] = {
                    "titulo": plegar_caption(caption) if caption else section_id,
                    "pagina": pagina,
                    "pagina_fin": pagina,
                }
            continue

        if not isinstance(item, TextItem):
            continue  # PictureItem u otros: imágenes ignoradas

        label = item.label
        texto_item = item.text

        if label in (DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER):
            chars_descartados += len(texto_item)
            continue

        if label == DocItemLabel.TITLE:
            chars_descartados += len(texto_item)
            continue

        if label == DocItemLabel.CAPTION and _TABLE_CAPTION_RE.match(texto_item.strip()):
            # Caption de tabla real sin TableItem asociado (Docling no siempre detecta
            # la estructura de la tabla): se registra igual como puntero, con la propia
            # página de la caption como rango mínimo.
            pagina = item.prov[0].page_no
            caption_plegado = plegar_caption(texto_item.strip())
            section_id = _table_section_id(caption_plegado)
            chars_tablas += len(texto_item)
            ultima_tabla_id = section_id
            if section_id in tablas_por_id:
                t = tablas_por_id[section_id]
                t["pagina"] = min(t["pagina"], pagina)
                t["pagina_fin"] = max(t["pagina_fin"], pagina)
            else:
                tablas_por_id[section_id] = {
                    "titulo": caption_plegado,
                    "pagina": pagina,
                    "pagina_fin": pagina,
                }
            continue

        # C1: el chequeo de id se aplica a CUALQUIER TextItem que llegue hasta aquí,
        # no solo a los que Docling etiquetó section_header/list_item — Docling
        # también etiqueta encabezados reales como "text" plano, y antes se fundían
        # en silencio en la sección anterior.
        texto_normalizado = texto_item.strip()
        primera_palabra = texto_normalizado.split(" ", 1)[0] if texto_normalizado else ""
        if _SECTION_ID_RE.match(primera_palabra):
            # Docling representa subsecciones (9-3.1, 9-3.2...) como list_item, con
            # id+título+cuerpo en el mismo texto; las secciones de tope (section_header,
            # o "text" cuando Docling falla al etiquetar) traen solo el título, el
            # cuerpo llega después en items propios.
            _cerrar_seccion()
            secciones_detectadas += 1
            seccion_actual_id = primera_palabra
            seccion_actual_pagina = item.prov[0].page_no
            resto = texto_normalizado[len(primera_palabra):].strip()
            # El split título/cuerpo no depende del label: Docling no es consistente
            # sobre qué labels traen el cuerpo pegado al título en el mismo texto (no
            # es solo list_item) — si hay un punto de frase real, se corta ahí siempre;
            # si no lo hay (título de tope sin cuerpo propio, ej. "MANNING
            # REQUIREMENTS"), el split no encuentra nada y todo el resto es el título.
            partes = _TITULO_CUERPO_SPLIT_RE.split(resto, maxsplit=1)
            seccion_actual_titulo = partes[0].strip() or primera_palabra
            seccion_actual_texto = [partes[1]] if len(partes) > 1 else []
            chars_prosa += len(texto_item)
        elif label == DocItemLabel.SECTION_HEADER and len(texto_normalizado.split()) <= 4:
            # encabezado fantasma (fuga de pie/cabecera, ej. título de capítulo repetido:
            # corto, sin id). Una caja WARNING real que Docling estiliza como
            # section_header es mucho más larga y cae en la rama de abajo.
            chars_descartados += len(texto_item)
        elif seccion_actual_id is None:
            chars_descartados += len(texto_item)  # preámbulo antes de la primera sección real
        else:
            # bullet/texto sin id propio, caja destacada (WARNING/CAUTION), o caption
            # de figura: prosa de la sección abierta
            seccion_actual_texto.append(texto_item)
            chars_prosa += len(texto_item)

    _cerrar_seccion()

    for section_id, t in tablas_por_id.items():
        texto = f"{t['titulo']} (capítulo {capitulo}, páginas {t['pagina']}-{t['pagina_fin']})."
        registros.append(
            Registro(
                corpus="manual",
                section_id=section_id,
                titulo=t["titulo"],
                tipo="puntero_tabla",
                texto=texto,
                fichero=None,
                capitulo=capitulo,
                pagina=t["pagina"],
                pagina_fin=t["pagina_fin"],
            )
        )

    chars_entrada = chars_prosa + chars_tablas + chars_descartados
    manifiesto_capitulo = {
        "chars_prosa": chars_prosa,
        "chars_tablas": chars_tablas,
        "chars_descartados": chars_descartados,
        "chars_entrada": chars_entrada,
        "secciones_detectadas": secciones_detectadas,
        "secciones_emitidas": secciones_detectadas,
        "descartes_altos": chars_entrada > 0 and (chars_descartados / chars_entrada) > 0.05,
    }
    return registros, manifiesto_capitulo


def parsear_manual(pdf: Path, solo_capitulos: set[int] | None = None) -> tuple[list[Registro], dict]:
    """Parsea los capítulos pedidos (o todos los curados) con Docling. Los rangos de
    página salen del pie de página real, no de una lista fija."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    capitulos = solo_capitulos if solo_capitulos is not None else CAPITULOS_CURADOS
    mapa = _mapa_paginas_por_capitulo(pdf)

    opts = PdfPipelineOptions(force_backend_text=True, do_table_structure=True)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})

    registros: list[Registro] = []
    manifiesto: dict = {}
    for capitulo in sorted(capitulos):
        paginas = mapa.get(capitulo)
        if not paginas:
            raise ValueError(
                f"capítulo {capitulo} pedido pero ausente del mapa de páginas "
                "(ningún pie de página del PDF lo reporta)"
            )
        rango = _rango_contiguo_mas_largo(paginas)
        print(f"parseando capítulo {capitulo} (páginas {rango[0]}-{rango[1]})...")
        registros_cap, manifiesto_cap = _parsear_capitulo(pdf, capitulo, rango, converter)
        manifiesto_cap["chars_entrada_pdfplumber"] = _chars_pdfplumber_rango(pdf, rango)
        registros.extend(registros_cap)
        manifiesto[str(capitulo)] = manifiesto_cap

    return registros, manifiesto


def escribir_corpus(registros: list[Registro], manifiesto: dict, processed_dir: Path) -> None:
    """JSONL (contrato) + manifiesto.json + vista de revisión en Markdown, solo para
    los capítulos del manual (los apuntes ya son un .md legible, revisar una copia
    casi idéntica no aporta nada)."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = processed_dir / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as f:
        for r in registros:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")

    (processed_dir / "manifiesto.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    review_dir = processed_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    grupos: dict[str, list[Registro]] = {}
    for r in registros:
        if r.corpus != "manual":
            continue
        clave = f"cap-{r.capitulo:02d}"
        grupos.setdefault(clave, []).append(r)

    for clave, regs in grupos.items():
        lineas = ["<!-- DERIVADO — no consumir -->", ""]
        for r in regs:
            lineas.append(f"## {r.titulo}")
            lineas.append("")
            lineas.append(r.texto)
            lineas.append("")
        (review_dir / f"{clave}.md").write_text("\n".join(lineas), encoding="utf-8")


def main() -> None:
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")

    pdf = raw_dir / "navy-diving-manual-rev7.pdf"
    if not pdf.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf}")

    registros = cargar_apuntes(raw_dir / "PADI_course")
    registros_manual, manifiesto = parsear_manual(pdf)
    registros.extend(registros_manual)
    print(f"listo: {len(registros)} registros ({len(registros_manual)} del manual)")

    escribir_corpus(registros, manifiesto, processed_dir)


if __name__ == "__main__":
    main()
