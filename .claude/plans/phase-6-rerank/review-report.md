# Review — Fase 6 Rerank (2026-08-31)

**Revisor**: code-reviewer ciego (plan sin Notas + diff + reglas). Árbol verificado
intacto tras la review. Tests congelados: sin tocar.

**Resumen en tres líneas**: la implementación T-01→T-04 es correcta y el camino
rerank-off es demostrablemente idéntico a F5 (0 regresiones). Nada CRITICAL. Lo
primero a arreglar: `RESUMEN.html` no distingue una fila rerank de su gemela off
(H-1) — es justo el artefacto del que Adolfo decide en T-05.

## Hallazgos

### HIGH

- **H-1 · CONFIRMED — la tabla HTML no distingue filas rerank**
  [corrector.py:239](../../../src/divefy/evals/corrector.py#L239):
  `_CONFIG_COLS` no incluye `rerank` (ni `run_id`). Repro: misma config con y sin
  `--rerank` + `--tabla` → dos filas idénticas en las 6 columnas de config con
  métricas distintas. Trampas del fix: las ~66 filas viejas no tienen clave
  `rerank` (línea 246 haría KeyError → `.get("rerank", False)`) y el CSS
  hardcodea `nth-child(-n+6)` (línea 257 → `-n+7`).
- **H-2 · CONFIRMED — nada verifica el ensanche a N=20**
  [test_p6_rerank.py:140](../../../tests/acceptance/test_p6_rerank.py#L140):
  mutando `n = config.k` en p5_retrieve.py:137 toda la suite sigue verde — la fase
  degeneraría a "reordenar los k que ya tenías" sin que el examen lo note. El
  acceptance está congelado → el fix va en `tests/unit/test_p6_rerank_core.py`
  (capturar `len(candidates)` con monkeypatch sobre una colección fake y afirmar 20).

### MEDIUM

- **M-1 · PLAUSIBLE** — en una máquina sin la caché HF los tests pesados se saltan
  en silencio y la suite queda verde con solo los 4 asserts de config. Mitigado
  aquí: corrieron de verdad (12 passed, 5:36). Pedir `pytest -rs` en /verify.
- **M-2 · CONFIRMED (aceptado por contexto)** — `device` depende del entorno
  ([p6_rerank.py:19](../../../src/divefy/pipeline/p6_rerank.py#L19)): scores MPS vs
  CPU difieren → en otra máquina `write_result` fallaría ruidoso contra la fila
  committeada. Proyecto mono-máquina Apple Silicon; fallo ruidoso, no corrupción.
- **M-3 · CONFIRMED** — identificadores en español en código nuevo:
  `texto_by_id` (p5_retrieve.py:160), `_texto` (p6_rerank.py:29) → `text_by_id`,
  `_text` (regla: identifiers en inglés).
- **M-4 · CONFIRMED** — falta newline final en p6_rerank.py.

### LOW

- **L-1** — `activation_fn=torch.nn.Sigmoid()` re-declara el default de la librería
  (verificado en ST 6.0 para num_labels=1). Matiz con sustancia: sigmoid satura —
  dos chunks muy buenos pueden redondear ambos a 1.0 en float32 y desempatarse
  alfabéticamente en vez de por relevancia; logits crudos discriminan mejor arriba.
  Sigmoid solo será necesario cuando exista el umbral (P1). Decisión de Adolfo.
- **L-2** — `_BATCH_SIZE = 8` sin comentario de motivo (no afecta al orden:
  predict() re-ordena por longitud internamente y lo deshace).

## Refutados durante la review (para no re-litigar)

- Regresión rerank-off: con `rerank=False`, `n == k` y el flujo reduce línea a
  línea al de F5. Sin repro.
- KeyError en `texto_by_id`: todo candidato existe en la colección (las filas
  chunk están en los 3 extras; BM25 sale de filas chunk de la misma colección).
- Orden de `collection.get()`: no preserva orden de entrada — el código re-indexa
  por dict, correcto tal cual está.
- Determinismo de `predict()`: función pura de la lista de candidatos; desempate
  total tras dedup. (Coincide con la sonda medida: bit a bit idéntico.)
- Limpieza del on/off: el reranker ve el mismo texto de chunk en base/contextual/
  hype — la comparación del grid es limpia.

## Adherencia al plan

| Punto | Estado |
|---|---|
| Tareas T-01→T-04 | implementadas, nada extra salvo la desviación autorizada (flag `--rerank` CLI) |
| Out of scope respetado | sí (sin umbral, sin N=40, sin instrumentación) |
| Tests congelados | intactos |
| Patrones de Context | seguidos (lazy load, desempate determinista, librería estándar) |

## Lo que el diff solo no responde

RED real capturado (está en Notas del plan, fuera del paquete ciego) · determinismo
punta a punta en MPS (corrido: 12 passed) · las 3 filas de T-05 (pendientes, Adolfo) ·
latencia del pipeline ensanchado: N=20 con híbrida+hype pide 80 hits densos por
consulta — la sonda de 1.45s midió los 20 pares del reranker, no ese ensanche.