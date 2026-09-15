# Review report: Fase 4 — Embeddings e índice vectorial

**Reviewers**: code-reviewer (standard) + architect (panel, requested by Adolfo — new
shared module, 5 new deps, a non-obvious workaround Fase 5 will inherit).
**Scope**: `.gitignore`, `pyproject.toml`, `src/divefy/pipeline/p4_indexing.py`,
`src/divefy/pipeline/p4_vectorstore.py`, `tests/unit/test_p4_indexing_core.py`,
`tests/acceptance/test_p4_indexing.py`. Excluded as unrelated to this phase (noted to
both reviewers): `.DS_Store`, `Document Parsing.md` (deleted), `promtp fase 4.md`
(untracked notes), `uv.lock` (generated).
**Tampering check**: `git status --porcelain` before and after both reviews — identical.
Neither reviewer touched the tree.

## 3-line summary

Sound design overall — both reviewers independently confirmed Decision #20's
`_collection.upsert()` bypass is *correct and necessary* (`add_texts` really does
silently ignore precomputed embeddings; verified by reading the installed
`langchain_chroma` source and, separately, by live reproduction). The real gap: nothing
currently tests that the stored vector actually came from `embed_text` rather than
`document` — the exact regression Decision #20 exists to prevent would pass every
existing test today. Second gap: the acceptance test's "36 collections exist" check is
self-fulfilling (`get_collection` creates empty collections on miss), so it can't
currently distinguish "built correctly" from "never built."

First thing to fix: add the embedding-level assertion (test gap below), before running
`main()` for real.

## Findings

### CRITICAL

**C1 — No test verifies the stored vector matches `embed_text`, not `document`.**
[CONFIRMED, code-reviewer] This is the exact property Decision #20 exists to
guarantee. Repro: revert `index_model` to call `collection.add_texts(texts=[document],
embeddings=[cache[embed_text]], ...)` instead of `upsert`. Ids, counts, metadata, "no
tipo key" — all still correct. **All 10 existing tests pass.** Every `contextual`/`hype`
row would silently store the raw-chunk embedding instead of the contexto-fused one,
and Decision 6 (the whole point of contextual retrieval) would be violated with zero
red. Reviewer's proposed fix (verified live): a fake `Embeddings` whose vector encodes
text length, then assert the stored vector for a contextual row reflects the *longer*
fused text, not the shorter raw document.

**C2 — "36 collections exist" is not actually verified — the check is self-fulfilling.**
[CONFIRMED, code-reviewer] `get_collection` → `Chroma(..., create_collection_if_not_exists=True)`
(the library default) — confirmed live that calling it alone creates an empty
collection on disk. Repro: `rm -rf data/chroma && uv run pytest
tests/acceptance/test_p4_indexing.py::test_all_collections_exist_and_are_queryable -q`
→ **passes**, and leaves 36 empty collections behind. The row-count tests downstream
would still catch this (0 ≠ expected), so it's not silently wrong end-to-end — but the
existence test's own docstring claim ("fails with collection-not-found errors") is
false, and it means a partial write (crashed mid-`main()`) that leaves *some*
collections empty is indistinguishable from "never ran" by this test alone.

### HIGH

**H1 — No invariant catches a partial/stale `enrich.jsonl`.** [CONFIRMED, architect]
`index_model`'s `if not extras_rows: continue` means running `p4` before `p3`, or
against an `enrich.jsonl` that `p3` only partially wrote (it raises mid-loop on a
contract violation and only prunes/rewrites at the end — `p3_enrich.py:190-214`),
produces short or empty `contextual`/`hype` collections with **no error, no log line**.
Fase 5 would then compare a 683-doc `base` against, say, a 400-doc `contextual` and
attribute the gap to the technique rather than the data. Fix suggested: assert
`len(rows["contextual"]) <= len(rows["base"])` (or the exact prosa-count equality the
plan itself states as invariant — Decision #18) before writing, and refuse to write an
empty collection rather than silently skipping it.

**H2 — All four models' embedding caches stay resident for the whole run (~1.1–1.2 GB),
independently confirmed by both reviewers with converging arithmetic.** Caused by the
corpus-outer/model-inner loop in `main()` — `caches` is built for all 4 models up
front and none is ever freed. Code-reviewer measured live: 4177 distinct texts/model ×
32 bytes/float × summed dims (1024+1024+4096+3072) ≈ 1.23 GB held simultaneously, on
top of two resident `SentenceTransformer`s and Ollama's 8 GB Q8_0 model — on the same
24 GB machine whose tight budget already drove the Q8_0 decision (Decision #4 in plan
Notas). **Swapping the loop to model-outer/corpus-inner removes the need for `cache` as
a parameter entirely** (one `cache = {}` per model, declared once, `main()` doesn't
need to know about caches at all) and caps peak at the single largest model (~549 MB)
instead of the sum of all four.

**H3 — No preflight check on external dependencies before the real run starts.**
[CONFIRMED, code-reviewer] Loop order means a failure on Ollama (not running / model
not pulled) or a missing `OPENAI_API_KEY` surfaces only on pass 3 or 4 of 12 — after
BGE-M3 (~2.3 GB) and Qwen3-0.6B (~1.2 GB) have already downloaded and ~226 texts
embedded. All four in-memory caches are lost on restart; everything before the failure
is re-embedded from scratch. A 2-line preflight (`emb.embed_query("ping")` for each of
the 4 models before the main loop) fails in seconds instead of after real compute —
directly relevant given the T-06 crash already cost one full restart this session.

### MEDIUM

**M1 — Decision #8's text still says "HuggingFaceEmbeddings for the 3 locals";
the Ollama substitution for qwen8b isn't recorded there.** [CONFIRMED, code-reviewer]
The reviewers correctly weren't shown `## Notas` (by design — blind review rule), and
under Decision #8 as written, the code deviates without the Decision itself saying so;
the actual record lives only in Notas and a code comment. Cheap fix: amend Decision #8
(or #7) directly to state the qwen8b/Ollama substitution, not just Notas.

**M2 — Chroma metadata is thin: no `section_ids`/`corpus`/`fichero`/`pagina`.**
[Both reviewers, independently] Only `entry_type`/`contexto`/`parent_chunk_id` are
stored. Consequence: recall@k (defined on `section_id` per the project glossary) and
any citation logic need a join back to `chunks.jsonl` by id; `combined` collections
can't distinguish a PADI hit from a Navy hit without it. Not a defect against this
phase's plan (which never specified this), but worth deciding *now* — re-indexing 36
collections later to add a metadata field costs the whole embedding budget again.
Flagged as an open question for Fase 5's plan, not a fix for this diff.

**M3 — `cap`/`tope` are two independent, unlinked default literals.**
[Both reviewers] `p2_chunking.main(tope: int = 512)` and `p4_indexing.main(cap: int =
512)` — nothing enforces agreement. Relevant once Fase 9 sweeps tope; a mismatch would
silently mislabel every collection name. `config.py` is empty and its own docstring
claims exactly this responsibility.

**M4 — Qwen3-Embedding's query side gets no instruction prefix.** [Both reviewers]
Irrelevant to this phase (document-side only), but `MODELS` is the object Fase 5 will
reuse for queries too, and Qwen3-Embedding is documented to expect an instruction
prefix on the query side. Left undecided, this handicaps Qwen in Fase 5's model
comparison for reasons that have nothing to do with the model itself. Flagged as a
question for Fase 5's plan.

**M5 — `hnsw:space: "cosine"` via the legacy metadata channel — checked live, confirmed
fine on the installed chromadb 1.5.9.** Architect flagged this as PLAUSIBLE (the
library's own docstring recommends a different, newer channel); code-reviewer verified
live that the legacy channel still correctly persists into `configuration.hnsw.space`
and survives `reset_collection()`. **No action needed** — noted here only so it isn't
re-litigated.

**M6 — `fingerprint` (written by Fase 3 precisely to detect stale context) is never
read by `build_rows`.** [CONFIRMED, architect] A chunk's `texto` edited without
re-running `p3` would embed `old_contexto + new_texto` silently. Low likelihood right
now (jsonl files are current), but cheap to guard.

**M7 — Acceptance test's `corpus_enrich_records["combined"]` doesn't apply the same
filter `build_rows` always applies.** [CONFIRMED, code-reviewer] Currently harmless (0
orphan enrich rows in the real data, verified), but latent — an enrich row referencing
a non-prosa/nonexistent id would pass in `build_rows`'s output but fail the `combined`
count check. This is in the **frozen** acceptance test; fixing it needs the unlock
flow, same as the earlier `puntero_tabla` fix this session.

**M8 — `._collection.upsert()` is inlined directly in `p4_indexing.index_model`
rather than wrapped as a named helper in `p4_vectorstore.py`.** [architect,
design suggestion] Not wrong — `_collection` raises a clear error if misused, and a
`langchain_chroma` version bump would break loudly, not silently. But `p4_indexing`
currently reaches through two layers (`Chroma` → `._collection`) to know about
chromadb internals that arguably belong encapsulated next to `get_collection`/
`reset_collection` usage in the vectorstore module.

### LOW

- **Shared mutable dicts between `contextual` and `hype` rows.** [Both reviewers,
  independently reproduced] `hype_rows = list(contextual_rows)` is a shallow copy;
  mutating a hype row's `metadata` dict today would mutate the corresponding
  contextual row too. Nothing mutates them currently — flagged because it's exactly
  the shape the project's own immutability rule warns about.
- `_batched` reimplements `itertools.batched` (stdlib, Python ≥3.12 project).
- No validation that `corpus` is one of the 3 valid values — a typo silently produces
  empty phantom collections rather than an error.
- `zip(batch, embeddings.embed_documents(batch))` without `strict=True` — a provider
  returning fewer vectors than requested truncates silently instead of erroring.
- `tests/acceptance/test_p4_indexing.py` carries ~100 lines of "real" sample data for
  a test whose only assertion is a length-equality dedup check; two of the three
  sample `texto` values are already truncated with `...`, so the "real rows" comment
  is mildly inaccurate. The unit test's 4-line fixtures cover the same ground faster.
- Minor missing coverage: `contexto` present as metadata on contextual rows (Decision
  6's second half), `entry_type == "chunk"` on base rows, and cache reuse *across*
  corpus passes specifically (only within-one-call dedup is tested today).
- Naming nits: `pregunta` is a Spanish identifier in new code (Decision #15 says
  English from this phase); the unit-test file uses Spanish locals throughout while
  the acceptance file is English — pick one. `typing.Callable` → `collections.abc.Callable`.
  `chunk_ids` is redundant with `set(chunk_by_id)`.

## Adherence table

| # | Decision | Status |
|---|---|---|
| 1 | Compute once per model, shared across corpus | Followed — verified live (4177 distinct texts/model, 0 re-embeds on `combined`) |
| 2 | Chunk / chunk+contexto share Chroma id | Followed |
| 3 | HyPE question id `{chunk_id}::hype::{i}` | Followed, unit-tested |
| 4 | `parent_chunk_id` metadata on hype rows | Followed, acceptance-tested |
| 5 | `entry_type`, not `tipo` | Followed, tested in both files |
| 6 | `documents` = raw text; `contexto` is metadata | Followed in code; **not tested at the embedding level (C1)** |
| 7 | 4 models | Followed |
| 8 | All via LangChain / HuggingFaceEmbeddings ×3 | **Deviated** (Ollama for qwen8b) — reason is sound, recorded in Notas + a code comment, **not in the Decision text itself (M1)** |
| 9 | Dense only, no sparse | Followed |
| 10 | `hnsw:space: cosine` on all 36 | Followed — confirmed live it persists correctly (M5) |
| 12 | Join lives in `p4_indexing.py` | Followed |
| 13 | `data/chroma/` gitignored | Followed |
| 14 | `corpus` 3 values, `combined` = no filter | Followed; unvalidated input (LOW) |
| 15 | English identifiers, new code | Mostly — a few Spanish leftovers (LOW) |
| 16 | 36 collections built | Followed in code; **not yet materialized in this tree** — `main()` hasn't successfully completed against real data since the `add_texts` fix, which is expected at this point (review was explicitly requested before that run) |
| 17 | Dynamic, never-hardcoded counts | Followed in both test files |
| 18 | `puntero_tabla` never indexed | Followed — single filter point, unit-tested, cross-checked (683 prosa == `len(enrich.jsonl)`) |
| 19 | `reset_collection()` per pass | Followed — confirmed to exist and behave as described in installed library |
| 20 | `upsert()` bypass of `add_texts` | Followed and **justified** — confirmed by both reviewers independently reading the installed source |
| Out of scope | Fase 5, tope sweep, sparse, rerank | Nothing touched |

## What the diff alone can't answer

- Whether the real `main()` run actually succeeds end-to-end on this machine within
  the 24 GB budget — the memory analysis (H2) is arithmetic on cache size, not a live
  run under load with two resident local models + Ollama simultaneously.
- Runtime behavior of the Ollama/OpenAI arms under the *current* `BATCH_SIZE=32` at
  real scale (the earlier crash was at unbounded batch size; 32 was chosen but not
  stress-tested against the full ~4177-text corpus in one continuous run).
- Whether `OPENAI_API_KEY`/Ollama are actually ready right now for a full run (H3's
  preflight would answer this in seconds; nothing here does).

---

**3 CRITICAL, 3 HIGH, 8 MEDIUM, ~9 LOW.** Top finding: nothing currently verifies the
one property Decision #20 exists to guarantee (C1) — a regression to `add_texts` would
pass every test today.

---

# Review 2026-08-28 — diff completo de Fase 4 (frontera F3 → HEAD, cierre de fase)

Revisor: code-reviewer ciego (plan sin Notas + diff verbatim de src/tests/scripts/
pyproject/modelo-datos). Árbol verificado intacto tras la review. Filtro adversarial
aplicado por el orquestador; anotaciones `[filtro]` donde el contexto de sesión
refuta o matiza.

**Resumen en tres líneas**: el código es sólido — cero CRITICAL, cero HIGH; los
CRITICAL del 27 (C1/C2) están verificados como aplicados y pasando. Lo primero que
convendría arreglar: `cap` solo etiqueta la colección — `main(256)` indexaría chunks
de 512 bajo nombre `-256-` sin que nada falle (muerde exactamente en el barrido de
tope de Fase 9). Todo lo demás es robustez de re-ejecución y huecos de test de
propiedades de eficiencia, no bugs activos.

## Hallazgos (6 MEDIUM, 2 LOW)

1. **[MEDIUM · CONFIRMED] `cap` sin validar contra los datos** — `main(cap)` solo usa
   `cap` en `canonical_name`; con `n_tokens` ya disponible, un guard
   `max(n_tokens) <= cap` en `main()` evitaría un grid entero mal etiquetado.
2. **[MEDIUM · CONFIRMED] `reset_collection()` → `upsert()` no es atómico** — un corte
   entre ambos deja una colección existente y vacía, indistinguible para F5 en
   runtime. `[filtro]` Mitigación real: los conteos del acceptance lo detectan — no
   es silencioso si se corre la suite antes de medir; el riesgo queda en lecturas
   runtime sin suite previa.
3. **[MEDIUM · CONFIRMED] Preflight materializa los 4 backends y nunca los libera** —
   bgem3+qwen06b residentes en proceso toda la pasada, en tensión con la optimización
   de memoria H2. `[filtro]` Trade-off deliberado del 27 (H3, fallo-rápido); la
   pasada real completó en la máquina de 24GB — real pero no urgente.
4. **[MEDIUM · CONFIRMED] Sin retry/persistencia en una pasada de horas** — un fallo
   transitorio del backend descarta todos los vectores en memoria de ese modelo.
   `[filtro]` Riesgo aceptado implícitamente (lotes de 32 acotan la pérdida por
   llamada, no por pasada); relevante para los re-indexados de F9.
5. **[MEDIUM · CONFIRMED] El reuso de cache entre corpus (Decision 1) no tiene test** —
   quitar `cache=cache` en `main()` pasa toda la suite mientras el coste de embedding
   se triplica. `[filtro]` Evidencia observacional en logs (pasadas combined con 0
   llamadas), pero sin guard automatizado — cierto.
6. **[MEDIUM · PLAUSIBLE] Cache sin clave de modelo** — hoy correcto (un dict por
   modelo en `main()`); un refactor que lo ice fuera del bucle mezclaría vectores de
   modelos de igual dimensión sin error. Lo zanjaría: clave `(model, text)` o assert
   de dimensión por colección.
7. **[LOW · CONFIRMED] `chromadb` importado directo sin declarar** — llega transitivo
   vía langchain-chroma; `uv add chromadb` lo hace explícito (una línea).
8. **[LOW · PLAUSIBLE] Upsert único por colección cerca del máximo local (5461)** —
   a tope=256 (F9) el hype combined puede superarlo. Lo zanjaría: reusar `_batched`
   en la escritura.

## Adherencia al plan

| Punto | Veredicto |
|---|---|
| Decisions 3-6, 10, 14, 17-23 | Implementadas y con test |
| `scripts/chroma_view.py` | Señalado fuera de plan — `[filtro]` REFUTADO: petición explícita de Adolfo en sesión (visor tras fallo de `chroma browse`), no scope creep del implementador |
| `langchain-ollama` / Q8_0 en qwen8b | Señalado como desvío de Decision 8 — `[filtro]` REFUTADO: decisión de Adolfo documentada en Notas T-04 (sección excluida del paquete ciego); el confound Q8_0-vs-fp16 se pesó explícitamente y Q8_0 se eligió para minimizarlo |
| Tests debilitados / acceptance tocado | Ninguno — los dos ficheros de test son primer commit; C1/C2 del 27 presentes |
| Out of scope | Respetado |

## Lo que el diff solo no puede responder

Cubierto ya fuera de la review: las 36 colecciones existen y la suite completa (99
tests, incluidos los 11 de acceptance contra el store real) pasó el 2026-08-28.
Queda abierto solo lo de siempre: comportamiento con `langchain_chroma` futuro
(`reset_collection`/`._collection` son superficie semi-privada, ya anotado el 27).