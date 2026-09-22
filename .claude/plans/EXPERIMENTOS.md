# Checklist de experimentos — Divefy

> Cuaderno de laboratorio. Cada fase del PRD (§7) deja aquí su configuración base y sus
> variantes a probar. Se marca `[x]` cuando la variante se ha medido, y se apunta el
> resultado al lado. Las mediciones llegan en dos oleadas: **Fase 5** (métricas de
> retrieval, sin LLM — baratas, se barre aquí casi todo) y **Fase 7/9** (métricas de
> generación con los 4 modelos, sobre la receta ganadora). Método: fija-y-barre.

## El plan de medición, explicado (por qué está ordenado así)

La regla que ordena todo el banco: **lo gratis se barre a lo ancho; lo caro se mide
poco, tarde y sobre una receta ya optimizada.** Todo lo que no llama a un LLM de
generación (retrieval puro) corre gratis en el Mac; cada pasada con LLM cuesta dinero.
Por eso las decisiones van en actos, de barato a caro, y cada acto fija lo suyo antes
de pasar al siguiente (fija-y-barre: nunca el cruce completo):

1. **Elegir el terreno — corpus ancla** (Fase 5, Paso 0; gratis). 36 pasadas densas
   k=5 cruzando corpus × extras × modelo de embeddings. Decisión oficial: solo el
   **corpus** (con la tabla delante, decide Adolfo). Las columnas de extras y
   embeddings se rellenan como *señal barata* — orientan, pero su elección oficial es
   la Oleada 1, re-medida con la búsqueda real. Se usa solo búsqueda densa porque BM25
   es ciego entre idiomas (preguntas ES vs manual EN) y contaminaría la comparación de
   corpus.
2. **Elegir la búsqueda** (Fase 5, T-08; gratis). Sobre el ancla: densa vs híbrida y
   k ∈ {3, 5, 10}. Sale la receta de búsqueda.
3. **Afinar el retrieval, ya en oficial** (Fases 6 y 9-Oleada 1; gratis salvo
   céntimos del arm OpenAI). Rerank on/off, el tope 256/1024 aplazado en F5, y la
   re-medición fija-y-barre de todas las dimensiones baratas con la búsqueda ganadora
   (14 pasadas).
4. **Solo entonces, la generación** (Fases 7 y 9-Oleada 2; las únicas pasadas caras,
   ~8). Primero lo estructural con UN modelo barato — contexto completo vs reducido,
   grader on/off — y al final los 4 modelos sobre la receta congelada. Oleada 3 cierra
   con 2-3 cruces de cordura.

El resultado práctico: de las ~60 pasadas del banco, solo ~11 tocan una API de pago, y
cuando lo hacen, el resto de la receta ya está decidido con dato. Cada pasada deja su
fila inmutable en `results/` — la tabla final se monta leyendo esas filas.

## Receta base v0 (lo que corre cuando no se toca nada)

| pieza            | base (v1, fijada por Adolfo el 2026-08-30 con la tabla de F5 delante)          |
| ---------------- | ------------------------------------------------------------------------------ |
| corpus           | **combined** (ancla del Paso 0 + duelo T-08; cordura con rerank en F6)         |
| parsing          | table-aware (Docling — bake-off resuelto 2026-08-23)                           |
| chunking         | estructural, granularidad subsección, tope 512                                 |
| extras de índice | **contextual** (mejor equilibrio del barrido qwen8b)                           |
| embeddings       | **Qwen3-Embedding-8B en Q8_0 vía Ollama** (ganador claro en todos los cortes del Paso 0; cuantizado desde F4/T-04 — ~8 GB, no el fp16 de ~15) |
| búsqueda         | **híbrida RRF (densa + BM25)**; **k=10** (fijado por Adolfo en F6, 2026-08-31; re-medir si la calidad de generación baja con LLMs pequeños) |
| rerank           | **on** (bge-reranker-v2-m3, N=20 → k; fijado por Adolfo en F6, 2026-08-31 — ver tabla F6; se re-juzga en F7 si perder la versión Navy en contexto duele) |
| generación       | no entra en el barrido barato; los 4 modelos se miden sobre la receta ganadora |

(v0 histórica: apuntes provisional · sin extras · BGE-M3 · k=5 — superada por el
método de Adolfo de arrastrar ganadores con dato: el Paso 0 y T-08 fijaron corpus,
extras y embeddings de una vez; la re-elección prevista en Oleada 1 queda reducida
a lo aún abierto — revisar su alcance al llegar a F9.)

## Fase 1 — Ingesta

- [x] Corpus apuntes solos → resultado (Paso 0, 2026-08-30): hit_rate medio 0.882
      sobre sus 12 brazos, mejor brazo 0.9286 (qwen8b base/hype); recall medio 0.491.
- [x] Corpus manual curado → resultado: hit_rate medio 0.486, mejor 0.5714
      (qwen8b contextual) — lastrado por las ~24 preguntas sin etiqueta de manual
      (fallo por construcción) y el cruce ES↔EN; dentro de sus 60 respondibles,
      qwen8b encuentra el 80%.
- [x] Corpus ambos combinados → resultado: hit_rate medio 0.882 (EMPATE con
      apuntes), mejor brazo del cruce entero 0.9405 (qwen8b contextual); recall
      medio 0.545 (+5.4 pts sobre apuntes: cubre secciones de ambas doctrinas).
      Interferencia interna medible: hit_rate_apuntes dentro de combined cae 3-5
      pts vs apuntes solo (chunks EN desplazan a ES del top-5), compensada por lo
      que gana vía manual.

**Paso 0 medido (2026-08-30, 36 pasadas densas k=5, filas en `results/`):**

| corpus | extras | modelo | hit_rate | recall | precision | mrr | apuntes | manual | tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| apuntes | base | bgem3 | 0.881 | 0.495 | 0.274 | 0.666 | 0.892 | 0.0 | 1450 |
| apuntes | base | qwen06b | 0.774 | 0.399 | 0.231 | 0.607 | 0.783 | 0.0 | 1304 |
| apuntes | base | qwen8b | 0.929 | 0.530 | 0.329 | 0.812 | 0.940 | 0.0 | 1534 |
| apuntes | base | openai3large | 0.881 | 0.482 | 0.312 | 0.781 | 0.892 | 0.0 | 1587 |
| apuntes | contextual | bgem3 | 0.893 | 0.489 | 0.269 | 0.764 | 0.904 | 0.0 | 1495 |
| apuntes | contextual | qwen06b | 0.833 | 0.442 | 0.260 | 0.657 | 0.843 | 0.0 | 1343 |
| apuntes | contextual | qwen8b | 0.917 | 0.515 | 0.331 | 0.801 | 0.928 | 0.0 | 1497 |
| apuntes | contextual | openai3large | 0.917 | 0.510 | 0.331 | 0.776 | 0.928 | 0.0 | 1604 |
| apuntes | hype | bgem3 | 0.857 | 0.488 | 0.255 | 0.721 | 0.868 | 0.0 | 1372 |
| apuntes | hype | qwen06b | 0.857 | 0.492 | 0.276 | 0.723 | 0.868 | 0.0 | 1416 |
| apuntes | hype | qwen8b | 0.929 | 0.529 | 0.312 | 0.774 | 0.940 | 0.0 | 1382 |
| apuntes | hype | openai3large | 0.917 | 0.521 | 0.293 | 0.792 | 0.928 | 0.0 | 1468 |
| combined | base | bgem3 | 0.857 | 0.534 | 0.288 | 0.673 | 0.735 | 0.483 | 1596 |
| combined | base | qwen06b | 0.821 | 0.458 | 0.257 | 0.639 | 0.759 | 0.283 | 1280 |
| combined | base | qwen8b | 0.917 | 0.586 | 0.350 | 0.794 | 0.868 | 0.467 | 1398 |
| combined | base | openai3large | 0.881 | 0.500 | 0.317 | 0.781 | 0.892 | **0.050** | 1589 |
| combined | contextual | bgem3 | 0.869 | 0.553 | 0.302 | 0.751 | 0.771 | 0.483 | 1578 |
| combined | contextual | qwen06b | 0.833 | 0.489 | 0.279 | 0.648 | 0.831 | 0.200 | 1334 |
| combined | contextual | qwen8b | **0.941** | **0.634** | **0.400** | 0.772 | 0.880 | 0.583 | 1499 |
| combined | contextual | openai3large | 0.917 | 0.531 | 0.341 | 0.776 | 0.928 | **0.067** | 1608 |
| combined | hype | bgem3 | 0.869 | 0.570 | 0.302 | 0.731 | 0.819 | 0.367 | 1472 |
| combined | hype | qwen06b | 0.845 | 0.538 | 0.298 | 0.706 | 0.783 | 0.317 | 1529 |
| combined | hype | qwen8b | 0.917 | 0.600 | 0.350 | 0.750 | 0.783 | 0.600 | 1521 |
| combined | hype | openai3large | 0.917 | 0.547 | 0.307 | 0.791 | 0.928 | **0.083** | 1469 |
| manual | base | bgem3 | 0.440 | 0.158 | 0.136 | 0.333 | 0.0 | 0.617 | 1692 |
| manual | base | qwen06b | 0.417 | 0.161 | 0.112 | 0.302 | 0.0 | 0.583 | 1276 |
| manual | base | qwen8b | 0.524 | 0.204 | 0.171 | 0.404 | 0.0 | 0.733 | 1221 |
| manual | base | openai3large | 0.536 | 0.204 | 0.176 | 0.401 | 0.0 | 0.750 | 1522 |
| manual | contextual | bgem3 | 0.488 | 0.172 | 0.155 | 0.400 | 0.0 | 0.683 | 1678 |
| manual | contextual | qwen06b | 0.452 | 0.171 | 0.136 | 0.301 | 0.0 | 0.633 | 1410 |
| manual | contextual | qwen8b | 0.571 | 0.227 | 0.212 | 0.458 | 0.0 | 0.800 | 1446 |
| manual | contextual | openai3large | 0.512 | 0.200 | 0.171 | 0.420 | 0.0 | 0.717 | 1549 |
| manual | hype | bgem3 | 0.464 | 0.170 | 0.145 | 0.378 | 0.0 | 0.650 | 1673 |
| manual | hype | qwen06b | 0.405 | 0.152 | 0.138 | 0.318 | 0.0 | 0.567 | 1584 |
| manual | hype | qwen8b | 0.488 | 0.188 | 0.169 | 0.383 | 0.0 | 0.683 | 1580 |
| manual | hype | openai3large | 0.536 | 0.206 | 0.174 | 0.419 | 0.0 | 0.750 | 1644 |

Hallazgo destacado del desglose: **openai3large en combined tiene hit_rate_manual
0.05-0.08** (vs 0.75 en manual solo) — sus embeddings agrupan por idioma: con
español disponible, el inglés casi nunca entra al top-5. bgem3 (0.37-0.48) y
qwen8b (0.47-0.60) cruzan ES↔EN mucho mejor. Es el termómetro que el desglose
existía para medir.

**Paso 0 — cómo se decide el ganador** (2026-08-24): búsqueda densa simple (sin BM25)
sobre las 84 preguntas de eval, resto de ajustes en su valor por defecto — no la
híbrida de la receta base, precisamente para no mezclar "el corpus no ayuda" con "BM25
no encuentra nada en inglés cuando la pregunta es en español" (apuntes es ES, manual es
EN, BM25 es ciego entre idiomas). El corpus con mejor recall aquí es el que entra en la
receta base v0 de arriba. Se vuelve a medir con búsqueda híbrida dentro de la Oleada 1
(PRD Fase 9) — este paso es solo la señal barata para elegir el ancla, no la medición
oficial.

Parsing (Docling vs pdfplumber): lo resuelve el bake-off de la Fase 1, no la oleada — el juez es el fixture, una vez.

- [x] **Bake-off resuelto (2026-08-23) → gana Docling.** Medido sobre cap 9 (86 págs,
  peor caso) + cap 2 (38 págs, control de prosa densa) vía `scripts/bakeoff_fase1.py`
  (desechable, no versionar el volcado JSON). Filas de tabla coladas en prosa —
  Docling: **0 / 0** · pdfplumber: **710 / 101** (peor que el baseline naive de 670 en
  cap 9). Tablas lógicas (tras plegar "(Continued)" y descartar Figuras, fuera de
  alcance): Docling 11 en cap9 (8 nombradas + 3 fragmentos sin caption — falta Table
  9-8, cae en fallback pendiente de T-05) frente a 235 sin plegar de pdfplumber.
  Tiempo: Docling ~165s (cap9+cap2) vs pdfplumber ~5s. Se pierde el bake-off en tiempo
  30x, se gana en separación tabla/prosa (el criterio que manda, por la regla ya
  pactada: "pdfplumber gana si separa igual de limpio, por 8 deps contra 103" — no fue
  el caso). Decisión de Adolfo. `pdfplumber` se retira en T-07.

## Fase 2 — Chunking

- [ ] Tope 256 → resultado:
- [ ] Tope 512 (base) → resultado:
- [ ] Tope 1024 → resultado:
- [ ] Empaquetado por secciones (respeta límites de sección, nunca mezcla dos secciones
  ya completas solo por aprovechar hueco) vs. empaquetado libre (base actual: junta
  secciones vecinas hasta el tope sin mirar si tratan el mismo tema) → resultado:
  Decisión de Adolfo (2026-08-24): empezar por lo simple (empaquetado libre,
  `RecursiveCharacterTextSplitter` sin lógica de fusión propia) y medir el estructurado
  como variante en Fase 5 si el recall lo pide — no hay benchmark publicado que compare
  exactamente estos dos casos (Chroma mide naive-vs-semántico, el paper NAACL 2025 mide
  fijo-vs-semántico; ninguno mide estructurado-vs-libre). Pinecone recomienda por
  defecto empezar por lo simple; Weaviate advierte del riesgo de mezclar temas sin
  relación. Fuentes: trychroma.com/research/evaluating-chunking ·
  aclanthology.org/2025.findings-naacl.114 · pinecone.io/learn/chunking-strategies ·
  weaviate.io/blog/chunking-strategies-for-rag.

Descartado con motivo: tamaño fijo con solape (corta procedimientos por la mitad; solo compite en texto sin costuras).

## Fase 3 — Extras de índice

- [ ] Sin extras (base) → señal barata del Paso 0 (solo-densa, 2026-08-30): el suelo — contextual lo iguala o supera en 10 de 12 pares corpus×modelo. Medición oficial: Oleada 1 con híbrida.
- [ ] +Contextual retrieval (contexto embebido con el trozo; ayuda a buscar Y a responder) → señal barata: mejor extra en denso — el mejor brazo del cruce entero es contextual (combined-qwen8b 0.9405).
- [ ] +HyPE encadenado (preguntas generadas sobre el trozo ya contextualizado; ayuda solo a buscar) → señal barata: no aporta consistente en denso (a veces resta vs contextual); su apuesta era pregunta-vs-pregunta y el denso ya cruza bien sin señuelos.

Nota: escalera acumulativa — HyPE se mide encima de contextual, nunca sabremos "HyPE solo" (trade aceptado; cruce de cordura en Fase 9 si hace falta). El LLM que genera contextos y preguntas es fijo y aparte del experimento (decisión de Adolfo).

## Fase 4 — Embeddings e índice

- [ ] BGE-M3 (base) → señal barata del Paso 0 (solo-densa, 2026-08-30): tercero (hit_rate 0.86-0.89 en apuntes/combined); el mejor cruce ES↔EN junto a qwen8b.
- [ ] Qwen3-Embedding-0.6B → señal barata: último en todos los cortes (0.77-0.85).
- [ ] Qwen3-Embedding-8B (**Q8_0 vía Ollama** — decisión F4/T-04: fp16 ~15 GB arriesgado en 24 GB; todo lo medido de este modelo es con Q8_0) → señal barata: **gana casi todo** — top del cruce (0.94), mejor MRR, buen cruce ES↔EN. El local 8B supera a la API.
- [ ] OpenAI text-embedding-3-large → señal barata: segundo en global PERO agrupa por idioma: en combined su hit_rate_manual se hunde a 0.05-0.08 (vs 0.75 en manual solo).

Vectorstore: Chroma (cerrado, no se barre). Mismo modelo indexa y consulta, siempre.
**Revisado 2026-08-24**: se añaden Qwen3-Embedding-8B (aísla la variable tamaño dentro
de la misma familia que el 0.6B, igual que ya se hace con los 4 modelos de generación)
y un arm de API, OpenAI `text-embedding-3-large` — medición del "caso ideal" vs. local,
no implica que sirva el chat en producción (introduce dependencia de red en cada
consulta, cosa que Fase 5 no tiene hoy). El motivo original de descartar API por
arquitectura (retrieval local + endgame embedded) sigue en pie para lo que se sirve en
producción; este arm es solo medición, no cambia esa decisión. Nomic Embed v2 sigue
apuntado en P2 embedded, fuera del grid.

## Fase 5 — Retrieval

- [x] Híbrida RRF densa+BM25 (base) → resultado (T-08, 2026-08-30, sobre qwen8b):
      **gana** — mejor hit_rate en casi toda fila de ambos corpus (p.ej. combined-ctx
      k10: 0.9762 vs 0.9524 densa). **Receta de búsqueda declarada (Adolfo):
      combined + contextual + híbrida**, k pendiente entre 5 y 10 → se cierra en
      F6 con el reranker delante.
- [x] Densa sola (ablación: cuánto aporta el lado léxico) → resultado: BM25 aporta
      +1-2 preguntas en apuntes (hipótesis de Adolfo confirmada); en combined cura
      la interferencia del lado ES (hit_apuntes 0.88→0.92) pero ahoga al manual
      (hit_manual 0.58→0.45, BM25 es ciego al inglés) — el global no lo paga.
- [x] k = 3 / 5 / 10 (se elige por curva de recall) → resultado: k=3 pierde 5-8
      preguntas; k=5→k=10 compra +3 preguntas y +10 pts de recall a cambio de ×2
      tokens (1.6K→3.2K) y precision 0.38→0.26. Decisión aplazada a F6: pescar
      ancho + reranker puede quedarse lo mejor de ambos.

Juez: métricas IR deterministas vía **ranx** — hit_rate@k (la principal), recall@k, precision@k, MRR + tokens recuperados — contra etiquetas por sección (solo `uso=eval`, 84 preguntas; etiquetado asistido por LLM en pasada única, auditado en 3 pasadas). Revisado por primeros principios 2026-08-28/30, razones y código en `phase-5-retrieval/metricas-framework.md`. Match numérico retirado (re-decidible en F7 si el guardarraíl lo pide). Alternativa anotada: sparse de BGE-M3 en vez de BM25 si el cruce ES↔EN duele. Descartados: ColBERT, juez LLM por pasada, similitud de embeddings como juez.

## Fase 6 — Rerank

- [x] Sin reranker (base) → resultado (2026-08-31, combined·contextual·qwen8b·híbrida):
      k=10 hit 0.9762 / recall 0.7146 / mrr 0.781 / manual 0.583 / 3230 tok ·
      k=5 hit 0.9405 / recall 0.6144.
- [x] bge-reranker-v2-m3 on (N=20) → resultado (2026-08-31): k=10 hit **0.9881** /
      recall 0.6891 / mrr **0.815** / apuntes 1.000 / manual 0.367 · k=5 hit 0.9762 /
      recall 0.6004. Control solo-apuntes (sin cruce de idioma): rerank neutro (±1 pt).
      Diagnóstico (recomputado del detalle, sin pasadas nuevas): el rerank saca el
      manual del top-k en 14 de 60 preguntas con etiqueta de manual, pero las 14
      conservan la respuesta vía apuntes — 0 preguntas huérfanas; el coste real es la
      doble cita PADI+Navy, no el soporte.

**Decisión (Adolfo, 2026-08-31): rerank ON y k=10 pasan a la config base.** Motivo:
hit_rate manda y el orden (MRR) es lo que más ayuda a los LLMs pequeños del grid de F7
(responden desde los primeros chunks, sufren distractores); el recall perdido (−2.5 pt)
es completitud de secciones secundarias. Condiciones de re-juicio escritas: (1) si en
F7 la calidad de generación con k=10 baja con los modelos pequeños, re-medir k; (2) si
perder la versión Navy en esas 14 preguntas daña calidad o la doble cita (regla 2),
re-juzgar el on/off con dato de generación. Sonda a N=40: **descartada por Adolfo
(2026-08-31)** — N=20 ya da hit 0.988/MRR 0.815; no hay señal que justifique doblar
el coste por consulta.

N=20 fijo (sonda única a N=40 solo si on gana). Umbral del reranker → P1 Post-MVP (2026-08-30; se calibrará con los negativos del eval fresco). Latencia medida en sonda (2026-08-28, M5, MPS, CrossEncoder ya instalado): ~1.45s por consulta con ~20 pares en caliente, carga 36.6s por proceso, contexto 8192 (chunks de 512 caben enteros) — la condición Jina se juzga con este dato; medición por etapa llegará con LangSmith (Fase 8). Alternativa anotada: Jina Reranker v3 (listwise) solo si la latencia molesta — revisar licencia antes. Descartados: APIs de rerank (peaje de red por consulta), Qwen3-Reranker 4B/8B (peso).

## Fase 7 — Generación

- [x] 4 modelos confirmados: Sonnet 5 / Haiku 4.5 (API) · Qwen 3.5 9B / 4B (MLX 4-bit) → resultado (2026-09-22, receta `combined-512-contextual-qwen8b-hibrida-k10-rerank`, prompt `generation_v2`, juez council `judge_v3`):

  | modelo | aprobado | score medio | abstenciones |
  |---|---|---|---|
  | sonnet5 | 83.3% (70/84) | 0.817 | 1 |
  | haiku45 | 82.1% (69/84) | 0.770 | 1 |
  | qwen9b | 67.9% (57/84) | 0.620 | 3 |
  | qwen4b | 57.1% (48/84) | 0.600 | 3 |

  Decisión (Adolfo, 2026-09-22): **Sonnet 5** como modelo principal, **qwen9b** como opción local (corre en el Mac, sin depender de API) — no se busca máxima precisión en la rama local, el objetivo es tenerla funcionando en el hardware actual. qwen4b descartado del grid final (10 puntos por debajo de qwen9b). Hardware dedicado para multiusuario, fuera de alcance de este proyecto: es un problema de servir peticiones concurrentes (vLLM/TGI + GPU), no de modelo más grande — se revisita si el proyecto continúa más allá del MVP.
- [ ] Contexto completo vs reducido (subsección ~2-4K tokens) → resultado:
- [ ] Abstención (grader) on/off → resultado:

Juez de generación: council de 3 modelos de API (sonnet45, gemini-3.1-flash-lite, gpt-4.1-mini; familias fuera de los 4 del grid), voto por mayoría, calibrado con etiquetas de Adolfo. Prueba extra anotada (no prioritaria): ventana conversacional >3 pares.

## Notas para cuando midamos (no antes)

- Con 84 preguntas, cada pregunta vale 1.2 puntos de recall: diferencias de 2-3 puntos son un par de preguntas. La tabla publica cada número con su margen; qué cuenta como empate se decide con la primera tabla delante.
- El recall crece mecánicamente con tope y k (más texto = más probabilidad de tocar sección etiquetada). Leerlo siempre junto a MRR y tokens recuperados, que el evaluador registra desde el día uno.

## Backlog medible (fuera del grid v1)

- [ ] Brazo "idioma normalizado a inglés" (índice 100% EN + query pivotada) vs multilingüe nativo.
- [ ] Eval fresco ~45 preguntas (inglés + sin-respuesta) — mide abstención de verdad.
- [ ] Ampliar corpus PADI: los apuntes son lo esencial, no todo; las preguntas que fallen con corpus "apuntes solos" son la lista exacta de qué añadir. Fuente oficial PADI disponible (ojo copyright: uso personal sí, redistribución no).
- [ ] Corpus-v2 con eRDPML/tablas (post-MVP, sustituye a la tool descartada): Adolfo se lee el manual del eRDPML y las tablas RDP y decide qué texto procedimental entra al corpus ("cómo se usa la tabla / el eRDPML") y qué preguntas entran a las evals. Bonus: segunda tanda de runs versionados en `results/` — ensayo de evals con cambio de versión como en prod.
- [ ] Preguntas de cálculo de los cuestionarios: NUNCA al eval del RAG. Coleccionarlas — son candidatas perfectas para el eval de abstención (respuesta correcta conocida = abstención + derivación al dispositivo). Se decide con el eval fresco.

## Descartados con motivo (no volver sin dato nuevo)

- HyDE, GraphRAG/LightRAG, RAPTOR, Self-RAG/CRAG completo, late chunking, fine-tuning como conocimiento, brazo capítulo 10-30K tokens, tamaño fijo con solape.
- Tool de cálculo de tablas (y con ella: JSON de tablas RDP + examen propio de la tool): duplica un dispositivo certificado que la doctrina obliga a usar (eRDPML/ordenador de buceo); sin eRDPML tampoco habría RAG embebido. Petición de cálculo → abstención con derivación. El valor del chat es explicativo.
