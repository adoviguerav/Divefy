# Plan: Fase 6 — Rerank

**Status**: archived (verified 2026-08-31 — 5/5 PASS, 165 passed, 0 regresiones; ver verify-report.md)
**Fuente**: PRD §7 Fase 6 (revisado 2026-08-30) · exploración 2026-08-28 (sonda en vivo) ·
conversación con Adolfo 2026-08-28/31 · checkpoint F5 `20260830-231920`.

## Goal

Al terminar existe el rerank opcional en el retriever: con `rerank=on`, `retrieve()`
recupera N=20 candidatos, bge-reranker-v2-m3 los reordena leyendo pregunta+chunk
juntos, y devuelve los k mejores según él. Las 3 filas nuevas del grid están medidas
en `EXPERIMENTOS.md` y con la tabla delante Adolfo decide el on/off y cierra la k
(5 vs 10) que la receta v1 dejó abierta.

## Findings

(sonda 2026-08-28 en el M5, datos reales; scratchpad, no en el repo)

- `sentence-transformers` 6.0.0 ya instalado ([pyproject.toml:17](../../../pyproject.toml#L17));
  su `CrossEncoder` carga el modelo — sin dependencia nueva. Modelo cacheado en HF
  (2.1 GB, Apache 2.0).
- Latencia en caliente: **~1.45s por consulta** (~20 pares, batch 8, MPS); carga del
  modelo 36.6s una vez por proceso. ~2 min extra por pasada de 84 preguntas.
- Contexto 8192 (backbone bge-m3): los chunks de 512 tokens + pregunta caben enteros.
- Scores sigmoid picudos: mejor relevante 0.18, mejor ruido 0.0007 (×250) — ordenan
  bien; como valor absoluto no significan nada intuitivo (relevante para el umbral
  de P1, no para esta fase).
- `retrieve()` devuelve `list[str]` de k ids ([p5_retrieve.py:117-151](../../../src/divefy/pipeline/p5_retrieve.py#L117-L151));
  los textos de los candidatos no viajan — hay que traerlos para el reranker.
- El corrector serializa la config explícitamente en la fila
  ([corrector.py:170-174](../../../src/divefy/evals/corrector.py#L170-L174)) — el
  campo nuevo debe entrar ahí o las filas on/off serían indistinguibles.

## Decisions

1. **Umbral de abstención → P1 Post-MVP** (Adolfo, 2026-08-30; PRD ya enmendado):
   las 84 etiquetadas no tienen negativos; se calibrará con el eval fresco.
   Clasificador de intención descartado (responde "¿es buceo?", no "¿está en mi
   corpus?"). Esta fase es solo rerank on/off.
2. **Latencia: sin cronómetro** (Adolfo, 2026-08-30): referencia = sonda; medición
   real por etapa con LangSmith en Fase 8. La fila de `results/` sigue determinista.
3. **Filas del grid** (Adolfo, sesión F5): rerank on sobre la receta v1
   (combined·contextual·qwen8b·híbrida) × k∈{5,10} + UN cruce de cordura
   (apuntes·base·qwen8b·híbrida·k5 con rerank). Brazos extra vetados. Los off ya
   existen del T-08 → **3 pasadas nuevas**, las lanza Adolfo.
4. **Interfaz** (Adolfo, 2026-08-31): rerank como etapa interna de `retrieve()` —
   contrato público `list[str]`, corrector y acceptance congelado de F5 intactos.
   Alternativa descartada: etapa aparte llamada por el corrector (tocaba contrato y
   corrector sin comprar nada).
5. **Defaults aprobados** (Adolfo, 2026-08-31): `rerank: bool = False` en
   `RetrievalConfig`; `run_id` con sufijo `-rerank` cuando on; N=20 como parámetro
   con default (constante en `p6_rerank.py`). Sonda a N=40 solo si on gana (PRD).
6. Textos de los candidatos: un `collection.get(ids=candidatos)` tras la fusión —
   una llamada, determinista, sin cambiar `Bm25Index` ni el lado denso.

## Context

- [p5_retrieve.py:117-151](../../../src/divefy/pipeline/p5_retrieve.py#L117-L151) —
  `retrieve()`: el punto de enganche; el flujo denso/híbrido se ensancha a N
  candidatos cuando rerank está on.
- [config.py:14-44](../../../src/divefy/config.py#L14-L44) — `RetrievalConfig`
  frozen + `run_id`; el campo nuevo con default mantiene válidas las configs de F5.
- [corrector.py:137-183](../../../src/divefy/evals/corrector.py#L137-L183) —
  `run()`/`_run_and_write`: no cambia salvo el `config_dict` (campo `rerank`).
- [p4_vectorstore.py:17-23](../../../src/divefy/pipeline/p4_vectorstore.py#L17-L23) —
  `get_collection`; `collection.get(ids=...)` para los textos.
- `tests/acceptance/test_p5_retrieval.py` — congelado (red de regresión; enmienda
  solo con desbloqueo de Adolfo). El estilo a seguir: conteos dinámicos, skip
  nombrando el artefacto que falta.
- Patrón de carga perezosa de modelos: `MODELS` en
  [p4_indexing.py:98-106](../../../src/divefy/pipeline/p4_indexing.py#L98-L106).
- Reglas de la casa: librería estándar sobre código propio; Adolfo lanza las
  pasadas del grid, nunca yo; desempates deterministas (score desc, id asc).

## Acceptance contract

- [ ] Con rerank on, `retrieve()` devuelve exactamente k ids, **subconjunto de los
  N=20 candidatos**, ordenados por score del reranker descendente (desempate id
  asc) — checked by: unit con reranker inyectado/fake + acceptance con el modelo
  real sobre la colección de la receta.
- [ ] Con rerank off, el comportamiento es idéntico a F5: la suite completa de F5
  pasa sin tocar — checked by: `uv run pytest -q` (149 tests, 0 regresiones).
- [ ] `run_id` de una config con rerank on termina en `-rerank`; con off no cambia
  respecto a F5 — checked by: unit de config.
- [ ] Determinismo: dos pasadas del corrector con rerank on producen ficheros byte a
  byte idénticos — checked by: acceptance (skip si falta `data/chroma/` o el modelo
  en la caché HF).
- [ ] Las 3 filas nuevas están en `results/` y las casillas F6 de `EXPERIMENTOS.md`
  rellenadas; decisión de on/off y de k anotada — checked by: inspección; la
  decisión es de Adolfo.

Gate: `uv run pytest tests/unit/test_p6_rerank_core.py tests/acceptance/test_p6_rerank.py -q`
y la suite completa `uv run pytest -q`.

## Out of scope

- Umbral de abstención y preguntas trampa (→ P1, eval fresco).
- Sonda N=40 (solo si on gana — se decide con la tabla).
- Jina Reranker v3 (dormida: 1.45s no molesta; revisar licencia si despierta).
- Latencia instrumentada (→ LangSmith, Fase 8).
- Cualquier brazo del grid fuera de las 3 filas fijadas.

## Interfaces

```python
# config.py
@dataclass(frozen=True)
class RetrievalConfig:
    ...                        # campos F5 sin cambios
    rerank: bool = False       # run_id += "-rerank" cuando True

# p6_rerank.py
N_CANDIDATES = 20
def rerank(query: str, candidates: list[tuple[str, str]], k: int) -> list[str]
    # candidates = [(chunk_id, texto)] en orden de retrieval; devuelve k ids
    # por score desc (desempate id asc). Carga perezosa del CrossEncoder,
    # una vez por proceso.
```

## Tasks

- **T-01 · UPDATE `config.py`** — campo `rerank: bool = False` + sufijo en
  `run_id`; UPDATE `corrector.py` `config_dict` con el campo.
  VALIDATE: `uv run pytest tests/unit/test_config.py -q`.
- **T-02 · CREATE `p6_rerank.py`** — `rerank()` con carga perezosa del
  CrossEncoder (sigmoid, MPS) y corte determinista.
  VALIDATE: `uv run pytest tests/unit/test_p6_rerank_core.py -q` (con fake, sin
  modelo real).
- **T-03 · UPDATE `p5_retrieve.retrieve()`** — con rerank on: ensanchar el flujo a
  N=20 candidatos (denso y fusión al ancho N), `collection.get` para textos,
  llamar a `p6_rerank.rerank`, devolver k ids.
  VALIDATE: unit de T-02 + `uv run pytest -q` (0 regresiones F5).
- **T-04 · CREATE `tests/acceptance/test_p6_rerank.py`** — subconjunto/orden con
  modelo real + determinismo del corrector con rerank on (skips si faltan
  artefactos).
  VALIDATE: `uv run pytest tests/acceptance/test_p6_rerank.py -q`.
- **T-05 · Medición** — Adolfo lanza las 3 pasadas; rellenar `EXPERIMENTOS.md` F6,
  decidir on/off y k, sincronizar la receta en el PRD. Matiz de Adolfo (2026-08-31):
  las filas son **candidatas a comparar**, no un veredicto precocinado — al llegar
  la tabla, proponerle cómo compararlas bien en `results/RESUMEN.html` (vista
  `--tabla`).
  VALIDATE: 3 ficheros en `results/` + casillas rellenadas + decisión anotada.

## Notas

- (2026-09-07) **Enmienda abierta (decisión de Adolfo, durante F7): marcar
  `TestCorrectorDeterminismWithRerank::test_run_twice_serializes_byte_identical`
  como `@pytest.mark.slow`.** Antes: corre en cada pasada de la suite (~4 min de
  los ~6.5 totales — 84 preguntas × 2 con reranker real). Después: corre solo
  cuando se piden los slow, y `/verify` pasa a lanzar la suite completa CON slow
  (`uv run pytest -m ""`), que es la frontera donde este examen aporta. Motivo:
  frecuencia — el determinismo de la cadena no cambia entre ediciones que no la
  tocan; vigilarlo en cada gate rápido cuesta 4 min y no compra señal nueva.
  Procedimiento de test congelado: Adolfo desbloquea (`touch
  .claude/plans/.unlock-tests`), se aplica el marcador, re-aprueba y retira el
  marcador. Pendiente de ese desbloqueo.
- (2026-08-31) **Step zero**: suite completa en verde antes de tocar nada — 149
  passed, 5 deselected.
- (2026-08-31) **Nombre "brazo" retirado del vocabulario** (Adolfo): a partir de
  ahora se dice **config** (una config = una combinación del grid = una fila).
- (2026-08-31) **Sonda de determinismo** (pregunta de Adolfo, medida antes de
  aceptar el criterio 5): bge-reranker-v2-m3 es bit a bit determinista en el M5 —
  mismo proceso idéntico, batch 8 vs 4 idéntico (diff 0.0), dos procesos → mismo
  hash de scores. El test de determinismo vigila la cadena (rerank+corrector+
  serialización), no el modelo.
- (2026-08-31) **N_CANDIDATES se queda en `p6_rerank.py`** tras verificar el
  convenio con fuentes (PEP 8 + discuss.python.org): constante usada por un solo
  módulo → en su módulo; se centralizaría solo si pasara a compartirse. Corrección
  registrada: "constants.py central = anti-patrón" era un exceso mío, retirado.
- (2026-08-31) **RED de aceptación**: `tests/acceptance/test_p6_rerank.py` escrito
  por agente ciego, aprobado por Adolfo sin cambios. Capturado: 8 failed + 4 errors,
  todos `TypeError` (kwarg `rerank` inexistente) / `ImportError` (`rerank`,
  `N_CANDIDATES`) — el RED esperado, ningún test pasó en vacío.
- (2026-08-31) T-01→T-03 en verde incremental; suite F5 completa sin regresiones
  tras T-03 (152 passed incl. 3 unit nuevos de p6).
- (2026-08-31) **GREEN de aceptación**: `tests/acceptance/test_p6_rerank.py`
  12 passed en 336s (dos pasadas completas del corrector con rerank on,
  byte-idénticas). T-01→T-04 completas; queda T-05 (las 3 pasadas, las lanza
  Adolfo, y la decisión on/off + k con la tabla delante).
- (2026-08-31) **Desviación (aprobada por Adolfo): flag `--rerank` en el CLI del
  corrector** — no estaba en las tareas del plan, pero el CLI es el único punto
  de entrada (regla F5) y sin él las configs con rerank no eran lanzables.
  3 líneas en `main()`; suite en verde tras el cambio (152 passed).
- (2026-08-31) **Review ciega: 0C/2H/4M/2L** (`review-report.md`). Fixes aplicados
  con OK de Adolfo: H-1 (columna `rerank` en RESUMEN.html, `.get` para las 66
  filas legacy, CSS a -n+7), H-2 (test unit del ensanche a N_CANDIDATES — la
  mutación `n = config.k` ahora falla), M-3 (`text_by_id`/`_text`), M-4 (newline),
  L-2 (comentario de _BATCH_SIZE). M-1/M-2 aceptados como avisos (mono-máquina).
  Suite tras fixes: 153 passed; tabla regenerada sobre 66 runs sin error.
  L-1 cerrado por Adolfo ("ese valor no lo vemos"): score crudo (Identity) en vez
  de sigmoid — solo importa el orden; sigmoid volverá si llega el umbral (P1).
  Validado contra el modelo real tras el cambio (11 passed).
- (2026-08-31) **T-05 hecha**: 3 pasadas lanzadas por Adolfo, tabla F6 de
  EXPERIMENTOS.md rellenada con diagnóstico (14/60 preguntas cambian manual→apuntes,
  0 huérfanas). **Decisión de Adolfo: rerank ON, k=10** — config base actualizada
  en EXPERIMENTOS.md con dos condiciones de re-juicio escritas (k con LLMs
  pequeños; on/off si la doble cita sufre). Pendiente externo: decidir si se corre
  la sonda N=40 (condición del PRD activada al ganar on).
