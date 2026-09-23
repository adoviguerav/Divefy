# Verify report: phase-8c-precarga-streaming-scores

**Overall verdict: ACCEPTED** (2026-09-23)

## Gate (tal cual en el plan)

```
uv run pytest tests/acceptance/test_p8c_scores.py tests/acceptance/test_p8b_web.py tests/acceptance/test_p8_chat.py -q
17 passed
```

Suite completa: `uv run pytest -q` → **216 passed, 11 deselected**. Los tests
congelados de F5, F6, F7, 8a y 8b siguen en verde.

## Veredicto por criterio

| # | Criterio | Test | Veredicto |
|---|---|---|---|
| 1 | `rerank_scored` devuelve k `(id, score)` y `rerank` los mismos ids | `TestRerankScored::test_scored_y_wrapper_coinciden` | PASS |
| 2 | `rrf_fuse_scored` = Σ 1/(60+rank) a mano; `rrf_fuse` mismo orden | `TestRrfScored::test_score_rrf_a_mano` | PASS |
| 3 | `answer()` deja `score` y `score_kind` en cada chunk | `TestAnswerScores::test_chunks_llevan_score_y_tipo` | PASS |
| 4 | `POST /api/warmup` llama a `warm_up`; body inválido → 400 | `TestWarmup::test_endpoint_llama_warm_up` | PASS |
| 5 | `warm_up` precalienta retrieval y solo carga MLX si toca | `TestWarmup::test_warm_up_carga_lo_que_toca` | PASS |
| 6 | La página lleva la escritura progresiva | `TestStreaming::test_pagina_tiene_escritura_progresiva` | PASS |
| 7 | Tests congelados de F5/F6/F7/8a/8b en verde | suite completa | PASS |
| 8 | QA manual: primera pregunta rápida, respuesta escribiéndose, scores con leyenda | Adolfo | PASS (confirmado por Adolfo 2026-09-23) |

## Regresiones

Ninguna. Un test unitario de andamiaje (`test_p6_rerank_core.py`) se adaptó a los
nombres nuevos sin cambiar su aserción (Notes del plan).

## Notas

- Añadido fuera de contrato, a petición de Adolfo: 4 preguntas de ejemplo en la
  pantalla vacía (`GET /api/options` → `ejemplos`).
- Crash de arranque encontrado en el QA (SIGSEGV en torch MPS por doble import del
  módulo con `python -m divefy.chat`): arreglado moviendo el arranque a
  `divefy/__main__.py`, con test de regresión en `tests/unit/test_entrypoint.py`.
