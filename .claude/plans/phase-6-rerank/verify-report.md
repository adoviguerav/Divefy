# Verify — Fase 6 Rerank (2026-08-31)

**Veredicto global: ACCEPTED — 5/5 PASS, 0 regresiones.**

Comandos corridos (exactos del contrato + suite completa):

- `uv run pytest tests/unit/test_p6_rerank_core.py tests/acceptance/test_p6_rerank.py -q -rs`
  → **16 passed** en 348s, **cero skips** (los tests con store y modelo real corrieron).
- `uv run pytest -q` → **165 passed, 5 deselected** en 334s (5 deselected = marker
  `slow` de Docling, deselección estándar del gate rápido desde F1).

| Criterio | Veredicto | Evidencia |
|---|---|---|
| rerank on → exactamente k ids, ⊂ N=20 candidatos, orden score desc (desempate id asc) | **PASS** | `TestRetrieveWithRerank` (3 param k) + `TestRerankSemantics` (4: permutación, prefijo, determinismo, subconjunto) + 4 unit con fake, incl. test del ensanche a `N_CANDIDATES` |
| rerank off idéntico a F5 (suite completa sin tocar) | **PASS** | 165 passed incluye los 149 tests de F1-F5 intactos, con el determinismo de F5 dentro |
| run_id con sufijo `-rerank` solo cuando on | **PASS** | `TestConfigSurface` (3 tests) |
| determinismo: evaluador dos veces con rerank on → byte-idéntico | **PASS** | `TestCorrectorDeterminismWithRerank` — corrió (sin skip), 2 pasadas completas de 84 preguntas |
| 3 filas nuevas en `results/` + casillas F6 rellenadas + decisión anotada | **PASS** | `results/{combined-512-contextual-qwen8b-hibrida-k5,-k10,apuntes-512-base-qwen8b-hibrida-k5}-rerank.json` (14:10-14:16) · EXPERIMENTOS.md F6 con `[x]` y decisión de Adolfo escrita (rerank ON, k=10, con condiciones de re-juicio) |

Regresiones de fases anteriores: ninguna (0 failed en la suite acumulada).

Nota de contexto no bloqueante: los dos ficheros de aceptación congelados llevan el
rename `corrector` → `retrieval_evaluator` hecho por Adolfo (solo imports/strings,
aserciones intactas); la suite en verde lo cubre.