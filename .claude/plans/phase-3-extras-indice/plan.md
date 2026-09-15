# Plan: Fase 3 — Extras de índice

**Estado**: implemented
**Fuente**: PRD §7 Fase 3 · debatido con Adolfo en conversación (2026-08-24), incluye
investigación externa sobre contextual retrieval y HyPE.

## Objetivo

Al terminar existe, cacheado en `data/processed/enrich.jsonl`: una línea por cada chunk
de prosa de `chunks.jsonl`, con su `id`, su frase situadora (`contexto`, ≤100 tokens,
generada mirando el chunk dentro de su documento padre — capítulo del manual o fichero
de apuntes) y sus 3-5 preguntas hipotéticas (`preguntas`, generadas sobre el chunk ya
contextualizado). Los chunks-puntero de tabla no tienen línea en este fichero. Es el
contrato que consume la Fase 4: "config → colección Chroma que embebe trozo[+contexto]
y preguntas HyPE si la config los lleva" — un único fichero para leer, sin cruzar por
`id` entre varios.

## Hallazgos (medidos 2026-08-24 sobre el código y los datos reales)

- `chunks.jsonl` existe ya (943 KB, Fase 2 en desarrollo) con schema `corpus,
  section_ids, titulo, tipo, texto, fichero, capitulo, pagina, pagina_fin` — **sin id
  único por chunk** (`section_ids` es una lista y puede compartirse entre chunks
  vecinos, no sirve como identidad).
- Padre de cada chunk: apuntes usan `fichero` (6 valores; `capitulo` siempre null);
  manual usa `capitulo` (hoy 9 valores en los datos: 2,3,4,6,7,9,10,11,14 — **falta el
  17** de los 10 curados del PRD; probablemente la Fase 2 en desarrollo no lo ha
  troceado aún, no es un problema de esta fase).
- **Ningún SDK de LLM está instalado** (`pyproject.toml`: docling, langchain-text-
  splitters, pymupdf, transformers — nada de Anthropic ni Google). Fase 3 es la primera
  en necesitar una llamada real a una API de LLM.
- **Orden de lectura NO garantizado al filtrar `chunks.jsonl` por capítulo**: en
  `p2_chunking.py::trocear_registros` (líneas 89-114), los `puntero_tabla` se añaden en
  una segunda pasada AL FINAL de todo el fichero, después de la prosa de TODOS los
  capítulos. Verificado con los datos reales: al filtrar capítulo 9, la secuencia de
  `pagina` deja de ser monótona porque los punteros de tabla del cap 9 aparecen muy
  después en el fichero aunque su página real sea intermedia. Concatenar "por orden de
  aparición en el fichero" reconstruiría un documento con las tablas fuera de sitio.
  Como se decidió no enriquecer punteros (ver Decisiones), en la práctica solo hace
  falta filtrar `tipo=="prosa"` y ordenar por `pagina` — el problema desaparece con esa
  decisión, pero el motivo por el que hacía falta ordenar explícitamente queda
  documentado aquí para que no se repita el error de fiarse del orden del fichero.
- Apuntes no tienen este problema (cero punteros, `tipo` siempre "prosa"), pero tampoco
  tienen `pagina` (siempre null) — ahí el orden de aparición en el fichero SÍ es fiable
  (se generan sección a sección, sin segunda pasada).
- Prompt de referencia verificado (Anthropic, contextual retrieval):
  `<document>{{doc}}</document><chunk>{{chunk}}</chunk>` + "Please give a short succinct
  context to situate this chunk within the overall document for the purposes of
  improving search retrieval of the chunk. Answer only with the succinct context and
  nothing else." → salida 50-100 tokens. Coincide con el tope ~100 ya fijado en el
  check del PRD. Usan prompt caching de Claude para no pagar el documento en cada chunk.
- HyPE en la literatura no usa el documento en absoluto, solo el chunk — el encadenado
  de Divefy (contexto ya generado + chunk, sin capítulo) es una composición propia, sin
  literatura que la respalde directamente (búsqueda hecha, sin resultado). Cada técnica
  por separado sí tiene resultados publicados: contextual retrieval -35%/-49% fallos de
  recuperación top-20 (Anthropic); HyPE +16pp recall / +20pp precisión vs RAG naive
  (paper que la propone).

## Decisiones (tomadas con Adolfo en esta conversación)

- **Modelo de enriquecimiento: `gemini-3.1-flash-lite`**, fijo, fuera de la ablación
  (decisión original del PRD era "Gemini Flash" sin más precisión; cambiado a este
  modelo concreto en esta conversación tras medir coste real — ver detalle más abajo,
  "Modelo final y caching"). Nuevas dependencias: `google-genai`, `python-dotenv`.
- **Reconstrucción del documento padre: desde `chunks.jsonl` mismo**, no desde
  `corpus.jsonl` (el chunking no pierde ni duplica texto — Fase 2 lo garantiza —, así
  que sería una dependencia redundante). Filtrando `tipo=="prosa"`, agrupando por
  `capitulo` (manual) o `fichero` (apuntes), ordenado por `pagina` en el manual y por
  orden de aparición en apuntes.
- **HyPE se genera sobre el chunk YA contextualizado** (chunk + su frase de contexto),
  no sobre el capítulo de nuevo — reutiliza el trabajo del paso anterior, coste
  acotado. Trade-off aceptado: esta fase nunca mide "HyPE puro"; apuntado como cruce de
  cordura de la Fase 9 (medir HyPE sobre el chunk sin contexto encadenado, para saber
  si el encadenado aporta algo).
- **El `id` único de chunk vive en Fase 2**: se añade un campo `id` (entero secuencial,
  asignado en `Chunk.to_dict()` de `p2_chunking.py`) — toca el fichero de Fase 2, que
  Adolfo tiene en desarrollo activo. Es identidad del chunk (la necesita también Fase
  4/5 para el dedup de HyPE), no algo específico de enriquecer.
- **Los chunks-puntero de tabla NO se enriquecen** — pasan sin tocar a la Fase 4. Ya
  son captions autocontenidos; generarles contexto/preguntas es coste sin beneficio
  claro.
- **Salida en un único fichero propio de Fase 3** (`enrich.jsonl`, campos `id`,
  `contexto`, `preguntas`), nunca se muta `chunks.jsonl` — sigue el mismo patrón que
  Fase 1→`corpus.jsonl` y Fase 2→`chunks.jsonl`: cada fase escribe su propio artefacto,
  la siguiente lo lee. Un solo fichero en vez de dos (decisión de Adolfo, 2026-08-24):
  contexto y preguntas se generan siempre juntos — HyPE depende del contexto ya
  generado — así que separarlos en dos ficheros solo obligaría a cruzarlos por `id` sin
  ganar nada a cambio. Se indexa por el `id` de chunk (T-01).
- **Caching de contexto de Gemini**: se investiga y usa si aplica limpio (para no pagar
  el capítulo entero por cada chunk del mismo documento) — detalle de implementación,
  no bloquea el diseño; si no aplica bien, se sigue sin caching y se acepta el coste.

## Contexto

- `.claude/plans/PRD.md` §7 Fase 3 — decisiones cerradas que este plan implementa.
- `src/divefy/pipeline/p3_enrich.py` — vacío (solo docstring), aquí se implementa.
- `src/divefy/pipeline/p2_chunking.py:14-69` (`Chunk`, `to_dict`) — aquí se añade `id`.
- `src/divefy/pipeline/p2_chunking.py:78-114` (`trocear_registros`) — el motivo del
  hallazgo de orden (punteros en segunda pasada al final).
- `src/divefy/pipeline/p2_chunking.py:117-120` (`cargar_tokenizer_bge_m3`) — reusar
  para contar tokens del contexto con el mismo tokenizador que Fase 2 (el tope debe
  significar lo mismo en todo el grid, regla ya fijada en Fase 2).
- `src/divefy/pipeline/p2_chunking.py:132-136` (`escribir_chunks`) — patrón de
  escritura JSONL a seguir para `enrich.jsonl`.
- `data/processed/chunks.jsonl` — entrada real, schema verificado arriba.
- Prompt de contexto (referencia Anthropic, verificado 2026-08-24, ver Hallazgos).
- `tests/unit/test_p2_chunking_core.py`, `tests/acceptance/test_chunking.py` — estilo
  de test del proyecto (pytest plano, sin clases). Fase 3 sigue el mismo patrón:
  `tests/unit/test_p3_enrich_core.py` + `tests/acceptance/test_enrichment.py`.
- Identificadores en español, igual que `p1_ingest.py`/`p2_chunking.py` (no aplicar la
  regla general de nombres en inglés aquí — esta parte del repo ya tiene su propia
  convención consistente, y coding-style.md pide respetar el estilo existente).

## Contrato de aceptación

Comandos gate: `uv run pytest tests/unit/test_p3_enrich_core.py
tests/acceptance/test_enrichment.py -q` · regenerar el artefacto:
`uv run python -m divefy.pipeline.p3_enrich`.

- [x] Todo chunk `id` con `tipo=="prosa"` en `chunks.jsonl` tiene una línea en
  `enrich.jsonl` con `contexto` no vacío de ≤100 tokens (tokenizador BGE-M3).
- [x] Ningún chunk con `tipo=="puntero_tabla"` tiene línea en `enrich.jsonl`.
- [x] Toda línea de `enrich.jsonl` tiene entre 3 y 5 `preguntas` no vacías y distintas
  entre sí.
- [x] Todo `id` referenciado en `enrich.jsonl` existe en `chunks.jsonl` (sin huérfanos).
- [x] Determinismo con caché: correr el enriquecimiento dos veces seguidas sobre el
  mismo `chunks.jsonl` sin borrar la caché no repite ninguna llamada al LLM (0
  llamadas en la segunda pasada) y el contenido de `enrich.jsonl` no cambia byte a
  byte.
- [x] Inspección a ojo (no bloqueante): ~10 contextos y ~10 preguntas del capítulo 9
  sitúan/preguntan lo que toca (criterio de aceptación ya fijado en el PRD).

## Out of scope

- Decidir si contextual/HyPE mejoran el recall — lo mide el corrector en Fase 5.
- Embeber contexto/preguntas en Chroma — Fase 4.
- El cruce de cordura "HyPE sin contexto encadenado" — apuntado para Fase 9.
- Completar el capítulo 17 si falta en los datos actuales de `chunks.jsonl` —
  responsabilidad de que la Fase 2 cierre su barrido, no de esta fase.

## Interfaces

```python
# src/divefy/pipeline/p2_chunking.py — cambio mínimo sobre lo existente
@dataclass(frozen=True)
class Chunk:
    id: int              # NUEVO: secuencial, asignado en escribir_chunks
    texto: str
    origen: list[Record]
    ...

# src/divefy/pipeline/p3_enrich.py
def documento_padre(chunks: list[dict], capitulo: int | None, fichero: str | None) -> str:
    """Concatena la prosa (tipo=='prosa') del mismo padre, en orden de lectura
    (por 'pagina' si es del manual, por aparición en el fichero si son apuntes)."""

def generar_contexto(documento: str, chunk_texto: str, cliente) -> str: ...
def generar_preguntas_hype(chunk_contextualizado: str, cliente) -> list[str]: ...

def enriquecer(chunks_path: Path, processed_dir: Path) -> None: ...  # orquesta y cachea
def main() -> None: ...  # python -m divefy.pipeline.p3_enrich
```

## Tareas

- **T-01 · UPDATE `p2_chunking.py`** — añadir `id: int` a `Chunk`/`to_dict()`, asignado
  secuencialmente en `escribir_chunks`.
  VALIDATE: `uv run pytest tests/unit/test_p2_chunking_core.py -q` +
  `chunks.jsonl` regenerado tiene `id` 0..N-1 sin huecos ni repetidos.
- **T-02 · ADD dependencia** — `uv add google-genai`.
  VALIDATE: `uv run python -c "import google.genai"`.
- **T-03 · CREATE núcleo puro** — `documento_padre` en `p3_enrich.py` (agrupar + ordenar,
  sin llamar a ningún LLM).
  VALIDATE: `uv run pytest tests/unit/test_p3_enrich_core.py -q`.
- **T-04 · CREATE `generar_contexto`** — prompt estilo Anthropic (ver Hallazgos),
  Gemini Flash, tope de tokens con `cargar_tokenizer_bge_m3`. Probar context caching de
  Gemini; si no aplica limpio, seguir sin él (Decisiones).
  VALIDATE: smoke manual sobre 2-3 chunks del cap 9, salida ≤100 tokens.
- **T-05 · CREATE `generar_preguntas_hype`** — mismo modelo, input = chunk + contexto
  ya generado (T-04), 3-5 preguntas.
  VALIDATE: smoke manual sobre los mismos 2-3 chunks.
- **T-06 · CREATE `enriquecer` + `main`** — orquesta T-04/T-05 sobre todos los chunks de
  prosa; cachea en disco (skip si el `id` ya tiene línea); escribe `enrich.jsonl`
  (`id`, `contexto`, `preguntas`).
  VALIDATE: `uv run python -m divefy.pipeline.p3_enrich` corre completo sobre los datos
  reales sin error.
- **T-07 · Check ruidoso + aceptación** — implementar el contrato de aceptación de
  arriba como tests; correr sobre el artefacto real; inspección a ojo del cap 9.
  VALIDATE: `uv run pytest tests/unit/test_p3_enrich_core.py
  tests/acceptance/test_enrichment.py -q`.

## Notas

- **Enmienda al test de aceptación** (2026-08-24, aplicada): el diseño original de
  este plan usaba dos ficheros de salida (`contexto.jsonl`, `hype.jsonl`); se
  simplificó a uno solo (`enrich.jsonl` con `id`, `contexto`, `preguntas`) — ver
  Decisiones. El hook de congelación bloqueó la edición automática (el fichero ya
  estaba escrito en `tests/acceptance/`); en vez de desbloquear con
  `.unlock-tests`, Adolfo aplicó el cambio él mismo directamente en su editor —
  contenido idéntico al que tenía preparado el agente ciego (un solo
  `ENRICH_PATH`/`enrich_records`, los 5 tests leyendo `contexto`/`preguntas` de ahí,
  test 5 comparando un solo fichero byte a byte). RED re-confirmado tras el cambio:
  4 `FileNotFoundError` (falta `enrich.jsonl`) + 1 `AttributeError` (falta
  `generar_contexto` en `p3_enrich.py`) — el motivo correcto, ningún test en verde
  por accidente. No hizo falta tocar `.unlock-tests` en ningún momento.
- **Bloqueo: cuota diaria del tier gratuito de Gemini** (2026-08-24): T-01 a T-05
  completados y validados (id secuencial en `chunks.jsonl`, `documento_padre`,
  `generar_contexto` y `generar_preguntas_hype` probados en vivo sobre chunks reales
  del cap 9 — contextos ≤100 tokens, 3-5 preguntas por trozo). Al probar T-06
  (`enriquecer`) sobre solo 8 chunks de muestra, la API devolvió 429
  `RESOURCE_EXHAUSTED`: el tier gratuito de `gemini-3.6-flash` tiene un tope de
  **20 peticiones/día** (no por minuto — se agotó con las pruebas de T-04/T-05 más
  el smoke de 8 chunks). La pasada completa (524 chunks × 2 llamadas ≈ 1050
  peticiones) es inviable en el tier gratuito. Pendiente de que Adolfo active
  facturación (pay-as-you-go) en el proyecto de Google Cloud de esa API key antes de
  poder validar T-06/T-07 sobre los datos reales. El código de `enriquecer` no tiene
  el problema — es la cuota de la cuenta.
- **Modelo final y caching** (2026-08-24): facturación activada. Cambio de
  `gemini-3.6-flash` a `gemini-3.1-flash-lite` (mismo trabajo, calidad equivalente
  probada en vivo, $0.25/$1.50 por millón frente a $0.75/$3.75 — precio real de HOY
  verificado en la página oficial, mi primera estimación de coste usaba por error el
  precio de 2027). Añadido caching de Gemini (`caches.create`, dentro de
  `generar_contexto`, transparente para `enriquecer`): sin él, el documento padre se
  reenviaba entero en cada llamada de contexto — ~9,6M de ~9,8M tokens de entrada
  eran ese reenvío repetido. Con modelo barato + caching, coste estimado de la pasada
  completa (683 chunks tras el cambio de Fase 2 de Adolfo, `fundir_minusculas`):
  **~0,52$** (frente a la estimación inicial de ~19$). Nueva dependencia:
  `python-dotenv` (decisión de Adolfo: cargar `.env` en vez de exportar la key a
  mano).
- **Verificación de fidelidad del contexto generado — decisión de Adolfo, no se
  añade nada** (2026-08-24): se planteó si comprobar que el LLM enriquecedor no
  inventa datos ausentes del chunk (riesgo real: la frase de contexto viaja también
  al LLM que genera la respuesta final, no solo a la búsqueda). Se descartaron LLM
  as judge y revisión humana ampliada — mismo motivo por el que el PRD ya descartó
  juez LLM en el recall de Fase 5: un LLM evaluando a otro LLM no es prueba, es una
  segunda opinión con los mismos puntos ciegos, y no vale la pena la complejidad
  ahora. Queda solo lo ya planeado: los checks deterministas del contrato de
  aceptación (forma, no contenido) + la inspección a ojo puntual del PRD. Sin
  cambios en tareas ni en el contrato de aceptación.
- **T-06/T-07 completados sobre datos reales** (2026-08-24): pasada completa
  ejecutada sobre los 683 chunks de prosa (de 723 totales tras el cambio de Fase 2
  de Adolfo) — `data/processed/enrich.jsonl` con 683 líneas, todas bien formadas.
  El backgrounding reportó "failed" por un artefacto de mi propio filtro de shell
  (`grep -v` sin salida que mostrar sale con código 1 aunque el proceso real
  terminara en 0) — confirmado sin fallo real: recuento de líneas exacto, JSON
  válido hasta la última línea, y sobre todo, la suite completa de aceptación en
  verde (9/9: 4 unitarios + 5 de aceptación) más la suite acumulada del proyecto
  (72/72, 5 lentos deseleccionados). Inspección a ojo de 10 contextos/preguntas del
  cap 9: situar correcto, preguntas relevantes, sin señales de invención. Contrato
  de aceptación completo, todas las casillas marcadas.
- **`/review` (un revisor) y fixes aplicados** (2026-08-24): veredicto BLOCK — 2
  CRITICAL, 2 HIGH, 3 MEDIUM, 3 LOW (`review-report.md`). Todos discutidos con
  Adolfo y resueltos, con un cambio de diseño real sobre lo que proponía el
  revisor:
  - **C1 (id posicional)** — en vez del hash-guard que proponía el revisor, se
    rediseñó el id de chunk en `p2_chunking.py`: pasa de entero por posición
    (asignado en `escribir_chunks`) a string de contenido (`section_ids` unidos +
    sufijo `#N` si la sección se partió), calculado en `trocear_registros`. Un
    subagente verificó independientemente que esto es la práctica estándar en
    ingesta de RAG (id estable por ubicación + hash de contenido aparte para
    invalidación — cita la indexing API de LangChain). Se añadió además un campo
    `fingerprint` (hash del texto) en cada fila de `enrich.jsonl`: el id identifica
    la sección, la huella detecta si su texto cambió desde la última pasada — las
    dos cosas son necesarias, no redundantes (razonado y verificado con Adolfo).
  - **C2 (nada persiste hasta el final)** — cada fila se escribe (append + flush)
    en cuanto se genera; al terminar, reescritura final ordenada por id que además
    poda filas huérfanas (ids de una pasada anterior con otro esquema).
  - **H1 (test necesita key real)** — el cliente de Gemini se construye ahora
    dentro de `generar_contexto`/`generar_preguntas_hype` (perezoso, memoizado),
    nunca en `enriquecer`. Verificado con `unittest.mock.patch` forzando
    `AssertionError` si `genai.Client()` se llega a invocar: no se invoca cuando
    esas dos funciones están mockeadas.
  - **H2 (sin validación de contrato al generar)** — preguntas ahora se piden como
    JSON con schema forzado (`types.Schema`, array 3-5 strings) en vez de parsear
    líneas de texto; contexto y preguntas se validan (tope de tokens BGE-M3, rango
    3-5, sin vacíos, sin duplicados) antes de cachear, con un reintento si no
    cumplen; si el reintento tampoco cumple, error explícito en vez de guardar una
    fila mala.
  - **M1** — `enriquecer` revienta con `FileNotFoundError` si `chunks_path` no
    existe, en vez de producir un `enrich.jsonl` vacío en silencio.
  - **M2** — anotado arriba en Decisiones (modelo final = `gemini-3.1-flash-lite`).
  - **M3** — el documento que se cachea en Gemini ahora va envuelto en
    `<document>...</document>`, igual que el prompt de referencia verificado.
  - **LOW (TTL)** — subido de 1h a 2h, margen barato.
  - **LOW (test de parseo de líneas)** — ya no aplica: H2 sustituyó el parseo de
    líneas por JSON con schema, no queda lógica frágil que testear ahí.
  - **LOW (`id: int = -1`)** — resuelto de raíz por el rediseño de C1: el id ya no
    tiene un sentinel de "sin asignar", se calcula en el momento de crear el chunk.
  - Regenerados desde cero: `chunks.jsonl` (723, ids únicos verificados) y
    `enrich.jsonl` (683, ids únicos, todas con `fingerprint`). Suite completa:
    76/76 (5 lentos deseleccionados). Inspección a ojo repetida sobre la nueva
    pasada: misma calidad que antes del fix.
