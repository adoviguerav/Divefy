# Verify report: phase-8-chat-cli

**Overall verdict inicial: NOT ACCEPTED (contrato desalineado con lo implementado — no
era un fallo de código)** — ver detalle abajo. Adolfo eligió la opción b) del veredicto
(el contrato estaba mal escrito): se corrigió el texto del contrato en `plan.md` para
apuntar a los tests reales (`## Notes` del plan). Re-verificado tras la corrección:

```
uv run pytest tests/acceptance/test_p8_chat.py -q  →  4 passed
uv run pytest -q (suite completa)                   →  201 passed, 11 deselected
```

**Overall verdict final: ACCEPTED.**

## Comando de gate del contrato, tal cual está escrito

```
uv run pytest tests/unit/test_config.py tests/unit/test_p8_condense.py tests/unit/test_chat.py -q
```

Resultado real:

```
ERROR: file or directory not found: tests/unit/test_p8_condense.py
```

Ninguno de los tres ficheros (`tests/unit/test_config.py`, `tests/unit/test_p8_condense.py`,
`tests/unit/test_chat.py`) existe. Los tests de esta fase se escribieron en un único
fichero, `tests/acceptance/test_p8_chat.py`, y esa desviación **no quedó registrada en
`## Notes`** del plan como pide el procedimiento de `/implement` — es un defecto del
proceso, no solo del contrato.

## Veredicto por criterio

| # | Criterio | Test nombrado en el contrato | Veredicto | Evidencia |
|---|---|---|---|---|
| 1 | `RECETA_GANADORA.run_id == "combined-512-contextual-qwen8b-hibrida-k10-rerank"` | `tests/unit/test_config.py::test_receta_ganadora_run_id` | **MISSING** | el fichero no existe; el test real que sí cubre esto (`tests/acceptance/test_p8_chat.py::TestRecetaGanadora::test_run_id_es_exactamente_el_string_acordado`) pasa: `PASSED` |
| 2 | `condense()` solo usa los últimos 3 pares de historial | `tests/unit/test_p8_condense.py::test_ventana_maximo_3_pares` | **MISSING** | el fichero no existe; el real (`TestCondenseHistorial::test_solo_envia_los_ultimos_3_pares_al_backend`) pasa: `PASSED` |
| 3 | El follow-up llega **condensado a `p5_retrieve.retrieve`** en el turno 2 | `tests/unit/test_chat.py::test_follow_up_se_condensa_antes_de_buscar` | **MISSING** | el fichero no existe; además el test real (`TestChatRunTurnCondensa`) verifica la query condensada en la llamada a **`p7_generate.answer`**, no en `p5_retrieve.retrieve` como dice literalmente el criterio — es una costura distinta a la escrita en el contrato (funcionalmente relacionada, porque `answer()` reenvía esa misma query a `retrieve()`, pero eso no lo comprueba este test: `p7_generate.answer` está sustituido por un fake) |
| 4 | `chat.py` ejecutable, bucle por stdin, Rich, `/salir`/Ctrl+C | sesión manual de Adolfo | **UNVERIFIABLE** (por mí) | Adolfo reporta haberla corrido (`uv run python -m divefy.chat --model haiku45`) y que funcionó; no es algo que yo pueda comprobar de forma independiente — pasos exactos para repetirla: `uv run python -m divefy.chat --model haiku45`, hacer una pregunta, un follow-up ambiguo, y `/salir` |

## Suite acumulada completa

```
uv run pytest -q
201 passed, 11 deselected, 5 warnings in 38.90s
```

Sin regresiones sobre la línea base (197 passed antes de esta fase).

## Regresiones

Ninguna.

## Notas

- El contrato del plan nombra rutas de test (`tests/unit/...`) que nunca se crearon;
  la cobertura real vive en `tests/acceptance/test_p8_chat.py` con otros nombres de
  clase/test. Los 4 tests reales pasan, pero el contrato tal como está escrito no se
  puede ejecutar literalmente.
- El criterio 3 verifica una costura distinta (`p7_generate.answer`) a la nombrada en
  el contrato (`p5_retrieve.retrieve`).

## Opciones para Adolfo

```
NOT ACCEPTED — el contrato nombra tests que no existen; la cobertura real existe con
otros nombres/ruta y (criterio 3) otra costura.

a) implementación insuficiente → no aplica: los 4 tests reales pasan y cubren la
   intención de cada criterio.
b) el contrato estaba mal escrito → abrir enmienda: actualizar el texto del contrato
   en el plan para que apunte a tests/acceptance/test_p8_chat.py con los nombres
   reales, y decidir si el criterio 3 se deja verificando p7_generate.answer o se
   añade un test aparte que sí llegue hasta p5_retrieve.retrieve.
c) aceptar como deuda → marcar WAIVED con el valor medido (4/4 tests reales en verde,
   201/201 suite) y seguir.
```
