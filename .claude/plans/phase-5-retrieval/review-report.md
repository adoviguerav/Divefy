# Review — Fase 5 (retrieval + corrector), 2026-08-30

**Revisor**: code-reviewer ciego (plan sin Notas + metricas-framework sin estado +
diff completo `ed3be72..working tree`). Verificó ejecutando, no solo leyendo:
suite unit + acceptance en verde por su cuenta, repros en vivo contra las 36
colecciones reales. `git status` idéntico antes y después — no tocó el árbol.

## Resumen en tres líneas

Sólido: el cableado de métricas es fiel al spec (ranx como única fuente, recall
sin cortar, centinela de otro-corpus y rama todo-sin_respuesta cubiertas); nada
bloquea el Paso 0 por corrección. Lo primero a arreglar: la escritura no atómica
de la caché de query-embeddings antes de un barrido largo e interrumpible.

**0 CRITICAL · 0 HIGH · 2 MEDIUM · 7 LOW**

## MEDIUM

1. **[CONFIRMED] Caché de query-embeddings escrita sin atomicidad** —
   `p5_retrieve.py:98`. `write_text` trunca y reescribe; un Ctrl-C/OOM a mitad
   deja el fichero corrupto y la siguiente pasada muere en `json.loads` con la
   única copia perdida (para openai3large, dinero; para qwen8b, una pasada de
   Ollama). Refutación parcial: ventana pequeña (~4 escrituras en todo el Paso
   0), pero coste alto y la regla global prohíbe simplificar el error handling
   que evita pérdida de datos. Fix de 2 líneas: escribir a `.tmp` + `replace`.
2. **[CONFIRMED] La ruta híbrida no tiene cobertura contra colección real** —
   el acceptance congelado fija `search="densa"` y ningún test la ejerce sobre
   Chroma real; `build_bm25` solo se prueba con `FakeCollection`. El revisor la
   corrió en vivo (base y hype, bgem3): funciona — no está rota, está *sin
   verificar*. T-08 produce números de la híbrida: falta un test NO congelado
   (o sign-off manual explícito) antes de reportar esos números.

## LOW

3. **[PLAUSIBLE] `ZeroDivisionError` sin diagnóstico** si el golden se queda sin
   filas `uso=eval` (`corrector.py:93`) — el guard de labels pasa con `[]==[]`.
   Entrada degenerada; `test_labels.py` lo cazaría pero es otro comando.
4. **[PLAUSIBLE] `retrieve` puede devolver <k en silencio** (densa+hype) si los
   4·k hits colapsan a menos de k padres (`p5_retrieve.py:129-131`). Hoy
   irreproducible (84 queries × 3 colecciones hype a k=10: mínimo 10). Riesgo
   real en F9 con tope 256 (más filas hype por padre). El fallo sería silencio,
   no ruido.
5. **[CONFIRMED] `CORPUS_VALUES` duplicada** en `config.py:7` y
   `p4_indexing.py:19` — trampa de deriva, sin bug vivo. Ídem `_read_jsonl`
   definida 3 veces.
6. **[CONFIRMED] Import perezoso de MODELS sin efecto en la ruta real** — `run()`
   lo importa incondicionalmente una línea después; y el comentario de
   `corrector.py:149` da un motivo que no es el real.
7. **[CONFIRMED] `n_preguntas` ≠ denominadores de ranking** cuando haya
   sin_respuesta>0 — la fila no registra cuántas preguntas puntuaron; dos filas
   de tandas de etiquetado distintas serían incomparables en silencio. Seguro
   barato: una clave más (p.ej. `n_puntuadas`).
8. **[CONFIRMED] Artefactos de edición**: espacio colgante tras `OVERSAMPLE = 4`
   y comentario `#define what is a "word" for BM25` (inglés, sin espacio tras
   `#`) en `p5_retrieve.py:17-19`. No hay linter configurado que los cace.
9. **[CONFIRMED, preexistente] Rutas relativas al CWD** en corrector y
   `chroma_directory()` — el corrector solo funciona desde la raíz del repo.
   Convención heredada de p4, no introducida aquí.

## Adherencia al plan

| Chequeo | Resultado |
| --- | --- |
| Construido sin tarea que lo pida | Nada de consecuencia (`_BM25_CACHE` con comentario ponytail justificado; `Bm25Index` dentro de la interfaz abierta) |
| Out of scope construido | Nada (sin rerank/umbral/juez/latencia/tope/Search API) |
| Tests de acceptance editados o debilitados | Ninguno — `test_p5_retrieval.py` aparece como fichero nuevo puro, 0 líneas borradas |
| Interfaces vs plan | Todas conformes; única desviación: orden de campos de `RetrievalConfig` (cap al final por el default) — inofensiva, todos los call sites usan keywords |
| Contrato pendiente | T-07/T-08 (results/ vacío, tablas EXPERIMENTOS, ancla) — estado de fase, no defecto |

Observación (no hallazgo): el `pytest.raises(Exception)` del acceptance congelado
es ancho, pero `test_p5_retrieve_core.py:135` lo cierra con
`RuntimeError, match="complete"`.

## Lo que el diff solo no responde

Comportamiento con las 36 colecciones bajo el barrido completo (T-07), la calidad
de las etiquetas (auditada por proceso aparte, fuera del alcance del revisor), y
los números reales de la híbrida (ejecutada en vivo una vez, nunca asertada).

## Resolución (Adolfo, 2026-08-30)

| # | Hallazgo | Decisión | Estado |
| --- | --- | --- | --- |
| 1 | Caché no atómica | Arreglar + mejora de Adolfo: escritura incremental (persiste tras CADA vector → reanudable) | Hecho + test |
| 2 | Híbrida sin cobertura real | Test nuevo NO congelado sobre colección real (base y hype, vector cacheado) | Hecho + test |
| 3 | ZeroDivision golden vacío | Excepción con mensaje claro | Hecho + test |
| 4 | <k silencioso en densa+hype | Solo warning (decisión: "avisar y ya") | Hecho |
| 5 | CORPUS_VALUES duplicada | config como fuente única; p4_indexing importa | Hecho + test |
| 6 | Import perezoso inerte | MODELS arriba en p5_retrieve y corrector (1.02s de import, medido) | Hecho |
| 7 | n_preguntas vs denominadores | Clave `n_puntuadas` en el resumen | Hecho + test |
| 8 | Artefactos de edición | NO tocar (decisión de Adolfo) | Descartado |
| 9 | Rutas relativas al CWD | `REPO_ROOT` en p4_vectorstore; corrector/caché/chroma anclados | Hecho + test |

Suite tras los fixes: **149 passed** (unit 111 + acceptance completo), acceptance
congelado intacto.

## Incidencia del proceso

El agente murió a mitad por un corte de red (ENOTFOUND) y fue reanudado con su
contexto intacto; el informe es de la pasada completa.
