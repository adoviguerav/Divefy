# Divefy

A dive-safety chat that answers only from a verified corpus, plus the experiment bench used to measure every piece of its RAG pipeline.

## What it is

Two things at once:

1. A chat (a small local web page) that answers dive-safety questions in Spanish or English using the US Navy Diving Manual Rev 7 and a set of PADI Open Water course notes. Every answer shows its sources. Safety numbers (depths, times, rates) are copied verbatim from the corpus and checked digit by digit by a deterministic guardrail; if a number cannot be verified, the chat abstains instead of guessing. When the corpus does not cover a question, it says so. It remembers the last 3 turns: a condenser rewrites follow-up questions into standalone queries before searching.
2. An experiment bench that compares RAG techniques (hybrid search, contextual retrieval, HyPE, reranking), models (Sonnet 5, Haiku 4.5, and Qwen 3.5 9B/4B running locally) and corpora against an exam of 84 questions from the PADI course. The output is a table: which configuration answers best, at what latency and cost, and whether a small local model keeps up with the API ones.

## Stack

Python 3.12+, uv, LangChain, Chroma, Ollama and HuggingFace for embeddings, bge-reranker, mlx-lm for local models on Apple Silicon, Gemini for the condenser, LangSmith for traces. The web layer is a stdlib HTTP server and one HTML file with inline CSS and JavaScript.

## Installation

### Requirements

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).
- [Ollama](https://ollama.com), for the embedding model used by the best configuration (about 8 GB on disk). There is a lighter option without Ollama below.
- A Mac with Apple Silicon only if you want the local models (Qwen through MLX). With the API models (Sonnet, Haiku) it runs on any system.
- API keys in a `.env` file at the repo root:

| Variable | Used for | Required? |
|---|---|---|
| `ANTHROPIC_API_KEY` | the `sonnet5` and `haiku45` models | yes, to chat with those models |
| `GEMINI_API_KEY` | the condenser (3-turn memory) | yes, for the chat |
| `OPENAI_API_KEY` | the evaluation judge and the `openai3large` embedding | only for experiments |
| `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | one trace per turn in LangSmith | no; without them nothing is sent |

### Steps

```bash
git clone https://github.com/adoviguerav/Divefy.git && cd Divefy
uv sync                                                    # dependencies

ollama pull qwen3-embedding:8b-q8_0                        # embedding model (once)
uv run python -m divefy.pipeline.p4_indexing \
  --corpus combined --extras contextual --embedding qwen8b # build the index (~2 min)

uv run python -m divefy                                    # opens the chat in your browser
```

The first run downloads the reranker (`BAAI/bge-reranker-v2-m3`, about 2 GB) and loads everything before opening the page. The terminal prints `Modelos cargados. Listo para preguntar.` when it is ready.

The corpus ships already processed (`data/processed/chunks.jsonl` and `enrich.jsonl`), so you do not need to parse the PDF or pay for the enrichment step.

### Lighter option (no Ollama)

Index with BGE-M3 instead (it downloads itself, about 2 GB), then pick it in the chat under Dev mode, embedding: bgem3, Apply:

```bash
uv run python -m divefy.pipeline.p4_indexing --corpus combined --extras contextual --embedding bgem3
```

### Local models (optional, Apple Silicon)

The `qwen9b` and `qwen4b` models download from HuggingFace the first time you pick them in Dev mode (about 5 GB and 3 GB). With everything loaded, expect around 14 GB of unified memory in use.

## Usage

Type a question or click one of the four examples. Enter sends. "Nueva conversación" clears the memory.

Dev mode adds two things: under each answer, the corpus chunks that were used, each with its score and a short legend explaining what that score means; and a panel to switch the model and the retrieval configuration on the fly. Apply preloads the new models and starts a clean conversation.

An answer shown in yellow is an abstention: the corpus does not support the question, or the question asked for a calculation, which Divefy never does.

## Experiments

Each evaluator writes one row of metrics per configuration into `results/`. Rows are never overwritten.

```bash
uv run python -m divefy.evals.retrieval_evaluator --help   # search: hit_rate@k, recall, MRR
uv run python -m divefy.evals.llm_evaluator --help         # generation: LLM judge and abstention
uv run pytest                                              # full suite, about a minute, no network
```

The golden dataset (`data/eval/golden.jsonl`) is the exam. It is never indexed.

## Layout

```
src/divefy/
  __main__.py        # `python -m divefy`: starts the API, preloads models, opens the browser
  api.py             # GET / · GET /api/options · POST /api/chat · POST /api/warmup
  chat.py            # one turn: condense, retrieve, generate, guardrail
  static/index.html  # the page (HTML, CSS and JS in one file)
  config.py          # RetrievalConfig and the best-known configuration
  pipeline/          # p1_ingest, p2_chunking, p3_enrich, p4_indexing,
                     # p5_retrieve, p6_rerank, p7_generate + p7_guardrail, p8_condense
  evals/             # retrieval_evaluator, llm_evaluator, judge
  prompts/           # versioned prompts (generation, judge, condenser)
data/raw/            # sources: the Navy manual (PDF) and the PADI notes (markdown)
data/processed/      # parsed corpus, chunks and enrichment (versioned)
data/chroma/         # Chroma collections (built locally, not versioned)
data/eval/           # golden dataset, labels and evaluation caches
data/guardrail/      # the table of safety constants the numeric guardrail checks against
results/             # one row of metrics per configuration
tests/               # unit (scaffolding) and acceptance (frozen per phase)
```

## Status

MVP: phases 1 to 8 are done and verified (ingestion, chunking, index extras, embeddings, retrieval, reranking, generation with guardrail, web chat). Phase 9, the full grid and the final comparison table, is in progress.

## License

MIT. The US Navy Diving Manual is in the public domain. The PADI notes are my own, paraphrased.
