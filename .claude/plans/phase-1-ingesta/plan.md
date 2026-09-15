# Plan: Fase 1 — Ingesta

**Estado**: implemented
**Fuente**: PRD §7 Fase 1 · Destilado del plan v1 (archivado en `plan-v1-original.md`)
el 2026-08-20 — misma evidencia y mismas decisiones, formato workflow v2.

## Objetivo

Al terminar existe `data/processed/corpus.jsonl`: una línea por sección de prosa de los
apuntes PADI y de los 10 capítulos curados del manual Navy, con las tablas fuera de la
prosa (un registro puntero por tabla lógica), texto normalizado, y un manifiesto contable
que demuestra que ningún texto se perdió en silencio. Es el contrato que consume la
Fase 2 (chunking).

## Hallazgos (medidos 2026-08-20 sobre el PDF real y los apuntes)

- El PDF tiene capa de texto embebida (no necesita OCR). 992 págs; cap 9 = págs PDF
  431-516. Rangos de capítulo verificados: cap2 121 · cap3 159 · cap4 223 · cap6 305 ·
  cap7 339 · cap9 431 · cap10 517 · cap11 531 · cap14 697 · cap17 851. NO fiarse de
  listas a ojo: los rangos se derivan del prefijo del pie de página (`9-86` → cap 9).
- Cap 9: ~29% de sus páginas son tabla (25 de 86). Baseline de contaminación con
  extractor naive: **825 filas distintivas de tabla dentro de la "prosa" en los 10 caps**
  (670 solo en el cap 9).
- **Pies de página pares** (`9-2`, `9-4`…) son indistinguibles de section_ids reales por
  regex: una regex ingenua contó 42 secciones fantasma en el cap 9. Hay que descartar
  cabeceras/pies ANTES de segmentar.
- Suciedad Unicode (caps 2+9): 53× guion suave U+00AD partiendo palabras (`chem­ical`),
  77× guion no-separable U+2011 (el caption real es `Table 9‑9`), 100× comillas curvas.
- La Table 9-9 ocupa ~13 páginas y repite caption con "(Continued)" 26 veces. Docling
  emite una tabla multipágina como N items de una página (verificado en su código):
  el plegado por caption NO es opcional.
- Cap 9 tiene ≥100 secciones reales y 4 cajas WARNING en la prosa; el cap 7 tiene una
  caja con la frase "These are the minimum personnel levels allowed".
- Apuntes PADI: 6 ficheros, 89 secciones `##` (7+6+15+5+42+15); solo Física tiene
  `###` (quedan dentro de su `##` padre). Cero tablas.
- Dependencias: Docling arrastra ~103 paquetes (torch incluido, que entra igual en
  Fase 4); pdfplumber, 8.

## Decisiones (ya tomadas con Adolfo — no re-decidir)

- **Normalizar al ingerir** (Q1): U+00AD fuera reuniendo la palabra (también a través de
  `\n`), U+2011→`-`, comillas curvas→rectas, espacios colapsados POR LÍNEA. Los saltos
  de línea se conservan. **Los dígitos no se tocan jamás.** `data/processed/` es la única
  fuente de verdad aguas abajo; deja de ser byte-idéntico al PDF y se acepta.
- **Tabla lógica** (Q2): las continuaciones "(Continued)" se pliegan en su tabla madre;
  el cap 9 tiene 9 tablas lógicas (9-1..9-9), un puntero por tabla con rango de páginas.
- **Salida JSONL + espejo Markdown** (Q3): `corpus.jsonl` es el contrato; el espejo
  `.md` por capítulo/fichero es solo para revisión humana (cabecera "DERIVADO — no
  consumir"), misma pasada, mismos registros.
- **Predicado de contaminación** (Q4, afinado con evidencia): fila distintiva = línea con
  ≥4 tokens numéricos (`[\d:.\-/]+`) que además son más de la mitad de sus tokens. Con
  esa fracción: cero falsos positivos en los 10 caps ("≥4 a secas" daba 44). **El
  predicado es SOLO el juez: la ingesta tiene PROHIBIDO usarlo como filtro** — la
  separación sale de la detección de tablas del parser.
- **Bake-off Docling vs pdfplumber** sobre el cap 9 antes de elegir parser; la decisión
  del ganador es de Adolfo con los datos delante (regla 5). Docling parte favorito
  (PRD), pero pdfplumber gana si separa igual de limpio, por 8 dependencias contra 103.
- El JSON de filas de tablas del bake-off se tira (no es entregable); el diff entre
  parsers corre una vez, no es test permanente (decisiones ya cerradas en PRD).

## Contexto

- `.claude/plans/PRD.md` §7 Fase 1 — decisiones cerradas que este plan implementa.
- `data/raw/PADI_course/Buceo - Fisica.md` — único fichero de apuntes con `###`: el
  loader corta SOLO por `##`; el `###` queda dentro de su sección padre. El texto antes
  del primer `##` (título `#` y preámbulo) se descarta.
- `src/divefy/ingest.py` — stub de una línea; todo se implementa aquí, un solo módulo.
- `tests/test_smoke.py` — estilo de test del proyecto: pytest plano, sin clases.
- Docling (verificado vía Context7): `DocumentConverter().convert(source,
  page_range=(a,b))` para convertir solo el cap 9;
  `PdfPipelineOptions(force_backend_text=True)` usa la capa de texto y esquiva el OCR;
  `do_table_structure=True`; `document.iterate_items()` en orden de lectura,
  discriminando `TextItem`/`SectionHeaderItem`/`TableItem` por `isinstance`; página en
  `item.prov[0].page_no`. Gotcha: si `TableItem.caption_text(doc)` viene vacío, buscar
  el `TextItem` adyacente con patrón `Table X-Y.`.
- Warnings: Docling sobre 465 págs en CPU tarda minutos — la pasada completa es offline
  y se paga una vez; el bake-off usa `page_range`. El golden dataset
  (`docs/Buceo - Golden dataset.jsonl`) ni se lee ni se indexa desde la ingesta.

## Contrato de aceptación

Comandos gate: `uv run pytest tests/acceptance/` (rápida, sobre el artefacto) ·
`uv run pytest tests/` (suite completa, incluye el test lento del parser vivo).
Regenerar el artefacto: `uv run python -m divefy.ingest`.

- [ ] **Apuntes completos** — un registro de prosa por sección `##` de cada fichero de
  apuntes (89 hoy; el conteo por fichero se deriva de los `.md`, no se hardcodea solo),
  cada uno con section_id `fichero#sección` no vacío, título, corpus="apuntes" y texto
  no vacío.
- [ ] **Manual: secciones y metadatos** — prosa de los 10 capítulos curados
  (2,3,4,6,7,9,10,11,14,17); todo registro con section_id jerárquico (tipo `9-3.2`)
  ÚNICO en el corpus, título y página; cero texto de cabeceras/pies dentro de la prosa
  (ni "U.S. Navy Diving Manual" ni líneas "CHAPTER N"); cap 9 con ≥100 registros;
  las cajas de aviso conservadas (≥4 "WARNING" en la prosa del cap 9, y la frase
  "These are the minimum personnel levels allowed" presente en el cap 7); muestra
  verificada: existen 9-1, 9-6.3 y 9-3.2 (este último con título que empieza por
  "Bottom Time").
- [ ] **Tablas lógicas como punteros** — exactamente un registro puntero por tabla
  lógica: el cap 9 tiene 9 (Table 9-1..9-9) con las "(Continued)" plegadas; todo
  puntero con caption, rango de páginas (fin ≥ inicio; la 9-9 abarca ≥10 págs) y texto
  NO vacío que nombre la tabla y su rango; section_ids de puntero únicos en el corpus.
- [ ] **Prosa sin filas de tabla** — cero líneas de la prosa del manual que cumplan el
  predicado de fila distintiva (≥4 tokens numéricos y >50% de los tokens). Baseline
  naive: 825. Ejemplos calibrados del predicado: "50 2:20 AIR 31 34:00 1 N" SÍ es fila;
  ":15 + :30 = :45 = 100/45 N" y "ascent rate is 30 fsw/min" NO lo son. El predicado
  vive en la ingesta como función compartida y el test lo importa: un solo juez.
- [ ] **10 hechos literales en su sección** — tras normalización y colapsando espacios,
  cada hecho aparece en un registro de la sección esperada (lista abajo). Si uno falla,
  la vía es re-verificar la fuente y enmendar el hecho en abierto — jamás "arreglar" la
  ingesta para que encaje.
- [ ] **Texto normalizado** — cero U+00AD, U+2011 y comillas curvas en texto y títulos
  de todos los registros (comprobado sobre los textos parseados, no sobre bytes del
  fichero); "chemical" aparece reunido y "chem ical" no (el guion suave se quita
  reuniendo, no reemplazando por espacio); los números de los 10 hechos matchean dígito
  a dígito.
- [ ] **Conservación contable** — `data/processed/manifiesto.json` por capítulo:
  chars_prosa + chars_tablas + chars_descartados == chars_entrada (esto SÍ falla el
  test si no cuadra); secciones detectadas == emitidas; y el total de secciones del
  manifiesto cuadra con los registros reales del corpus. Sin esto, un parser que trague
  el 30% del texto pasa el resto de criterios en silencio. Descartes (pies/cabeceras)
  por encima del 5% de la entrada NO falla el test ni cambia qué se recoge — el
  manifiesto lo marca con un flag (`descartes_altos: true`) por capítulo, solo para
  revisión manual.
- [ ] **Parser vivo** — un test de integración (marcado `slow`) corre `parsear_manual`
  de verdad sobre el cap 10 (13 págs) y comprueba: hay prosa, cero filas distintivas,
  punteros sin duplicar y contabilidad cuadrada. Sin él, romper el parser queda verde
  sobre un JSONL viejo.

Comprobación manual (no bloqueante, tras la primera pasada): abrir
`data/processed/espejo/cap-09.md` y ver a ojo que la prosa fluye sin filas numéricas,
que la Table 9-9 aparece solo como puntero y que los section_id coinciden con el PDF.

### Los 10 hechos (verificados por grep contra las fuentes, 2026-08-20)

| Hecho (literal, espacios colapsados) | Corpus | Sección |
|---|---|---|
| one atmosphere is equal to 33 feet of sea water | manual | 2-9.1 |
| 14.7 psi divided by 33 feet equals 0.445 psi per foot | manual | 2-9.1 |
| Bottom time is the total elapsed time from the time the diver leaves the surface to the time he leaves the bottom | manual | 9-3.2 |
| 30 fsw/min (20 seconds per 10 fsw) | manual | 9-6.3 |
| ascender despacio (18 m/min o lo que diga el ordenador) | apuntes | Buceo - Fisiologia y salud#Cómo funcionan los ordenadores y tablas de buceo |
| 10 m: 219 min | apuntes | Buceo - Fisiologia y salud#Buceo sin paradas |
| Máximo 18 m/min o lo que marque el ordenador | apuntes | Buceo - Fisiologia y salud#Buceo sin paradas |
| (5 m, 3 min) | apuntes | Buceo - Fisiologia y salud#Buceo sin paradas |
| 4 m más profunda | apuntes | Buceo - Fisiologia y salud#Inmersiones con frío o agotadoras |
| fondeado a 5-6 m | apuntes | Buceo - Entornos y condiciones#Bucear desde un barco |

## Out of scope

- Chunking por tope de tokens (Fase 2) — aquí la unidad es la sección completa.
- JSON de filas de tablas como entregable — solo inspección del bake-off, se tira.
- Tabla de constantes del guardarraíl (Fase 7) — esta fase solo da la prosa limpia.
- Indexado, embeddings, retrieval (Fases 4-5). Determinismo punta a punta (Fase 5).
- Curar los apuntes (erratas, `###` de Física) — son fuente de verdad tal cual.

## Interfaces (contrato con la Fase 2 y entre módulos)

```python
# src/divefy/ingest.py
@dataclass(frozen=True)
class Registro:
    """Una sección de prosa o un puntero de tabla. Contrato de corpus.jsonl."""
    corpus: Literal["apuntes", "manual"]
    section_id: str          # apuntes: "fichero#sección" · manual: "9-3.2" · tabla: "table-9-9"
    titulo: str              # título de sección, o caption completo si es puntero
    tipo: Literal["prosa", "puntero_tabla"]
    texto: str               # normalizado, saltos de línea conservados
    fichero: str | None      # stem del .md (solo apuntes)
    capitulo: int | None     # nº de capítulo (solo manual)
    pagina: int | None       # pág PDF inicial (solo manual)
    pagina_fin: int | None   # pág final (punteros multipágina; si no, == pagina)

def normalizar(texto: str) -> str: ...
def es_fila_distintiva(linea: str) -> bool: ...   # el juez compartido ingesta/tests
def plegar_caption(caption: str) -> str: ...      # "Table 9-9 ... (Continued)." → "Table 9-9"
def cargar_apuntes(directorio: Path) -> list[Registro]: ...
def parsear_manual(pdf: Path, solo_capitulos: set[int] | None = None
                   ) -> tuple[list[Registro], dict]: ...   # registros + manifiesto
def escribir_corpus(registros, manifiesto, processed_dir: Path) -> None: ...
def main() -> None: ...                            # python -m divefy.ingest
```

## Tareas

- **T-01 · ADD dependencias del bake-off** — `uv add docling pdfplumber` (docling
  arrastra torch: primera instalación lenta, es normal).
  VALIDATE: `uv run python -c "import docling, pdfplumber"`.
- **T-02 · CREATE núcleo puro** — `Registro`, `normalizar`, `es_fila_distintiva`,
  `plegar_caption` en `ingest.py`. Funciones puras, dataclass frozen. Sin tocar PDF.
  VALIDATE: `uv run pytest tests/unit -q` (andamiaje del implementador).
- **T-03 · CREATE `cargar_apuntes`** — recorrer `data/raw/PADI_course/*.md` ordenado;
  sección = bloque entre `##` consecutivos; `###` no corta; preámbulo descartado;
  texto normalizado. VALIDATE: `uv run pytest tests/unit -q`.
- **T-04 · CREATE `scripts/bakeoff_fase1.py` + correr el bake-off — ⛔ PUERTA ADOLFO** —
  one-shot: Docling (page_range del cap 9, force_backend_text, do_table_structure) vs
  pdfplumber sobre el cap 9 + la sección 2-9 como prosa de control. Por parser: nº
  tablas lógicas · filas distintivas restantes en prosa (baseline naive 670) · nº
  secciones · tiempo. Volcado a dir de inspección NO versionado. Resultado a
  EXPERIMENTOS.md. **Adolfo elige el parser antes de T-05.**
  VALIDATE: el informe imprime las 4 métricas para ambos.
- **T-05 · CREATE `parsear_manual`** con el ganador — rangos por prefijo de pie de
  página; descartar cabeceras/pies ANTES de segmentar; secciones por encabezado
  jerárquico; tablas fuera y plegadas por caption en punteros; pies de figura en la
  prosa; imágenes ignoradas; manifiesto contable por capítulo.
  VALIDATE: smoke sobre el cap 9 solo.
- **T-06 · CREATE `escribir_corpus` + `main` y correr la ingesta completa** — JSONL
  UTF-8 sin escapar no-ASCII + espejo md con cabecera "DERIVADO — no consumir" +
  `manifiesto.json`. VALIDATE: `uv run python -m divefy.ingest` termina y
  `wc -l data/processed/corpus.jsonl` > 0.
- **T-07 · Suite en verde + retirar el parser perdedor** — `uv remove` del perdedor;
  marcar las tareas de Fase 1 en el PRD (mecánico). VALIDATE: `uv run pytest tests/`.

## Notas

- **Ruta del módulo** (2026-08-23): el plan dice `src/divefy/ingest.py` (líneas 67, 156,
  205), pero el repo ya tiene la reorganización de `src/divefy/` en `pipeline/`
  commiteada (`e639d83`). Adolfo decidió implementar en
  `src/divefy/pipeline/p1_ingest.py` en vez de crear un módulo suelto — el resto de
  interfaces y tareas del plan aplican igual, solo cambia la ruta del fichero.
- **T-04 resuelto** (2026-08-23): gana Docling. Detalle completo y las 4 métricas en
  `EXPERIMENTOS.md` (§Fase 1). Hallazgo nuevo para T-05: Table 9-8 no sale con caption
  propio en la extracción de Docling — cae como fragmento sin caption, hace falta el
  fallback ya previsto en el plan (buscar el `TextItem` adyacente con patrón
  `Table X-Y.`) para plegarla en su tabla lógica correcta.
- **Enmienda al predicado `es_fila_distintiva`** (2026-08-23, Q4): un token que es
  *solo* separadores (`-`, `:`, `.`, `/`, sin ningún dígito) contaba como "token
  numérico" — falso positivo real en cap 6, sección 6-6.4.1: la línea de prosa normal
  "1 - Critical 2 - Serious 3 - Moderate 4 - Minor 5 - Negligible" se marcaba como
  fila de tabla colada (10 de 15 tokens "numéricos" por los guiones sueltos). Arreglo:
  `_FILA_TOKEN_RE` ahora exige al menos un dígito real en el token
  (`[\d:.\-/]*\d[\d:.\-/]*` en vez de `[\d:.\-/]+`). Verificado que los 3 ejemplos
  calibrados del plan (línea 105) no cambian de resultado.
- **Enmienda al test de aceptación** (2026-08-23, Adolfo desbloqueó y corrigió
  directamente): el hallazgo del plan "Cap 9 tiene ≥100 secciones reales" (línea 32)
  era erróneo. Verificado por dos vías independientes: (1) el parser real (Docling)
  encuentra 88 secciones jerárquicas reales en el cap 9, última en `9-15` (página 488);
  el resto del capítulo hasta la página 516 es solo contenido de las tablas 9-1..9-9.
  (2) Una regex ingenua sobre texto plano (misma heurística del bake-off) da 131
  coincidencias, de las cuales 43 son ruido de pie de página (`"N-M U.S. Navy Diving
  Manual — Volume 2"`) — 131−43=88, cuadra exacto con (1). El propio plan ya había
  diagnosticado este modo de fallo dos líneas antes ("una regex ingenua contó 42
  secciones fantasma en el cap 9") pero el "≥100" no aplicó esa corrección. Test
  ajustado de `>= 100` a `>= 85` en `tests/acceptance/test_ingest.py`.
- **Enmienda al test de aceptación (2)** (2026-08-23, Adolfo corrigió directamente):
  `test_manifiesto_secciones_emitidas_coincide_con_corpus` comparaba
  `secciones_emitidas` (que en el manifiesto solo cuenta prosa) contra el total de
  registros manual (prosa + punteros de tabla) — ambigüedad de mi propia
  especificación al agente ciego, no un bug del parser. Corregido añadiendo
  `and r["tipo"] == "prosa"` al filtro de `n_registros` (línea 281).
- **Content Layer WARNING atrapado en Figure** (2026-08-23): en el cap 7, una caja
  WARNING ("These are the minimum personnel levels allowed...") vive dentro de la
  rejilla de "Figure 7-3" (Docling la mete como celda de tabla, no como texto suelto).
  El parser descartaba TODA "Figure" por defecto (fuera de alcance); ahora, antes de
  tirar una Figure, busca una celda que empiece por "WARNING" en su markdown y la
  salva como prosa de la sección abierta — el resto de la rejilla se sigue tirando.
- **Fixes de `/review`** (2026-08-23, un revisor `code-reviewer`, ver
  `review-report.md`): 3 críticos + 7 warnings + 6 suggestions, todos implementados.
  - **C1 (crítico)**: el chequeo de `section_id` solo se aplicaba a `TextItem` con
    label `section_header`/`list_item`; Docling también etiqueta encabezados reales
    como `text` plano y esos se fundían en silencio en la sección anterior. 37
    secciones reales (6.1%) se perdían así, incluidas `7-6.1`, `17-1.1`, `11-2.10`,
    `2-4.1`, `6-6.4`, `3-5.1` — verificadas ausentes antes del fix, presentes después.
    Arreglo: el chequeo de id ahora corre sobre cualquier `TextItem` que llegue al
    final de la cadena de labels (no solo esos dos), reestructurando el bloque de
    clasificación en `_parsear_capitulo`.
  - **C2 (crítico)**: `chars_entrada = chars_prosa+chars_tablas+chars_descartados` es
    tautológico por construcción (los 4 números salen de la misma pasada) — el test
    frozen que lo comprueba (igualdad exacta) nunca puede fallar y se deja intacto tal
    cual. Se añade un chequeo GENUINAMENTE independiente aparte: nuevo campo
    `chars_entrada_pdfplumber` en el manifiesto (medido con pdfplumber, sin pasar por
    Docling) + `tests/acceptance/test_ingest_conservacion.py` (fichero nuevo, no
    edita el frozen) que verifica que ambos quedan cerca. Tolerancia (20%) fijada con
    los diffs reales medidos tras corregir C1/C3 sobre los 10 capítulos: máximo 12.6%
    (cap 17), resto entre 0.1%-5.1%.
  - **C3 (crítico)**: las tablas se contaban como `len(markdown renderizado)` en vez
    de caracteres de origen — cap 9 reportaba 1.6M caracteres de tabla para un
    capítulo de ~86 páginas. Arreglo: cuenta de celdas crudas
    (`item.data.table_cells`), el markdown se sigue usando solo para el regex de
    WARNING/CAUTION (W2). Tras el fix, cap 9 pasa de 1,639,107 a 39,895 caracteres de
    tabla — coherente con el resto del capítulo.
  - **W1**: `plegar_caption` colapsaba TODA caption a `"Table N-M"` desnudo, incluida
    la primera aparición no continuada — se perdía la descripción real. Ahora solo
    pliega el sufijo `(Continued)`, conserva la descripción.
  - **W2**: el salvamento de cajas destacadas solo buscaba `WARNING` (no `CAUTION`) y
    se quedaba con la primera coincidencia, cortando en el primer `|`. Ahora captura
    ambas palabras clave, todas las ocurrencias, hasta la siguiente marca o fin de
    texto (no corta en pipes intermedios).
  - **W4**: `pytest.mark.slow` no estaba registrado y el test lento corría siempre.
    Añadido `[tool.pytest.ini_options]` en `pyproject.toml` con el marker registrado y
    `addopts = "-m 'not slow'"` — el gate rápido (`pytest tests/acceptance/`) ahora sí
    excluye el test en vivo por defecto.
  - **W5**: fragmentos de tabla sin caption se fundían con "la última tabla vista" sin
    comprobar página. Guardarraíl: solo se funde si la página del fragmento está a
    ≤3 páginas de la última página conocida de esa tabla; si no, se descarta como
    huérfano.
  - **W6**: un capítulo pedido ausente del mapa de páginas devolvía `([], {})` en
    silencio. Ahora `parsear_manual` lanza `ValueError`.
  - **W7**: `cargar_apuntes` no validaba `section_id` duplicados dentro de un mismo
    fichero. Ahora lanza `ValueError` si aparece un `##` repetido (verificado: no hay
    ninguno en los datos reales de `data/raw/PADI_course/`).
  - **Suggestions**: un solo `DocumentConverter` reutilizado entre los 10 capítulos
    (antes uno nuevo por capítulo) — `parsear_manual` lo construye una vez y lo pasa a
    `_parsear_capitulo`; `resto.split(". ", 1)` endurecido contra abreviaturas cortas
    (`_TITULO_CUERPO_SPLIT_RE`, exige ≥3 letras antes del punto); `main()` valida que
    el PDF exista y ahora imprime progreso por capítulo; `data/processed/` añadido a
    `.gitignore` (**nota**: ya estaba trackeado desde el commit inicial — el
    `.gitignore` evita que ensucie diffs futuros, pero destrackearlo con
    `git rm --cached` es una decisión de repo aparte, no tomada aquí);
    `_bakeoff_inspection/` ya no existe en disco, nada que limpiar.
  - Tests unitarios no-frozen actualizados para el nuevo comportamiento de
    `plegar_caption` (W1). Artefactos regenerados corriendo la ingesta completa;
    suite completa verde: 48 tests rápidos + 1 lento (`-m slow`), 0 fallos.
