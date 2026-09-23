# PRD: Divefy

> Método de trabajo de este PRD: se recorre el flujo del RAG paso a paso (§7), y ese orden es
> a la vez el orden de decisión y el de implementación. Cada paso se rellena al cerrarlo con
> Adolfo: decisiones cerradas, pendientes y variantes a medir. El grid comparativo se define
> al final del recorrido, no antes. Ninguna sección se rellena sin pasar por Adolfo.
> Las variantes a medir de cada fase se acumulan en `.claude/plans/EXPERIMENTOS.md`
> (cuaderno de laboratorio: base + variantes + resultado cuando se mide).

## 1. Executive Summary

Copiloto conversacional de seguridad en buceo: un chat (CLI) que responde dudas de buceo apoyándose solo en un corpus verificado (US Navy Diving Manual Rev 7 + apuntes propios del Open Water PADI), en español e inglés. Se construye sobre un banco de experimentos que mide cada pieza del RAG y cada modelo con un examen propio de 186 preguntas, para encontrar la configuración de máxima calidad — y en particular si un modelo local pequeño alcanza a los de API.

## 2. Problem

### Context

Un buceador maneja tanta información de seguridad (física, fisiología, procedimientos, números críticos) que es improbable recordarla toda en el momento en que la necesita. ~90% de las muertes en buceo vienen de error del buceador, casi siempre prevenible con la información correcta a tiempo (ver `docs/proyectos.md`).

### Target Users

- Adolfo (creador): buceador en formación (Open Water PADI). Usa el chat para repaso y pre-inmersión. Único usuario en esta fase.
- Secundario: la audiencia de la historia en redes ("me construyo mi copiloto de buceo con IA") — consume la tabla comparativa, no el producto.

### Actores

Humanos:

| rol    | descripción                       | puede | no puede |
| ------ | --------------------------------- | ----- | -------- |
| Adolfo | usuario, desarrollador y operador | todo  | —        |

Técnicos:

| genera carga                                          | consume salida                 | sistemas externos de los que depende                                                    | quién lo opera |
| ----------------------------------------------------- | ------------------------------ | --------------------------------------------------------------------------------------- | -------------- |
| Adolfo (chat) + los evaluadores (pasadas batch) | el chat y la tabla comparativa | APIs de LLM (generación y juez), Hugging Face (descarga de modelos), LangSmith (trazas) | Adolfo         |

### Current Alternatives

Releer manuales y apuntes a mano; buscar en Google; preguntar a un chatbot genérico sin grounding (riesgo de alucinar procedimientos y números de seguridad).

## 3. Solution

### Value Proposition

Respuestas conversacionales basadas exclusivamente en el corpus verificado, con números de seguridad citados textualmente y abstención explícita cuando el corpus no cubre la pregunta. Cada pieza del sistema elegida por medición propia, no por fe.

### Differentiators

- Cada decisión del pipeline validada con un examen propio (186 preguntas derivadas del curso PADI, con respuesta esperada).
- Guardrail numérico determinista: los números de seguridad de cada respuesta se comprueban dígito a dígito contra el corpus.
- Bilingüe ES/EN sin capas de traducción (índice multilingüe único).

## 4. Features

### P0 - Must Have (MVP)

#### Feature 1: Pipeline RAG por pasos

- **Description**: construcción incremental siguiendo el flujo RAG (§7). Cada paso deja las variantes a medir registradas en su fase.
- **Who uses it / data**: interno; corpus en `data/raw/` (PDF Navy + apuntes en `data/raw/PADI_course/`).
- **Acceptance Criteria**: los criterios de aceptación de cada fase de §7 (las 9 cerradas).

#### Feature 2: Los evaluadores (arnés de evals)

- **Description**: dos scripts que lanzan las preguntas `uso=eval` del golden dataset (84 de 186; las de repaso quedan fuera) contra una configuración del sistema y puntúan: `retrieval_evaluator` — ¿el contexto recuperado contiene la información de la respuesta esperada? — y `llm_evaluator` — calidad de respuesta con juez LLM calibrado (20-30 etiquetas a mano de Adolfo) + ¿se abstuvo cuando tocaba?
- **User story**: como creador, quiero correr un comando con una config y obtener una fila de la tabla, para comparar variantes sin fe ciega.
- **If it fails**: una pasada fallida no corrompe resultados anteriores (resultados versionados por config).
- **Acceptance Criteria**:
  - [ ] Un comando + un fichero de config producen una fila de métricas reproducible.
  - [ ] Las métricas de retrieval corren sin llamar a ningún LLM generador.
  - [ ] Retrieval: hit_rate@k contra etiquetas por sección (vía ranx), con recall@k, precision@k, MRR y tokens recuperados registrados (Fase 5).
  - [ ] Generación: juez calibrado + abstención (Fase 7); los números los protege el guardarraíl runtime, no una métrica aparte.

#### Feature 3 [PRIMARY]: Chat CLI conversacional

- **Description**: chat multi-turno en terminal. Condensa la conversación en una query autónoma, recupera, genera con cita de fuente y números textuales, responde en el idioma de la pregunta, y se abstiene ("no está en el corpus") si no hay soporte.
- **User story**: como buceador en formación, quiero preguntar dudas en mis palabras y recibir respuestas fiables basadas en el manual y mis apuntes, para repasar y preparar inmersiones.
- **If it fails**: ante error de modelo/red, mensaje de error claro; nunca una respuesta sin grounding.
- **Acceptance Criteria**:
  - [ ] Conversación multi-turno con follow-up implícito resuelta por el condensador (ventana de 3 pares).
  - [ ] Toda respuesta lleva cita de fuente; los números de seguridad pasan el guardarraíl (textuales o abstención).
  - [ ] Pregunta fuera del corpus → respuesta plantilla de abstención, sin generación.
  - [ ] Responde en el idioma de la pregunta (ES/EN).
  - [ ] Modo buceo y modo dev conmutables; `/fuentes` muestra los trozos y scores de la última respuesta.

### P1 - Important (Post-MVP)

- **Ampliación del corpus con eRDPML/tablas** (sustituye a la tool de cálculo, descartada — ver Out of Scope) — Adolfo se lee el manual del eRDPML y las tablas RDP y decide qué entra al corpus (cómo se usa la tabla / cómo se configura y usa el eRDPML: texto procedimental, no números calculables) y qué preguntas entran a las evals. Las preguntas de cálculo quedan **fuera** del eval del RAG; son candidatas al eval de abstención (eval fresco) — se decide entonces. Bonus metodológico: corpus-v2 = segunda tanda de runs versionados en `results/`, ensayo real de evals con cambio de versión como en prod.
- **Grid comparativo y tabla final** — método fija-y-barre: (1) barrer búsqueda sin LLMs, (2) barrer modelos con la receta ganadora, (3) cruces de cordura. Se define al terminar el recorrido de §7.
- **Eval fresco (~45 preguntas)** — añade lo que el golden no mide: preguntas en inglés y preguntas sin respuesta en el corpus (miden abstención). Generadas por modelo fuera de la ablación, revisadas al 100% por Adolfo.
- **Umbral de abstención del reranker** (movido desde Fase 6, decisión de Adolfo 2026-08-30) — calibrar el score mínimo ("nada supera el umbral → no está en el corpus") usando las preguntas sin respuesta del eval fresco como negativos (las 84 etiquetadas tienen todas respuesta — hoy no hay contra qué calibrar). Hasta entonces la abstención del MVP depende del prompt (plantilla si el contexto no da soporte); este umbral es su refuerzo determinista. Dato de sonda (2026-08-28, M5): los scores sigmoid separan relevante de ruido ×250 pero son picudos (mejor relevante 0.18) — calibración empírica obligatoria, señal = máximo score de los N candidatos.
- **Brazo "idioma normalizado a inglés"** — decisión guardada como medible: índice 100% EN (apuntes traducidos offline) + query pivotada, contra el multilingüe nativo. Responde con datos al consejo del CTO.
- **TTS/STT — modo de voz** (decisión de Adolfo, 2026-08-27): doble objetivo, feature real y banco de medición. Como feature, añade una tercera cara al Chat CLI junto a modo buceo/dev (Fase 8) — entrada hablada (STT) transcrita a la query, respuesta leída en voz alta (TTS), sobre la receta RAG ya cerrada. Como experimento, compara modelos SOTA locales y de API, pequeños y grandes, midiendo **latencia y precisión** (mismo espíritu que el grid de generación de Fase 7: ¿el local pequeño alcanza al de API?). Candidatos concretos y metodología de medición (WER para STT, métrica de calidad para TTS) pendientes de cerrar al planificar la fase.
- **Escalera de cuantización del modelo local ganador** (decisión de Adolfo, 2026-09-03; ampliada 2026-09-08) — el mismo modelo en 2-3 niveles de cuantización, **elegidos partiendo de la capacidad real del Mac** (24 GB unificados compartidos: el 9B en fp16 ~18-19 GB va al límite; la RAM decide qué peldaños caben), pasado por el examen de 84 preguntas con `llm_evaluator`. Se mide **todo lo medible, en dos capas**: (a) **extrínseca** — degradación real contra corpus propio (tasa_aprobado, score_medio, abstenciones, intervenciones del guardarraíl vía logs), no contra benchmarks ajenos; (b) **intrínseca** (ampliación de Adolfo) — KL divergence entre las distribuciones del cuantizado y el original sobre texto del corpus, perplexity, y lo que el tooling dé (vive en llama.cpp/GGUF, no en MLX — investigar el cómo al abrir la fase). **Pregunta explícita de la escalera: ¿la métrica intrínseca (barata, sin examen) predice la degradación extrínseca (la que importa)?** — la correlación en cualquier sentido es hallazgo para M5/paper. Insumo: documento propio de Adolfo sobre memoria y cuantización (estudiado, se aporta al planificar la fase). Da la curva calidad/tamaño que necesita el camino embedded de P2. Coste: local, gratis, sin API. Orden intacto: el grid de F7 corre los Qwen en 4-bit y elige modelo; la escalera se barre después y solo sobre el ganador (fija-y-barre).
- **Fine-tuning del modelo local (LoRA con `mlx-lm`)** (decisión de Adolfo, 2026-09-03) — doble objetivo, como el modo de voz: experimento real y expertise de IA local. **Diana: el contrato de salida, no el conocimiento** (el conocimiento lo pone el RAG) — pasos numerados, números textuales, plantilla de abstención, idioma. Se justifica solo si la línea base de Fase 7 muestra que el modelo pequeño pierde por seguimiento de instrucciones y no por saber menos: ese diagnóstico es su prerrequisito. Orden con la cuantización: escalera primero (fija el punto de la curva), afinado después sobre ese punto (QLoRA = afinar sobre base cuantizada). **Pregunta abierta — datos de entrenamiento**: las 102 de repaso salen del mismo curso PADI que las 84 del examen, así que entrenar con unas y examinar con otras puede contaminar el eval; alternativa limpia = pares sintéticos generados desde el corpus con Gemini Flash (ya en el stack). Se decide al planificar la fase, con el dato de la línea base delante.
- **Web UI** — una vez funcione el RAG.

### P2 - Nice to Have (Future)

- **CI bien hecho** (decisión de Adolfo, 2026-09-07): GitHub Actions con el reparto de tres pisos del sector — (1) suite rápida determinista (0 tokens, <60s) en cada push; (2) regresión de retrieval (golden-master contra la fila ganadora de `results/`) gateada por ruta (solo si el diff toca `src/divefy/prompts/`, `pipeline/` o `evals/`) — corre en el Mac como runner local, la nube no tiene los artefactos (Chroma, modelos, Ollama; los tests ya se saltan solos con skip-with-hint); (3) evals con juez LLM jamás en CI automático — son experimentos versionados a demanda (T-07), protegidos del cambio silencioso por la política nunca-sobreescribir. Valor real cuando haya un segundo committer o releases frecuentes.
- Servir el modelo ganador con vLLM en GPU alquilada (aprender el stack de producción real).
- Camino embedded (ordenador de buceo): clase "SoC con NPU", modelo ~0.5-1B + embeddings pequeños (candidatos: EmbeddingGemma, Nomic Embed v2). Investigación futura.
- Ampliar corpus (NOAA u otras fuentes).

### Out of Scope

- Hardware/embedded en esta fase (futuros steps).
- Multiusuario, auth, deploy.
- Proyectos #1 (alerta de ascenso) y #3 (compresión acústica) de `docs/proyectos.md` — este repo es solo el #2.
- Redistribuir contenido con copyright (NOAA 6ª ed. de pago, fuera).
- **Tool de cálculo de tablas de buceo — descartada con motivo**: duplica un dispositivo certificado (eRDPML / ordenador de buceo) que la doctrina obliga a usar y que el buceador ya lleva; si no llevas eRDPML, menos aún llevas un RAG embebido. El valor del chat es explicativo, no calculador. Petición de cálculo → abstención (la plantilla puede derivar al dispositivo). Con la tool caen el JSON de tablas RDP y su examen propio.

## 5. Technical Architecture

### Stack (solo lo confirmado)

- Python (uv + pyproject). Sin API web en esta fase: interfaz CLI.
- LangChain como librería; **sin LangGraph** (entra solo si aparece orquestación real). LlamaIndex evaluado y descartado (decisión de Adolfo, 2026-08-23): en modelos pequeños/edge el punto queda neutro — desde `mlx-lm` 0.18 hay un servidor compatible OpenAI que las dos librerías consumen igual — y la ventaja real de LlamaIndex (menos código para RAG genérico) no compensa perder la integración automática de **LangSmith**, ya cerrada más abajo (con LlamaIndex haría falta instrumentación manual).
- Modelos locales vía **mlx-lm** (Apple Silicon M5). Modelos API vía SDK.
- Modelos del experimento (confirmados): Sonnet 5 y Haiku 4.5 (API); Qwen 3.5 9B y 4B (local, 4-bit MLX). Más pequeños → P2.
- Embeddings: a medir — BGE-M3 vs Qwen3-Embedding-0.6B (ambos locales).
- Reranker candidato: bge-reranker-v2-m3 (modelo pequeño local, on/off a medir).
- Vectorstore: **Chroma** (embebida; una colección con nombre canónico por config del grid).
- Observabilidad: **LangSmith**.
- Arnés de evals: propio (`retrieval_evaluator` F5, `llm_evaluator` F7).
- Enriquecedor de índice (Fase 3): Gemini Flash. Juez de evals (Fase 7): un GPT — ambos fuera de la ablación.
- Idioma: índice multilingüe único, cero traducción en el pipeline; el LLM responde en el idioma de la pregunta.

### Logic map

| pieza                   | dónde vive                                    | por qué                        |
| ----------------------- | --------------------------------------------- | ------------------------------ |
| ingesta/chunking/índice | Python local, offline                         | se paga una vez, revisable     |
| retrieval + rerank      | Python local, por consulta                    | latencia controlada, sin red   |
| generación              | LLM local (mlx) o API según config            | es la dimensión a medir        |
| juez de evals           | LLM de API fijo, familia fuera de la ablación | evita auto-preferencia         |
| guardrail numérico      | Python puro (regex + tabla de constantes)     | determinista, sin dependencias |

Diseño completo pendiente — lo produce `/system-design` en `.claude/plans/SYSTEM-DESIGN.md`. Esta sección se rellena entonces.

## 6. User Flows

### Flow 1: Pregunta en el chat

1. Adolfo escribe una duda en ES o EN (posiblemente un follow-up con contexto implícito).
2. El sistema condensa la conversación en una query autónoma.
3. Recupera los pasajes relevantes del índice (manual + apuntes).
4. El LLM redacta la respuesta en el idioma de la pregunta, citando fuente y con números textuales.
5. Si el corpus no soporta la respuesta: "no está en el corpus", sin inventar.
6. Adolfo repregunta; vuelta al paso 2.

### Flow 2: Pasada de experimento

1. Adolfo define una config (variante de receta + modelo + corpus).
2. Corre el evaluador: las 84 preguntas de eval pasan por el sistema.
3. Obtiene una fila de métricas (retrieval en F5; juez + abstención en F7).
4. Compara filas en la tabla y decide la siguiente variante.

## 7. Implementation Phases

> El orden del flujo RAG = orden de decisión = orden de implementación. Cada fase se rellena
> (tareas, decisiones, variantes a medir) al cerrarla con Adolfo. Estado: 🔓 por discutir · 🔒 cerrada.

### Fase 1: Ingesta 🔒

Conseguir las fuentes y sacarles el texto con las tablas intactas.

**Decisiones cerradas:**

- Fuentes v1: US Navy Diving Manual Rev 7 (descargado: `data/raw/navy-diving-manual-rev7.pdf`, 991 págs, ed. dic-2016, dominio público, espejo ASU porque NAVSEA bloquea descargas por script) + apuntes leídos directamente de `data/raw/PADI_course/` (única fuente de verdad). NOAA aparcada.
- El golden dataset NO se indexa: es el examen.
- **Conflicto de doctrinas (PADI vs Navy): PADI manda** (decisión de Adolfo — el usuario de Divefy es recreativo y el examen es PADI). El manual aporta profundidad y se citan ambos cuando difieren ("PADI: 18 m/min; la Navy usa 30 fsw/min"). La ablación de corpus sigue intacta: con resultados se re-decide qué aporta el manual.
- **Todo `data/` se versiona en git** (decisión de Adolfo: contenido propio + un PDF público descargable; nada que bloquear). `data/processed` es además regenerable (borrar + relanzar ingesta lo reconstruye).
- Curación del manual (criterio de Adolfo: quitar solo lo 100% seguro inútil — lo que ningún curso de buceo cubriría). **Fuera**: cap 1 (historia), 5 (administración Navy), 8 (suministro superficie aire), 12 (gases mixtos superficie), 13 (saturación), 15-16 (rebreathers militares MK16/MK25), 18 (operación de cámaras) ≈ 440 págs. **Dentro**: caps 2, 3, 4, 6, 7, 9, 10, 11, 14, 17 ≈ 465 págs. Frontera resuelta por la regla "en caso de duda, dentro": 4 (sistemas), 11 (hielo — existe especialidad Ice Diver), 14 (mezcla de gases — existe especialidad Gas Blender).
- Tablas numéricas (descompresión, límites, tiempos): **NO se indexan como texto del RAG ni se convierten en producto** (decisión de Adolfo). El parser debe detectarlas y separarlas limpias de la prosa (si no, sus filas contaminan los chunks); el JSON que salga se inspecciona en el bake-off y no se usa. En el índice solo entra un chunk-puntero por tabla ("la Tabla 9-9 cubre X"), que solo necesita la tabla detectada + su caption. La tabla de constantes del guardarraíl se cura a mano desde la **prosa** del corpus (los números que el chat citará), con procedencia PADI/Navy — no depende de las tablas. Verificado contra el golden: ninguna de las 186 preguntas exige un lookup de tabla — las 11 menciones son conceptuales y las cubre la prosa.
- **El corpus de anclaje del grid se decide con una pasada barata, no a priori** (revisado 2026-08-24 y 2026-08-27, ver Fase 9 Paso 0): búsqueda densa simple sobre las 84 preguntas de eval, cruzando corpus × extras × modelo de embedding (36 pasadas retrieval-only) — el ancla lo decide Adolfo con la tabla delante. Motivo del cambio de "apuntes solos → manual → combinados" fijo a esto: apuntes está en español y el manual en inglés, y BM25 es ciego entre idiomas — decidir el ancla sin medir arriesgaba tunear las otras 6 dimensiones del barrido contra un corpus subóptimo sin enterarse hasta el final.

**Variantes registradas para el grid (fase 9):**

- Parsing naive vs table-aware.
- Corpus: apuntes / manual curado / ambos.

**Tareas:**

- [x] Descargar el manual a `data/raw`.
- [x] Loader de apuntes markdown (`data/raw/PADI_course/*.md`) con metadatos (fichero, `section_id` = `fichero#sección`, título).
- [x] Bake-off de parser (decisión de Adolfo: favorito Docling por coste único de indexado; retador pdfplumber): ambos sobre el cap 9 (caso duro: la Table 9-9 fragmenta con pdfplumber sin ajustar) + una sección de prosa. Juez: el check ruidoso de abajo. Imágenes ignoradas, pies de figura conservados.
- [x] Parser ganador sobre los capítulos curados: prosa por sección con metadatos (capítulo, **`section_id` tipo `9-3.2`**, título, página) → `data/processed/`; tablas numéricas → fuera de la prosa + chunk-puntero por tabla (caption). El volcado a JSON es solo inspección del bake-off, no entregable.
- [x] Test de ingesta (pytest, dos checks y ya):
  - Conteos: captions "Table X-Y" == tablas extraídas; secciones `##` de apuntes == chunks; todo trozo lleva `section_id` no vacío (es el metadato del que depende la métrica de la Fase 5).
  - Fixture: ~10 hechos elegidos a mano (frase del cap 2, número de seguridad de la prosa, número de apuntes) presentes literalmente en el output; y la Table 9-9 al revés: su chunk-puntero existe y **ninguna** fila suya aparece dentro de la prosa (check de contaminación).
- [x] El diff Docling vs pdfplumber es solo el juez del bake-off, una vez; no es test permanente. (La red final es el eval de retrieval de la Fase 5.)

**Criterio de aceptación de la fase:** existe en `data/processed/` la prosa troceada (10 caps + apuntes, con metadatos) con las tablas fuera (solo chunk-puntero), **y** los dos checks pasan (conteos cuadran, fixture completo incluida la no-contaminación de la Table 9-9). Esto prueba extracción _correcta_; la _utilidad_ la prueba el eval de retrieval en Fase 5.

### Fase 2: Chunking 🔒

Trocear los documentos (solo la prosa: apuntes + manual curado; las tablas ya salieron del texto en Fase 1).

**Decisiones cerradas:**

- **Chunking estructural** (decisión de Adolfo): cortar por las costuras del documento, no por tamaño fijo. Los dos corpus nacen estructurados: apuntes con `##` por tema, manual con numeración jerárquica (9-3.2) donde cada subsección es un concepto autocontenido.
- **Granularidad fija por criterio, no se barre**: nivel subsección numerada en el manual (9-3.2; ni sección gorda 9-3 ni sub-sub 9-3.2.1.x), nivel `##` en los apuntes. Barrer granularidad × tope mediría casi lo mismo dos veces (ambos encogen los trozos); si el eval de Fase 5 da resultados raros, se revisita.
- **Tope de tamaño** (tokens contados con el tokenizador de BGE-M3, fijo para todos los brazos — que "512" signifique lo mismo en todo el grid): dentro de cada frontera de documento (mismo fichero de apuntes, mismo capítulo del manual), el texto de las secciones se une y se deja que el splitter empaquete libremente hasta el tope — junta secciones vecinas pequeñas, parte las que no caben (párrafo → línea → frase, nunca a mitad de frase salvo último recurso). Cada trozo resultante se atribuye a las secciones de origen con las que solapa. **Decisión revisada el 2026-08-24**: la regla original ("sección minúscula se pega a su hermana anterior", con un umbral propio) se sustituye por dejar que `RecursiveCharacterTextSplitter` empaquete libre — ninguna fuente publicada compara exactamente empaquetado-libre vs. respetar límites de sección (ver `EXPERIMENTOS.md` Fase 2), así que se empieza por lo simple y el enfoque que respeta secciones queda registrado como variante a medir en Fase 5 si el recall lo pide. El valor del tope no se decide: es la variable del grid.
- **Implementación: `RecursiveCharacterTextSplitter` de LangChain** (decisión de Adolfo, 2026-08-23 — LlamaIndex evaluado y descartado, ver §5 Stack), con el tokenizador de BGE-M3 inyectado (`length_function` propia) para que el tope cuente igual que en el resto del grid, y `chunk_overlap=0` forzado (el default de la librería es 200, no 20 como se pensó al principio). Código propio encima solo donde la librería no llega: mapear cada trozo devuelto a qué sección(es) de origen solapa (por posición de caracteres), necesario para citar fuente.
- **Tamaño fijo con solape: descartado con motivo** (como HyDE). Corta procedimientos de seguridad por la mitad y tira la estructura que el documento ya trae; solo compite en texto sin costuras (transcripciones, novelas), que no es este caso.
- Cada trozo lleva metadatos de origen (fichero/capítulo, sección, título) — vienen de Fase 1 y permiten citar fuente en la respuesta.

**Variantes registradas para el grid (fase 9):**

- Tope de tamaño: 256 / 512 / 1024 tokens.

**Tareas:**

- [ ] Chunker estructural sobre `data/processed/` (apuntes + prosa del manual), parametrizado por tope.
- [ ] Check ruidoso (uno): ningún trozo vacío ni sobre el tope, y nº de trozos ≥ nº de secciones de entrada (nada se pierde por el camino).

**Criterio de aceptación de la fase:** con tope 512, los trozos existen con sus metadatos, el check pasa, y una inspección a ojo de ~10 trozos del cap 9 y de apuntes muestra ideas completas (no frases cortadas). La _utilidad_ del tope la decide el eval de Fase 5.

### Fase 3: Extras de índice 🔒

Enriquecimientos opcionales en indexado, a medir: contexto por chunk (contextual retrieval), preguntas hipotéticas (HyPE).

**Decisiones cerradas:**

- Escalera acumulativa a medir: sin extras (base) → +contextual → +HyPE. No se hace HyPE de primeras (decisión de Adolfo): primero la base, y cada extra tiene que ganarse el puesto en el eval.
- Contextual retrieval: al LLM se le da el capítulo entero + el trozo, escribe 1-2 frases que lo sitúan, y esa frase se embebe **junto al trozo** (ayuda al buscador) y viaja con él al modelo que responde (ayuda a la generación).
- HyPE encadenado: las preguntas hipotéticas se generan sobre el trozo **ya contextualizado** (reutiliza el contexto, no repite la pasada de documento entero). Solo ayuda a la búsqueda; el LLM que responde nunca las ve. Trade aceptado: no se medirá "HyPE solo" — cruce de cordura en Fase 9 si el resultado extraña.
- **El LLM generador de contextos y preguntas es fijo y aparte del experimento** (decisión de Adolfo): el índice se construye una vez y es idéntico para las 4 configs de modelo — el grid mide solo el modelo que responde. Modelo: **Gemini Flash** (barato, contexto largo para capítulos enteros, fuera de la ablación).

**Variantes registradas para el grid (fase 9):** la escalera de arriba — ver `.claude/plans/EXPERIMENTOS.md`.

**Tareas:**

- [ ] Script de enriquecimiento offline: contexto por trozo (capítulo + trozo → 1-2 frases), cacheado en `data/processed/` para no repagar.
- [ ] Script HyPE sobre trozos contextualizados (3-5 preguntas por trozo, mismo modelo fijo).
- [ ] Check ruidoso (uno): todo trozo tiene contexto no vacío y N preguntas; ningún contexto excede ~100 tokens.

**Criterio de aceptación de la fase:** los dos enriquecimientos existen cacheados con su check en verde, y una inspección a ojo de ~10 contextos y ~10 preguntas del cap 9 muestra que sitúan/preguntan lo que toca. Su _utilidad_ la decide el eval de Fase 5.

### Fase 4: Embeddings e índice vectorial 🔒

Elegir embeddings (2 candidatos) y vectorstore.

**Decisiones cerradas:**

- **El mismo modelo de embeddings indexa y consulta, siempre.** Cada modelo define su propio espacio; mezclar espacios = ruido. La asimetría explotable es otra: los documentos se embeben offline en el Mac, el dispositivo final solo embebe la pregunta en vivo — con el mismo modelo.
- Candidatos a medir (sin cambios): **BGE-M3** (nº1; extra: saca denso y sparse del mismo modelo, simplifica la híbrida de Fase 5) vs **Qwen3-Embedding-0.6B** (mide "¿cuánto pierdo con un pequeño bueno?").
- Modelos de API (OpenAI/Cohere/Voyage) descartados por arquitectura, no por calidad: retrieval local sin red (logic map) y endgame embedded los hacen inviables. No se miden.
- **Nomic Embed v2** (hallazgo de artículo aportado por Adolfo): NO entra en el grid; queda apuntado en el camino embedded P2 junto a EmbeddingGemma, donde la pregunta es "¿qué cabe en el hardware?".
- Vectorstore: **Chroma** (embebida, un directorio en disco, decisión de Adolfo). Una **colección con nombre canónico por config** (`corpus-tope-extras-embedding`, p.ej. `apuntes-512-base-bgem3`) — cambiar algo aguas arriba del índice = otra colección.

**Variantes registradas para el grid (fase 9):** BGE-M3 vs Qwen3-Embedding-0.6B.

**Tareas:**

- [ ] Indexador parametrizado: config → colección Chroma con su nombre canónico (embebe trozo[+contexto] y preguntas HyPE si la config los lleva).
- [ ] Check ruidoso (uno): nº de vectores en la colección == nº de trozos (+ preguntas) de entrada.

**Criterio de aceptación de la fase:** existe al menos la colección base (`apuntes-512-base-bgem3`) con el check en verde, y una búsqueda a mano ("¿a qué velocidad se asciende?") devuelve trozos que hablan de ascenso. La _calidad_ real la mide el eval de Fase 5.

### Fase 5: Retrieval + corrector v1 🔒

Cómo se busca (semántica vs híbrida, cuántos trozos). Aquí nace el corrector en su versión retrieval (sin LLMs) y se miden por fin las fases 1-5.

**Decisiones cerradas — búsqueda:**

- **Híbrida como base** (decisión de Adolfo): densa + léxica fusionadas con RRF (fusión por posición, sin pesos que tunear). Cubre paráfrasis y términos exactos sin elegir. La **densa sola queda como ablación**: mide cuánto aporta el lado léxico.
- Lado léxico: BM25 clásico de primeras (pick mecánico, vetable); el sparse nativo de BGE-M3 queda anotado como alternativa si el cruce ES↔EN duele (BM25 es ciego entre idiomas).
- **top-k se barre {3, 5, 10}** y se elige por la curva de recall, no por número redondo (decisión de Adolfo).
- **Umbral mínimo de score: trasladado al reranker (Fase 6)** — los scores RRF son posicionales y no soportan umbral; el score del reranker sí, y de paso será la señal barata de abstención. *(2026-08-30: movido de nuevo, Fase 6 → P1 Post-MVP — sin negativos etiquetados no hay calibración posible.)*
- Multi-vector (ColBERT) descartado con motivo: coste de almacenamiento/servicio injustificable a nuestro tamaño.
- La reformulación de follow-ups ya vive en el Flow 1 / Fases 7-8; el eval usa preguntas sueltas, no aplica aquí.

**Decisiones cerradas — corrector v1:**

- Corre solo sobre el **subconjunto `uso=eval` (84 preguntas)**; las 102 de repaso ni se etiquetan ni se examinan (decisión de Adolfo). Mismo fichero, filtro por campo.
- Métrica principal: **hit_rate@k determinista contra etiquetas a nivel de sección** (revisado 2026-08-28/30 por primeros principios — el "recall@k" de la jerga RAG es hit rate en terminología IR; cálculo vía ranx, familia trec_eval). Se anota en qué secciones (de apuntes Y de manual) vive cada respuesta; acierto = algún trozo recuperado pertenece a una sección etiquetada. Las etiquetas sobreviven a todo el barrido porque la granularidad es fija y los hijos heredan metadatos (Fase 2). Junto al hit rate se registran desde el día uno **recall@k** (completitud: de las secciones etiquetadas, cuántas cubren los k trozos), **precision@k** (ruido en el contexto), **MRR** (¿lo bueno salió arriba?) y **tokens recuperados** — contexto para leer la tabla, porque hit rate y recall crecen mecánicamente con tope y k. Detalle en `phase-5-retrieval/metricas-framework.md`.
- Regla de etiquetado ante el conflicto doctrinal: en preguntas con número PADI, una sección Navy con valor distinto NO se etiqueta como respuesta.
- Con HyPE: k cuenta **trozos únicos** (cada pregunta recuperada se resuelve a su trozo padre y se deduplica); BM25 indexa **solo trozos**, nunca contextos ni preguntas hipotéticas — la parte léxica es idéntica en todos los brazos.
- **Etiquetado asistido** (decisión de Adolfo): un LLM barato hace UNA pasada proponiendo secciones candidatas por pregunta y corpus; Adolfo audita ~25-30 etiquetas. Regla: ≤2 mal → válidas; más → se replantea con ese dato. Etiquetas = fichero versionado y auditable; pregunta que puntúe raro en un barrido → abrir su etiqueta primero.
- Bonus de las etiquetas: dicen qué preguntas NO tienen respuesta por corpus — insumo directo para medir abstención en Fase 7.
- Métrica secundaria: match textual normalizado de números (no se parafrasean, no cruzan mal los idiomas).
- El corrector reporta el recall **desglosado por corpus de origen**, comparando solo sobre preguntas cuya etiqueta dice que el manual contiene la respuesta (si no, confundiría idioma con cobertura temática): es el chivato objetivo de si el cruce ES↔EN duele, y el disparador del brazo "normalizado a EN" del backlog.
- Descartados con motivo: juez LLM por pasada (coste y varianza recurrentes en cada run), similitud de embeddings como juez (el juez compartiría los puntos ciegos del examinado).

**Variantes registradas para el grid (fase 9):** densa vs híbrida · k ∈ {3, 5, 10}.

**Tareas:**

- [ ] Retriever híbrido (denso Chroma + BM25 + RRF) y denso solo, parametrizados por config.
- [ ] Pasada de etiquetado asistido → `data/eval/labels.jsonl` (versionado) + auditoría de muestra por Adolfo.
- [ ] Corrector v1: config → hit_rate/recall/precision/MRR/tokens (ranx) → fila versionada de resultados. (Match numérico retirado en la revisión de métricas 2026-08-28; re-decidible en F7 si el guardarraíl lo pide.)
- [ ] Check ruidoso (uno): correr dos veces la config base produce exactamente la misma fila (determinismo de punta a punta).
- [ ] Barrido barato: corpus × tope × extras × embedding × búsqueda × k → rellenar `EXPERIMENTOS.md` y fijar la receta ganadora de búsqueda.

**Criterio de aceptación de la fase:** etiquetas auditadas y válidas, el check de determinismo pasa, y las variantes de las fases 1-5 tienen su casilla rellenada en `EXPERIMENTOS.md` con una receta de búsqueda ganadora declarada.

### Fase 6: Rerank 🔒

Reordenado con modelo pequeño local, on/off medido.

**Decisiones cerradas:**

- Mecánica: se recuperan **N=20 candidatos** (fijo por criterio, no dimensión del grid), el reranker los lee uno a uno junto a la pregunta y se queda los k mejores. Sonda única a N=40 solo si el on/off da mejora.
- Modelo: **bge-reranker-v2-m3** (local, multilingüe — lee pregunta ES + trozo EN —, misma familia M3 que el embedding). APIs de rerank descartadas por arquitectura (corre por consulta: peaje de red + endgame embedded). Qwen3-Reranker 4B/8B descartado por peso (portero más pesado que el equipo).
- **Jina Reranker v3 anotado como alternativa** (hallazgo de Adolfo: arquitectura listwise, N candidatos en una pasada) con condición de activación concreta: solo si la latencia del rerank en el M5 molesta al medir — y revisando antes su licencia (históricamente no-comercial en algunas versiones).
- ~~**Umbral mínimo de score vive aquí**~~ **Movido a P1 Post-MVP** (decisión de Adolfo, 2026-08-30): las 84 etiquetadas tienen todas respuesta — no hay negativos contra los que calibrar; los negativos llegan con el eval fresco (P1). La fase queda solo con el rerank on/off. Descartado también un clasificador de intención de entrada: responde "¿es buceo?" y no "¿está en mi corpus?" — deja pasar justo el caso peligroso (pregunta de buceo que el corpus no cubre).
- **Latencia: sin cronómetro en el corrector** (Adolfo, 2026-08-30) — la fila de `results/` sigue determinista; la referencia es la sonda del 2026-08-28 en el M5 (~1.45s por consulta con ~20 pares en caliente, carga del modelo 36.6s, contexto 8192 — los chunks de 512 caben enteros) y la medición real por etapa llega gratis con LangSmith al montar el chat (Fase 8). La condición Jina se juzga con ese dato.
- **Ejecución**: `sentence-transformers` (ya instalado) vía `CrossEncoder` con sigmoid — sin dependencia nueva. El brazo con rerank on añade `-rerank` al `run_id` para no chocar con la fila de off.
- **Secuencia**: la Fase 5 se termina y verifica primero; la interfaz retrieve→rerank (de dónde salen los textos de los N candidatos) se decide entonces, contra la interfaz real.

**Variantes registradas para el grid (fase 9):** reranker on/off.

**Tareas:**

- [ ] Rerank opcional en el retriever (config on/off, N parametrizado).
- [ ] Check ruidoso (uno): con rerank on, la salida son exactamente k trozos, subconjunto de los N candidatos, orden por score descendente.

**Criterio de aceptación de la fase:** la fila on/off está medida en `EXPERIMENTOS.md` (recall sobre las 84; latencia = dato de sonda anotado). ~~Umbral calibrado~~ → P1 Post-MVP.

### Fase 7: Generación + juez 🔒

Prompt, guardrail numérico, abstención. Nace `llm_evaluator`: el juez que elige modelo.
*(Recorte MVP 2026-08-31, decisión de Adolfo: condensador → Fase 8; grader → fuera con condición de activación; "corrector v2" sustituido por `llm_evaluator` con solo juez + abstención; brazo contexto completo/reducido eliminado.)*

**Decisiones cerradas:**

- **Modelos confirmados** (Adolfo): Sonnet 5 + Haiku 4.5 (API) y Qwen 3.5 9B + 4B (local, 4-bit MLX). La pareja Qwen sí aísla la variable "tamaño"; la de API mezcla tamaño y generación (4.5 vs 5) — se compara sin esa pretensión. Modelos aún más pequeños → P2 (escalera hacia el embedded).
- **Interfaz única en `llm/`** (2026-08-31): una interfaz de llamada con dos backends (SDK de API / mlx-lm local); los 4 modelos son 4 configs de esa interfaz y `p7_generate` no sabe cuál hay detrás.
- **Salida: texto con citas inline** (2026-08-31, opción b): el modelo cita en la prosa ("según tus apuntes de X"); las fuentes y metadata verificables viajan **deterministas desde el retrieval** en el estado de la respuesta — la respuesta del LLM se añade al objeto que ya trae los trozos. Structured output (JSON) descartado: frágil en modelos locales pequeños y no compra nada que texto + metadata de retrieval no den.
- **Cachés**: embeddings de las 84 preguntas del eval (un fichero por modelo de embeddings, `data/eval/`); resultados de los evaluadores versionados por config en `results/` (fila resumen + detalle por pregunta, nunca se sobreescriben); prompt caching de la API para Sonnet/Haiku; caché KV del prompt fijo en mlx-lm para los locales. NO se cachean respuestas del chat.
- **Guardarraíles runtime — dos puertas de salida, ninguna de entrada**: (1) sin filtro de entrada de off-topic; (2) abstención en el MVP **por prompt** (contexto sin soporte → el modelo emite la plantilla fija) — el umbral del reranker como refuerzo determinista se movió a P1 Post-MVP (2026-08-30); (3) guardarraíl numérico determinista tras generar (regex + chuleta de constantes **con procedencia y ámbito PADI/Navy** — un número es válido si coincide con la fuente que la respuesta cita; PADI manda en doctrina): número no verificado → un reintento avisando al modelo → si reincide, abstención en esa cifra. Nunca se emite un número de seguridad sin verificar.
- **Chuleta asistida, no a mano** (2026-08-31): regex extrae `número + unidad + la frase donde vive` de la prosa ya procesada, acotado a lo que el chat citará (apuntes PADI primero + números Navy de los conflictos doctrinales); Adolfo audita la lista leyendo las frases — de "escribir tabla" a "revisar tabla". Regex-con-frase vs pasada de LLM etiquetada: se decide en el plan con una muestra real delante.
- **Grader descartado del MVP** (2026-08-31): era otro modelo más en runtime. Condición de activación medible: entra solo si el eval muestra que la abstención por prompt falla (los modelos no se abstienen cuando la etiqueta dice "sin respuesta"). Hasta entonces el chat vive con prompt estricto + guardarraíl numérico.
- El guardarraíl **verifica** números citados del corpus; nunca calcula. Las peticiones de cálculo ("¿cuánto tiempo puedo estar a 18 m?") caen en la abstención: sin tool (descartada, §4), cálculo = sin soporte en corpus → plantilla, que puede derivar al dispositivo (eRDPML / ordenador de buceo). Si el número pedido está textual en el corpus, no es cálculo: es retrieval normal + guardarraíl.
- **Juez LLM: solo evaluación, nunca runtime ni hardware.** Compara la respuesta con la `respuesta_esperada` del golden. Fijo, de API, familia fuera de los 4 (un GPT; modelo concreto al implementar), temperatura 0, rúbrica aprobado/suspenso. **Calibración**: Adolfo etiqueta 20-30 respuestas **mezcladas de los 4 modelos**; el juez se da por bueno solo con ≥90% de acuerdo; si no, se ajusta la rúbrica y se repite. Las preguntas sin respuesta en el corpus no pasan por el juez: se puntúan aparte con "¿se abstuvo?" (sí/no). El juez NO puede hacer de guardarraíl runtime: necesita la respuesta esperada, que solo existe en el examen. Framework: candidato deepeval (del doc de métricas de F5); se cierra en el plan.
- **`llm_evaluator`** (2026-08-31, sustituye a "corrector v2"; `corrector.py` renombrado a `retrieval_evaluator.py`): módulo aparte que corre el pipeline completo (retrieve → generar → puntuar) y escribe sus propias filas. Métricas: **juez + ¿se abstuvo cuando tocaba?** Descartados: exactitud numérica como métrica separada (el guardarraíl runtime ya protege; re-decidible con dato) y latencia/coste elaborados (LangSmith los da gratis en F8).

**Variantes registradas para el grid (fase 9):** los 4 modelos, y ya. *(Contexto completo vs reducido y grader on/off: eliminados 2026-08-31.)*

**Tareas:**

- [x] Interfaz LLM en `llm/` (backend API + backend mlx-lm) con las 4 configs.
- [x] Prompt de sistema (solo corpus, citas inline, números textuales, idioma de la pregunta, plantilla de abstención).
- [x] Chuleta asistida (regex + auditoría de Adolfo) + guardarraíl numérico con la política reintento-una-vez.
- [x] `llm_evaluator`: juez con rúbrica + calibración contra las etiquetas de Adolfo; abstención; filas versionadas.
- [x] Check ruidoso (uno): fixture de 10 respuestas sintéticas — 5 con números correctos y 5 con números alterados; el guardarraíl pilla las 5 malas y deja pasar las 5 buenas.

**Criterio de aceptación de la fase:** el juez está calibrado (≥90% de acuerdo con Adolfo), el check del guardarraíl pasa, y los 4 modelos tienen su pasada (una por modelo) con fila en `EXPERIMENTOS.md`.

### Fase 8: Chat CLI 🔒

La interfaz conversacional sobre la receta vigente.

**Decisiones cerradas:**

- **Dos caras** (decisión de Adolfo): **modo buceo** — pantalla estética de ordenador de buceo (dígitos estilo digital/figlet, paleta fosforescente), solo pregunta-respuesta con cita — y **modo dev** — comandos `/fuentes` (trozos recuperados con scores), `/config` (cambiar modelo/receta al vuelo), `/reset` (vaciar la ventana de 3 pares). Se conmuta con una tecla.
- **Condensador con ventana de 3 pares** (movido desde F7, 2026-08-31): solo actúa en el chat — el eval usa preguntas sueltas. Convierte historial + pregunta nueva en query autónoma antes de buscar; la ventana (últimos 3 pares pregunta-respuesta) ES la memoria a corto plazo, sin memoria larga. Modelo **fijo fuera de la ablación: Gemini Flash** — mismo condensador para todos los brazos, no añade dimensión al grid (medirlo exigiría un eval multi-turno que no existe).
- Framework: **Textual** (TUI con pantallas, estilos CSS-like) + pyfiglet para los dígitos grandes. Rich a pelo se queda corto con dos pantallas y comandos.
- Streaming de la respuesta (el usuario ve escribir al modelo) y trazas a LangSmith por conversación.
- **Convivencia RAM con modelo local** (decisión de Adolfo, 2026-09-07, corregida 2026-09-07 tras releer el código): el `qwen8b` del grid **ya corre cuantizado a Q8_0 vía Ollama (~8 GB)** — decisión de F4/T-04, no fp16 — así que la receta ganadora ya se midió con el embedder que usará el chat: **retrieval cerrado, F7 arranca sin nada por delante**. Cuenta del chat local: Q8 8 + Qwen 9B 4-bit ~5 + reranker ~1 ≈ 14 GB en 24 compartidos — cabe sobre el papel, se verifica gratis en el smoke de T-06 (F7): cargar el MLX con el Ollama levantado y mirar la presión de memoria (en el eval de F7 el embedder ni se carga: embeddings de las 84 cacheados). LangSmith da latencia, no RAM.
- **Brazo embedder Q4_K_M — condicional, solo si el smoke de T-06 dice que no cabe** (decisión de Adolfo, 2026-09-07): una variable (Q8_0 medido vs Q4_K_M ~4.7 GB, mismo modelo), todo lo demás clavado. Plan ya especificado por si dispara: `ollama pull qwen3-embedding:8b-q4_K_M` → entrada `qwen8b_q4` en `EMBEDDING_VALUES` y `MODELS` + filtro `--embedding/--corpus/--extras` en `p4_indexing.main()` → colección `combined-512-contextual-qwen8b_q4` → pasada de `retrieval_evaluator` híbrida k=10 rerank vs la fila Q8 (hit 0.9881 / recall 0.6891 / MRR 0.815). Práctica investigada 2026-09-07: reindexar con la misma precisión en ambos lados (mezclar precisiones del mismo modelo degrada poco — acuerdo top-10 ~0.98 int8 vs fp32 — pero reindexar elimina la deriva y aquí es barato). Nota: el "Q8 casi sin pérdida / 4-bit sesgaría" del comentario de T-04 es supuesto de conocimiento general, no medido contra el examen — este brazo lo convertiría en dato.

**Tareas:**

- [ ] App Textual con las dos pantallas y el conmutador.
- [ ] Condensador (Gemini Flash) con ventana de 3 pares.
- [ ] Comandos `/fuentes`, `/config`, `/reset`.
- [ ] Check ruidoso (uno): sesión guionizada de 3 turnos con follow-up ("¿y a 30 metros?") — el condensador resuelve la referencia y la respuesta llega con cita.

**Criterio de aceptación de la fase:** una conversación real multi-turno en modo buceo funciona de punta a punta (condensación, cita, abstención ante pregunta fuera de corpus), y en modo dev se ven los trozos de esa misma conversación.

### Fase 9: Grid y tabla final 🔒

Con todas las variantes registradas en las fases 1-8, se define el grid (fija-y-barre) y se corre.

**Decisiones cerradas (plan de barrido — divide y vencerás):**

- **Paso 0 — elegir el corpus de anclaje** (antes de fijar la receta base v0, añadido 2026-08-24; revisado 2026-08-27 en el plan de Fase 4): cruce barato con búsqueda densa simple — no híbrida, para no confundir con el ciego-entre-idiomas de BM25 entre apuntes (ES) y manual (EN) — sobre las 84 preguntas de eval, cruzando corpus (3) × extras (3) × modelo de embedding (4) = **36 pasadas** retrieval-only a k=5 (las 36 colecciones de Fase 4 existen exactamente para esto). El corpus ancla lo decide Adolfo con la tabla delante; ese valor entra en la receta base v0. La Oleada 1 (abajo) vuelve a medir corpus como una de sus 7 dimensiones, ya con la búsqueda híbrida real — este paso previo es una señal barata para no tunear a ciegas, no sustituye esa medición oficial.
- **Oleada 1 — barata (solo retrieval, sin LLM, gratis en el Mac):** desde la receta base (corpus del Paso 0 · 512 · sin extras · BGE-M3 · híbrida · k=5) se barre una dimensión cada vez volviendo a la base: corpus (3) · tope (3) · extras (3) · embedding (4: BGE-M3, Qwen3-Embedding-0.6B, Qwen3-Embedding-8B en Q8_0 vía Ollama, OpenAI text-embedding-3-large) · búsqueda (2) · k (3) · rerank (2) = **14 pasadas** de corrector v1 (la base se comparte). Sale la receta ganadora de búsqueda. El arm de OpenAI es la única excepción a "gratis en el Mac" — tiene coste real, pero del orden de céntimos (ver Fase 4), no cambia la cuenta de abajo.
- **Oleada 2 — cara (generación):** sobre la receta ganadora, los 4 modelos, una pasada por modelo = **4 pasadas** con LLM. *(Los brazos estructurales de F7 — contexto completo/reducido y grader on/off — se eliminaron el 2026-08-31.)*
- **Oleada 3 — cruces de cordura (2-3 pasadas):** uno fijo — si el corpus ganador ≠ apuntes, re-medir densa-vs-híbrida sobre él (BM25 es ciego entre idiomas y se decidió sobre el corpus ES) — y el resto a la vista de los resultados (p.ej. receta ganadora vs base con el mejor modelo).
- Total ≈ **56-57 pasadas** (Paso 0: 36 · Oleada 1: 14 · Oleada 2: 4 · Oleada 3: 2-3), **solo ~7 con coste real de API** (Oleada 2 + parte de Oleada 3; Paso 0/Oleada 1/Oleada 3 corren en local, salvo los céntimos del arm de embedding de OpenAI). La tabla final se monta leyendo las filas versionadas de `results/` — una fila por config. Es el entregable estrella (la historia en redes).

**Tareas:**

- [ ] Correr la oleada 1 y rellenar `EXPERIMENTOS.md` (fases 1-6).
- [ ] Correr la oleada 2 y rellenar `EXPERIMENTOS.md` (fase 7).
- [ ] Elegir y correr los cruces de cordura.
- [ ] Generar la tabla final desde `results/` (script, no a mano).

**Criterio de aceptación de la fase:** toda casilla de `EXPERIMENTOS.md` tiene resultado o motivo de descarte, y existe la tabla comparativa final con la config campeona declarada (calidad, latencia y coste a la vista).

### Futuro (fuera del recorrido)

- Web UI → vLLM en GPU alquilada → camino embedded.
- Triaje manual de las tablas del Navy Diving Manual (documento de apoyo, no fuente primaria — PADI manda en conflicto): en vez de la regla binaria actual de Fase 1 (toda tabla numérica fuera, solo puntero), extraerlas, leerlas una a una y decidir caso por caso cuáles aportan valor real al RAG frente a cuáles no. Aparcado porque el Navy es secundario y ninguna de las 186 preguntas del golden lo requiere hoy.
- Jev (TypeSafe AI, lanzado 2026-09-15): modelo de decisiones tipadas sin generación de texto — elige entre opciones, puntúa contra escala o da sí/no con probabilidad ($0.042/M entrada, 70-500ms, API cerrada en early access). Aparcado 2026-09-17 (decisión de Adolfo: "apuntarlo para ver alguna vez, ahora no"). Papeles candidatos SI algún día el dato lo pide: (a) clasificador "¿pide cálculo?" para el eval fresco de abstención (P1); (b) bake-off de jueces: cualquier candidato se enchufa a `judge.calibrate()` contra las etiquetas ciegas de Adolfo y compite por el ≥90% a céntimos. NO vale para: guardarraíl numérico (el nuestro es determinista, no se degrada a probabilístico) ni reranker (bge local gratis ya medido).

## 8. Success Metrics

Se fijan al cerrar cada fase — sin inventar ninguna ahora. Candidatas ya sobre la mesa (pendientes de umbral): recall@k sobre las 84 de eval · tasa de exactitud numérica en respuestas emitidas · % aprobado por el juez · latencia p50/p95 por config · coste por pasada.

## 9. Risks and Mitigations

| Risk                                                                            | Impact | Probability | Mitigation                                                                                  |
| ------------------------------------------------------------------------------- | ------ | ----------- | ------------------------------------------------------------------------------------------- |
| Tablas mal separadas de la prosa (filas sueltas contaminando chunks del índice) | Alto   | Alta        | Parsing table-aware desde la fase 1 + check de no-contaminación (Table 9-9) en el fixture   |
| Contaminación eval/corpus si se indexan los 186 Q-A                             | Alto   | Media       | Los Q-A son solo examen hasta que exista el eval fresco                                     |
| Juez LLM sesgado (verbosidad, auto-preferencia)                                 | Medio  | Media       | Rúbrica estricta, juez fijo de familia fuera de la ablación, calibrado con etiquetas a mano |
| El cruce de idiomas ES↔EN degrada más de lo publicado                           | Medio  | Baja        | Fila por idioma en el eval; brazo "normalizado a EN" como plan B medible                    |
| Gasto API descontrolado                                                         | Bajo   | Baja        | Fija-y-barre + métricas de retrieval sin LLM + techo ~20€/mes                               |

## 10. External Dependencies

- API de LLM (generación de los 2 modelos API + juez de evals): si desaparece, quedan los modelos locales y el juez se re-calibra con otro proveedor.
- Hugging Face: descarga de pesos (modelos locales, embeddings, reranker). Cacheados en local tras la primera descarga.
- LangSmith: trazas. Si falla, el sistema funciona igual (observabilidad, no camino crítico).
- US Navy Diving Manual Rev 7: descarga pública oficial (dominio público).

## 11. Project Constraints

| constraint      | value                                                                           | hard or soft      |
| --------------- | ------------------------------------------------------------------------------- | ----------------- |
| Presupuesto API | ~20€/mes                                                                        | soft ("da igual") |
| Plazo           | sin fecha, ritmo constante                                                      | —                 |
| Equipo          | Adolfo solo (construye, mantiene, opera)                                        | hard              |
| Hardware        | Mac (Apple M5, 24 GB RAM) en esta fase                                          | hard              |
| Stack impuesto  | Python + LangChain + mlx-lm + LangSmith (elegidos, no impuestos)                | soft              |
| Regulación      | ninguna vinculante; el producto no sustituye formación ni planificación oficial | —                 |

## 12. Milestones públicos y camino al paper

> Decisión de Adolfo (2026-09-03): track **paralelo** — nada de esta sección cambia el plan de §7
> ni añade rigor de paper por adelantado. El paper es un subproducto de terminar el proyecto,
> no una alternativa a terminarlo. El rigor extra (semillas múltiples, acuerdo entre anotadores,
> tests estadísticos) solo se paga cuando el hallazgo exista.

### Milestones contables en X/Twitter

Cada uno es una historia autocontenida con dato propio:

| # | Milestone | Qué se cuenta | Depende de |
|---|-----------|---------------|------------|
| M1 ✅ | Retrieval medido | Evaluador propio + reranker: hit_rate/recall/MRR sobre examen de 84 preguntas de un curso PADI real | F5 + F6 (hecho) |
| M2 | Primera generación medida | 4 modelos (Sonnet 5, Haiku 4.5, Qwen 3.5 9B/4B local) contra el mismo examen, con juez calibrado + guardarraíl numérico | F7 |
| M3 | El chat vivo | Vídeo del modo buceo (TUI estilo ordenador de buceo), multi-turno, citas, abstención | F8 |
| M4 | La tabla final | Grid completo: ¿alcanza un modelo local pequeño a los de API en QA de seguridad con grounding estricto? Config campeona declarada | F9 |
| M5 | Escalera de cuantización | Curva calidad/tamaño (4-bit/8-bit/fp16) contra corpus propio, no contra benchmarks ajenos | P1 (post-F9) |
| M6 | Fine-tuning LoRA | Solo si el diagnóstico de M2 lo justifica (pierde por instrucciones, no por conocimiento) | P1, condicional |

### El paper (milestone final, condicional)

**Disparador**: existen M4 + M5 — es decir, hay medición de la degradación API→local partida en
sus dos componentes (conocimiento vs seguimiento de instrucciones) y dato de cuánto recupera el
guardarraíl determinista. Sin ese hallazgo no hay paper; si el dato sale plano, el milestone muere
y se cuenta igualmente (resultado negativo en el blog, no en venue).

**Formulación candidata** (se re-decide con los datos delante): al pasar de un modelo de API a uno
local pequeño en QA con grounding estricto bajo restricción de seguridad, la degradación se parte
en conocimiento y seguimiento de instrucciones; se miden por separado, y una capa de verificación
determinista recupera la parte crítica sin tocar el modelo.

**Venue**: familia NLP/IR — ACL/EMNLP/NAACL (Findings como peldaño real) o SIGIR/ECIR para la parte
de retrieval. NO NeurIPS/ICML/ICLR (compite contra teoría y pierde).

**Escalera de publicación** (cada peldaño cuenta por sí solo, afiliación "Independent Researcher"):
1. Informe técnico + repo público (M4 ya lo es en forma de tabla).
2. Workshop de 4 páginas.
3. arXiv (necesita endorsement de alguien ya publicado — se consigue entonces).
4. Main track / Findings, solo si los peldaños anteriores aguantan.

**Pendientes bloqueantes antes de escribir** (no antes):
- Copyright del golden: deriva de material PADI — publicar el dataset ≠ usarlo en privado. Resolver antes de prometer release.
- El crítico (paso 1 de Madsen): alguien que sepa qué rechaza un revisor de EMNLP y se juegue el nombre. Idealmente de un grupo que interese (DLR, ETH, TUM) — paper y red se construyen a la vez.
- Debilidades conocidas que el rigor pagado entonces debe cubrir: n=84, un solo anotador, un solo dominio, un solo par de idiomas.
