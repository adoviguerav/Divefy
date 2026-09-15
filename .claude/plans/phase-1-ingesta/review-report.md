# Review report — Fase 1: Ingesta

**Modo**: un revisor (`code-reviewer`), pedido por Adolfo.
**Fecha**: 2026-08-23.

## Desviación de procedimiento (léase antes que el resto)

El paquete ciego debía llevar el diff pegado dentro del prompt; por un error mío al
construirlo, el bloque quedó vacío. El agente lo detectó, lo dijo explícitamente, y en
vez de inventar contenido leyó el módulo real en disco (`p1_ingest.py`, `tests/`, y los
artefactos generados en `data/processed/`) — sin git, sin ediciones. Confirmado con
`git status --porcelain` antes/después: idéntico salvo el `git add -N` que hice yo antes
de lanzarlo (pasa `??` a `A`, cero contenido tocado). No hubo manipulación del árbol.

Efecto práctico: la revisión vio **más** que un diff (incluido el `corpus.jsonl` real
generado), no menos — lo que le permitió encontrar C1 con datos reales en vez de solo
leer el código. Pero no fue estrictamente "solo el diff + plan sin Notas" como pide el
procedimiento. El hallazgo C1 lo verifiqué yo mismo aparte (`7-6.1` y `17-1.1` no están
en el corpus, confirmado), así que es fiable independientemente de esta desviación.

## Resumen en tres líneas

La separación tabla/prosa y la elección de Docling son sólidas (0 filas de tabla
coladas, verificado). Pero el detector de límites de sección tiene un punto ciego real:
descarta encabezados válidos que Docling etiqueta como `text` plano en vez de
`section_header`/`list_item`, fundiendo su contenido en la sección anterior en
silencio — y el manifiesto contable, que el propio plan diseñó para detectar
exactamente este tipo de fallo, es una tautología que nunca puede fallar. Lo primero
que arreglaría: el chequeo de id en `_parsear_capitulo` debe aplicarse a **todo**
`TextItem`, no solo a los de label `section_header`/`list_item`.

## Hallazgos

### CRÍTICO — C1: 37 secciones reales (6.1%) se funden en silencio en la anterior

**Ubicación**: `src/divefy/pipeline/p1_ingest.py`, el bloque de detección de sección
(rama `if label in (SECTION_HEADER, LIST_ITEM)`).

**Repro**: cualquier encabezado real que Docling etiquete `text` (no
`section_header`/`list_item`) nunca pasa por el chequeo `_SECTION_ID_RE.match(...)` —
cae directo a la rama genérica de prosa y se anexa a la sección que estuviera abierta.

Verificado en el corpus real: `7-6.1 Equipment Preparation.` (p366) y
`17-1.1 Purpose.` (p851) **no existen** como `section_id` en `corpus.jsonl` — confirmado
con una consulta directa sobre el JSONL, no es un artefacto de la revisión.

Conteo del revisor (escaneo del PDF vs `corpus.jsonl`, no verificado por mí número a
número pero la muestra sí): 37 de 603 ids reales ausentes — cap7 el peor (11, ~10% del
capítulo), cap9 y cap10 en cero (justo los dos únicos capítulos que el contrato de
aceptación inspecciona de cerca).

**Por qué importa**: `section_id` es la clave de la que depende el recall@k de Fase 5
(glosario de CLAUDE.md). Una pregunta del golden etiquetada `7-3.5` (ejemplo citado por
el revisor, también ausente) sería irrecuperable por construcción — no por mal
retrieval, sino porque el registro nunca se creó.

**Refutación intentada**: ¿hay algún test que ya cubra esto? No — la suite de
aceptación no hace un check "ids detectados por una vía independiente ⊆ ids emitidos"
sobre ningún capítulo salvo indirectamente (9-1, 9-6.3, 9-3.2 puntuales). ¿Podría ser
un texto que solo *parece* un id (falso positivo del propio escaneo del revisor)? Los
6 ejemplos citados (`7-6.1`, `17-1.1`, `11-2.10`, `2-4.1`, `6-6.4`, `3-5.1`) son títulos
de sección con frase completa detrás, no menciones sueltas — no sobrevive la
refutación, se confirma.

**Veredicto**: CONFIRMED.

### CRÍTICO — C2: el criterio de conservación contable no puede fallar nunca

**Ubicación**: `p1_ingest.py` — `chars_entrada = chars_prosa + chars_tablas + chars_descartados`
(la misma operación que el test verifica). Mismo patrón en
`secciones_emitidas = secciones_detectadas` (misma variable, dos nombres).

**Por qué importa**: el propio plan pidió este criterio explícitamente para atrapar
"un parser que trague el 30% del texto... en silencio" — pero al derivar los tres
sumandos y el total de la MISMA pasada de clasificación, el chequeo es una tautología:
siempre suma exacto, pase lo que pase. Es exactamente el fallo que C1 representa, y el
manifiesto no lo vio (`descartes_altos: false` en varios de los capítulos donde C1
pierde secciones).

**Refutación intentada**: ¿el test realmente pasa con datos corruptos? Sí — es
estructuralmente imposible que falle, ya que `entrada` se calcula sumando los mismos
tres números que se comparan contra él, no midiendo el texto de entrada por una vía
independiente.

**Veredicto**: CONFIRMED.

### CRÍTICO — C3: la contabilidad mezcla unidades (markdown renderizado vs caracteres de origen)

Las tablas se cuentan como `len(caption) + len(export_to_markdown(doc))` — texto
markdown con `|` y relleno, no caracteres del PDF original. Cap 9 reporta 1.6M
caracteres de tabla para un capítulo de ~86 páginas — cifra sin relación clara con el
tamaño real de entrada. Combinado con C2, no hay ninguna señal fiable de que un
capítulo se parseó mal.

**Veredicto**: CONFIRMED (consecuencia directa de C2, no independiente pero sí un
problema propio).

## WARNINGS (no bloquean, pero pesan)

- **W1** — `plegar_caption` reduce TODAS las captions a `"Table N-M"` desnudo, incluso
  la primera aparición no continuada; se pierde la descripción real
  ("Air Decompression Table") en los 48 punteros. Una consulta de Fase 5 por contenido
  de la tabla no tendría nada que matchear.
- **W2** — Las cajas CAUTION no se salvan (el patrón solo busca `WARNING`), y solo se
  toma la primera coincidencia por tabla. Repro citado: una caja CAUTION real en cap 7
  sobrevive como prosa pero sin la palabra "CAUTION" — relevante porque el proyecto
  trata texto de seguridad como citable verbatim (regla 3 de CLAUDE.md).
- **W3** — El test relajado a `>= 85` (frente al 88 real verificado) deja una ventana de
  3 secciones de regresión silenciosa. Ya registrado y decidido por Adolfo en las Notas
  del plan — el revisor no tenía esas Notas, así que lo marca como hallazgo nuevo; no
  lo es, ya está resuelto.
- **W4** — `pytest.mark.slow` no está registrado (sin `[tool.pytest.ini_options]` en
  `pyproject.toml`), así que el comando "rápido" del contrato de aceptación
  (`pytest tests/acceptance/`) en realidad corre también el test lento con Docling.
- **W5** — Fragmentos de tabla sin caption se funden con "la última tabla vista" sin
  comprobar que estén en páginas contiguas — sin caso real encontrado, pero sin
  guardarraíl tampoco.
- **W6** — Un capítulo pedido que no aparece en el mapa de páginas devuelve `([], {})`
  en silencio, sin error ni entrada en el manifiesto.
- **W7** — `section_id` de apuntes no valida duplicados si un fichero tiene dos `##`
  con el mismo texto.

## SUGGESTIONS

- Un solo `DocumentConverter` reutilizado entre capítulos en vez de uno nuevo por
  capítulo (reinicializa modelos 10 veces).
- `resto.split(". ", 1)` puede cortar mal un título con abreviatura (`U.S. Navy`, `No.`) —
  sin caso vivo encontrado, solo latente.
- `main()` no valida que el PDF exista ni imprime progreso en un job de varios minutos.
- El `review/` (antes "espejo") se decidió sin Notas explícitas que no incluya apuntes —
  cambio de alcance frente al Q3 original, decidido con Adolfo en esta sesión pero el
  revisor no lo sabía (no tenía las Notas).
- `data/processed/` no está en `.gitignore` pese a ser regenerable; el volcado del
  bake-off (`_bakeoff_inspection/`) sigue en disco pese a que el plan dice que se tira.
- Licencias de las nuevas dependencias (Docling MIT, pdfplumber MIT) sin problema.

## Tabla de adherencia al plan

| Ítem del plan | Estado |
|---|---|
| Loader de apuntes, `###` no corta | OK |
| Bake-off + puerta de decisión Adolfo | OK, ganador Docling registrado en EXPERIMENTOS.md |
| Rangos por pie de página, no hardcodeados | OK, verificado con casos límite (cap6 p576) |
| Tablas fuera de la prosa, plegadas por caption | Parcial — plegado OK, pero W1 vacía el contenido descriptivo |
| Manifiesto contable "para no perder texto en silencio" | **Roto** — C1/C2/C3, no cumple su propio propósito |
| Predicado de contaminación como juez, no filtro | OK, respetado |
| `data/processed/` como único contrato con Fase 2 | En riesgo por C1: hay contenido real que no llegó |

## Lo que el diff no puede responder

- Si los 37 ids ausentes (o cualquier subconjunto) coinciden con preguntas reales del
  golden dataset — requiere cruzar contra `docs/Buceo - Golden dataset.jsonl`.
- Comportamiento con el PDF completo de las otras figuras/gráficos no vistos en esta
  pasada (solo se inspeccionaron cap 7 y 9 con detalle).
