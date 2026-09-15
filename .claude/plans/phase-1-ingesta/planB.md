# Fase 1 — Ingesta

Plan definitivo. Sustituye a `plan.md` y a la implementación anterior, borrada
por completo (código y tests). Nada de lo que decía aquel plan se da por bueno.

---

## Qué queremos

Sacar del US Navy Diving Manual el texto de **10 capítulos** (2, 3, 4, 6, 7, 9,
10, 11, 14, 17), troceado por sección y con metadatos, para que la Fase 2 lo
chunkee. Las tablas **no van al corpus**; se queda una referencia a cada una.

Los apuntes PADI (`data/raw/PADI_course/*.md`) son la otra fuente y **no entran
en este rediseño**: son Markdown, se cargan con un regex sobre `^## ` y nunca han
dado problema.

---

## Herramienta: Docling

Decidido con un bake-off cara a cara sobre el capítulo 9, midiendo recall de
prosa real (910 frases de referencia sacadas del texto crudo del PDF) tolerante a
reformateo:

| | recall de prosa | qué pierde |
|---|---|---|
| **Docling** | **99,9 %** (909/910) | 1 frase |
| PyMuPDF (`find_tables` + bloques) | 99,2 % (903/910) | 7 frases, **una de ellas el contenido de una caja WARNING** |

No decide el 0,7 %, decide **qué** se pierde: PyMuPDF se come un aviso de
seguridad al descartar páginas dominadas por tabla. Con la regla 3 del CLAUDE.md
encima (números de seguridad), eso no es margen aceptable. Se podría afinar el
umbral, pero afinar umbrales es el parcheo de casos límite que reventó la
implementación anterior; Docling acierta sin afinar nada.

**OCR/VLM descartado**: el PDF es nativo, el texto ya está dentro. Un modelo de
visión re-adivinaría desde píxeles algo que se lee perfecto. (Ni siquiera la
Table 9-8 necesita OCR: sus números son texto; lo que falla es reconstruir la
rejilla.)

**PyMuPDF se queda**, pero solo para lo que Docling no da: leer el outline
embebido (paso 1), cortar el subset (paso 2) y leer los captions del texto crudo
(paso 4).

---

## El pipeline

### Paso 1 — Localizar los capítulos

```python
doc = pymupdf.open("data/raw/navy-diving-manual-rev7.pdf")
toc = doc.get_toc()          # [(nivel, título, página), ...]
```

`get_toc()` devuelve **páginas físicas** (`9-1 INTRODUCTION → 431`), no la
numeración impresa `9-1`. (El PDF **no** define page labels; no hacen falta.)

**Un capítulo llega hasta la siguiente división de nivel 3 del outline, sea la
que sea**: otro capítulo, un apéndice o el front matter del volumen siguiente.
Cortar por "el capítulo siguiente" mete los apéndices dentro — el 11 se comía 68
páginas de `APPENDIX 2A-2D` y el 14 doce de front matter del Volumen 4.

| cap | páginas | nº | cap | páginas | nº |
|---|---|---|---|---|---|
| 2 | 121-158 | 38 | 9 | 431-516 | 86 |
| 3 | 159-222 | 64 | 10 | 517-530 | 14 |
| 4 | 223-240 | 18 | 11 | 531-546 | 16 |
| 6 | 305-338 | 34 | 14 | 697-708 | 12 |
| 7 | 339-390 | 52 | 17 | 851-902 | 52 |

**Total: 386 páginas** (no 464).

*Check:* cada página lleva impreso `capítulo-página` en la cabecera, así que la
última página de un capítulo de N páginas dice `cap-N`. Los 10 pasan.

### Paso 2 — Cortar el subset

```python
subset.insert_pdf(doc, from_page=first - 1, to_page=last - 1)
```

Se guarda el mapa `{página_subset: página_original}`: al cortar, la 431 pasa a
ser la 1, y sin el mapa el corpus citaría páginas que no existen.

### Paso 3 — Docling

```python
result = DocumentConverter().convert("subset.pdf")
dl_doc = result.document
```

Devuelve items en orden de lectura: `TableItem` (con rejilla) o `TextItem` (con
un `label`), todos con `prov[0].page_no`. **143 s para las 86 páginas del cap 9**
→ los 10 capítulos, ~10 minutos.

### Paso 4 — Punto de control manual

```python
print(dl_doc.export_to_markdown())
```

Lo lee Adolfo. Es **la vía de feedback de esta fase**: no solo las tablas, también
secciones con metadata mal, pies de página colados, texto sin sentido.

Automatizado, porque es gratis y ruidoso: **restar los captions**. El manual lleva
escritos sus `Table N-M` en el texto, los detecte Docling o no.

```python
perdidas = captions_in_pdf_text(manual, first, last) - captions_in_docling(parsed)
```

Corrido sobre el cap 9 encuentra la única pérdida solo: `{'9-8'}`. Escala a todo
el PDF sin tocar nada.

### Paso 5 — ❌ ELIMINADO

Coser tablas partidas cae con la decisión de sacar las rejillas del corpus. Sin
rejillas no hay nada que coser: los 21 fragmentos de la Table 9-9, los 5
huérfanos sin caption y el problema de la 9-8 desaparecen de golpe.

> Si algún día se reabre: la señal es el `(Continued)` del caption, que lo pone el
> documento. La regla `mismas columnas and not misma_cabecera` **no vale** — el
> agente de tests comparó la fila 0 de las dos mitades de la 9-9 con el dato real
> y **son idénticas, sí repiten cabecera**.

### Paso 6 — Guardar el crudo

```python
dl_doc.save_as_json("data/processed/parsed-capN.json")
```

Todo etiquetado, sin filtrar nada. Es lo que hace reversible la decisión de sacar
las tablas: siguen en disco. Regla del framework: parsea una vez, filtra al leer.

### Paso 7 — Del crudo al corpus ✅

Además del bucle, dos reglas que salieron al implementarlo:

- **Un contenedor cuyo cuerpo son sus hijas no emite registro.** `9-1
  INTRODUCTION` producía un chunk cuyo texto era solo su título — nada que
  recuperar. Se descarta si al quitar el encabezado no queda nada. (Cap 9: de 75
  registros a 73.)
- **`texto` incluye siempre el encabezado.** Así un título mal cortado es un
  título feo, nunca contenido perdido — que es justo el fallo de
  `docs/aprendizajes-parseo-pdf.md`, donde 13 secciones acabaron con el cuerpo
  vacío por fiar el corte al label.
- **Se normaliza el espaciado** del texto justificado (`This  chapter  discusses`)
  y se quitan guiones suaves. **Los dígitos no se tocan** (regla 3 del CLAUDE.md).



**La estructura la decide el texto, nunca el label.** No se cambia ningún label
de Docling ni se le pregunta por la estructura:

```python
SECTION_START = re.compile(r"^(\d+-\d+(?:\.\d+)*)\s")

for item in parsed.iterate_items():
    if isinstance(item, TableItem):
        caption = item.caption_text(parsed) or ""
        if caption.startswith("Figure"):
            continue                       # formularios de dive chart, fuera
        table_pointers.append(caption)     # solo el puntero; la rejilla no va al corpus
        continue
    if match := SECTION_START.match(item.text.strip()):
        close_section()
        open_section(match.group(1))
    else:
        current_section.append(item.text)
```

Tres problemas, ningún caso especial:

- **Secciones sin encabezado** — 56 de 88 en el cap 9, 11 de 13 en el 14. Da
  igual: no se mira el label, y las 88 de 88 **empiezan** el texto de un item.
- **WARNING que abrían sección falsa** — no empiezan por `9-`, caen en el `else`,
  se quedan como prosa de su sección. Que es donde van.
- **Figuras clasificadas como tabla** — su caption empieza por `Figure`.

---

## Decisiones cerradas

### Fórmulas: NO se extraen, con motivo ✅

Docling puede extraerlas (`do_formula_enrichment=True`) y sin eso **se pierden**:
en `2-12.1` el texto queda como *"The formula for expressing Dalton's law is:"*
seguido de nada. Aun así se deja apagado:

- **Coste: ~30x.** El capítulo 2 pasa de 19 segundos a más de 10 minutos. Sobre
  un pipeline que se relanza constantemente, eso es prohibitivo.
- **Ninguna de las 84 preguntas de eval del golden necesita una fórmula.** De las
  186 totales solo 3 rozan el tema, y se responden con procedimientos en palabras
  ("resta de la presión inicial la reserva y el aire de la parada de seguridad").
- **Las fórmulas que sí importan ya están a salvo**: las de los apuntes PADI
  (`F = ½ · ρ · Cd · A · v²`, `q = k·A·(ΔT/x)`) son markdown en texto plano, se
  leen literales y no pasan por ningún modelo.

Se reabre si algún día el eval falla por una fórmula del manual.

### Los apuntes PADI: un documento madre único ✅

Decisión de Adolfo: los 6 `.md` sueltos se fusionan en
`data/raw/apuntes-buceo.md` (127 KB, 90 secciones, 6 temas). Motivo: hace falta
un documento presentable que enseñar a gente, no seis ficheros sueltos.

- Estructura: preámbulo con índice · `#` tema · `##` sección. **El marcador de
  sección no cambia**, así que el loader sigue siendo un regex.
- `section_id` pasa de `Buceo - Fisica#X` a `Física#X`. Comprobado que **el golden
  dataset no referencia section_id** (solo `id`, `pregunta`,
  `respuesta_esperada`, `uso`), así que no rompe el examen.
- **Se descartó convertirlos a PDF.** Habría metido contenido hoy 100% seguro por
  la única parte del pipeline que sabemos que pierde cosas — las fórmulas de los
  apuntes pasarían por el mismo extractor que se comió la ley de Dalton. Y una
  página de un PDF generado por uno mismo no es una cita: `Física#Resistencia al
  avance` dice qué es y dónde está, "página 7" no dice ninguna de las dos.
- Los 6 originales quedan en git (`1d60ad0`).

### Orden de lectura: por geometría, no por el modelo ✅

Docling **no respeta el orden de lectura dentro de una página**. En la 121
entrega `2-2 PHYSICS` y salta a `2-3 MATTER`; el cuerpo de `2-2` llega siete
items después, ya dentro de `2-3.3`. Sus 682 caracteres se perdían.

Entre páginas sí acierta (0 inversiones en 4.211 items), así que basta ordenar
por posición vertical dentro de cada página (`prov[0].bbox.t`, origen
abajo-izquierda). La geometría del PDF es un hecho; el orden que infiere el
modelo, no.

De paso resuelve las cabeceras de página, que aparecían como `section_header`
(`Underwater Physics`): se detectan por **repetición** — mismo texto en 5+
páginas — que es la regla del framework, no por coordenadas mágicas.

### El markdown de revisión se genera DESDE el corpus ✅

Antes se exportaba el crudo de Docling, y eso hizo perder tiempo revisando
tablas, figuras y WARNING como titulares **que el paso 7 ya filtraba**. Ahora
`review/cap-NN.md` y `review/apuntes.md` salen de los registros que de verdad
entran al índice: lo que ahí se vea mal, está mal.

### Estructura de `data/processed` ✅

```
corpus.jsonl · manifiesto.json · review/ · work/
```

`work/` son los intermedios (subsets y crudo de Docling, ~30 MB) y es borrable:
re-parsear cuesta unos 4 minutos.


**Solo capítulos con contenido.** Apéndices y front matter fuera, y salen solos
por la regla del paso 1.

**Granularidad: la unidad es `N-M.K`.** Medido sobre los 10 capítulos:

| | `N-M` | `N-M.K` | `N-M.K.J` | `N-M.K.J.I` |
|---|---|---|---|---|
| total (505) | 93 | 334 | 68 | 10 |

Regla: **unidad = `N-M.K` + los `N-M` que no tienen hijos** → **352 secciones**.

- Las 78 de nivel 3-4 se pliegan en sus 25 padres. **Ninguna queda huérfana.**
- Los **18 `N-M` sin hijos** son unidad propia, y hay que cubrirlos o se pierden
  enteros: `9-2 THEORY OF DECOMPRESSION`, `9-15 DIVE COMPUTER`, `10-10 BREATHING
  GAS PURITY`.
- Los 75 `N-M` con hijos emiten registro solo si traen texto propio.
- Si un apartado queda largo, lo parte la Fase 2. No es trabajo de aquí.

**Tablas fuera del corpus, referencia dentro.** Las rejillas son ruido para el
RAG y un buceador recreativo usa las tablas de PADI, que no están en este PDF. Se
queda el caption como chunk-puntero. Reversible: las rejillas siguen en
`parsed-capN.json`.

**El título sale del cuerpo, nunca del outline.** El outline está desactualizado:
dice `9-15 RECOMPRESSION CHAMBER REQUIREMENTS` y el cuerpo dice `9-15 DIVE
COMPUTER`. Igual en `7-2`, `6-2`, `4-2.2`, `4-4.1`. Los IDs y las páginas sí son
buenos.

---

## Salida

```
data/processed/
  subset-capN.pdf       # paso 2
  page-map-capN.json    # paso 2 — traduce página del subset a página real
  parsed-capN.json      # paso 6 — crudo de Docling, rejillas incluidas
  review-capN.md        # paso 4 — lo que lee Adolfo
  corpus.jsonl          # paso 7 — el contrato de la Fase 2
```

`corpus.jsonl`, un registro por sección:

```
corpus, section_id, titulo, tipo, texto, fichero, capitulo, pagina, pagina_fin
```

**No markdown como contrato**: no tiene dónde colgar página ni capítulo. Sirve
para revisar (paso 4).
**No el JSON de Docling como contrato**: es su esquema interno, atado a la versión
de la librería. La Fase 2 tendría que aprendérselo para nada.

---

## Estado

**La fase corre entera.** `src/divefy/pipeline/p1_ingest.py`, ~330 líneas.
10 capítulos + apuntes en **~3,5 minutos**. **44 tests en verde.**

```
541 registros = 90 apuntes + 411 secciones del manual + 40 punteros de tabla
```

| cap | seg | secciones | tablas | perdidas |
|---|---|---|---|---|
| 2 | 19 | 54 | 15 | 2-8, 2-9, 2-14, 2-17 |
| 3 | 8 | 63 | 2 | — |
| 4 | 4 | 22 | 4 | — |
| 6 | 6 | 18 | 2 | — |
| 7 | 7 | 45 | 1 | — |
| 9 | 137 | 73 | 8 | 9-8 |
| 10 | 4 | 22 | 2 | — |
| 11 | 2 | 34 | 0 | — |
| 14 | 2 | 12 | 0 | — |
| 17 | 7 | 68 | 6 | 17-2, 17-8, 17-9 |

**Cobertura verificada:** de 427 unidades que el manual contiene, 400 llegan al
corpus. Las **27 ausentes son contenedores legítimamente vacíos** (`9-1
INTRODUCTION`, cuyo cuerpo son sus hijas), comprobado midiendo su texto real en
el PDF. **Pérdida de contenido: cero.**

**Tablas: 40 referenciadas, 8 perdidas** de 48 que el manual dice tener. Todas
anotadas en `manifiesto.json` y en la cabecera de su `review/cap-NN.md`. Perder
una rejilla es aceptable; perderla en silencio no.

### Tests

Escritos por un agente ciego (sin ver la implementación), sobre datos reales
recortados del manual.

**47 rápidos + 9 lentos, todos en verde.**

- `tests/unit/test_p1_ingest.py` — el rango de capítulo contra la numeración impresa.
- `tests/unit/test_p1_chapters.py` — pasos 1-2, incluida la regresión del apéndice.
- `tests/unit/test_p1_sections.py` — invariantes de contenido sobre `build_records`.
- `tests/acceptance/test_p1_corpus.py` — 10 invariantes sobre el corpus real.
- `tests/acceptance/test_p1_chain.py` — cadena entera (lento), y la regresión del
  orden de lectura.
- ~~`test_p1_tables.py`~~ borrado (era del paso 5) · ~~`test_p1_pipeline.py`~~
  sustituido por `test_p1_chain.py`.

**Los tests van contra nuestro código, no contra una librería.** Los que había
medían `HierarchicalChunker` de `docling_core`, un chunker que **este pipeline no
llama nunca**: el troceado lo hace `build_records` con un regex sobre el texto.
Podían seguir en verde con `build_records` roto.

**Dos de ellos se verificaron no-vacuos**, que es el listón que pide
`docs/aprendizajes-parseo-pdf.md` (48 tests en verde con el parseo roto):

- El de paginación: desplazando el mapa una página, fallan 58 de 59.
- El del orden de lectura: sustituyendo `ordered_items` por el orden crudo de
  Docling, `2-2` vuelve a perder su cuerpo y el test falla.

---

## Lo que sigue sin medirse

| Pregunta | Estado |
|---|---|
| ¿El comportamiento del cap 9 se repite en los otros 9? | **NO MEDIDO.** Solo se ha corrido el 9. |
| ¿Cuántas tablas pierde Docling en total? | **NO MEDIDO.** En el cap 9, 1 de 9 (la 9-8). |
| ¿Los WARNING de los otros capítulos se comportan igual? | **NO MEDIDO.** |

Se contesta corriendo los 10 capítulos, ~10 minutos.
