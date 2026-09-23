# Plan: Fase 8b — Chat web local (HTML/CSS/JS sencillo, botones, LangSmith)

**Status**: archived (verified 2026-09-23)
**Fuente**: PRD §7 Fase 8 enmendado 2026-09-23 (Textual → interfaz web local, decisión
de Adolfo) · `phase-8-chat-cli` (archivado; `run_turn` es la base) · conversación con
Adolfo 2026-09-23 ("una UI que utilizaría una persona normal, minimalista"; aprobado con
"hazlo").

**Historia**: la primera versión de este plan era una TUI con Textual, siguiendo el PRD
al pie de la letra. Adolfo la tiró antes de escribir código: una persona normal no usa
un terminal. Queda aquí para que conste el porqué del cambio.

## Goal

Al terminar, `uv run python -m divefy.chat` levanta un servidor local y abre en el
navegador una página de chat minimalista: hilo de conversación, caja de texto, botón
enviar, botón *Nueva conversación*. Un interruptor discreto "modo dev" muestra además
las fuentes de cada respuesta (trozos recuperados) y un panel de configuración con
selectores (modelo y receta) y botón *Aplicar*. Cada turno queda trazado en LangSmith.
La lógica de chat (`run_turn`, condensador, guardarraíl) no cambia: la web la envuelve.

## Findings

- **Servidor: stdlib** (`http.server.ThreadingHTTPServer`), cero dependencias nuevas.
  `uv.lock` tiene `uvicorn` transitivo pero ni `starlette` ni `fastapi` ni `flask`, así
  que no hay framework web "ya instalado" que aprovechar; para un endpoint JSON y un
  HTML estático, stdlib basta. Un solo usuario local: sin auth, sin CORS, escucha en
  `127.0.0.1`.
- **`Answer.chunks` ya trae id/texto/metadata** ([`p7_generate.py:53-58`](../../../src/divefy/pipeline/p7_generate.py#L53-L58)):
  el panel de fuentes no necesita nada nuevo del pipeline (scores → Fase 8c).
- **Cambiar receta al vuelo solo entre lo ya indexado**: 34 colecciones `.complete` en
  `data/chroma/`. Una combinación no indexada ya falla con `RuntimeError` claro en
  [`p5_retrieve.py:122-128`](../../../src/divefy/pipeline/p5_retrieve.py#L122-L128) —
  se muestra ese mensaje en la página, no se duplica validación.
- **`run_turn` fija `RECETA_GANADORA` dentro** ([`chat.py:20-28`](../../../src/divefy/chat.py#L20-L28)):
  para cambiar receta hay que sacar la config a parámetro (ver Interfaces).
- **LangSmith**: `@traceable` envuelve cualquier función; sin `LANGSMITH_TRACING` es un
  no-op. Hoy no hay wiring en el repo.
- **Las llamadas tardan segundos** (API) o decenas la primera vez con modelo local
  (carga ~36s): la página muestra "pensando…" y deshabilita enviar mientras espera.

## Decisions

- **Web local en vez de terminal** (Adolfo, 2026-09-23). HTML/CSS/JS en un único
  fichero estático, sin build, sin npm, sin framework JS.
- **Botones, no comandos** (Adolfo): *Nueva conversación*, *Aplicar* (config), y un
  interruptor *modo dev* que muestra/oculta fuentes y configuración.
- **Estilo minimalista** (Adolfo): skill `minimalist-ui` como guía visual.
- **Solo grupo 1 en esta pasada**: streaming simulado y scores → `phase-8c` tras su QA.
  Medir con/sin condensador → eliminado.
- **Cambiar modelo o receta vacía la memoria** (aplicar = nueva conversación).
- **LangSmith**: `run_turn` con `@traceable`; `conversation_id` (uuid, se renueva al
  resetear) como metadata para agrupar turnos. Adolfo pone la clave en `.env`.
- **Nada cambia en el pipeline**: `p7_generate`, `p8_condense`, `p5_retrieve` intactos.

## Context

- Leer antes de implementar: [`chat.py`](../../../src/divefy/chat.py) (`run_turn`),
  [`p7_generate.py:53-58`](../../../src/divefy/pipeline/p7_generate.py#L53-L58) (`Answer`),
  [`config.py`](../../../src/divefy/config.py) (`*_VALUES`, `RECETA_GANADORA`),
  [`llm/__init__.py:15-18`](../../../src/divefy/llm/__init__.py#L15-L18) (claves de modelo).
- Patrón: la lógica del turno sigue en `run_turn` (pura, con fakes); el servidor solo
  serializa a JSON y la página solo pinta.
- Aviso de seguridad (trust boundary): el body JSON del POST se valida (campos y tipos)
  antes de tocar `run_turn`; la respuesta se inserta en el DOM como texto, nunca como
  HTML (sin `innerHTML` con contenido del modelo).

## Acceptance contract

Tests contra el servidor real levantado en un hilo en un puerto libre, con `run_turn`
sustituido por un fake (sin red, sin modelos).

- [ ] `GET /` devuelve 200, `text/html`, y el HTML contiene la caja de texto, el botón
      de enviar y el botón de nueva conversación — checked by:
      `tests/acceptance/test_p8b_web.py::TestPagina::test_get_raiz_sirve_la_pagina`
- [ ] `POST /api/chat` con `{"pregunta": "...", "historial": [], "model": "haiku45"}`
      devuelve 200 y JSON con `respuesta` (la del fake), `historial` (con el par nuevo
      al final) y `chunks` (lista con `id`, `texto`, `metadata` del `Answer` del fake) —
      checked by: `tests/acceptance/test_p8b_web.py::TestTurno::test_post_turn_devuelve_respuesta_historial_y_chunks`
- [ ] `POST /api/chat` con el `historial` de un turno anterior pasa ese historial al fake
      (memoria vive en el cliente, el servidor no guarda estado) — checked by:
      `tests/acceptance/test_p8b_web.py::TestTurno::test_historial_viaja_de_ida_y_vuelta`
- [ ] `POST /api/chat` con `config` (`{"corpus": ..., "extras": ..., "embedding": ...,
      "search": ..., "k": ..., "rerank": ...}`) hace que el fake reciba una
      `RetrievalConfig` con esos valores; sin `config` recibe `RECETA_GANADORA` —
      checked by: `tests/acceptance/test_p8b_web.py::TestConfig::test_config_llega_a_run_turn`
- [ ] `POST /api/chat` con body inválido (sin `pregunta`, o `pregunta` no string, o JSON
      roto) devuelve 400 y NO llama al fake — checked by:
      `tests/acceptance/test_p8b_web.py::TestValidacion::test_body_invalido_400_sin_llamar`
- [ ] `GET /api/options` devuelve JSON con los modelos válidos y los valores permitidos de
      cada dial de `RetrievalConfig` (lo que rellena los selectores) — checked by:
      `tests/acceptance/test_p8b_web.py::TestOpciones::test_options_lista_modelos_y_diales`
- [ ] `run_turn` está decorado con `traceable` y un turno sin `LANGSMITH_TRACING`
      completa sin error — checked by:
      `tests/acceptance/test_p8b_web.py::TestTracing::test_traceable_sin_clave_es_noop`
- [ ] Los 4 tests de `tests/acceptance/test_p8_chat.py` siguen en verde — checked by:
      esos mismos tests
- [ ] QA manual de Adolfo en el navegador: conversación con follow-up, modo dev con
      fuentes, cambio de modelo desde el panel, trace visible en LangSmith — checked by:
      Adolfo

Comando de gate: `uv run pytest tests/acceptance/test_p8b_web.py tests/acceptance/test_p8_chat.py -q`

## Out of scope

- Streaming simulado y scores en fuentes → `phase-8c`.
- Medir con/sin condensador — eliminado.
- Multiusuario, auth, HTTPS, despliegue: es local, un usuario.
- Indexar colecciones nuevas desde la UI.

## Interfaces

```python
# src/divefy/chat.py
def run_turn(
    historial: list[tuple[str, str]],
    model: str,
    pregunta: str,
    config: RetrievalConfig = RECETA_GANADORA,
) -> tuple[str, list[tuple[str, str]]]: ...
# Compatible con test_p8_chat.py. El Answer completo (chunks) se expone con
# `run_turn_full(...) -> tuple[Answer, list[tuple[str,str]]]`; run_turn lo envuelve.

# src/divefy/api.py
def make_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer: ...
# port=0 → puerto libre (los tests lo leen de server.server_address).
# Rutas: GET / (html) · GET /api/options (json) · POST /api/chat (json).
```

## Tasks

1. **UPDATE** `src/divefy/chat.py` — `run_turn_full` + `run_turn` con `config`
   opcional; `@traceable` sobre `run_turn_full`.
   VALIDATE: `uv run pytest tests/acceptance/test_p8_chat.py -q` (4/4).
2. **CREATE** `src/divefy/api.py` — `make_server` con las tres rutas, validación del
   body, errores como JSON `{"error": ...}` con 400/500.
   VALIDATE: `uv run pytest tests/acceptance/test_p8b_web.py -q`
3. **CREATE** `src/divefy/static/index.html` — página única (CSS y JS inline),
   minimalista, con hilo, caja, enviar, nueva conversación, interruptor modo dev,
   panel de fuentes y panel de configuración.
   VALIDATE: abrirla con el servidor y probar el flujo en el navegador (Chrome
   DevTools MCP), fake de `run_turn` no hace falta si hay `.env`.
4. **UPDATE** `src/divefy/chat.py` — `main()` levanta el servidor y abre el navegador
   (`webbrowser.open`); `.env.example` con las variables de LangSmith.
   VALIDATE: comando de gate + `uv run pytest -q` (sin regresiones).

## Notes

- **`.env.example` → README** (2026-09-23): el plan decía documentar las variables de
  LangSmith en `.env.example`; no existe ese fichero en el repo y el hook de ficheros
  protegidos bloquea patrones `.env*`. Se documentaron en la tabla de variables del
  `README.md` (Quick start), que además no existía y hacía falta.
- **Probado en navegador real** (Chrome DevTools MCP) con `run_turn_full` sustituido
  por un fake: turno, follow-up con memoria, abstención, modo dev con fuentes
  desplegables, cambio de modelo/receta con *Aplicar* (resetea la conversación). Sin
  errores de consola tras añadir `<link rel="icon" href="data:,">` (404 del favicon).
- **Renombrado por claridad (Adolfo, 2026-09-23)**: `web.py` → `api.py`,
  `POST /turn` → `POST /api/chat`, `GET /options` → `GET /api/options`,
  `Handler` → `ApiHandler`, `_parse_turn` → `_parse_chat_request`. Enmienda abierta
  sobre `test_p8b_web.py` (Adolfo desbloqueó el hook): solo cambian el módulo importado
  y las dos rutas; ninguna aserción cambia. Re-verificado 11/11 y suite 208/208.
- El bucle Rich del CLI desaparece: `python -m divefy.chat` ahora levanta el servidor
  web y abre el navegador (`--port`, `--no-browser`). `run_turn` se conserva intacto
  (tests de `phase-8-chat-cli` en verde).
