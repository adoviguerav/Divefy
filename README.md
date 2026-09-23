# Divefy

Copiloto de buceo con IA: un chat que responde dudas de seguridad en buceo (ES/EN) apoyándose **solo** en un corpus verificado, construido sobre un banco de experimentos que mide cada pieza del RAG.

## Qué es

Dos cosas a la vez:

1. **Un chat** (página web local, minimalista) que responde desde el US Navy Diving Manual Rev 7 y unos apuntes del Open Water PADI — con las fuentes a la vista, números de seguridad copiados textualmente del corpus y verificados dígito a dígito por un guardarraíl determinista, y abstención explícita cuando el corpus no cubre la pregunta. Recuerda los últimos 3 turnos (un condensador reescribe los follow-ups antes de buscar).
2. **Un banco de experimentos** que compara técnicas de RAG (búsqueda híbrida, contextual retrieval, HyPE, rerank…), modelos (Sonnet 5, Haiku 4.5, Qwen 3.5 9B/4B en local) y corpus contra un examen propio de 84 preguntas del curso PADI. El resultado es una tabla: qué configuración responde mejor, a qué latencia y a qué coste — y si un modelo local pequeño alcanza a los de API.

## Stack

Python 3.12+ · uv · LangChain · Chroma · Ollama / HuggingFace (embeddings) · bge-reranker · mlx-lm (modelos locales, Apple Silicon) · Gemini (condensador) · LangSmith (trazas) · servidor stdlib + HTML/CSS/JS sin framework.

## Instalación

### Requisitos

- **Python ≥ 3.12** y [`uv`](https://docs.astral.sh/uv/).
- **[Ollama](https://ollama.com)** para el modelo de embeddings ganador (~8 GB en disco). Alternativa ligera sin Ollama más abajo.
- **macOS con Apple Silicon** solo si quieres los modelos locales (Qwen vía MLX). Con los modelos de API (Sonnet/Haiku) funciona en cualquier sistema.
- Claves de API en un `.env` en la raíz:

| Variable | Para qué | ¿Obligatoria? |
|---|---|---|
| `ANTHROPIC_API_KEY` | modelos `sonnet5` / `haiku45` | sí para chatear con esos modelos |
| `GEMINI_API_KEY` | condensador del chat (memoria de 3 turnos) | sí para el chat |
| `OPENAI_API_KEY` | juez de los evals y embedding `openai3large` | solo para experimentos |
| `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` + `LANGSMITH_PROJECT` | trazas de cada turno en LangSmith | no (sin ellas no se envía nada) |

### Pasos

```bash
git clone https://github.com/adoviguerav/Divefy.git && cd Divefy
uv sync                                                    # dependencias

ollama pull qwen3-embedding:8b-q8_0                        # embedder ganador (una vez)
uv run python -m divefy.pipeline.p4_indexing \
  --corpus combined --extras contextual --embedding qwen8b # índice ganador (~2 min)

uv run python -m divefy                                    # abre el chat en el navegador
```

La primera vez, `python -m divefy` descarga el reranker (`BAAI/bge-reranker-v2-m3`, ~2 GB) y precarga todo antes de abrir la página; verás `Modelos cargados. Listo para preguntar.` en la terminal.

El corpus ya viene procesado en el repo (`data/processed/chunks.jsonl` y `enrich.jsonl`): no hace falta parsear el PDF ni pagar el enriquecedor.

### Alternativa ligera (sin Ollama)

Indexa con BGE-M3 (se descarga solo, ~2 GB) y elígelo en el chat en *Modo dev → embedding: bgem3 → Aplicar*:

```bash
uv run python -m divefy.pipeline.p4_indexing --corpus combined --extras contextual --embedding bgem3
```

### Modelos locales (opcional, Apple Silicon)

Los modelos `qwen9b` / `qwen4b` se descargan de HuggingFace la primera vez que los eliges en *Modo dev* (≈5 GB y ≈3 GB). Cuenta unos 14 GB de memoria unificada con todo cargado.

## Uso

- Escribe una pregunta o pulsa una de las cuatro de ejemplo. `Enter` envía.
- **Nueva conversación** borra la memoria.
- **Modo dev** muestra, bajo cada respuesta, los trozos del corpus usados con su score (y una leyenda de qué significa), y un panel para cambiar modelo y receta de búsqueda al vuelo (*Aplicar* precarga los modelos nuevos y empieza una conversación limpia).
- Una respuesta en amarillo es una **abstención**: el corpus no respalda la pregunta (o pedía un cálculo, que Divefy nunca hace).

## Experimentos

Cada evaluador escribe una fila de métricas por configuración en `results/` (nunca se sobreescriben):

```bash
uv run python -m divefy.evals.retrieval_evaluator --help   # búsqueda: hit_rate@k, recall, MRR
uv run python -m divefy.evals.llm_evaluator --help         # generación: juez LLM + abstención
uv run pytest                                              # suite completa (~1 min, sin red)
```

El golden dataset (`data/eval/golden.jsonl`) es el examen: **nunca se indexa**.

## Estructura

```
src/divefy/
  __main__.py        # `python -m divefy`: arranca la API, precarga modelos, abre el navegador
  api.py             # GET / · GET /api/options · POST /api/chat · POST /api/warmup
  chat.py            # lógica de un turno (condensar → recuperar → generar → guardarraíl)
  static/index.html  # la página (HTML/CSS/JS, un fichero)
  config.py          # RetrievalConfig y la receta ganadora
  pipeline/          # p1_ingest → p2_chunking → p3_enrich → p4_indexing →
                     # p5_retrieve → p6_rerank → p7_generate/p7_guardrail → p8_condense
  evals/             # retrieval_evaluator, llm_evaluator, judge
  prompts/           # prompts versionados (generación, juez, condensador)
data/raw/            # fuentes: manual Navy (PDF) + apuntes PADI (markdown)
data/processed/      # corpus parseado, chunks y enriquecimiento (versionados)
data/chroma/         # colecciones Chroma (se construyen en local, no versionadas)
data/eval/           # golden dataset, etiquetas y cachés de evaluación
data/guardrail/      # chuleta de constantes de seguridad para el guardarraíl numérico
results/             # una fila de métricas por configuración
tests/               # unit (andamiaje) + acceptance (congelados por fase)
```

## Estado

MVP: fases 1-8 cerradas y verificadas (ingesta → chunking → extras de índice → embeddings → retrieval → rerank → generación con guardarraíl → chat web). En curso: Fase 9, el grid completo y la tabla comparativa final.

## Licencia

MIT. El US Navy Diving Manual es de dominio público; los apuntes PADI son material propio, parafraseado.
