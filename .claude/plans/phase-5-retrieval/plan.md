# Plan: Fase 5 — Retrieval + corrector v1

**Status**: archived (verified 2026-08-30 — 10/10 PASS, suite 149; acta en verify-report.md)
**Modo de ejecución** (Adolfo, 2026-08-28): T-01→T-08 en orden, enseñando el diff de
cada tarea a Adolfo antes de pasar a la siguiente.
**Fuente**: PRD §7 Fase 5 · explorado 2026-08-27 (hallazgos abajo) · conversación con
Adolfo 2026-08-27.

## Goal

Al terminar existen: (1) el retriever parametrizado por config — denso sobre Chroma +
BM25 + fusión RRF, con la regla HyPE→padre — que el corrector usa hoy y el chat usará
en Fase 8; (2) las etiquetas por sección de las 84 preguntas de eval, auditadas por
Adolfo, en `data/eval/labels.jsonl`; (3) el corrector v1: config → fila versionada en
`results/` con recall@k, MRR, tokens recuperados y match numérico, desglosada por
corpus de origen; (4) el check de determinismo en verde; y (5) el Paso 0 medido (cruce
denso corpus×extras×modelo, 36 pasadas) con el corpus ancla decidido por Adolfo, más la
receta de búsqueda (densa vs híbrida, curva de k) declarada en `EXPERIMENTOS.md`.

## Findings

(de la exploración del 2026-08-27, en sesión)

- `p5_retrieve.py`, `evals/corrector.py` y `config.py` son stubs de un docstring.
- Interfaz de Fase 4 lista: `canonical_name`/`get_collection`
  ([p4_vectorstore.py:9-23](../../../src/divefy/pipeline/p4_vectorstore.py#L9-L23)) y
  `MODELS` con los 4 embeddings perezosos
  ([p4_indexing.py:98-106](../../../src/divefy/pipeline/p4_indexing.py#L98-L106)).
- ~~Los metadatos en Chroma son mínimos (`entry_type`, `contexto`, `parent_chunk_id`);
  la atribución a secciones vive en `chunks.jsonl` (`section_ids`) — el corrector
  resuelve trozo→secciones con un join local, sin pedir nada a Chroma.~~ **Superado
  2026-08-28** (ejercicio de modelo de datos, contrato en
  [docs/modelo-datos.md](../../../docs/modelo-datos.md) + Decisions 21-23 del plan de
  Fase 4): toda fila es autocontenida — `section_ids` (JSON string), `corpus`,
  `titulo`, procedencia y `n_tokens` vienen en la metadata; las filas hype-pregunta
  traen el texto y la metadata del padre (dedup por `parent_chunk_id`, sin `get`
  extra). El corrector NO hace join local — ver Decision 8.
- ~~**`data/chroma/` no existe**: las 36 colecciones de Fase 4 no están construidas
  (la primera pasada murió en qwen8b; fix de lotes aplicado 2026-08-27). Prerequisito
  de esta fase, no tarea (Decision 3).~~ **Superado 2026-08-28**: las 36 colecciones
  están construidas y selladas (marcadores `.complete`), suite completa en verde
  contra ellas. Prerequisito satisfecho.
- Golden verificado (solo esquema, jamás indexado): 186 filas
  (`id`/`pregunta`/`respuesta_esperada`/`uso`/`requiere_tool`), 84 eval / 102 repaso;
  **solo 1 pregunta de eval con `requiere_tool=true`**. `data/eval/` vacío.
- Corpus: 723 chunks (113 apuntes / 610 manual; 683 prosa + 40 punteros), 541
  secciones únicas, ~205K tokens estimados (apuntes ~117K chars, manual ~701K).
- El barrido de tope no es gratis: `chunks.jsonl` es fichero único sin tope en el
  nombre ([p2_chunking.py:158](../../../src/divefy/pipeline/p2_chunking.py#L158)) —
  regenerar a 256/1024 lo pisa e invalida el caché de `enrich.jsonl`.
- Sin BM25 en el árbol de deps ([pyproject.toml:6-18](../../../pyproject.toml#L6-L18)).
  Externo: LangChain 1.x movió los retrievers legacy a `langchain-classic` y
  `langchain-community` está deprecado; su `EnsembleRetriever` no conoce la regla
  HyPE→padre.
- **Chroma tiene búsqueda híbrida nativa (Search API: `Knn` + `Rrf` + BM25 sparse),
  pero solo en Chroma Cloud** — docs: "Support for local Chroma deployments will be
  available in a future release", y **probado en vivo** sobre la 1.5.9 instalada
  (EphemeralClient + Schema con `SparseVectorIndexConfig`):
  `InvalidArgumentError: Sparse vector indexing is not enabled in local`.
- Patrón Gemini probado en vivo en p3 (caching de documento, salida JSON con schema) —
  quedó sin uso aquí tras la Decision 4 (etiquetado por sesión de Claude).

Sources externas consultadas:
- https://docs.langchain.com/oss/python/migrate/langchain-v1
- https://docs.langchain.com/oss/python/releases/langchain-v1
- https://github.com/chroma-core/chroma/blob/main/docs/mintlify/cloud/search-api/overview.mdx
- https://github.com/chroma-core/chroma/blob/main/docs/mintlify/cloud/search-api/hybrid-search.mdx
- https://github.com/chroma-core/chroma/blob/main/docs/mintlify/integrations/embedding-models/chroma-bm25.mdx

## Decisions

1. **El barrido de tope (256/1024) queda fuera de Fase 5** — decisión de Adolfo,
   2026-08-27. Motivo: primero encontrar la combinación ganadora de búsqueda sin
   ampliar más el grid; además el tope no es barato de barrer hoy (los ficheros de
   p2/p3 se pisan entre topes, ver Findings) — la infraestructura de versionar por
   tope encaja en Fase 9, donde el PRD ya lo lista como dimensión de la Oleada 1.
   Alternativa descartada: barrido completo en Fase 5 (PRD Fase 5, tarea 5 literal) —
   compraba cerrar la receta con todas las dimensiones baratas, costaba parametrizar
   por tope las salidas de p2/p3/p4 y dos indexados más.

2. **Paso 0 = cruce denso corpus×extras×modelo (36 pasadas retrieval-only)** —
   decisión heredada del plan de Fase 4 (Decision 16 y Goal, revisión 2026-08-27),
   confirmada por Adolfo en esta conversación. La comparación barata usa búsqueda
   densa sola (BM25 es ciego entre idiomas y contaminaría apuntes-ES vs manual-EN)
   sobre las 84 preguntas, cruzando las 3 dimensiones ya indexadas — las 36
   colecciones existen exactamente para esto. De ahí sale el corpus ancla; el resto
   del barrido va en fija-y-barre anclado en él. Corpus se re-mide UNA sola vez con
   la híbrida real en la Oleada 1 (medición oficial, PRD Fase 9) — no se re-barre en
   cada paso. Nota: el §7 Fase 9 Paso 0 del PRD (texto de 2026-08-24) aún dice
   "3 pasadas, solo corpus"; quedó superado por la revisión de Fase 4 — sincronizar
   esa línea del PRD al aprobar este plan.

3. **El indexado de Fase 4 lo gestiona Adolfo; este plan asume las 36 colecciones
   construidas** — decisión de Adolfo, 2026-08-27. Ninguna tarea de Fase 5 lo lanza;
   si una decisión del plan necesita el índice en pie (p.ej. leer la tabla del Paso 0),
   se espera a que Adolfo dé la señal. Queda como prerequisito externo, no como tarea.

4. **El etiquetado asistido lo hace una sesión de Claude con prompt especializado,
   no un script Gemini** — decisión de Adolfo, 2026-08-27 ("si al final es etiquetar,
   no hace falta un modelo programático"). Motivo: artefacto único y auditado — el
   código de una pasada que no se repite es peso muerto; la sesión lee el corpus
   completo (sin retriever de por medio → sin circularidad) y produce
   `data/eval/labels.jsonl` directamente. Se mantienen intactos del PRD: una pasada,
   auditoría de ~25-30 por Adolfo con la regla ≤2 mal, etiquetas versionadas, y la
   regla doctrinal (pregunta con número PADI → la sección Navy con valor distinto NO
   se etiqueta). Guardarraíles que el prompt debe forzar: trabajo sistemático pregunta
   a pregunta con evidencia (sección citada, no impresión), secciones de apuntes y
   manual por separado, y el esquema de `labels.jsonl` de la Decision 6. Trade
   aceptado: menos repetible que un script — irrelevante porque el artefacto es
   one-shot y la auditoría es la puerta de calidad. El prompt es entregable versionado
   de la fase; la sesión que lo ejecuta, no.

5. **Lado léxico y fusión: `rank_bm25` + fórmula RRF estándar, en `p5_retrieve.py`** —
   cierre 2026-08-27 tras el mandato de Adolfo ("busca cómo se hace ahora, no quiero
   reinventar la rueda"). Lo que se hace ahora, verificado: (a) la vía moderna nativa
   (Search API de Chroma con BM25 sparse + `Rrf`) es solo Cloud — probado en vivo que
   la 1.5.9 local lo rechaza (ver Findings); y aunque llegase a local, obligaría a
   re-indexar las 36 colecciones con schema sparse y sus estadísticas léxicas
   incluirían las preguntas HyPE, rompiendo la regla cerrada del PRD ("BM25 indexa
   solo trozos; la parte léxica es idéntica en todos los brazos"); (b) la vía
   LangChain (`BM25Retriever`/`EnsembleRetriever`) envuelve exactamente `rank_bm25`
   añadiendo 2-3 deps (una deprecada) y una semántica de dedup que no conoce la regla
   HyPE→padre. Conclusión: usar la rueda sin el embalaje — `rank_bm25` (una dep, pura
   Python, el estándar) sobre los 723 chunks de `chunks.jsonl` (índice léxico único
   compartido por todos los brazos) — **fuente superada en Decision 8, 2026-08-28:
   pasa a construirse desde las filas chunk de la colección** —, y RRF con la fórmula publicada
   `score = Σ 1/(60 + rank)` — la misma que implementa el `Rrf` de Chroma. Anotado:
   si el Search API llega a local Chroma, re-evaluar en Fase 9+ con dato.

6. **Contratos de datos** (defaults elegidos por delegación de Adolfo, vetables en
   la revisión de este plan):
   - `RetrievalConfig` (frozen dataclass en `config.py`): `corpus`, `cap`, `extras`,
     `embedding`, `search` (`"densa"|"hibrida"`), `k`. Deriva `collection`
     (= `canonical_name`) y `run_id` = `f"{collection}-{search}-k{k}"`
     (p.ej. `apuntes-512-base-bgem3-hibrida-k5`).
   - `data/eval/labels.jsonl` — una fila por pregunta de eval:
     `{"id", "pregunta", "secciones_apuntes": [...], "secciones_manual": [...],
     "sin_respuesta": bool, "notas": str|null}`. Todo `section_id` debe existir en
     `chunks.jsonl` (invariante ruidosa del check de etiquetas).
   - `data/eval/query-embeddings-{model}.json` — caché de vectores de las 84
     preguntas, un fichero por modelo de embeddings; se construye una vez y da
     determinismo y coste cero a las pasadas siguientes.
   - `results/{run_id}.json` — `{"config": {...}, "resumen": {...},
     "detalle": [una entrada por pregunta]}`. Sin timestamp dentro (la fila debe ser
     determinista byte a byte). Política nunca-se-sobreescribe: si el fichero existe
     y la fila nueva es idéntica → no-op OK; si difiere → **error con el diff**
     (borrado manual si el cambio es intencionado). Resumen: `recall_at_k` global,
     `recall_apuntes` y `recall_manual` (cada uno solo sobre preguntas cuya etiqueta
     tiene secciones en ese corpus), `mrr`, `tokens_recuperados_media` (tokenizador
     BGE-M3, la vara única del grid), `match_numerico` (solo sobre preguntas con
     números en `respuesta_esperada`), `n_preguntas`.
   - Preguntas con `sin_respuesta=true` quedan fuera del recall/MRR (no hay sección
     correcta que recuperar); se listan en el detalle como insumo de abstención para
     Fase 7.

7. **Parámetros mecánicos del retriever** (defaults vetables):
   - Tokenización BM25: minúsculas + `\w+` (regex Unicode: cubre acentos ES).
     Alternativa anotada en PRD si el cruce ES↔EN duele: sparse nativo de BGE-M3.
   - RRF: `k_rrf=60` (constante estándar). Desempate determinista: (score RRF desc,
     `chunk_id` asc) — necesario para el check de determinismo.
   - Dedup HyPE: en colecciones `hype` se piden `4*k` resultados a Chroma, cada hit
     `entry_type=="hype"` se resuelve a `parent_chunk_id`, se deduplica conservando
     la mejor posición, y se corta en k trozos únicos. En `base`/`contextual` se
     piden `k` directamente.
   - Híbrida: lista densa (ya deduplicada a padres) + lista BM25 (chunks, top `4*k`)
     → RRF → top k. La densa consulta con el vector cacheado de la pregunta
     (`similarity_search_by_vector`), nunca re-embebiendo en vivo.
   - Match numérico: se extraen números de `respuesta_esperada` normalizando coma
     decimal → punto; acierto = todos presentes (misma normalización) en el texto
     concatenado de los k trozos.

8. **Revisión por modelo de datos (2026-08-28)** — contrato en
   [docs/modelo-datos.md](../../../docs/modelo-datos.md), implementado en Fase 4
   (Decisions 21-23 de su plan). Implicaciones para esta fase:
   - El corrector lee `section_ids` (`json.loads`), `corpus` y `n_tokens` de la
     metadata de las filas recuperadas — **sin join local contra `chunks.jsonl`**.
     `tokens_recuperados_media` sale de sumar `n_tokens` de los k trozos, sin
     re-tokenizar en eval.
   - La regla HyPE→padre de Decision 7 queda como está (dedup por `parent_chunk_id`),
     pero ya no requiere ningún `get` al padre: la fila hype-pregunta trae el texto y
     la metadata del padre.
   - **El retriever/corrector exige el marcador `data/chroma/{colección}.complete`**
     antes de leer una colección (invariante 6 del contrato, añadido 2026-08-28 tras
     la review): sin marcador la colección quedó a medias entre reset y escritura —
     error ruidoso, nunca 0 resultados en silencio.
   - **Fuente del índice BM25: las filas `entry_type=="chunk"` de la colección del
     brazo, vía `collection.get()`** (cerrada 2026-08-28 — Adolfo delegó en "lo que
     hacen los mejores", verificado con búsqueda externa). Amend a la Decision 5, que
     lo construía desde `chunks.jsonl` (723 filas). Motivos: (a) el estándar de la
     industria en híbrida — Elasticsearch, Weaviate, Qdrant, el Search API de Chroma —
     es SIEMPRE dos índices (léxico y denso) sobre el MISMO conjunto de documentos de
     la misma colección, nunca dos corpus distintos; (b) los 723 de `chunks.jsonl`
     incluyen 40 `puntero_tabla` que el lado denso nunca puede devolver — conjunto
     recuperable desalineado entre brazos, contaminaría la fusión RRF y las métricas;
     (c) D1 del contrato: el runtime lee solo Chroma. La propiedad "índice léxico
     único por corpus" se conserva por construcción: las filas chunk de base/
     contextual/hype de un corpus tienen documents idénticos.

## Context

- [p4_vectorstore.py](../../../src/divefy/pipeline/p4_vectorstore.py) — conexión
  Chroma compartida indexing/retrieve; `canonical_name` es el contrato de nombres.
- [p4_indexing.py:98-106](../../../src/divefy/pipeline/p4_indexing.py#L98-L106) —
  registro `MODELS`: el retriever embebe la query con estas mismas instancias
  (mismo modelo indexa y consulta, siempre).
- [p4_indexing.py:37-67](../../../src/divefy/pipeline/p4_indexing.py#L37-L67) —
  `build_rows`: qué metadatos llevan las filas (`entry_type`, `parent_chunk_id`) —
  el dedup HyPE depende de ellos.
- [p2_chunking.py:57-71](../../../src/divefy/pipeline/p2_chunking.py#L57-L71) —
  esquema de `chunks.jsonl` (`section_ids`), base del join trozo→secciones.
- `data/eval/golden.jsonl` — el examen; el corrector filtra `uso=="eval"`. (Hasta el
  2026-08-28 vivía en `docs/Buceo - Golden dataset.jsonl`; movido por Adolfo en la
  revisión: todo el material de eval bajo `data/eval/`.)
  **Jamás se indexa** (regla inmutable 1 del CLAUDE.md).
- `.claude/plans/PRD.md` §7 Fase 5 (decisiones cerradas: híbrida base, densa
  ablación, k barrido {3,5,10}, etiquetado, métricas) y Fase 9 (Paso 0, Oleada 1).
- `.claude/plans/phase-4-embeddings-indice/plan.md` — Decision 16 (por qué 36
  colecciones) y Notas (batching, LazyEmbeddings).
- `tests/unit/test_p4_indexing_core.py` y `tests/acceptance/test_p4_indexing.py` —
  estilo de test a seguir (conteos dinámicos, nunca hardcodeados — regla de Adolfo).
- Patrón de skip si falta artefacto pesado: `tests/conftest.py` (se salta si falta el
  PDF) — el acceptance de esta fase se salta igual si falta `data/chroma/`.

## Acceptance contract

- [ ] `data/eval/labels.jsonl` existe con exactamente las 84 preguntas `uso=eval`;
  todo `section_id` de toda etiqueta existe en `chunks.jsonl`; la pregunta con
  `requiere_tool=true` está marcada coherentemente (`sin_respuesta` o etiquetada con
  motivo en `notas`) — checked by: test de etiquetas (unit, sin Chroma).
- [ ] Auditoría de Adolfo: muestra de ~25-30 etiquetas con ≤2 mal — checked by:
  Adolfo, resultado anotado en Notas de este plan.
- [ ] `retrieve(config, ...)` devuelve exactamente k ids de chunk únicos, todos
  existentes en `chunks.jsonl`, ninguno con `::hype::` — checked by: tests unit del
  dedup con datos sintéticos + acceptance sobre la colección real.
- [ ] La parte léxica es idéntica en todos los brazos: el índice BM25 se construye
  solo desde las filas `entry_type=="chunk"` de la colección del corpus (nunca
  contextos, preguntas ni punteros — Decision 8) — checked by: test unit
  (el ranking BM25 para una query es el mismo con extras base y hype).
- [ ] RRF: con dos rankings sintéticos conocidos, la fusión reproduce el orden
  calculado a mano con `Σ 1/(60+rank)` y el desempate (score, id) — checked by: test
  unit.
- [ ] Determinismo de punta a punta: correr el corrector dos veces con la config base
  produce ficheros de resultado byte a byte idénticos — checked by: acceptance (skip
  si falta `data/chroma/`).
- [ ] Política nunca-se-sobreescribe: resultado existente + fila distinta → error con
  diff; idéntica → no-op — checked by: test unit con tmp_path.
- [ ] Métricas correctas sobre fixture sintético mini (etiquetas y recuperados
  conocidos a mano): recall@k, MRR, desglose por corpus (condicionado a que la
  etiqueta tenga secciones de ese corpus), tokens y match numérico dan los valores
  esperados — checked by: tests unit del corrector.
- [ ] Paso 0 corrido: 36 filas (densa, k=5) en `results/` y tabla en
  `EXPERIMENTOS.md` (Fases 1, 3 y 4 rellenadas como señal barata) — checked by:
  inspección de la tabla; la decisión del ancla es de Adolfo.
- [ ] Receta de búsqueda declarada: sobre el ancla, densa vs híbrida y k∈{3,5,10}
  medidos y anotados en `EXPERIMENTOS.md` Fase 5 — checked by: filas en `results/` +
  casillas rellenadas.

Comandos gate:
`uv run pytest tests/unit/test_p5_retrieve_core.py tests/unit/test_corrector_core.py
tests/acceptance/test_p5_retrieval.py -q` · Paso 0/barrido: CLI del corrector (una
orden por pasada o `--sweep`, se cierra en implementación).

## Out of scope

- Barrido de tope 256/1024 (→ Fase 9, Decision 1).
- Rerank, umbral de score y abstención (→ Fase 6).
- Juez LLM, exactitud numérica sobre respuestas generadas, latencia/coste de
  generación (→ Fase 7, corrector v2).
- Construir las 36 colecciones (→ prerequisito externo, Decision 3).
- Sparse nativo de BGE-M3 como lado léxico (anotado en PRD, solo si el desglose por
  corpus muestra que el cruce ES↔EN duele).
- Search API híbrido de Chroma (Cloud-only hoy; re-evaluar con dato si llega a local).
- Re-medición oficial de corpus/extras/embedding con híbrida (→ Fase 9, Oleada 1).

## Interfaces

```python
# config.py
@dataclass(frozen=True)
class RetrievalConfig:
    corpus: str      # "apuntes" | "manual" | "combined"
    cap: int         # 512 (fijo en esta fase)
    extras: str      # "base" | "contextual" | "hype"
    embedding: str   # "bgem3" | "qwen06b" | "qwen8b" | "openai3large"
    search: str      # "densa" | "hibrida"
    k: int           # 3 | 5 | 10
    # derivados: collection (canonical_name), run_id

# p5_retrieve.py
def build_bm25(collection) -> ...                    # léxico desde filas entry_type=="chunk" (Decision 8)
def rrf_fuse(rankings: list[list[str]], k_rrf: int = 60) -> list[str]
def retrieve(config: RetrievalConfig, query: str,
             query_vector: list[float] | None = None) -> list[str]  # k chunk ids únicos

# evals/corrector.py
def run(config: RetrievalConfig) -> dict             # {"config", "resumen", "detalle"}
def main() -> None                                   # CLI → results/{run_id}.json
```

## Tasks

- **T-01 · ADD dependencia** — `uv add rank-bm25`.
  VALIDATE: `uv run python -c "import rank_bm25"`.
- **T-02 · CREATE `RetrievalConfig` en `config.py`** — dataclass frozen + derivados
  `collection`/`run_id` + validación de valores.
  VALIDATE: `uv run pytest tests/unit/test_config.py -q`.
- **T-03 · CREATE prompt de etiquetado** (fichero versionado en
  `.claude/plans/phase-5-retrieval/etiquetado-prompt.md`) **+ ejecutar la sesión de
  etiquetado** → `data/eval/labels.jsonl` + check de etiquetas (84 filas, secciones
  existentes, esquema). No depende del índice — puede arrancar la primera.
  VALIDATE: `uv run pytest tests/unit/test_labels.py -q` + auditoría de Adolfo
  (~25-30, regla ≤2 mal) anotada en Notas.
- **T-04 · CREATE `p5_retrieve.py`** — `build_bm25`, `rrf_fuse`, dedup HyPE→padre,
  `retrieve` (denso vía `similarity_search_by_vector` con vector cacheado; híbrida =
  denso + BM25 + RRF) + caché `query-embeddings-{model}.json`.
  VALIDATE: `uv run pytest tests/unit/test_p5_retrieve_core.py -q` (partes puras con
  datos sintéticos, sin Chroma ni modelos).
- **T-05 · CREATE corrector v1 en `evals/corrector.py`** — carga golden (`uso=eval`),
  etiquetas y chunks; por pregunta: retrieve → resolver secciones → métricas; escribe
  `results/{run_id}.json` con la política nunca-se-sobreescribe; CLI.
  VALIDATE: `uv run pytest tests/unit/test_corrector_core.py -q` (fixture sintético).
- **T-06 · CREATE acceptance** — determinismo (doble pasada idéntica) + retrieve real
  sobre la colección base (k únicos, sin `::hype::`), con skip si falta `data/chroma/`.
  VALIDATE: `uv run pytest tests/acceptance/test_p5_retrieval.py -q`.
  (Prerequisito del índice satisfecho el 2026-08-28 — 36 colecciones selladas.)
- **T-07 · Paso 0** — 36 pasadas densas k=5 (cruce corpus×extras×modelo), tabla en
  `EXPERIMENTOS.md`, y **decisión del ancla por Adolfo** con la tabla delante.
  VALIDATE: 36 ficheros en `results/` + tabla rellenada.
  ⛔ Bloqueada por T-03 (etiquetas auditadas) — el índice ya está construido.
- **T-08 · Barrido de búsqueda** — sobre el ancla: densa vs híbrida y k∈{3,5,10};
  rellenar `EXPERIMENTOS.md` Fase 5 y declarar la receta de búsqueda; sincronizar la
  línea del Paso 0 en el PRD (Decision 2).
  VALIDATE: filas en `results/` + casillas de `EXPERIMENTOS.md` + PRD actualizado.

## Notas

- (2026-08-28) **Step zero**: suite completa en verde antes de tocar nada — 102
  passed, 5 deselected.
- (2026-08-28) **RED de aceptación**: `tests/acceptance/test_p5_retrieval.py`
  escrito por agente ciega (solo contrato + interfaces + convenciones + muestras
  reales) y aprobado por Adolfo. Capturado: 5 failed con
  `ImportError: cannot import name 'RetrievalConfig'` (el esperado — los módulos
  son stubs) + 1 skipped (el de determinismo: `labels.jsonl` aún no existe).
- (2026-08-28) **T-03 ejecutado**: sesión de etiquetado por 6 lotes paralelos según
  `etiquetado-prompt.md` (A=apuntes + M1–M5=manual por capítulos). Incidente: el
  fan-out paralelo (~120-160K tokens/lote) agotó el límite de sesión del plan y 3
  agentes murieron en su paso final — pero los 6 ficheros quedaron escritos y
  completos; su auto-verificación pendiente se sustituyó por verificación mecánica
  local: **302/302 citas encontradas literales en su sección** (a nivel de frase;
  0 section_ids inexistentes). Reconciliación: 84 filas, 0 `sin_respuesta`
  (esperable: el golden sale del curso PADI y los apuntes son el curso — ojo, deja
  SIN conjunto negativo la calibración de abstención de F6), 68 con ambos corpus,
  15 solo apuntes, 1 solo manual (q140, apuntes no cubren ReActivate), media 3.46
  secciones/pregunta. Regla doctrinal aplicada en 7 preguntas (q013, q023, q169,
  q171, q176, q181, q186 — descartes anotados en `notas` de cada fila).
  `test_labels.py` (8 tests) RED→GREEN.
- (2026-08-28) **Auditoría delegada por Adolfo a un agente auditor independiente**
  ("mira mejor crea un agente que haga el chequeo") — desviación del plan, que
  asignaba la auditoría a Adolfo. Además, decisión de Adolfo sobre q013: no exige
  tool — explicar el método desde los apuntes es respuesta válida (nota de la fila
  actualizada). Veredicto del auditor sobre la muestra de 28: **17 mal (> regla
  ≤2)** — apuntes impecables, 11 descartes doctrinales todos correctos, fallo
  sistemático = sobre-etiquetado de secciones Navy tangenciales (24% de las
  etiquetadas de la muestra), 2 de ellas contradiciendo doctrina PADI (3-10,
  9-12.11). Los 17 descartes aplicados a labels.jsonl (check en verde; 65
  preguntas conservan soporte manual, 0 sin_respuesta).
- (2026-08-28) **Pasada de precisión aprobada por Adolfo ("dale a opción A")** y
  ejecutada: 2 auditores sobre los 113 pares restantes → 26 NO_SOSTIENE más
  (~23%, mismo patrón tangencial; otra contradicción doctrinal: 6-6.2 permite
  descongestionantes). Aplicados. **Etiquetas finales**: 84 filas, 43 secciones
  Navy purgadas en total, 0 sin_respuesta, 83 preguntas con apuntes / 60 con
  manual, media 2.95 secciones/pregunta; todos los pares (pregunta, sección
  manual) auditados por agente independiente; apuntes con 0 fallos en la muestra.
  `test_labels.py` en verde. T-03 CERRADO.
- (2026-08-28) **T-07 abortado y re-asignado**: lancé el Paso 0 en background sin
  preguntar; Adolfo lo paró ("no quiero que ejecutes el corrector") — las 18
  filas ya escritas (brazos bgem3/qwen06b) borradas a petición suya. **El grid lo
  ejecuta Adolfo** (mismo patrón que el indexado de F4), con **gate previo: Adolfo
  repasa el código de la fase antes de ejecutar** — sin su visto bueno explícito
  no se le entrega la orden del grid.
- (2026-08-28) **Revisión de métricas por primeros principios (Adolfo, durante el
  gate)**: el conjunto pasa a **hit rate@k · recall@k (proporcional, espacio
  sección) · precision@k · MRR · tokens** — entra precision/recall clásicas,
  **sale el match numérico** de la Decision 6 (si el guardarraíl de F7 lo
  necesita como insumo, se re-decide entonces). Framework: se propone `ranx`
  (familia trec_eval; RAGAS no tiene MRR ni hit rate, deepeval solo juez LLM —
  verificado en docs). Propuesta con código en `metricas-framework.md`,
  **pendiente de validación de Adolfo antes de aplicar**. También en esta
  revisión: golden movido a `data/eval/golden.jsonl` (Adolfo editó la línea del
  acceptance congelado él mismo; suite completa verde tras el movimiento).
- (2026-08-30) **Métricas ranx APLICADAS** tras validar Adolfo el documento
  (framing final suyo: "la métrica sigue la etiqueta" — `section_ids` separado
  en sus dos papeles: procedencia para citar y puente con la etiqueta):
  `uv add ranx`; `evaluate` reescrito (agregados SOLO de ranx — única fuente de
  cálculo; detalle en crudo `{id, recuperados, tokens, sin_respuesta}`; caso
  borde etiqueta-en-otro-corpus = fallo vía centinela, no exclusión);
  `extract_numbers` eliminado con su métrica; `run()` pasa a una sola llamada
  `collection.get()`. Tests del corrector rehechos RED→GREEN (7). Suite completa
  **143 passed** (−1: murió el test del match numérico), acceptance congelado
  intacto sin editar. PRD y EXPERIMENTOS sincronizados (hit_rate@k pasa a
  métrica principal — el "recall@k" de la jerga RAG era hit rate).
- (2026-08-30) **Review ciega de la fase** (informe fechado en review-report.md):
  0 CRITICAL / 0 HIGH / 2 MEDIUM / 7 LOW, veredicto sólido, árbol intacto.
  Adolfo triató: arreglados 1-7 y 9 (con mejora suya en el 1: caché incremental
  reanudable), descartado el 8. 6 tests nuevos (incl. híbrida contra colección
  real — cerraba el MEDIUM 2). Suite: **149 passed**. El agente revisor murió a
  mitad por corte de red y se reanudó con contexto intacto.
- (2026-08-30) **T-07 hecho** (ejecutado por Adolfo): 36 pasadas densas k=5, tabla
  en EXPERIMENTOS + `results/RESUMEN.html` (vista con filtros, generada por
  `--tabla` — el `--paso0` y la vista nacieron de esta ejecución; el md se
  descartó: "solo la mejor forma de verlo"). Diagnóstico extra a petición de
  Adolfo, sin pasadas nuevas (recomputado del detalle): con etiquetas solo-PADI
  apuntes busca mejor lo suyo (0.94 vs 0.87), pero el cara a cara global
  combined gana 2 preguntas (q007, q105) y pierde 0 — el manual compensa su
  propia interferencia (5-6 preguntas "salvadas").
- (2026-08-30) **T-08 redefinido por Adolfo y ejecutado por él** (desviación del
  plan, método "arrastrar ganadores": qwen8b fijado por dominancia — supersede la
  elección de embeddings prevista para Oleada 1; manual-solo descartado; extras
  se mantuvo abierto): 2 corpus × 3 extras × 2 búsquedas × 3 k = 36 pasadas
  qwen8b (66 filas totales en results/). **Decisión de Adolfo — receta de
  búsqueda: combined + contextual + híbrida; k abierto entre 5 y 10, se cierra
  en F6** (pescar ancho + reranker). Criterio de optimización decidido por
  Adolfo: producto de seguridad → hit_rate y recall mandan, tokens como límite.
  F6 medirá rerank sobre la receta × k∈{5,10} + UN cruce de cordura
  (apuntes-base-híbrida) — brazos extra "bonitos" vetados por regla 6.
- (2026-08-28) **T-04 hecho**: `p5_retrieve.py` (Bm25Index ordenado por chunk_id
  para determinismo; `rrf_fuse` con la fórmula literal y desempate (score desc,
  id asc); dedup HyPE→padre; marcador `.complete` comprobado antes de tocar nada;
  caché BM25 por colección; `ensure_query_vectors`). 11 tests unit RED→GREEN. Un
  test de andamiaje propio tenía la aritmética mal (`k_rrf=1` simétrico empata) y
  se sustituyó por uno más fuerte (k_rrf cambia el orden); el código no cambió.
- (2026-08-28) **Decisión de Adolfo**: sin scores en el `detalle` de `results/`
  (D2: el consumidor probable de F6 es el score del reranker, no la distancia
  densa; y con 0 sin_respuesta la calibración de abstención irá por preguntas
  fuera de dominio nuevas en F6). Las métricas de F5 no los necesitan.
- (2026-08-28) **T-05 hecho**: corrector v1 (`evaluate` puro + `run` que lee solo
  Chroma vía `collection.get(ids=...)` — Decision 8, sin join con chunks.jsonl;
  `write_result` nunca-se-sobreescribe con diff; CLI una-orden-por-pasada). 8
  tests unit con fixture calculado a mano, RED→GREEN.
- (2026-08-28) **T-06 hecho**: caché `query-embeddings-bgem3.json` construida (84
  vectores) y acceptance congelado **6 passed, 0 skipped** — determinismo doble
  pasada incluido. Suite completa: **144 passed** (baseline era 102).
- (2026-08-28) **Decisión de Adolfo al aprobar el test**: `cap` queda **libre**
  en `RetrievalConfig`, con default `512` (opción A, "simpleza"). Matiza el
  "512 (fijo en esta fase)" de Interfaces y la "validación de valores" de T-02:
  se validan solo los campos categóricos (corpus/extras/embedding/search/k); la
  validez real de un cap la impone el marcador `.complete` en runtime
  (invariante 6) — el barrido de tope de F9 necesitará caps distintos igualmente.
