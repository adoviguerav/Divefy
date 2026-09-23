# Plan: Fase 8c — Precarga de modelos, streaming simulado y scores en fuentes

**Status**: archived (verified 2026-09-23)
**Fuente**: conversación con Adolfo 2026-09-23 (QA de 8b: "el modelo tarda mucho en
cargarse… déjalo cargado para que la primera pregunta ya vaya normal"; "no hay
streaming"; scores aprobados con permiso para tocar código de F5/F6) · explore de
2026-09-23 (choque streaming/guardarraíl, scores descartados en `rerank()`/`retrieve()`).

## Goal

Al terminar: (1) la primera pregunta tarda lo mismo que la segunda, porque el servidor
carga embedder, BM25, reranker y modelo local al arrancar y al aplicar una config
nueva, y la página avisa "cargando modelos…" mientras tanto; (2) la respuesta aparece
escribiéndose (efecto máquina de escribir sobre el texto YA verificado por el
guardarraíl — nunca tokens crudos del modelo); (3) cada fuente muestra su score y de
qué tipo es (rerank / RRF / distancia densa).

## Findings

- **Qué se carga en la primera pregunta** (todo cacheado a nivel de proceso, así que
  solo se paga una vez): embedder ([`p4_indexing.py:146-154`](../../../src/divefy/pipeline/p4_indexing.py#L146-L154),
  `LazyEmbeddings`), índice BM25 ([`p5_retrieve.py:114`](../../../src/divefy/pipeline/p5_retrieve.py#L114),
  `_BM25_CACHE`), reranker ([`p6_rerank.py:14-25`](../../../src/divefy/pipeline/p6_rerank.py#L14-L25),
  `lru_cache`, ~36 s) y modelo MLX si toca ([`mlx_backend.py:17-26`](../../../src/divefy/llm/mlx_backend.py#L17-L26),
  `_mlx_load`). Una llamada real a `retrieve(config, "…")` dispara los tres primeros.
- **Streaming real choca con el guardarraíl** (`p7_generate.py:111-123` necesita la
  respuesta completa antes de aprobarla): por eso es simulado, en el navegador.
- **Los scores existen y se tiran**: `p6_rerank.rerank()` calcula el score del
  cross-encoder y devuelve solo ids; `rrf_fuse()` calcula el score RRF y devuelve solo
  ids; el lado denso usa `similarity_search_by_vector` (sin score) aunque Chroma ofrece
  `similarity_search_by_vector_with_relevance_scores` (mismo query, misma ordenación,
  devuelve además la distancia).
- **Radio de impacto de `retrieve()`**: 2 llamadores en producción + 5 ficheros de test
  (2 congelados). Se evita tocando nada de eso: funciones nuevas `*_scored` y las
  antiguas pasan a ser envoltorios que devuelven solo ids — comportamiento byte a byte
  igual.

## Decisions

- **Precarga = una función `warm_up(model, config)` en `chat.py`** que hace un
  `retrieve` real con una query fija y, si el modelo es MLX, `_mlx_load`. La llama
  `main()` en un hilo al arrancar (config por defecto) y la página vía `POST
  /api/warmup {model, config}` al cargar y tras *Aplicar*. Un `threading.Lock` compartido
  con `/api/chat`: una pregunta que llegue mientras se carga espera, no dispara una
  segunda carga.
- **Streaming simulado en el navegador**: el JS recibe la respuesta completa y la va
  pintando por caracteres (unos 400 caracteres/segundo, ajustable con una constante).
  Cero cambios en servidor.
- **Scores aditivos, sin romper F5/F6**: `rerank_scored`, `rrf_fuse_scored`,
  `retrieve_scored` nuevas; `rerank`, `rrf_fuse`, `retrieve` = ids de las nuevas. El
  tipo de score sale de la config: rerank → `"rerank"`, híbrida sin rerank → `"rrf"`,
  densa → `"distancia"` (Chroma devuelve distancia: menor = mejor; la página lo dice).
  `p7_generate._fetch_chunks` añade `score` y `score_kind` a cada chunk.
- **Nada de esto cambia el orden de los chunks** ni el texto de la respuesta: los
  resultados del grid siguen siendo comparables.

## Context

- [`p5_retrieve.py:57-79,117-160`](../../../src/divefy/pipeline/p5_retrieve.py) —
  `rrf_fuse`, `dedup_to_chunk_ids`, `retrieve` (donde nacen los `*_scored`).
- [`p6_rerank.py:28-36`](../../../src/divefy/pipeline/p6_rerank.py#L28-L36) — `rerank`.
- [`p7_generate.py:72-81`](../../../src/divefy/pipeline/p7_generate.py#L72-L81) —
  `_fetch_chunks`, donde el score entra al `Answer`.
- [`api.py`](../../../src/divefy/api.py), [`chat.py`](../../../src/divefy/chat.py),
  [`static/index.html`](../../../src/divefy/static/index.html) — 8b, base de todo esto.
- Aviso: `dedup_to_chunk_ids` conserva la MEJOR posición de cada padre HyPE; la
  versión con scores debe conservar el MEJOR score (el primero visto), no el último.

## Acceptance contract

- [ ] `p6_rerank.rerank_scored(query, candidates, k)` devuelve `k` pares `(id, score)`
      ordenados por score descendente, y `rerank(...)` devuelve exactamente sus ids en
      el mismo orden (con el cross-encoder sustituido por un fake que puntúa por
      longitud del texto) — checked by:
      `tests/acceptance/test_p8c_scores.py::TestRerankScored::test_scored_y_wrapper_coinciden`
- [ ] `p5_retrieve.rrf_fuse_scored([...])` devuelve `(id, score)` con `score ==
      Σ 1/(60+rank)` calculado a mano para un caso de 2 rankings, y `rrf_fuse` devuelve
      esos mismos ids en el mismo orden — checked by:
      `tests/acceptance/test_p8c_scores.py::TestRrfScored::test_score_rrf_a_mano`
- [ ] `p7_generate.answer(...)` con `p5_retrieve.retrieve_scored` sustituido por un
      fake que devuelve `[("c1", 0.9), ("c2", 0.4)]` y la colección/LLM falsos: cada
      chunk del `Answer` lleva `score` (0.9 / 0.4) y `score_kind == "rerank"` cuando la
      config lleva rerank — checked by:
      `tests/acceptance/test_p8c_scores.py::TestAnswerScores::test_chunks_llevan_score_y_tipo`
- [ ] `POST /api/warmup {model, config}` con `chat.warm_up` sustituido por un fake
      devuelve 200 y el fake recibe ese `model` y una `RetrievalConfig` con esa config;
      con body inválido devuelve 400 sin llamar — checked by:
      `tests/acceptance/test_p8c_scores.py::TestWarmup::test_endpoint_llama_warm_up`
- [ ] `chat.warm_up("qwen4b", RECETA_GANADORA)` con `p5_retrieve.retrieve` y
      `llm._mlx_load` sustituidos por fakes llama a ambos exactamente una vez; con
      `"haiku45"` llama a `retrieve` y NO a `_mlx_load` — checked by:
      `tests/acceptance/test_p8c_scores.py::TestWarmup::test_warm_up_carga_lo_que_toca`
- [ ] `GET /` sirve una página cuyo JS contiene la lógica de escritura progresiva
      (presencia de la constante `CHARS_PER_SECOND` en el HTML) — checked by:
      `tests/acceptance/test_p8c_scores.py::TestStreaming::test_pagina_tiene_escritura_progresiva`
- [ ] Tests congelados de F5, F6, F7, 8a y 8b siguen en verde — checked by: suite completa
- [ ] QA manual de Adolfo: la primera pregunta tras arrancar va rápida; la respuesta se
      ve escribiéndose; las fuentes muestran score y tipo — checked by: Adolfo

Comando de gate: `uv run pytest tests/acceptance/test_p8c_scores.py tests/acceptance/test_p8b_web.py tests/acceptance/test_p8_chat.py -q`

## Out of scope

- Streaming real token a token (incompatible con el guardarraíl).
- Umbral de score para abstener (P1 del PRD, sin cambios).
- Medir con/sin condensador — eliminado.

## Interfaces

```python
# p6_rerank.py
def rerank_scored(query: str, candidates: list[tuple[str, str]], k: int) -> list[tuple[str, float]]: ...
# p5_retrieve.py
def rrf_fuse_scored(rankings: list[list[str]], k_rrf: int = K_RRF) -> list[tuple[str, float]]: ...
def retrieve_scored(config: RetrievalConfig, query: str, query_vector=None) -> list[tuple[str, float]]: ...
def score_kind(config: RetrievalConfig) -> str: ...   # "rerank" | "rrf" | "distancia"
# chat.py
def warm_up(model: str, config: RetrievalConfig = RECETA_GANADORA) -> None: ...
# api.py
# POST /api/warmup  {model, config?} -> 200 {"ok": true} | 400 {"error": ...}
```

## Tasks

1. **UPDATE** `p6_rerank.py`, `p5_retrieve.py` — `*_scored` + envoltorios.
   VALIDATE: `uv run pytest tests/acceptance/test_p5_retrieval.py tests/acceptance/test_p6_rerank.py tests/unit/test_p5_retrieve_core.py tests/unit/test_p6_rerank_core.py -q`
2. **UPDATE** `p7_generate.py` — `_fetch_chunks` con `score`/`score_kind`.
   VALIDATE: `uv run pytest tests/acceptance/test_p7_generacion.py tests/acceptance/test_p8c_scores.py -q -k "Scores or Rrf or Rerank"`
3. **UPDATE** `chat.py` — `warm_up` + lock; `main()` precarga en hilo.
   **UPDATE** `api.py` — `POST /api/warmup`; `/api/chat` bajo el mismo lock.
   VALIDATE: `uv run pytest tests/acceptance/test_p8c_scores.py -q -k Warmup`
4. **UPDATE** `static/index.html` — estado "cargando modelos…", llamada a warmup al
   cargar y tras Aplicar, escritura progresiva, score y tipo en cada fuente.
   VALIDATE: gate completo + prueba en navegador (Chrome DevTools) + `uv run pytest -q`.

## Notes

- **Streaming: opción A (simulado) confirmada por Adolfo** tras ver las dos opciones
  (real por frases con buffer, como en voz/NeMo Guardrails, vs. simulado sobre el texto
  ya verificado). B queda como posible cambio futuro si la espera con modelo local molesta.
- **Un test unitario de andamiaje adaptado** (`tests/unit/test_p6_rerank_core.py::
  test_retrieve_widens_to_n_candidates_when_rerank_on`): su colección falsa exponía
  `similarity_search_by_vector` y su fake apuntaba a `rerank`; ahora exponen
  `similarity_search_by_vector_with_relevance_scores` y `rerank_scored`. La aserción
  (N candidatos llegan al reranker) no cambia. Los tests de aceptación congelados de F5,
  F6 y F7 pasan sin tocar.
- **Leyenda de scores en modo dev** (petición de Adolfo): bajo "Fuentes" se explica el
  tipo de score de esa respuesta (rerank / RRF / distancia) y hacia dónde es mejor.
- **`DEFAULT_MODEL` vive en `chat.py`** y `api.py` lo lee, para que la precarga de
  arranque y el valor por defecto de la página no diverjan.
- **Añadido a petición de Adolfo (2026-09-23)**: 4 preguntas de ejemplo en la pantalla
  vacía (clic → se envía), servidas en `GET /api/options` como `ejemplos`. Frescas, no
  sacadas del golden. Fuera del contrato original; probado en navegador.
- **Crash en el QA de Adolfo (2026-09-23) — causa raíz y arreglo**: 4 `SIGSEGV` en
  `libtorch` (MPS, `MetalShaderLibrary`, caché de shaders no segura entre hilos) con
  dos hilos dentro de torch a la vez (informes en `~/Library/Logs/DiagnosticReports/`).
  Causa: `python -m divefy.chat` cargaba `chat.py` dos veces (`__main__` + `divefy.chat`
  importado por `api.py`) → dos `LOCK` distintos → la precarga de arranque y el
  `/api/warmup` de la página cargaban el reranker en paralelo ("Loading weights" ×2).
  Arreglo estructural: el arranque se mueve a `divefy/__main__.py` (`python -m divefy`);
  `chat.py` queda como librería pura y ya no puede ejecutarse como script. Regresión
  cubierta en `tests/unit/test_entrypoint.py`. README actualizado.
- **Probado en navegador** con fakes: precarga al cargar y tras *Aplicar* (Enviar
  bloqueado + "Cargando modelos…"), escritura progresiva, score y leyenda en fuentes.
