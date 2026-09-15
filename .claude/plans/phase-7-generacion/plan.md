# Plan: Fase 7 — Generación + juez

**Status**: approved
**Fuente**: PRD §7 Fase 7 (enmendado 2026-08-31) · conversación con Adolfo 2026-08-31
(recorte MVP) · checkpoint F5 `20260830-231920` · explore del repo 2026-08-31.

## Goal

Al terminar, los 4 modelos (Sonnet 5, Haiku 4.5, Qwen 3.5 9B, Qwen 3.5 4B) responden
tras una interfaz única en `llm/`; `p7_generate` produce respuestas con citas inline
sobre el estado que ya trae los trozos del retrieval; el guardarraíl numérico verifica
cada cifra contra la chuleta de constantes; y `llm_evaluator` escribe una fila por
modelo (juez calibrado + abstención). Con las 4 filas delante, Adolfo elige modelo.

## Findings

(explore 2026-08-31 sobre el repo, evidencia citada)

- **Censo de etiquetas: 0 de las 84 tienen `sin_respuesta: true`** (grep sobre
  `data/eval/labels.jsonl`). Implicación: en F7 la abstención solo se mide como
  **falsa abstención** (el modelo se abstiene teniendo respuesta = fallo); los
  negativos reales ("debería abstenerse") llegan con el eval fresco (P1). La
  condición de activación del grader se juzga con el juez (respuestas suspensas /
  inventadas), no con la abstención.
- Golden: campos `id`, `pregunta`, `respuesta_esperada`, `uso` — `respuesta_esperada`
  es la referencia del juez, ya existe.
- Deps ([pyproject.toml:6-20](../../../pyproject.toml#L6-L20)): `langchain-openai` ya
  instalado (trae `openai` transitivo) → **el juez GPT no necesita dependencia
  nueva**. NO están: SDK de Anthropic, `mlx-lm`, `deepeval`. `langchain-ollama` está
  instalado sin uso conocido — no tocar, solo anotado.
- Patrón LLM de la casa: [p3_enrich.py:1-40](../../../src/divefy/pipeline/p3_enrich.py#L1-L40)
  — cliente perezoso a nivel de módulo (los tests con fakes nunca construyen el
  cliente real), `dotenv`, `REINTENTOS = 1`, contrato verificado tras la llamada.
- [retrieval_evaluator.py:105-129](../../../src/divefy/evals/retrieval_evaluator.py#L105-L129)
  (`serialize`/`write_result`, política nunca-sobreescribir con diff) y
  [137-176](../../../src/divefy/evals/retrieval_evaluator.py#L137-L176) (forma de
  `run()`: config → `{"config", "resumen", "detalle"}`) — el molde de `llm_evaluator`.
- `retrieve()` devuelve `list[str]` de k ids; los textos y metadata se traen con
  `collection.get(ids=...)` (patrón ya usado en F6).
- [config.py](../../../src/divefy/config.py) — `RetrievalConfig` frozen (con `rerank`
  de F6, aún sin commitear); la config de generación debe envolverla sin romper su
  `run_id`.
- `p7_generate.py` y `p7_guardrail.py` son stubs de 1 línea; `llm/__init__.py` vacío.
- F6 tiene pendiente su T-05 (3 pasadas + decisión on/off y k, las lanza Adolfo): la
  **implementación** de F7 no está bloqueada; la **medición** (T-07) sí — corre sobre
  la receta cerrada.

## Decisions

(cerradas con Adolfo el 2026-08-31, ya reflejadas en el PRD; append-only)

1. **Interfaz única en `llm/`**: una firma de llamada, dos backends (SDK de API /
   mlx-lm local); los 4 modelos son 4 configs; `p7_generate` no sabe cuál hay detrás.
2. **Salida: texto con citas inline (opción b)** — el modelo cita en la prosa; las
   fuentes/metadata verificables viajan deterministas desde el retrieval en el estado
   de la respuesta. Structured output (JSON) descartado: frágil en locales pequeños y
   no compra nada.
3. **Condensador → Fase 8** (Gemini Flash fijo, fuera de la ablación). Fuera de esta
   fase.
4. **Grader fuera del MVP**, con condición de activación medible (ver Findings).
5. **`llm_evaluator` separado** (el "corrector v2" murió; `corrector.py` →
   `retrieval_evaluator.py`, renombre ya aplicado). Métricas: **juez + abstención**.
   Descartados: exactitud numérica como métrica separada, latencia/coste elaborados.
6. **Chuleta asistida**: regex extrae `número + unidad + frase donde vive` de la
   prosa procesada, acotado a apuntes PADI + números Navy de los conflictos; Adolfo
   audita leyendo frases. Regex-solo vs pasada LLM etiquetadora: **se decide en T-02
   con una muestra real delante** (gate de Adolfo).
7. **Juez**: un GPT, temperatura 0, rúbrica aprobado/suspenso, calibración con 20-30
   etiquetas de Adolfo (mezcladas de los 4 modelos), ≥90% de acuerdo o se ajusta la
   rúbrica. Framework (deepeval vs llamada directa con el `openai` ya instalado):
   **gate en T-05** con el censo delante — regla de la casa (librería estándar), pero
   si deepeval solo aporta un wrapper, menos deps gana.
8. **Secuencia MLX**: backend API primero; el backend local se implementa **después
   del repaso de teoría de IA local de Adolfo** (prompt de arranque entregado
   2026-08-31).
9. Los IDs exactos de modelo (Anthropic/OpenAI) se confirman al implementar con la
   referencia de API vigente, no de memoria.
10. **Plantillas de librería antes que prompts propios** (Adolfo, 2026-08-31): nunca
    inferir un prompt a ciegas — buscar primero una plantilla publicada (métrica
    built-in de deepeval para el juez; plantilla RAG estándar para generación) y
    partir de ella, adaptando solo lo que el PRD exige (citas inline, números
    textuales, idioma, plantilla de abstención). Refuerza el gate de T-05 hacia
    deepeval.
11. **Gates de ejecución** (Adolfo, 2026-08-31): cada task termina con su revisión
    de código antes de continuar; toda llamada real a API y toda pasada del eval la
    lanza él.
12. **División de módulos: transporte vs dominio** (Adolfo, 2026-08-31). `llm/` es
    transporte puro — los 4 modelos del experimento y nada más; el juez NO pasa por
    ahí (es fijo, fuera de la ablación, y con deepeval trae su propio cliente). Los
    prompts no viven en el módulo del cliente: `p7_generate` carga el suyo,
    `evals/judge.py` la rúbrica, `evals/llm_evaluator.py` queda solo con el bucle,
    los agregados y la fila. Alternativas descartadas: meter el cliente del juez en
    `llm/` (lo mete en una interfaz diseñada para la ablación sin comprar nada) y
    juez inline en `llm_evaluator` (el archivo feo que se quería evitar).
13. **Prompts como fichero versionado, en `.txt`** (Adolfo, 2026-08-31). Motivo: esto
    es una ablación — cambiar el prompt entre la pasada de Haiku y la de Qwen las
    hace incomparables y hoy nada en `results/` lo delataría. Van en `prompts/` en la
    raíz del repo (anclado a `REPO_ROOT` como `data/` y `results/`, misma convención;
    vetable si los prefieres dentro del paquete), con la
    versión en el nombre y esa versión se estampa en la fila (`prompt_version`),
    igual que `run_id` estampa la config. **`.txt` y no `.md` porque el hook
    PostToolUse ejecuta Prettier (3.9.6, verificado en vivo 2026-08-31) sobre todo
    `.md` escrito**: normalizaría marcadores, encabezados y espacios, cambiando en
    silencio los bytes que ve el modelo. El contenido sí puede llevar estructura
    markdown. Descartado un registro de prompts con servidor: resuelve problemas de
    varios equipos, aquí hay uno.
14. **Respuestas procedimentales en pasos numerados** (Adolfo, 2026-09-02): cuando lo
    que responde el corpus es un procedimiento (montaje de equipo, buddy check,
    ascenso de emergencia), el prompt pide pasos numerados y el razonamiento de cada
    paso, no un párrafo corrido. Requisito explícito para T-04: si la plantilla RAG
    publicada no lo trae, se añade. **No** es entrega paso-a-paso por turnos (el
    patrón del asistente de procedimientos de astronautas, que sirve a alguien
    ejecutando con las manos ocupadas): Divefy es consultivo, la respuesta llega
    entera.
15. **Marcadores de fuente en el texto: fuera** (delegado por Adolfo, 2026-09-02). La
    metadata del retrieval ya identifica los k trozos de forma determinista; un
    marcador tipo `<<FUENTE ...>>` solo añadiría atribución por afirmación, y cargar
    el prompt con formato estricto ensancha la brecha local-vs-API por
    seguimiento-de-instrucciones en vez de por conocimiento — que no es lo que mide
    el grid. Reconsiderable en F8 si `/fuentes` lo pide.
16. **Guardarraíl v1: solo pertenencia** (Adolfo, 2026-09-07): `verify()` extrae
    pares número+unidad de la respuesta (regex + normalización ortográfica de
    unidad: minutos→min, horas→h — mismo mapa que la chuleta), y comprueba
    pertenencia contra `constantes.jsonl`. Ni contexto ni fuente en v1. La
    verificación por fuente del PRD ("un número es válido si coincide con la
    fuente que la respuesta cita") queda como mejora anotada CON mecanismo
    definido por Adolfo: no parsear atribuciones en prosa (frágil), sino cruzar
    contra la metadata determinista del retrieval — los chunks del `Answer`
    llevan `corpus`/`section_id`; número solo-Navy con contexto solo-apuntes =
    señal. Condición de activación: el eval de T-07 muestra atribuciones
    cruzadas reales. Unidades "segundos" y "pies": fuera del set en v1 (números
    con unidad no reconocida no se vigilan).
17. **Logs de estado por etapa** (Adolfo, 2026-09-07, requisito de T-04): `logger.debug`
    con el estado serializado a JSON (`dataclasses.asdict` + `json.dumps`) en cada
    frontera — tras retrieval (pregunta + chunks), tras generación (+ respuesta,
    abstención), tras guardarraíl (+ verdict). Stdlib `logging` puro, en silencio
    salvo `level=DEBUG`; LangSmith dará la vista equivalente en F8, esto es la
    versión gratis desde la primera pasada. El `Answer` es frozen: cada etapa
    construye objeto nuevo, el log enseña esa progresión.

## Context

- [retrieval_evaluator.py](../../../src/divefy/evals/retrieval_evaluator.py) — molde
  de `llm_evaluator`: reusar `serialize`/`write_result` tal cual (importándolos, no
  copiándolos) y la forma de `run()`.
- [p5_retrieve.py:117-160](../../../src/divefy/pipeline/p5_retrieve.py#L117-L160) —
  `retrieve()` con rerank integrado (F6): el punto del que salen los k ids.
- [p3_enrich.py:1-60](../../../src/divefy/pipeline/p3_enrich.py#L1-L60) — patrón
  cliente perezoso + reintento único + verificación de contrato: seguirlo en los
  backends y en el juez.
- [config.py](../../../src/divefy/config.py) — `RetrievalConfig`; la config de
  generación (modelo) envuelve, no muta.
- `data/eval/golden.jsonl` (`respuesta_esperada`), `data/eval/labels.jsonl`
  (`sin_respuesta`, secciones por corpus).
- `results/` — una fila por `run_id`, nunca se sobreescribe; `RESUMEN.html` es la
  vista.
- `prompts/` — ficheros `.txt` versionados (decisión 13); su nombre es la fuente de
  `prompt_version`. No convertirlos a `.md` jamás: el hook los reformatearía.
- Avisos: el hook bloquea editar `.env` (las claves las pone Adolfo a mano); el hook
  PostToolUse pasa Prettier a todo `.md` escrito (verificado: 3.9.6 disponible) —
  motivo del `.txt` de los prompts; **Adolfo lanza todas las pasadas** (regla de
  memoria); la generación no es determinista — la política nunca-sobreescribir aplica
  igual (repetir una pasada = borrar la fila a mano, decisión consciente).
- `tests/acceptance/` congelados de F5/F6: red de regresión, no se tocan.

## Acceptance contract

- [ ] La interfaz de `llm/` responde a la misma firma para los 4 modelos; con un
  backend fake inyectado, `p7_generate.answer()` produce el estado completo
  (pregunta, trozos con ids/textos/metadata del retrieval, respuesta) — checked by:
  unit con fake, sin red.
- [ ] Con contexto vacío o sin soporte forzado (fake), la respuesta es exactamente la
  plantilla de abstención — checked by: unit.
- [ ] Ante una pregunta procedimental del golden, la respuesta llega en pasos
  numerados (no un párrafo corrido) — checked by: inspección de la pasada real sobre
  las preguntas de procedimiento; el prompt lo exige explícitamente.
- [ ] Guardarraíl: fixture de 10 respuestas sintéticas (5 con números correctos, 5
  alterados) — pilla las 5 malas, deja pasar las 5 buenas; la política
  reintento-una-vez es observable con un fake que reincide — checked by: unit
  (`tests/unit/test_p7_guardrail.py`).
- [ ] La chuleta existe versionada (`data/guardrail/constantes.jsonl`): cada entrada
  con número, unidad, concepto, fuente (PADI/Navy) y `section_id` de origen; auditada
  por Adolfo (registro en Notas) — checked by: check de esquema + inspección.
- [ ] `llm_evaluator.run(config)` produce una fila versionada con veredicto por
  pregunta (aprobado/suspenso/abstención) y agregados; el `run_id` incluye el modelo
  — checked by: acceptance con juez fake (sin red) + inspección de una pasada real.
- [ ] La fila registra `prompt_version` (generación y juez) leído del nombre del
  fichero de `prompts/`, no de una constante suelta: dos filas con prompts distintos
  son distinguibles sin abrir el código — checked by: unit sobre la serialización.
- [ ] El juez está calibrado: fichero de calibración versionado con las 20-30
  etiquetas de Adolfo y acuerdo ≥90% — checked by: script de calibración + registro.
- [ ] Las 4 filas están en `results/`, casillas F7 de `EXPERIMENTOS.md` rellenadas,
  decisión de modelo anotada — checked by: inspección; la decisión es de Adolfo.

Gate: `uv run pytest tests/unit/test_p7_generate_core.py tests/unit/test_p7_guardrail.py tests/acceptance/test_p7_generacion.py -q` y la suite completa `uv run pytest -q`.

## Out of scope

- Condensador y ventana de 3 pares (→ F8, Gemini Flash fijo).
- Grader / guardarraíl semántico (→ backlog con condición de activación).
- Umbral de abstención del reranker y negativos del eval (→ P1, eval fresco).
- Exactitud numérica como métrica del eval y latencia/coste instrumentados (LangSmith
  en F8).
- Modelos < 4B, vLLM, embedded (→ P2).

## Interfaces

Reparto de módulos (decisión 12):

```
llm/         transporte puro: los 4 modelos del experimento (API + mlx)
prompts/     generation_v1.txt, judge_v1.txt — versionados, sin formateador
pipeline/    p7_generate.py (carga prompt + monta estado), p7_guardrail.py
evals/       judge.py (rúbrica), llm_evaluator.py (bucle + agregados + fila)
```

```python
# llm/ — una firma, N backends (API / mlx); cliente perezoso por backend
def generate(model: ModelConfig, system: str, user: str) -> str

# p7_generate.py — el estado es el objeto del retrieval + la respuesta encima
@dataclass(frozen=True)
class Answer:  # pregunta, chunks (ids, textos, metadata), respuesta, abstencion: bool
def answer(retrieval_config, model, pregunta) -> Answer

# p7_guardrail.py
def verify(respuesta: str, constantes: ...) -> Verdict  # ok | reintento | abstener_cifra

# evals/llm_evaluator.py
def run(retrieval_config, model) -> dict  # {"config", "resumen", "detalle"}
```

## Tasks

- **T-01 · CREATE `llm/`** — interfaz + backend API: Anthropic para Sonnet/Haiku
  (dependencia nueva: `langchain-anthropic`, coherente con el `langchain-openai` de
  la casa — pick vetable) y el cliente del juez GPT con lo ya instalado. IDs de
  modelo confirmados contra la referencia vigente.
  VALIDATE: unit con fake + smoke de 1 llamada real (la lanza Adolfo con su key).
- **T-02 · Chuleta** — script de extracción regex (número+unidad+frase, acotado) →
  muestra real → **gate: Adolfo decide regex-solo vs pasada LLM** → auditoría →
  `data/guardrail/constantes.jsonl`.
  VALIDATE: check de esquema + auditoría registrada en Notas.
- **T-03 · CREATE `p7_guardrail.py`** — `verify()` + política reintento-una-vez.
  VALIDATE: `uv run pytest tests/unit/test_p7_guardrail.py -q` (fixture 5+5).
- **T-04 · UPDATE `p7_generate.py`** + CREATE `prompts/generation_v1.txt` — prompt de
  sistema **partiendo de una plantilla RAG publicada** (buscarla antes de escribir;
  adaptar solo lo del PRD: citas inline, números textuales, idioma, plantilla de
  abstención, **pasos numerados razonados cuando la respuesta es un procedimiento**)
  + `answer()` montando el estado con los textos del retrieval + guardarraíl
  enganchado.
  VALIDATE: `uv run pytest tests/unit/test_p7_generate_core.py -q` (todo con fakes).
- **T-05 · CREATE `evals/judge.py` + `evals/llm_evaluator.py`** — **gate: framework
  del juez** (deepeval con su métrica/prompt built-in vs directo, con el censo
  delante, decide Adolfo; la decisión 10 inclina hacia deepeval) → `judge.py` con la
  rúbrica (+ `prompts/judge_v1.txt` si no la trae la librería) + script de
  calibración contra las etiquetas de Adolfo; `llm_evaluator.py` solo bucle,
  agregados y fila con `prompt_version`.
  VALIDATE: acceptance con juez fake + calibración real ≥90% (la corrida real la
  lanza Adolfo).
- **T-06 · Backend MLX** (`mlx-lm`, Qwen 3.5 9B/4B 4-bit, caché KV del prompt fijo) —
  **gated: tras el repaso de teoría de IA local de Adolfo**.
  VALIDATE: unit de interfaz (mismo contrato que el backend API) + smoke local.
- **T-07 · Medición** — Adolfo lanza las 4 pasadas sobre la receta cerrada de F6
  (requiere su T-05 de F6 decidido), rellena `EXPERIMENTOS.md` F7, elige modelo;
  proponer cómo comparar las filas en `RESUMEN.html`.
  VALIDATE: 4 ficheros en `results/` + casillas + decisión anotada.

## Notas

- (2026-09-07) **T-05**: implementada con **deepeval** (gate de Adolfo: "quiero
  lo de producción"; investigado — `measure()` standalone sin pytest +
  `strict_mode` binario + `reason` por veredicto para calibrar con causa; la
  recomendación previa "directa" se corrigió con la doc delante). `judge.py`:
  G-Eval perezoso, rúbrica versionada en `prompts/judge_v1.txt`, modelo
  **gpt-5.6-terra** (confirmado contra referencia vigente; fuera de la
  ablación), `calibrate()` contra `data/eval/judge-calibration.jsonl` con
  umbral 0.9. `llm_evaluator.py`: bucle golden uso=eval → answer() → abstención
  directa o juez → fila {config (con model, run_id `receta-modelo`,
  prompt_version × 2), resumen (n/aprobado/suspenso/abstenciones/tasa),
  detalle} → write_result reutilizado. `tabla()` del retrieval_evaluator hecha
  tolerante a esquemas mixtos (unión de claves, celda "—"). Adolfo corrigió la
  línea PROMPTS_DIR del test congelado (deuda del veto de ubicación).
  VALIDATE: **aceptación completa 21/21 con slow incluidos** (criterios 6-7
  GREEN con fakes) + suite rápida 197 passed. **Enmiendas de la revisión de
  Adolfo (2026-09-07)**: juez → `gpt-5.6-luna` con `reasoning_effort: "xhigh"`
  (vía `OpenAIModel(generation_kwargs=...)` de deepeval, verificado en su doc;
  ~10× más barato que Terra, la calibración valida) y **score continuo 0-1 +
  umbral 0.5** en vez de strict_mode binario — el veredicto sigue binario por
  `is_successful()`, pero el score fino (ponderado por logprobs, paper G-Eval)
  se guarda por pregunta en el detalle (`judge.last`, costura grade() intacta
  para los fakes) y como `score_medio` en el resumen. Re-VALIDATE tras las
  enmiendas: 21/21 + 197, verde. `async_mode=False` ratificado por Adolfo tras
  ver que el flag no acelera el caso secuencial (doc interna de deepeval);
  "juzgar por lotes" anotado como optimización con condición de activación (si
  las pasadas de T-07 se hacen lentas). Flujo de calibración explicado y
  aceptado: primera pasada → ~25 muestras autocontenidas (pregunta + respuesta
  + esperada) → etiquetas CIEGAS de Adolfo → ≥90% o rúbrica v2 y repetir → el
  juez validado puntúa; el modelo lo elige Adolfo con la tabla. **Gate cumplido
  ("vale", 2026-09-07). T-05 CERRADA** (la calibración real vive dentro de
  T-07).
- (2026-09-07) **Veto a la decisión 13 (ubicación)**: Adolfo ejerció el veto
  previsto — `prompts/` pasa DENTRO del paquete (`src/divefy/prompts/`), "es
  parte" de divefy. `PROMPTS_DIR` ahora se ancla al propio paquete, no a
  REPO_ROOT. Lo demás de la decisión 13 (`.txt`, versión en el nombre,
  `prompt_version` estampada) intacto. ⚠️ Deuda para T-05: el test congelado
  `test_p7_generacion.py` define `PROMPTS_DIR = ROOT / "prompts"` — cuando se
  corran los slow, esa línea debe apuntar a `ROOT / "src" / "divefy" /
  "prompts"`; la edita Adolfo directamente (test congelado).
- (2026-09-07) **T-04**: `prompts/generation_v1.txt` + `answer()` implementados.
  Prompt partiendo de la plantilla publicada rlm/rag-prompt del Hub de LangChain
  (decisión 10; buscada y citada), adaptada con lo del PRD: grounding estricto,
  números verbatim sin conversión, jerarquía PADI>Navy con doble cita (conflict-
  aware, de la investigación del 2026-09-07), citas inline, idioma de la
  pregunta, pasos numerados en procedimientos. `ABSTENTION_TEMPLATE` vive como
  constante única en p7_generate y se interpola en el prompt (un solo origen —
  si divergieran, la comparación exacta se rompería; unit lo vigila). `answer()`:
  retrieval determinista → system fijo (cacheable) + user con contexto y
  pregunta → `llm.generate` → guardarraíl con reintento-una-vez → si reincide,
  la respuesta ENTERA pasa a plantilla de abstención. **Simplificación
  deliberada a revisar por Adolfo**: el PRD decía "abstención en esa cifra" —
  v1 abstiene la respuesta completa, no solo la cifra (más simple y más
  conservador; editar solo la cifra = reescribir prosa del modelo con regex).
  Logs de estado JSON por etapa (decisión 17) en DEBUG, silenciosos sin él.
  VALIDATE: aceptación no-slow **16/16 en verde** (RED→GREEN de criterios 1, 2,
  4, 5 — interfaz, abstención exacta, 5+5 + reintentos, esquema) + 5 units
  nuevos (`test_p7_generate_core.py`) + suite completa 197 passed, 0
  regresiones (41s — el marcador slow de Adolfo en F6 ya activo). **Gate
  cumplido**: Adolfo revisó el flujo función a función (2026-09-07) y decidió:
  (a) abstención-completa aceptada; (b) **B1 "reintento reparador" APARCADA con
  condición de activación** — entra solo si T-07 muestra reintentos que pierden
  contenido bueno al regenerar (lección de Adolfo: las invariantes de seguridad
  se construyen, las optimizaciones se ganan el puesto con dato); (c) el
  guardarraíl numérico SE QUEDA (regla inmutable 3, coste ~cero) sin
  instrumentación extra — si hiciera falta el conteo de intervenciones, los
  logs DEBUG ya lo llevan; (d) escalera de abstención intacta (prompt hoy →
  umbral reranker P1 → grader con condición). T-04 CERRADA.
- (2026-09-07) **T-03**: `verify()` implementada — v1 pertenencia pura (decisión
  16): regex de pares número+unidad con variantes ortográficas (metros por
  minuto→m/min, minutos→min, horas→h, °C/ºC), compuestas antes que prefijos,
  coma decimal normalizada (10.3→10,3). verify es pura y sin memoria: devuelve
  `ok`/`reintento`; `abstener_cifra` es el escalado que orquestará `answer()`
  (T-04). VALIDATE: el 5+5 congelado de aceptación **10/10 en verde** + 7 units
  nuevos (`tests/unit/test_p7_guardrail.py`) = 17 passed. Los 2 tests de
  reintento siguen en rojo esperado (`AttributeError: no attribute 'answer'` —
  es T-04). **Gate cumplido**: revisión de Adolfo (2026-09-07, "ok"; cuestionó
  ubicación en utils/ — resuelto: se queda en pipeline/, es camino crítico, no
  extra). T-03 CERRADA.
- (2026-09-07) **Step zero**: suite completa en verde — 165 passed, 5 deselected
  (6m24s).
- (2026-09-07) **RED de aceptación**: `tests/acceptance/test_p7_generacion.py`
  escrito por agente ciego; Adolfo pidió una revisión (podados 2 tests redundantes
  y 3 parametrizaciones de modelo; skips de chuleta añadidos a criterios 1-2;
  criterios 6-7 marcados `slow`) y aprobó la versión revisada, con docstrings en
  humano añadidos a los 13 tests a petición suya. Capturado: **10 failed
  (ImportError: cannot import name 'verify'), 11 skipped (artefactos pendientes:
  chuleta y prompts/), 0 passed** — el RED esperado, ningún test pasó en vacío.
- (2026-09-07) **T-01**: implementada con `langchain-anthropic` (1.7.1), como
  decía el plan. Hubo una desviación intermedia al SDK oficial `anthropic`
  argumentando el precedente de p3_enrich — **vetada por Adolfo y revertida**:
  el precedente no aplicaba (p3 bajó a `google.genai` solo porque la caché
  explícita de documento de Gemini no está en LangChain; aquí no falta ninguna
  feature) y LangChain da trazado LangSmith automático en F8, el mismo motivo
  por el que se descartó LlamaIndex. IDs confirmados contra la referencia
  vigente: `claude-sonnet-5`, `claude-haiku-4-5` (sin sufijos de fecha).
  Sonnet 5 con thinking adaptativo por defecto → `_solo_texto()` filtra bloques
  de texto del content (str o lista). Qwen: `NotImplementedError` hasta T-06.
  Unit: 5 passed (`tests/unit/test_llm_core.py`, fakes en la caché de clientes).
  **Gate cumplido**: smoke real con Haiku (orden de Adolfo, 2026-09-07) → "Hola".
  T-01 CERRADA.
- (2026-09-07) **T-02 — gate resuelto por Adolfo con tercera vía**: ni regex-solo
  ni pasada Gemini — la curación semántica la hace el agente principal (Fable)
  sobre las 128 candidatas del regex, y Adolfo audita el resultado. Incluye los
  conflictos PADI↔Navy adyacentes para que él elija auditando. Hecho: 86 filas
  curadas en `data/guardrail/constantes-borrador.jsonl` (una por par
  número+unidad, unidades normalizadas min/h, conceptos redactados) + añadidos
  que el regex perdió (los 11 NDL de la tabla RDP, rangos 600-2400 m / 30-60 m,
  49 ºC, ejemplos multinivel y de tercios) + 9 filas Navy textuales (30 fsw/min
  de 9-6.3; 130/190 fsw de 7-2.1; 200 fsw de 3-9.1). Descartado con motivo: el
  worksheet de 9-4 (etiquetas de formulario), sample problems del cap 2 Navy,
  números sin unidad (1,33 · 800 veces · 0,75 — el guardarraíl compara pares
  número+unidad). **Huecos anotados para T-03**: unidades "segundos" y "pies"
  fuera del set (decidir si verify() las vigila); verify() debe normalizar
  minutos→min y horas→h como hizo la chuleta. El script `p7_chuleta.py` se borró
  tras servir (decisión de Adolfo): one-shot cumplido, y vivo era peligroso —
  relanzarlo machacaría la curación con las candidatas crudas; el método queda
  documentado en esta nota. **Auditoría (registro)**: Adolfo delegó la lectura en
  un agente auditor independiente (verificación de las 87 filas contra
  chunks.jsonl: NDL, cadena de bar, filas Navy, fuentes) — resultado 85 OK /
  1 error real (línea "6 m": sub-claim ACEN mal emparejado, el corpus da 6-9 m)
  / 1 imprecisión (línea "130 fsw": narcosis vive en 3-9.1, no en 7-2.1).
  Adolfo aprobó las dos correcciones ("si", 2026-09-07) y se aplicaron. Sobre el
  conflicto de ascenso, decidido con literatura delante (búsqueda 2026-09-07):
  se citan ambos con jerarquía (PADI la respuesta, Navy la nota, cada uno en su
  unidad, sin convertir — el "9 m/min" convertido NO entra y el guardarraíl debe
  bloquearlo); la regla del conflicto irá escrita en el prompt de T-04
  (conflict-aware prompting). Los números del golden NO entran a la chuleta
  (contaminaría el eval vía guardarraíl; la chuleta se cura solo desde la prosa
  del corpus, PRD F1). **`data/guardrail/constantes.jsonl` oficial: 87 filas, check
  de esquema en verde (1 passed). T-02 CERRADA.** (contexto: investigación
  de práctica del sector sobre testing de apps LLM): tests con fakes (0 tokens)
  en el gate rápido; los del fixture del evaluador (84 preguntas por retrieval
  local) como `slow` → solo `/verify`; llamadas reales a LLM solo en las
  mediciones (T-07), nunca en tests. El test gordo de F6 pasó además a golden
  master contra la fila ganadora de `results/` (enmienda en el plan de F6,
  editada directamente por Adolfo).
