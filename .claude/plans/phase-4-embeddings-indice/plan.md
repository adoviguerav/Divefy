# Plan: Fase 4 — Embeddings e índice vectorial

**Estado**: approved
**Fuente**: PRD §7 Fase 4 · explorado y debatido con Adolfo en conversación (2026-08-24
a 2026-08-27) — incluye investigación externa sobre BGE-M3, Qwen3-Embedding, Chroma,
LangChain, y sobre metodología de búsqueda de hiperparámetros en RAG.

## Goal

Al terminar existen, indexadas: **36 colecciones Chroma reales** — los 3 valores de
corpus (`apuntes`, `manual`, `combined`) × las 3 variantes de la escalera de extras
(`base`, `contextual`, `hype`) × los 4 modelos de embeddings a medir (BGE-M3,
Qwen3-Embedding-0.6B, Qwen3-Embedding-8B, OpenAI `text-embedding-3-large`), todas con
`tope=512` (lo que ya existe en `data/processed/`). Esto deja todo listo para que Fase 5
pueda comparar corpus × extras × modelo con búsqueda densa simple y decidir con datos
qué corpus ancla el resto del barrido — **esa comparación, las etiquetas que necesita, y
la decisión en sí NO son parte de esta fase** (ver Out of scope).

## Findings

- **`data/processed/chunks.jsonl` y `enrich.jsonl` traen los dos corpus mezclados**:
  723 chunks totales (113 `apuntes`, todos `tipo=="prosa"`; 610 `manual`, de los cuales
  570 `prosa` y 40 `puntero_tabla`). `enrich.jsonl`: 683 líneas (113 de apuntes, 570 de
  manual). Ni Fase 1 ni Fase 2 ni Fase 3 filtran por corpus — procesan todo junto. El
  indexador filtra explícitamente; `corpus="combined"` significa **sin filtro** (todas
  las filas), no es un valor que exista en el campo `corpus` de los datos.
- **Por qué 36 y no 12 (solo apuntes)**: decidido con Adolfo tras revisar qué hace la
  práctica habitual en RAG/HPO — un grid completo de las 7 dimensiones del barrido
  (corpus/tope/extras/embedding/búsqueda/k/rerank) es inviable (crece exponencial,
  confirmado contra literatura de HPO en RAG — ver Sources del hilo de exploración).
  Pero hay razón concreta para sospechar que corpus SÍ interactúa con extras y con el
  modelo de embeddings — no es solo cautela genérica: (a) contextual/HyPE podrían
  ayudar más al manual (más grande, menos limpio) que a apuntes; (b) apuntes está en
  español y manual en inglés, y los 4 modelos difieren en capacidad multilingüe — un
  modelo con mejor cruce ES↔EN podría cambiar qué corpus rinde mejor. Por eso se hace
  el cruce completo de esas 3 dimensiones (3×3×4=36) en vez de fijar corpus a ciegas y
  barrer las demás una a una.
- Schema de `chunks.jsonl` verificado:
  [p2_chunking.py:14-25](../../../src/divefy/pipeline/p2_chunking.py#L14-L25) — `id`
  (string estable de contenido), `corpus`, `section_ids`, `titulo`, `tipo`, `texto`,
  `fichero`, `capitulo`, `pagina`, `pagina_fin`.
- Schema de `enrich.jsonl` verificado:
  [p3_enrich.py:172-186](../../../src/divefy/pipeline/p3_enrich.py#L172-L186) — `id`,
  `fingerprint`, `contexto` (≤100 tokens BGE-M3), `preguntas` (3-5 strings). Los
  punteros de tabla no tienen entrada aquí; apuntes no tiene punteros de tabla.
- `p3_enrich.py` construye el texto contextualizado como
  `f"{contexto}\n\n{c['texto']}"` ([p3_enrich.py:107](../../../src/divefy/pipeline/p3_enrich.py#L107))
  — este plan reutiliza exactamente ese patrón como texto a embeber para
  `contextual`/`hype`.
- `src/divefy/pipeline/p4_indexing.py` y `p4_vectorstore.py` son stubs (solo docstring).
- `pyproject.toml` no tiene `chromadb`, `langchain-chroma`, `langchain-huggingface`,
  `langchain-openai`, `sentence-transformers` — todos nuevos.
- BGE-M3 `dense_vecs` ya sale L2-normalizado de fábrica — cosine e inner-product son
  equivalentes para rankear; no hace falta normalizar a mano.
- Ventanas de contexto: BGE-M3 y Qwen3-Embedding (0.6B y 8B) llegan a 8192 tokens — muy
  por encima del chunk+contexto más grande posible.
- Dimensión por defecto: BGE-M3 = 1024; Qwen3-Embedding-0.6B = 1024 (MRL, truncable).
  Cada colección de Chroma tiene su espacio HNSW independiente — sin conflicto entre
  colecciones de distinta dimensión en el mismo directorio.
- `langchain_chroma.Chroma` puede envolver un `chromadb.PersistentClient` existente;
  `add_texts(texts, metadatas=None, embeddings=None, ...)` acepta vectores precomputados.
- `HuggingFaceEmbeddings(model_name=..., model_kwargs={"device": ...},
  encode_kwargs={"normalize_embeddings": ...})` es genérico: da solo el vector denso.
- Overhead de almacenamiento de Chroma (HNSW + SQLite) ronda 2× el crudo de los
  vectores — a este tamaño de corpus, irrelevante frente al peso del propio modelo.
- Coste de indexar el corpus combinado completo con OpenAI `text-embedding-3-large`:
  del orden de céntimos — no es una restricción real ni multiplicado por 3 corpus.

## Decisions

1. **Una sola escalera de compute, tres colecciones de store, por cada corpus.** Cada
   texto distinto se embebe una vez **por modelo** (corregido 2026-08-27, T-06: no "por
   (modelo, corpus)" — `corpus` filtra qué se indexa, no transforma el texto, así que
   `"combined"` (== apuntes ∪ manual) reutiliza los vectores ya calculados para apuntes
   y manual en vez de recomputarlos); las 3 colecciones de extras se pueblan repartiendo
   esos vectores, nunca recalculando.
2. **El chunk puro y el chunk+contexto comparten el mismo `id` de Chroma** dentro de su
   corpus — no coexisten en la misma colección. Solo las preguntas HyPE necesitan id
   propio.
3. **Id de pregunta HyPE**: `f"{chunk_id}::hype::{i}"`.
4. **Metadato `parent_chunk_id`** en cada fila de pregunta HyPE.
5. **Metadato `entry_type` (`"chunk"` | `"hype"`)** — no se reusa `tipo` (ya significa
   prosa/puntero_tabla en el schema heredado de Fase 1/2).
6. **`documents` de Chroma = texto crudo del chunk, siempre.** El `contexto` va como
   metadato propio; el texto fusionado se usa solo como input al modelo de embeddings.
7. **4 modelos**: BGE-M3, Qwen3-Embedding-0.6B, Qwen3-Embedding-8B, OpenAI
   `text-embedding-3-large`.
8. **Todo vía LangChain**: `langchain_chroma.Chroma` para escribir y leer;
   `HuggingFaceEmbeddings` para los 3 locales, `OpenAIEmbeddings` para el arm de API.
   **Excepción forzada (2026-08-27, T-07, ver Decision #20)**: la propia API pública de
   `Chroma` no soporta escribir con vectores precalculados — el objeto sigue siendo
   `langchain_chroma.Chroma` en todo momento, pero la escritura concreta pasa por su
   `._collection` (chromadb crudo) en vez de por `add_texts`.
9. **Solo vector denso de BGE-M3, sin sparse** — no tiene consumidor hoy.
10. **`hnsw:space: "cosine"` en las 36 colecciones.**
11. **El tokenizador de BGE-M3 sigue siendo la única vara de medida para "tope".**
12. **El join `chunks.jsonl` + `enrich.jsonl` vive dentro de `p4_indexing.py`.**
13. **`data/chroma/` es el directorio de persistencia**, gitignorado.
14. **`corpus` es un parámetro con 3 valores válidos: `"apuntes"`, `"manual"`,
    `"combined"`.** `"apuntes"`/`"manual"` filtran por el campo `corpus` real de los
    datos; `"combined"` significa sin filtro (no existe como valor de dato, es un
    identificador nuevo de esta fase — inglés, como el resto del código nuevo).
15. **Identificadores de código nuevo, en inglés, desde esta fase** — `p1`-`p3` no se
    tocan. Excepción: valores de datos ya definidos por fases anteriores
    (`corpus: "apuntes"|"manual"`, `tipo: "prosa"|"puntero_tabla"`, nombres de campo
    del JSON de entrada) se leen tal cual, son vocabulario heredado.
16. **Esta fase construye los 36 = 3×3×4, no solo los 12 de apuntes** (revisado
    2026-08-27, corrige el alcance original del plan). Motivo: se sospecha interacción
    real entre corpus y (extras, modelo) — ver Findings — así que hace falta el cruce
    completo de esas 3 dimensiones para que la comparación de Fase 5 tenga sentido. La
    comparación en sí, las etiquetas que necesita, y la decisión de qué corpus ancla el
    resto del barrido quedan fuera de esta fase (Fase 5).
17. **Los conteos del contrato de aceptación se derivan de los ficheros reales en el
    momento del test, nunca se hardcodean** — corrige un fallo real que Adolfo pilló en
    la primera versión de los tests (números "113"/"12" sueltos en vez de calculados
    desde `chunk_records`/`enrich_records`/`MODELS`).
18. **`puntero_tabla` no se indexa en ninguna colección, ni siquiera `base`** (corregido
    2026-08-27, T-07 — Adolfo lo pilló antes de que se ejecutara nada). `build_rows`
    filtra a `tipo=="prosa"` junto con el filtro de corpus, como único punto de entrada
    del que derivan `base`/`contextual`/`hype`. Consistente con la política ya cerrada
    del proyecto (EXPERIMENTOS.md "Descartados"): las tablas quedan fuera de
    retrieval/generación, una petición sobre una tabla es abstención + derivación al
    dispositivo certificado — indexar un chunk-puntero (sin contenido real de prosa)
    solo podría devolver un resultado inútil. Solo afecta a `manual`/`combined`
    (`apuntes` no tiene punteros de tabla); `combined` prosa = 683, que coincide
    exactamente con `len(enrich.jsonl)` — confirmación cruzada de que el filtro es
    correcto.
19. **Cada colección se recrea desde cero en cada pasada de `main()`**, usando el método
    propio de la librería `Chroma.reset_collection()` (`delete_collection()` +
    recrear, idempotente incluso si la colección no existía — NO una función propia:
    se escribió una en `p4_vectorstore.py` primero, se encontró que LangChain ya trae
    exactamente esto y se borró la propia, T-07) — corregido 2026-08-27, T-06, a
    petición de Adolfo. Motivo: `add_texts` con un id repetido hace upsert (confirmado
    en vivo), así que un chunk cuyo texto cambia mientras conserva su id ya se
    autocorregía solo; pero un chunk que se elimina o cambia de id en una fase anterior
    dejaría una fila huérfana en
    Chroma si solo se sobrescribiera. Recrear entera cada colección en cada pasada
    garantiza que siempre refleja exactamente el `chunks.jsonl`/`enrich.jsonl` actuales.
20. **La escritura NO usa `Chroma.add_texts`, usa `collection._collection.upsert(...)`
    directo** (encontrado y corregido 2026-08-27, T-07, antes de correr nada — Adolfo
    pidió revisar todo tras el fallo de T-06). Motivo: un Finding del plan original
    ("`add_texts(texts, metadatas=None, embeddings=None, ...)` acepta vectores
    precomputados") era falso — confirmado leyendo el código fuente instalado de
    `langchain_chroma`: `add_texts` SIEMPRE llama a
    `self._embedding_function.embed_documents(texts)` por su cuenta; cualquier
    `embeddings=` que se le pase cae en `**kwargs` y se ignora en silencio, sin error.
    No es solo ineficiencia — es un bug de corrección: el vector realmente guardado
    para `contextual`/`hype` habría sido el del `document` (texto crudo del chunk),
    nunca el de `embed_text` (contexto fusionado / pregunta HyPE) — Decision 6 nunca se
    habría cumplido de verdad. Confirmado en vivo con un fake `Embeddings` que lanza
    si se le llama: `collection._collection.upsert(ids=, embeddings=, documents=,
    metadatas=)` no dispara ninguna llamada de embedding y guarda el vector exacto que
    se le pasa. Sigue siendo el mismo objeto `langchain_chroma.Chroma` gestionado por
    `get_collection` — solo el método de escritura cambia (Decision 8 actualizada).
21. **Metadata completa por contrato** (añadida 2026-08-28, ejercicio de modelo de
    datos con Adolfo — contrato en [docs/modelo-datos.md](../../../docs/modelo-datos.md)):
    cada fila chunk lleva `entry_type`, `corpus`, `section_ids` (JSON string),
    `titulo`, `fichero`/`capitulo`/`pagina`/`pagina_fin` (omitidos si `None` — Chroma
    no admite null en metadata), `n_tokens`, y `contexto` en contextual/hype. Todo
    campo entra con consumidor nombrado (D2 del contrato); `fingerprint` fuera (clave
    de caché de F3, sin consumidor de retrieval); `tipo` sigue fuera (constante,
    Decision 5). Supersede la metadata mínima implícita en Decisions 4-5: la fila de
    Chroma pasa a ser autocontenida — F5 y el corrector no hacen join local contra
    `chunks.jsonl` en runtime (D1 del contrato: JSONL system of record, colección =
    vista materializada regenerable).
22. **Filas hype-pregunta autocontenidas** (añadida 2026-08-28, decisión de Adolfo):
    `document` = texto crudo del chunk **padre** (no la pregunta — nunca se le enseña
    a nadie), `embed_text` = la pregunta (sin cambio), metadata = la del padre +
    `entry_type`/`parent_chunk_id`/`pregunta`. Refuerza Decision 6: ahora TODO
    `document` de TODA fila es texto crudo de chunk, sin excepción. Es lo que hacen
    las implementaciones de referencia de HyPE (vector de la pregunta + chunk como
    payload); elimina el `get` al padre en F5 — la regla HyPE→padre queda en pura
    dedup por `parent_chunk_id`.
23. **`n_tokens` en `chunks.jsonl`** (añadida 2026-08-28; toca `p2_chunking.py`, se
    documenta aquí porque su consumidor es el índice/corrector — no hay plan de Fase
    2): contado en F2 con el tokenizador BGE-M3 que ya circula como `contar`.
    Regenerar `chunks.jsonl` es seguro: ids y textos no cambian, y el fingerprint de
    F3 va solo sobre `texto`
    ([p3_enrich.py:157](../../../src/divefy/pipeline/p3_enrich.py#L157)) — 0 llamadas
    nuevas a Gemini.

## Context

- [p2_chunking.py:14-70](../../../src/divefy/pipeline/p2_chunking.py) — `Chunk`, campo
  `id`, `to_dict()`.
- [p3_enrich.py](../../../src/divefy/pipeline/p3_enrich.py) completo.
- `.claude/plans/PRD.md` §7 Fase 4 — decisiones cerradas que este plan implementa.
- `.claude/plans/PRD.md` §7 Fase 9 — Paso 0 y Oleada 1, contexto de por qué se
  necesitan los 3 valores de corpus.
- `.claude/plans/phase-3-extras-indice/plan.md`, sección Notas.
- `tests/unit/test_p2_chunking_core.py`, `tests/unit/` de Fase 3 — estilo de test.
- `data/processed/chunks.jsonl`, `data/processed/enrich.jsonl` — entrada real.

## Acceptance contract

- [ ] Existen las 36 colecciones (`{apuntes,manual,combined}-512-{base,contextual,
  hype}-{bgem3,qwen06b,qwen8b,openai3large}`) en `data/chroma/`.
- [ ] Para cada uno de los 3 valores de corpus, la colección `*-512-base-*` tiene
  exactamente `len(chunks de tipo prosa filtrados a ese corpus)` filas — `puntero_tabla`
  nunca se indexa, ni en `base` — calculado leyendo `chunks.jsonl` en el momento del
  test, nunca hardcodeado.
- [ ] Para cada corpus, la colección `*-512-contextual-*` tiene exactamente
  `len(chunks de prosa de ese corpus con entrada en enrich.jsonl)` filas — calculado
  igual, dinámico.
- [ ] Para cada corpus, la colección `*-512-hype-*` tiene
  `contextual_count + sum(len(preguntas) de ese corpus)` filas — leyendo el número real
  de preguntas de `enrich.jsonl` filtrado a ese corpus en el momento del check.
- [ ] Toda fila de pregunta en `hype` lleva `parent_chunk_id` cuyo valor existe como
  `id` real de un chunk del mismo corpus — sin huérfanos.
- [ ] Ninguna fila usa `tipo` para distinguir chunk de pregunta; usa `entry_type`.
- [ ] `documents` de cada fila es el texto crudo del chunk — nunca el contexto fusionado
  ni la pregunta (en filas hype-pregunta, el texto del chunk padre — Decision 22).
- [ ] Toda fila chunk cumple el contrato de metadata de `docs/modelo-datos.md`:
  `corpus`, `section_ids` (JSON que decodifica a lista no vacía), `titulo`, `n_tokens`,
  procedencia presente solo cuando no es `None` en el chunk de origen, `contexto` solo
  en contextual/hype (Decision 21).
- [ ] Toda fila hype-pregunta es copia autocontenida de su padre: misma metadata que
  la fila chunk del padre en esa colección + `entry_type`/`parent_chunk_id`/`pregunta`
  (Decision 22).
- [ ] Ningún texto se envía dos veces al mismo modelo de embeddings — checked by: test
  con el modelo de embeddings mockeado, contando llamadas.
- [ ] Inspección a ojo (no bloqueante): búsqueda manual "¿a qué velocidad se asciende?"
  contra `apuntes-512-base-bgem3` devuelve trozos sobre ascenso.

Comandos gate: `uv run pytest tests/unit/test_p4_indexing_core.py
tests/acceptance/test_p4_indexing.py -q` · regenerar: `uv run python -m
divefy.pipeline.p4_indexing`.

## Out of scope

- **Fase 5 entera**: las etiquetas del golden eval (sección real por pregunta, en
  ambos corpus), la búsqueda densa real, la comparación corpus×extras×modelo, y la
  decisión de qué corpus ancla el resto del barrido. Esta fase solo deja las 36
  colecciones construidas y listas para que Fase 5 las use.
- Barrer tope (256/1024) — Fase 9, no esta fase (fija en 512).
- Sparse/colbert de BGE-M3 — anotado, no se activa.
- Reranking y umbral de abstención — fases posteriores.

## Interfaces

```python
# p4_vectorstore.py — shared between indexing (this phase) and retrieve (Fase 5)
def canonical_name(corpus: str, cap: int, extras: str, model: str) -> str: ...
def chroma_directory() -> Path: ...
def get_collection(name: str, embeddings: Embeddings) -> Chroma: ...  # get_collection(...).reset_collection() to clear+recreate — library's own method, no wrapper

# p4_indexing.py
CORPUS_VALUES = ("apuntes", "manual", "combined")  # "combined" = no filter
MODELS: dict[str, Embeddings]  # "bgem3"/"qwen06b"/"qwen8b"/"openai3large" -> instance (lazy, T-04)

def build_rows(chunks: list[dict], enrich: list[dict], corpus: str) -> dict[str, list[dict]]:
    """{"base": [...], "contextual": [...], "hype": [...]}, filtered to `corpus`
    ("combined" = no filter) and to tipo=="prosa" (puntero_tabla never indexed).
    Pure — no model/network calls."""

def index_model(model: str, embeddings: Embeddings, rows: dict[str, list[dict]], corpus: str, cap: int,
                 cache: dict[str, list[float]] | None = None) -> None: ...
    # cache: optional, shared across corpus passes for the same model (T-06) so
    # "combined" reuses vectors already computed for apuntes/manual.
    # Writes via collection._collection.upsert(...), NOT add_texts (T-07: add_texts
    # ignores precomputed embeddings, always re-embeds `texts` itself).

def main() -> None: ...
    # Loops over CORPUS_VALUES x MODELS: build_rows + index_model, 12 calls -> 36 collections.
    # One cache dict per model, threaded through all 3 corpus passes for that model.
```

## Tasks

- **T-01 · ADD dependencias** — `uv add langchain-chroma langchain-huggingface
  langchain-openai`.
  VALIDATE: `uv run python -c "from langchain_chroma import Chroma; from
  langchain_huggingface import HuggingFaceEmbeddings; from langchain_openai import
  OpenAIEmbeddings"`.
- **T-02 · CREATE núcleo puro `build_rows`** — filtra por `corpus` (maneja
  `"combined"` como sin filtro), join por `id`, arma las 3 listas de filas.
  VALIDATE: `uv run pytest tests/unit/test_p4_indexing_core.py -q` — incluye casos
  para los 3 valores de `corpus`, incluido `"combined"`.
- **T-03 · CREATE helpers de `p4_vectorstore.py`** — `canonical_name`,
  `chroma_directory`, `get_collection`. `data/chroma/` a `.gitignore`.
  VALIDATE: import limpio + inspección del `.gitignore`.
- **T-04 · CREATE registro `MODELS`** — las 4 instancias de `Embeddings`.
  VALIDATE: smoke manual, `embed_query("prueba")` en cada una.
- **T-05 · CREATE `index_model`** — un texto único por (modelo, corpus), puebla las 3
  colecciones canónicas de ese modelo+corpus vía `Chroma.add_texts`.
  VALIDATE: smoke sobre 5-10 chunks reales de un corpus, un modelo.
- **T-06 · CREATE `main`** — orquesta T-02 + T-04 + T-05 sobre los 3 corpus × 4
  modelos = 12 llamadas a `index_model`, 36 colecciones totales.
  VALIDATE: `uv run python -m divefy.pipeline.p4_indexing` corre completo sin error.
- **T-07 · Check ruidoso + aceptación** — implementar el contrato de aceptación como
  tests (conteos dinámicos, ningún texto embebido dos veces, para los 3 corpus).
  VALIDATE: `uv run pytest tests/unit/test_p4_indexing_core.py
  tests/acceptance/test_p4_indexing.py -q` + inspección a ojo.

## Notas

- **2026-08-27** — revisión de alcance tras conversación con Adolfo: de 12 colecciones
  (solo `corpus="apuntes"`) a 36 (los 3 valores de corpus). Motivo completo en
  Decisions #16. Los tests que había escrito la agente ciega (fijos a `corpus="apuntes"`
  y con conteos 113/12 hardcodeados) se mandan de vuelta a esa misma agente para
  corregir ambas cosas — no se editan a mano aquí, siguiendo la regla de que los
  cambios a tests de aceptación vuelven al escritor original.
- **2026-08-27 (T-04)** — `MODELS` no es un dict de instancias `Embeddings` ya
  construidas como decía el plan (Interfaces: `MODELS: dict[str, Embeddings]`). Cada
  instancia real (`HuggingFaceEmbeddings`, `OpenAIEmbeddings`) carga el modelo (o
  valida la API key) en el propio `__init__`, no en el primer embed — un dict literal
  a nivel de módulo dispararía la descarga/carga de los 3 modelos locales
  (Qwen3-Embedding-8B es pesado) y la validación de `OPENAI_API_KEY` con solo
  **importar** `p4_indexing.py`, incluso desde un test que no toca Fase 4 para nada.
  Adolfo decidió (pregunta explícita, dos opciones con coste) un wrapper perezoso:
  `MODELS` sigue siendo `dict[str, Embeddings]` por duck-typing (implementa
  `embed_documents`/`embed_query`), pero cada entrada difiere la construcción real
  hasta la primera llamada.
- **2026-08-27 (T-04)** — `qwen8b` NO usa `HuggingFaceEmbeddings` como decía Decision 8;
  usa `langchain_ollama.OllamaEmbeddings` sobre Ollama corriendo `qwen3-embedding:8b`.
  Motivo: en fp16 (HuggingFaceEmbeddings/PyTorch), Qwen3-Embedding-8B pesa ~15GB de
  pesos — en la máquina real de Adolfo (Apple M5, 24GB de memoria unificada, medido en
  vivo con `sysctl`/`system_profiler`) eso es arriesgado para una pasada de indexado
  larga (700+ chunks). vLLM se descartó (soporte Apple Silicon "no production-ready"
  en 2026, confirmado por búsqueda externa). Ollama sí soporta el modelo de forma
  nativa. Cuantización elegida: **Q8_0** (~8GB), no el Q4_K_M por defecto (~4.7GB) —
  Adolfo señaló que bgem3/qwen06b corren en precisión completa vía HuggingFaceEmbeddings,
  así que meter qwen8b en 4-bit sesga la comparación entre modelos del propio grid (un
  score peor podría deberse a la cuantización, no al modelo); Q8_0 es casi sin pérdida
  para embeddings y cabe con margen en 24GB. Bgem3 y qwen06b no cambian — caben de sobra
  en precisión completa. Añadida dependencia `langchain-ollama`.
- **2026-08-27 (T-01/T-04)** — dos dependencias que faltaban en T-01: `sentence-transformers`
  (backend real que `langchain-huggingface` necesita para `HuggingFaceEmbeddings`, T-01
  solo listaba el paquete langchain, no el suyo) y `langchain-ollama` (arriba). Confirmado
  con smoke real (`embed_query("prueba")`) en los 4 modelos tras el ajuste: bgem3 dim=1024,
  qwen06b dim=1024, qwen8b dim=4096, openai3large dim=3072.
- **2026-08-27 (T-06)** — la primera pasada de `main()` reventó en qwen8b: `index_model`
  mandaba TODOS los `embed_text` distintos de un corpus en una sola llamada a
  `embed_documents` (702 para apuntes solo) y el servidor local de Ollama murió a mitad
  (`EOF` en `/tokenize`, batch config `-b 2048/-ub 2048`). No es un problema solo de
  Ollama — cualquier backend de embeddings tiene un límite de tamaño de petición, mandarlo
  todo de golpe siempre iba a fallar tarde o temprano. Fix: `index_model` ahora embebe en
  lotes de `BATCH_SIZE = 32` en vez de todo junto.
- **2026-08-27 (T-06/T-07) — revisión completa antes del segundo intento de `main()`,
  a petición de Adolfo, tres correcciones más:**
  - **Log, no print.** `logging.getLogger(__name__)` + `logger.info(...)`,
    `logging.basicConfig` solo en `if __name__ == "__main__"`. Un `print` no es un log
    (nivel, formato, silenciable) — corrección directa de Adolfo.
  - **`puntero_tabla` nunca se indexa** (Decision #18) — `build_rows` filtraba por
    corpus pero no por `tipo`, así que los 40 chunks-puntero de tabla de `manual` (0 en
    `apuntes`) colaban en la colección `base`. Adolfo lo cazó antes de ejecutar nada.
    Fix de una línea: `corpus_chunks = [c for c in _filter_by_corpus(...) if c["tipo"]
    == "prosa"]`, único punto del que derivan `base`/`contextual`/`hype`. El test de
    aceptación tenía el mismo fallo (su fixture `corpus_chunk_records` tampoco filtraba
    por `tipo`) — Adolfo lo desbloqueó y pegó la versión corregida él mismo.
  - **Cache de embeddings compartido por modelo entre las 3 pasadas de corpus**
    (Decision #1 corregida) — `"combined"` es exactamente apuntes ∪ manual, mismo
    `embed_text` byte a byte, así que sin esto se re-embebía dos veces el mismo
    contenido — coste real duplicado en qwen8b (Ollama) y sobre todo en `openai3large`
    (dinero real). `index_model` ahora acepta `cache: dict | None = None`; `main()`
    crea un dict por modelo y lo pasa en las 3 pasadas de corpus de ese modelo.
    Retrocompatible con la firma que ya usa el test de aceptación congelado
    (`index_model(model, embeddings, rows, corpus=..., cap=...)`, sin `cache` — sigue
    funcionando, usa un dict propio como antes).
  - **`reset_collection` (Decision #19)** — cada colección se borra y recrea al
    empezar cada pasada de `main()`, para que una re-ejecución del pipeline siempre
    refleje `chunks.jsonl`/`enrich.jsonl` actuales y no acumule filas huérfanas de
    chunks borrados o re-identificados en una fase anterior. Confirmado en vivo:
    `add_texts` con un id repetido hace upsert (no lanza error), pero eso no cubre el
    caso de un chunk eliminado — de ahí el reset completo en vez de confiar solo en
    upsert.
- **2026-08-27 (T-07) — bug real encontrado revisando el cache antes de volver a correr
  `main()` (Decision #20, detalle completo ahí):** `Chroma.add_texts` ignora en
  silencio cualquier `embeddings=` que se le pase y siempre re-embebe `texts` con su
  propio `embedding_function` — confirmado leyendo el código fuente instalado. El
  Finding original del plan ("`add_texts` acepta vectores precomputados") era falso.
  Esto no es solo ineficiencia: sin corregirlo, `contextual`/`hype` habrían guardado
  el vector del `document` crudo, nunca el de `embed_text` (contexto fusionado /
  pregunta HyPE) — Decision 6 no se habría cumplido. Fix: escribir con
  `collection._collection.upsert(ids=, embeddings=, documents=, metadatas=)`
  directamente, bypaseando `add_texts`; sigue siendo el mismo objeto
  `langchain_chroma.Chroma`, solo cambia el método de escritura (Decision 8
  actualizada). De paso: `reset_collection` propio en `p4_vectorstore.py` (T-06) se
  borró — `langchain_chroma.Chroma` ya trae `.reset_collection()` como método público,
  idéntico a lo que se había escrito a mano. Verificado todo en vivo antes de volver a
  correr `main()` sobre datos reales: cache de dedup cruzado entre corpus (0 llamadas
  de embedding en la pasada "combined"), y `upsert` directo sin ninguna llamada a
  `embed_documents`.
- **2026-08-27 (`/review`)** — panel code-reviewer + architect sobre el diff completo,
  a petición de Adolfo, antes de volver a correr `main()`. Informe completo en
  `.claude/plans/phase-4-embeddings-indice/review-report.md` (2 CRITICAL, 3 HIGH, 8
  MEDIUM, ~9 LOW). Las dos CRITICAL son de test (C1: nada verifica que el vector
  guardado sea el de `embed_text` y no el de `document` — justo lo que Decision #20
  existe para garantizar; C2: el test "existen las 36 colecciones" es auto-cumplido,
  `get_collection` crea la colección vacía si no existe) — Adolfo las aplica él mismo
  en el test de aceptación congelado (desbloqueo pendiente). Las 3 HIGH se corrigen
  aquí mismo:
  - **H1 — invariante de enriquecido.** `build_rows` ahora lanza `ValueError` si algún
    chunk de prosa del corpus no tiene entrada en `enrich.jsonl` (antes se omitía en
    silencio de `contextual`/`hype`, produciendo colecciones más cortas sin ningún
    aviso — Fase 5 habría atribuido la diferencia a la técnica, no a datos
    incompletos). Verificado contra los datos reales antes de aplicar: 0 chunks de
    prosa sin enrich en los 3 valores de corpus. Rompe el fixture del test de
    aceptación congelado (`SAMPLE_ENRICH` le faltaba la entrada de un chunk de
    prosa) — tercera cosa que Adolfo pega junto con C1/C2.
  - **H2 — orden de bucles en `main()`.** Antes: corpus por fuera, modelo por dentro,
    con un cache por modelo construido de golpe al principio — los 4 caches (~1.1-1.2GB
    medido por ambos revisores independientemente) convivían en memoria toda la
    pasada. Ahora: modelo por fuera, corpus por dentro — un único `cache = {}` por
    modelo, liberado al pasar al siguiente. Mismo resultado (mismo reuso de vectores
    en "combined"), pico de memoria mucho menor. `index_model` no cambia de firma.
  - **H3 — preflight de los 4 modelos.** `main()` ahora llama `embed_query("prueba")`
    en los 4 modelos antes de indexar nada — si Ollama no está corriendo o falta
    `OPENAI_API_KEY`, falla en segundos en vez de a mitad de la pasada 3 de 12 (que es
    justo lo que costó el reinicio de T-06).
  Las MEDIUM/LOW quedan en el informe como backlog — no bloquean, se retoman si/cuando
  aplica (varias son preguntas explícitas para el plan de Fase 5, no fixes de esta fase).
- **2026-08-28 — modelo de datos definido en retrospectiva (Decisions 21-23) e
  implementado.** Adolfo detectó que las fases 1-4 se construyeron sin definir el
  modelo de datos; se derivó en inverso (consumidores → Chroma → JSONL), quedó como
  contrato en `docs/modelo-datos.md`, y se implementó: `n_tokens` en `Chunk`/
  `chunks.jsonl` (regenerado; verificado con checks ruidosos: 723 ids idénticos, los
  683 fingerprints de `enrich.jsonl` coinciden con los textos nuevos → caché Gemini
  intacto), `_chunk_metadata()` + filas hype autocontenidas en `build_rows`. Tests:
  unit core reescritos al contrato (RED→GREEN, 67/67 en verde); el test de aceptación
  congelado lo actualizó una agente ciega (solo contrato + jsonl, sin leer `src/`)
  pero el hook de enmienda lo dejó pendiente de que Adolfo lo pegue/desbloquee — los
  2 tests puros del fichero nuevo (dedup de embeddings, vector guardado = embed_text
  en contextual Y en hype-pregunta) pasan en verde contra la implementación desde el
  scratchpad. Las 36 colecciones siguen sin construirse — el re-indexado no tiene
  coste marginal (los vectores no cambian: `embed_text` idéntico).
- **2026-08-28 — indexado completo y aceptación en verde.** Adolfo pegó el test de
  aceptación actualizado (protocolo de enmienda) y lanzó `main()`: las 36 colecciones
  construidas (preflight de los 4 modelos OK; `combined` reutilizando caché de
  vectores como estaba previsto). Suite completa contra las colecciones reales:
  **99 passed, 0 failed** — contrato de metadata verificado fila a fila en las 36,
  filas hype autocontenidas, conteos dinámicos correctos, vector guardado =
  `embed_text` en contextual y hype-pregunta. Fase 4 lista para /verify y para que
  Fase 5 arranque.
- **2026-08-28 — /review del diff completo de la fase + fixes.** Panel ciego (informe
  fechado en `review-report.md`): 0 CRITICAL, 0 HIGH, 6 MEDIUM, 2 LOW. Adolfo decidió
  aplicar los hallazgos 1, 2, 3, 4 y 8 y descartar 5-7 (blindajes ante refactors
  futuros y una dep transitiva). Aplicado con TDD (3 tests nuevos en unit core,
  RED→GREEN; el acceptance congelado intacto y en verde):
  - #1 — `index_model` valida `n_tokens <= cap` de toda fila antes de tocar nada:
    una colección ya no puede llevar un tope falso en el nombre.
  - #4/#8 — decisión de Adolfo: se escribe por lotes según se embebe (lotes de
    BATCH_SIZE por colección) en vez de todo al final; de paso ningún upsert vuelve
    a acercarse al máximo local de Chroma (5461). Más `_embed_with_retry` (3 intentos,
    espera creciente): un 429 o un tosido de Ollama ya no tira la pasada.
  - #2 — marcador `data/chroma/{colección}.complete` (borrado antes del reset, creado
    al terminar): una colección interrumpida es detectable. NO va en la metadata de
    colección: probado en vivo que `modify` la reemplaza entera y borra `hnsw:space`,
    que langchain lee para la función de score. Invariante 6 nuevo en
    `docs/modelo-datos.md`; el plan de F5 exige el marcador al leer. Las 36
    colecciones existentes (verificadas por la suite ese mismo día) se sellaron con
    un one-off.
  - #3 — `LazyEmbeddings.release()`: el preflight suelta cada modelo tras validarlo
    y `main()` suelta cada modelo al terminar su pasada — ya no conviven los 4 en
    memoria.
  - Incidente durante el fix, corregido: la primera pasada RED del test del cap
    ejecutó el `index_model` viejo (sin guard) contra el `data/chroma` real y creó 3
    colecciones `apuntes-2-*` con vectores fake — detectado por el conteo 39≠36 al
    sellar, borradas, y el test ahora monkeypatchea `chroma_directory` aunque el
    guard salte antes (defensa si el guard regresa). Suite completa final: 102 passed.
