# Plan: Fase 8 (recorte) — Chat CLI mínimo funcional

**Status**: archived (verified 2026-09-23)
**Fuente**: PRD §7 Fase 8 (`PRD.md:354-374`, 🔒) · conversación con Adolfo 2026-09-20
(recorte: solo el loop de chat con memoria, sin Textual/dos pantallas/comandos dev/
streaming/LangSmith todavía — eso queda como resto de Fase 8) · explore del repo
2026-09-20.

## Goal

Al terminar, `chat.py` es un CLI ejecutable que mantiene una conversación real de
varios turnos: pregunta → condensador (resuelve follow-ups con la ventana de los
últimos 3 pares) → retrieval → generación → guardarraíl numérico → respuesta pintada
en terminal. Reutiliza `p7_generate.answer()` sin tocarlo. La config de retrieval por
defecto es la receta ya medida como mejor; el modelo de generación se elige por flag.
Sin Textual, sin comandos `/fuentes /config /reset`, sin streaming, sin LangSmith —
esas piezas completan Fase 8 en una pasada posterior.

## Findings

(explore 2026-09-20 sobre el repo, evidencia citada)

- [`chat.py:1-2`](../../../src/divefy/chat.py#L1-L2) — solo un docstring, sin código.
- [`p7_generate.py:97-132`](../../../src/divefy/pipeline/p7_generate.py#L97-L132) —
  `answer(retrieval_config, model, pregunta) -> Answer` hace retrieval + prompt +
  generación + guardarraíl + abstención. `Answer` es `frozen` con
  `pregunta, chunks, respuesta, abstencion`. El chat es, en esencia, un bucle que
  llama a esto y pinta `respuesta`.
- [`config.py:14-26`](../../../src/divefy/config.py#L14-L26) — `RetrievalConfig` no
  tiene defaults para corpus/extras/embedding/search/k.
- [`llm/__init__.py:19-27,121-133`](../../../src/divefy/llm/__init__.py#L19-L133) —
  `generate(model, system, user)` acepta `sonnet5 | haiku45 | qwen9b | qwen4b`.
- [`EXPERIMENTOS.md:210-212`](../EXPERIMENTOS.md#L210-L212) — receta ganadora medida:
  `combined-512-contextual-qwen8b-hibrida-k10-rerank` (hit_rate 0.9881, MRR 0.815).
  Confirmada por Adolfo como default para el chat (2026-09-20).
- [`p3_enrich.py:1-46`](../../../src/divefy/pipeline/p3_enrich.py#L1-L46) — patrón de
  cliente Gemini de la casa: `genai.Client()` perezoso a nivel de módulo, `load_dotenv()`,
  modelo `gemini-3.1-flash-lite` ya probado y barato (`$0.25/$1.50` por millón). El
  condensador reutiliza este patrón — cero dependencia nueva (`google-genai` ya está en
  `pyproject.toml:9`).
- `rich` está resuelto en `uv.lock` (transitivo, vía Textual/otros) pero no es
  dependencia directa en `pyproject.toml` — hay que declararlo si `chat.py` lo importa
  directamente.
- Convención de módulos de pipeline: `pN_nombre.py` (`p1_ingest.py` … `p7_guardrail.py`)
  — el condensador de Fase 8 encaja como `pipeline/p8_condense.py`.
- Convención de prompts versionados: `prompts/generation_v2.txt`, `prompts/judge_v3.txt`
  — el condensador necesita su propio `prompts/condense_v1.txt`.

## Decisions

- **Retrieval config por defecto**: constante `RECETA_GANADORA` en `config.py`
  (`combined-512-contextual-qwen8b-hibrida-k10-rerank`) — Adolfo, 2026-09-20: "si hay
  receta ganadora... yo lo metería en algún sitio como default en config".
- **Memoria: condensador real, no concatenación naive** — Adolfo revirtió su primera
  idea (memoria naive sin condensar) al ver que un follow-up ambiguo llega roto al
  retrieval sin condensar. Ventana de 3 pares (mismo tamaño ya cerrado en el PRD para
  el condensador de Fase 8, así una futura comparación con/sin condensador no cambia
  dos variables a la vez).
- **Modelo del condensador**: reutilizar el patrón de cliente Gemini de `p3_enrich.py`,
  con `gemini-3.1-flash-lite` (confirmado por Adolfo, 2026-09-20) — el mismo modelo ya
  probado y barato que usa el enriquecedor de Fase 3.
- **UI: Rich, no Textual, no web** — Adolfo delegó la elección ("usa algo de front
  normal, no te fumes con cosas raras... me da igual"). Rich porque no añade músculo
  nuevo real (ya resuelto transitivamente) y porque Textual (que sí llegará después)
  se apoya en Rich — no hay retrabajo. Se descarta HTML/CSS/JS: el PRD ya fija esta
  fase como CLI y lista "Web UI" como P1 post-MVP (`PRD.md:98`), no algo a mezclar aquí.
- **Modelo de generación**: flag CLI (`--model`), no hardcode — son intercambiables por
  diseño en `llm.generate`.
- **Fuera de esta pasada** (resto de Fase 8, sin fecha): Textual, dos pantallas
  (modo buceo/dev), comandos `/fuentes /config /reset`, streaming, trazas LangSmith,
  medir con/sin condensador.

## Context

- Leer antes de implementar:
  - [`p7_generate.py`](../../../src/divefy/pipeline/p7_generate.py) completo — la
    única puerta de generación, no se toca.
  - [`p3_enrich.py:34-46`](../../../src/divefy/pipeline/p3_enrich.py#L34-L46) — patrón
    de cliente Gemini perezoso a copiar para el condensador.
  - [`config.py`](../../../src/divefy/config.py) — dónde añadir `RECETA_GANADORA`.
  - [`llm/__init__.py`](../../../src/divefy/llm/__init__.py) — claves de modelo válidas
    para el flag `--model`.
  - [`PRD.md:354-374`](../PRD.md#L354-L374) — decisiones cerradas de Fase 8 completa,
    para no contradecirlas sin querer al construir el recorte.
- Patrón a seguir: cliente perezoso a nivel de módulo (nunca se construye al importar,
  para que los tests con fakes no necesiten `GEMINI_API_KEY` real) — igual que
  `_cliente()` en `p3_enrich.py:41-46` y `_cliente(model_id)` en `llm/__init__.py:38-42`.
- Prompt del condensador: fichero nuevo `prompts/condense_v1.txt`, versionado igual que
  `generation_v2.txt`/`judge_v3.txt` — instrucción: dados los últimos N pares + la
  pregunta nueva, devolver una única query autónoma de retrieval, sin resolver la
  pregunta ni añadir información.
- Variable de entorno: `GEMINI_API_KEY` ya se usa en el proyecto (`judge.py:91-94`,
  `p3_enrich.py`) — el condensador la reutiliza, no hace falta ninguna nueva.

## Acceptance contract

**Enmendado 2026-09-23** (ver `## Notes`): el contrato original nombraba rutas
`tests/unit/...` que nunca se crearon — los tests reales quedaron consolidados en un
único fichero de aceptación. Texto corregido para apuntar a lo real:

- [x] `RECETA_GANADORA` existe en `config.py` y su `.run_id` es exactamente
      `combined-512-contextual-qwen8b-hibrida-k10-rerank` — checked by:
      `tests/acceptance/test_p8_chat.py::TestRecetaGanadora::test_run_id_es_exactamente_el_string_acordado`
- [x] `p8_condense.condense(historial, pregunta)` con un cliente Gemini falso (patrón
      de fakes de la casa) recibe como mucho los últimos 3 pares de `historial` aunque
      se le pasen 5 — checked by:
      `tests/acceptance/test_p8_chat.py::TestCondenseHistorial::test_solo_envia_los_ultimos_3_pares_al_backend`
- [x] Sesión guionizada de 2 turnos con un follow-up ambiguo: en el turno 2, la query
      que llega a **`p7_generate.answer`** (no a `p5_retrieve.retrieve` directamente —
      `answer` está sustituido por un fake en este test, así que no comprueba el
      reenvío interno de `answer` a `retrieve`; eso ya lo cubre `test_p7_generacion.py`
      de Fase 7) es la condensada, no la pregunta suelta — checked by:
      `tests/acceptance/test_p8_chat.py::TestChatRunTurnCondensa::test_turno_2_usa_query_condensada_no_texto_ambiguo`
- [x] `chat.py` es ejecutable (`uv run python -m divefy.chat --model haiku45`), acepta
      preguntas por stdin en bucle, imprime la respuesta con Rich, y termina limpio con
      `/salir` o Ctrl+C — checked by: sesión manual real de Adolfo (confirmada
      2026-09-22 — no automatizable sin gastar tokens de verdad contra la API/el
      modelo local)

Comando de gate: `uv run pytest tests/acceptance/test_p8_chat.py -q`

## Out of scope

- Textual, modo buceo/modo dev, comandos `/fuentes /config /reset`.
- Streaming de la respuesta.
- Trazas LangSmith.
- Web UI (HTML/CSS/JS) — explícitamente P1 post-MVP en el PRD.
- Medir con/sin condensador (próxima tarea, no esta).

## Interfaces

```python
# src/divefy/pipeline/p8_condense.py
def condense(historial: list[tuple[str, str]], pregunta: str) -> str:
    """Últimos hasta-3 pares (pregunta, respuesta) + pregunta nueva -> query
    autónoma de retrieval. historial ya viene recortado por el llamador o se
    recorta aquí (a decidir en implementación, sin cambiar el contrato)."""
```

## Tasks

1. **UPDATE** `pyproject.toml` — añadir `rich` como dependencia directa.
   VALIDATE: `uv sync && uv run python -c "import rich"`
2. **UPDATE** `src/divefy/config.py` — añadir constante `RECETA_GANADORA`.
   VALIDATE: `uv run python -c "from divefy.config import RECETA_GANADORA; print(RECETA_GANADORA.run_id)"`
   imprime `combined-512-contextual-qwen8b-hibrida-k10-rerank`.
3. **CREATE** `src/divefy/prompts/condense_v1.txt` — instrucción del condensador.
4. **CREATE** `src/divefy/pipeline/p8_condense.py` — `condense()` con cliente Gemini
   perezoso (patrón de `p3_enrich.py`).
   VALIDATE: `uv run pytest tests/unit/test_p8_condense.py -q`
5. **CREATE** `src/divefy/chat.py` — bucle: input → `condense()` con ventana de 3 pares
   → `p7_generate.answer(RECETA_GANADORA, model, query_condensada)` → pintar con Rich →
   guardar el par en el historial.
   VALIDATE: `uv run pytest tests/unit/test_chat.py -q`, luego sesión manual de Adolfo.

## Notes

- **Desviación de proceso (2026-09-23, hallada en `/verify`, corregida por Adolfo)**:
  los tests de aceptación se escribieron todos en un único fichero
  (`tests/acceptance/test_p8_chat.py`) en vez de los tres ficheros `tests/unit/...`
  que el contrato original nombraba, y esa desviación no se anotó aquí en su momento
  — debía haberlo estado. Además, el criterio del follow-up (#3) verifica la costura
  `p7_generate.answer` en vez de `p5_retrieve.retrieve` como decía el texto original.
  Adolfo decidió (opción b de `/verify`): el contrato estaba mal escrito, se corrige el
  texto para reflejar lo real en vez de tocar los tests congelados.
