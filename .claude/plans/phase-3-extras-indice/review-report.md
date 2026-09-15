# Review report — Fase 3: Extras de índice

**Revisor**: 1 agente `code-reviewer`, ciego (plan sin `## Notas`, diff completo, reglas del proyecto).
**Nota sobre el proceso**: el diff no llegó al agente por un error mío al montar el prompt
(el bloque quedó vacío). El agente, con herramientas propias, leyó directamente los
ficheros reales del working tree que nombra el plan más el artefacto generado — cobertura
equivalente a la del diff en este caso (son ficheros nuevos o casi enteros), pero
técnicamente no siguió al pie de la letra "no leas nada más que el diff". Queda anotado
por transparencia; no invalida los hallazgos, que están todos referenciados a líneas
reales.

**Veredicto**: BLOCK — 2 CRITICAL, 2 HIGH, 3 MEDIUM, 3 LOW/sugerencias.
**Lo primero a arreglar**: C1 — el `id` de chunk es posicional, no es identidad de
contenido; si Fase 2 vuelve a trocear sin borrar `enrich.jsonl`, el caché reatribuye
contexto/preguntas al chunk equivocado en silencio, y ningún test actual lo detectaría.

---

## CRITICAL

**[C1] Caché indexado por `id` posicional, sin comprobar contenido → mis-enriquecimiento silencioso**
`p2_chunking.py:152`, `p3_enrich.py:111,118`. El `id` es la posición final en el
fichero, no una huella del contenido. Si Fase 2 cambia (tope, fusión, fix de parseo) sin
borrar `enrich.jsonl`, los `id` se desplazan y el caché sigue devolviendo como válidas
filas que ahora corresponden a un chunk distinto. Los 5 tests de aceptación pasarían
igual sobre un artefacto corrupto (solo comprueban forma, no que el contenido
corresponda al chunk correcto). Propone: guardar un hash del `texto` en cada fila y
invalidar si no coincide.

**[C2] Cero manejo de errores en ~1400 llamadas a la API; nada se persiste hasta que el bucle entero termina**
`p3_enrich.py:117-135`. `enrich.jsonl` se abre y escribe solo DESPUÉS del bucle
completo. Un 429/503 transitorio en la llamada 1300 tira todo lo generado en esa pasada
— el propio mecanismo de caché en disco que justifica todo el diseño nunca llega a
grabar nada. Propone: escribir cada fila según se genera (append + flush), reordenar al
final.

## HIGH

**[H1] El test de aceptación no puede correr sin una API key real, aunque mockea las dos llamadas al LLM**
`test_enrichment.py:99-172`. `enriquecer` construye `genai.Client()` antes de llegar a
las funciones mockeadas. Reproducido en vivo por el revisor: sin `GEMINI_API_KEY` ni
`GOOGLE_API_KEY`, el test falla con `ValueError`. Pasa en esta máquina solo porque
`load_dotenv()` coge el `.env` local — en cualquier otro sitio (CI, otra persona), el
examen "congelado" da rojo por un motivo ajeno a lo que dice medir.

**[H2] El tope de tokens de T-04 nunca se implementó; ni el tope ni el nº de preguntas se fuerzan al generar**
`p3_enrich.py:47-74`. `generar_contexto` devuelve `respuesta.text.strip()` sin
comprobar tope; `generar_preguntas_hype` devuelve todas las líneas no vacías, sin acotar
a 3-5. Hoy pasa por buena voluntad del modelo (medido: máx 48 palabras, 3-5 preguntas
en los 683). Nada lo garantiza en la próxima pasada — y si un día falla, la fila mala
queda cacheada para siempre (solo se arregla borrando la línea a mano). Además,
`respuesta.text` puede ser `None` (bloqueo de seguridad, tope de salida) y `.strip()`
reventaría — PLAUSIBLE, no confirmado (no ocurrió en los 683 reales); a vigilar si
Gemini bloquea alguna vez contenido sobre ahogamiento/descompresión.

## MEDIUM

- **[M1]** `chunks_path` inexistente no lanza error — con `_leer_jsonl` tolerante,
  correr mal ubicado produce un `enrich.jsonl` vacío en silencio, exit 0.
- **[M2]** El modelo cambió de Gemini Flash a `gemini-3.1-flash-lite`, y el plan dice
  literalmente "no se reabre" en su sección `## Decisiones` — el revisor no tenía
  acceso a `## Notas` (donde sí está la aprobación real de Adolfo con datos de coste).
  Falso positivo del proceso ciego, pero señala un hueco real de documentación: la
  sección `## Decisiones` no refleja la elección final, solo `## Notas` la tiene.
- **[M3]** El prompt de contexto ya no envuelve el documento en `<document>...</document>`
  (se manda como `contents` de la caché sin ese delimitador) — se aleja del prompt de
  referencia que el propio plan verificó, aunque el modelo sigue viendo el documento
  igual (vía caché).

## LOW / sugerencias

- Caché de documento en memoria (`_cache_de_documento`) con TTL de 1h sin refresco — si
  algún padre tardara más de una hora en procesarse, la siguiente llamada fallaría con
  400. Bajo riesgo hoy (máx 110 chunks por padre), relevante solo si el corpus crece o
  se paraleliza.
- Sin test para el parseo de líneas de `generar_preguntas_hype` (el `lstrip` que quita
  numeración) — la lógica más barata de testear y la más fácil de romper en silencio.
- `Chunk.id: int = -1` hace representable un estado inválido (chunk sin id asignado);
  inalcanzable hoy vía `main()`, pero sin ningún assert que lo impida.

## Lo que el diff acierta

`documento_padre` filtra `tipo=="prosa"` ANTES de ordenar, con el motivo documentado —
justo la trampa que el propio plan había anotado en Hallazgos. El orden estable para
apuntes (sin `pagina`) es correcto y está probado. La reescritura final ordenada sí da
salida byte-idéntica en una pasada 100% cacheada. Las interfaces coinciden con las del
plan. `.env` está en `.gitignore`, sin secretos en el código. Verificado contra el
artefacto real: 683/683 chunks de prosa enriquecidos, 0 punteros colados, 0 huérfanos,
0 ids duplicados, 0 contextos vacíos, preguntas siempre 3-5, ids `0..722` contiguos.
Todos los criterios de aceptación se cumplen hoy — la objeción de C1/H2 es que se
cumplen por suerte en esta única pasada, no por construcción.
