# Verify report: phase-8b-chat-tui

**Overall verdict: ACCEPTED** (2026-09-23)

## Gate (tal cual en el plan)

```
uv run pytest tests/acceptance/test_p8b_web.py tests/acceptance/test_p8_chat.py -q
11 passed
```

Suite completa: `uv run pytest -q` → **216 passed, 11 deselected**. Sin regresiones
(línea base al empezar la fase: 201).

## Veredicto por criterio

| # | Criterio | Test | Veredicto |
|---|---|---|---|
| 1 | `GET /` sirve la página con campo, enviar y nueva conversación | `TestPagina::test_get_raiz_sirve_la_pagina` | PASS |
| 2 | `POST /api/chat` devuelve respuesta, historial y chunks | `TestTurno::test_post_turn_devuelve_respuesta_historial_y_chunks` | PASS |
| 3 | El historial viaja ida y vuelta, servidor sin estado | `TestTurno::test_historial_viaja_de_ida_y_vuelta` | PASS |
| 4 | `config` llega como `RetrievalConfig`; sin config → `RECETA_GANADORA` | `TestConfig::test_config_llega_a_run_turn` | PASS |
| 5 | Body inválido → 400 sin llamar al modelo | `TestValidacion::test_body_invalido_400_sin_llamar` | PASS |
| 6 | `GET /api/options` lista modelos y diales | `TestOpciones::test_options_lista_modelos_y_diales` | PASS |
| 7 | `run_turn_full` con `@traceable`, no-op sin clave | `TestTracing::test_traceable_sin_clave_es_noop` | PASS |
| 8 | Los 4 tests de `test_p8_chat.py` siguen en verde | esos tests | PASS |
| 9 | QA manual en navegador (follow-up, fuentes, cambio de modelo, LangSmith) | Adolfo | PASS (confirmado por Adolfo 2026-09-23: "funcionó muy bien la última ejecución") |

## Regresiones

Ninguna.

## Notas

- Los nombres de módulo y rutas se renombraron durante la implementación (`web.py` →
  `api.py`, `/turn` → `/api/chat`, `/options` → `/api/options`) con enmienda abierta
  sobre el test congelado, desbloqueada por Adolfo; el contrato del plan ya refleja
  los nombres finales.
- Durante el QA se encontró y corrigió un crash de arranque (doble import por
  `python -m divefy.chat`); el detalle y el arreglo están en las Notes de `phase-8c`.
