# Verify — Fase 5 (retrieval + corrector), 2026-08-30

**Veredicto global: ACCEPTED** — 10/10 criterios PASS, suite completa acumulada
**149 passed** (0 regresiones de F1-F4), gate exacto del contrato **26 passed**.

## Evidencia por criterio

| # | Criterio | Verdicto | Evidencia |
| --- | --- | --- | --- |
| 1 | labels.jsonl: 84 uso=eval, secciones existentes, requiere_tool coherente | PASS | `tests/unit/test_labels.py` → 8 passed |
| 2 | Auditoría de etiquetas (≤2 mal en muestra), anotada en Notas | PASS¹ | Notas 2026-08-28: muestra de 28 → 17 mal → revisión prescrita por el propio plan ejecutada como **censo completo** (los 113 pares restantes auditados, 43 descartes totales; censo ⊃ muestra). Anotaciones en plan.md:357,367 |
| 3 | retrieve: k ids únicos, en chunks.jsonl, sin `::hype::` | PASS | unit dedup + acceptance real (en el gate: 26 passed, 0 skipped) |
| 4 | BM25 idéntico en todos los brazos (solo filas chunk) | PASS | `test_bm25_ignora_las_filas_hype…` (gate) |
| 5 | RRF reproduce orden a mano `Σ 1/(60+rank)` + desempate | PASS | `test_rrf_reproduce_el_orden_calculado_a_mano` + desempate (gate) |
| 6 | Determinismo: corrector ×2 byte a byte | PASS | acceptance `test_running_the_corrector_twice…` (gate, sin skip) |
| 7 | Nunca-se-sobreescribe: distinta→error con diff, idéntica→no-op | PASS | `test_write_result_*` (gate) |
| 8 | Métricas correctas sobre fixture a mano | PASS² | `tests/unit/test_corrector_core.py` → 11 passed, valores calculados a mano en comentarios |
| 9 | Paso 0: 36 filas densa k=5 + tabla en EXPERIMENTOS (F1/3/4 rellenadas) | PASS | 36/36 ficheros verificados por nombre; tabla + 7 casillas `[x]`; ancla decidido por Adolfo (combined) |
| 10 | Receta de búsqueda: densa vs híbrida × k∈{3,5,10} sobre el ancla, anotada | PASS³ | 6/6 filas verificadas por nombre; declaración en EXPERIMENTOS:191 |

¹ La regla de muestra (≤2 mal) saltó en la primera pasada (17>2) y disparó la
revisión que el plan prescribía; la revisión fue un censo (100 % de los pares
manual auditados), garantía estrictamente más fuerte que la muestra. Dirigido y
decidido por Adolfo, anotado en Notas.

² **Defecto de texto del contrato, no de implementación**: el criterio enumera
"recall@k, MRR, … y match numérico" según la Decision 6 original; el conjunto de
métricas fue reemplazado por decisión de Adolfo (2026-08-28/30, en
`metricas-framework.md`, PRD y EXPERIMENTOS sincronizados) — hit_rate/recall/
precision/mrr/tokens vía ranx, match numérico retirado. Los tests verifican el
conjunto decidido. La línea del contrato quedó sin re-redactar; se deja constancia
aquí en lugar de editar un contrato de fase ya cerrada.

³ La receta queda declarada como **combined + contextual + híbrida** con k
deliberadamente abierto entre 5 y 10 → se cierra en F6 con el reranker (decisión
de Adolfo, anotada). El criterio pedía "medidos y anotados": cumplido.

## Regresiones

Ninguna: la suite acumulada completa (F1 ingesta, F2 chunking, F3 enrich, F4
indexing + acceptance congelados, F5) → 149 passed, 5 deselected (slow de F1).

## Comandos ejecutados

```
uv run pytest tests/unit/test_p5_retrieve_core.py tests/unit/test_corrector_core.py tests/acceptance/test_p5_retrieval.py -q   → 26 passed
uv run pytest -q                                                                                                               → 149 passed, 5 deselected
uv run pytest tests/unit/test_labels.py -q                                                                                     → 8 passed
```