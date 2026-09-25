# Divefy

I am learning to dive. The course hands you more safety information than anyone can hold in their head: physics, physiology, procedures, and numbers where being off by a little matters. Most diving deaths come down to diver error, and most of those errors were preventable with the right information at the right moment. I wanted something I could ask in plain Spanish, the night before a dive, and trust.

A generic chatbot fails that test. It will happily invent a decompression stop. So Divefy answers only from two sources, the US Navy Diving Manual Rev 7 and my own PADI Open Water notes, and every number it says has to appear verbatim in one of them. If it cannot verify a number, it says it does not know. If the sources do not cover the question, it says that too.

The second half of the project is how I chose every piece of it. Instead of picking a retrieval technique or a model on faith, I wrote an exam of 84 questions from the course and measured each option against it. The table further down is the result.

## Results at a glance

Two separate evaluations, both on the same 84-question exam and the best configuration.

**RAG evaluation** (does search find the right passage?). Deterministic, no LLM involved: each retrieved chunk is checked against the section of the corpus labeled as the answer.

| Metric | Result | What it means |
|---|---|---|
| hit_rate@10 | **98.8%** (83/84) | the right section is among the 10 chunks retrieved |
| MRR | 0.815 | on average, the first right chunk is at position 1 or 2 |
| recall@10 | 0.689 | share of all labeled sections that were retrieved |
| precision@10 | 0.230 | share of retrieved chunks that are labeled sections |
| tokens per query | 3,327 | context size handed to the model |

**Generation evaluation** (is the final answer correct?). An LLM judge compares each answer with the expected one; the judge is a council of three models from families outside the four being tested, calibrated against my own hand labels.

| Model | Judged correct | Mean score | Abstentions |
|---|---|---|---|
| Claude Sonnet 5 | **83.3%** (70/84) | 0.817 | 1 |
| Claude Haiku 4.5 | 82.1% (69/84) | 0.770 | 1 |
| Qwen 3.5 9B, local | 67.9% (57/84) | 0.620 | 3 |
| Qwen 3.5 4B, local | 57.1% (48/84) | 0.600 | 3 |

Plus the numeric guardrail's acceptance test: it caught 5 of 5 altered safety numbers and let 5 of 5 correct ones through. In total, 77 retrieval runs and 4 generation runs are behind these numbers.

## What it does

A small web page on your machine. You ask a question in Spanish or English, it searches the corpus, writes an answer, and shows the chunks it used. Follow-up questions work: it keeps the last 3 turns and rewrites "and at 30 meters?" into a standalone query before searching. A dev mode shows the retrieved chunks with their scores and lets you switch models and search settings on the fly.

Behind the page: hybrid search (dense plus BM25) over a Chroma index, a cross-encoder reranker, a numeric guardrail that checks every depth, time and rate against the corpus before the answer is shown, and a choice of four models (Claude Sonnet 5, Claude Haiku 4.5, or Qwen 3.5 9B and 4B running locally through MLX). Answers that fail the guardrail twice become an abstention.

## Try it

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com) for the embedding model. A Mac with Apple Silicon is only needed for the local Qwen models; with the API models it runs anywhere.

Put your keys in a `.env` file at the repo root:

| Variable | Used for | Required? |
|---|---|---|
| `ANTHROPIC_API_KEY` | the `sonnet5` and `haiku45` models | yes, to chat with those models |
| `GEMINI_API_KEY` | the condenser (3-turn memory) | yes, for the chat |
| `OPENAI_API_KEY` | the evaluation judge and the `openai3large` embedding | only for experiments |
| `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | one trace per turn in LangSmith | no; without them nothing is sent |

Then:

```bash
git clone https://github.com/adoviguerav/Divefy.git && cd Divefy
uv sync                                                    # dependencies

ollama pull qwen3-embedding:8b-q8_0                        # embedding model (once, ~8 GB)
uv run python -m divefy.pipeline.p4_indexing \
  --corpus combined --extras contextual --embedding qwen8b # build the index (~2 min)

uv run python -m divefy                                    # opens the chat in your browser
```

The first run downloads the reranker (about 2 GB) and loads everything before opening the page. The terminal prints `Modelos cargados. Listo para preguntar.` when it is ready. The corpus ships already processed, so you do not parse the PDF or pay for the enrichment step.

No Ollama? Index with BGE-M3 instead (it downloads itself, about 2 GB) and pick it in dev mode under embedding. It ties the 8B model on hit rate, as the table below shows.

```bash
uv run python -m divefy.pipeline.p4_indexing --corpus combined --extras contextual --embedding bgem3
```

Local models: `qwen9b` and `qwen4b` download from HuggingFace the first time you select them (about 5 GB and 3 GB). With everything loaded, expect around 14 GB of unified memory in use.

## What the exam says

Every setting of the pipeline was measured against the 84 questions: which corpus, chunk size, index extras, embedding model, search type, how many chunks to retrieve, and whether to rerank. The search settings were swept first because they run locally for free. Then each of the four models was run once on the winning search configuration. Each row below changes one setting from that configuration, so it answers one question: does this change help or hurt?

hit_rate is the share of questions whose correct section was among the retrieved chunks. "passed" is the share of answers an LLM judge marked correct; the judge is a council of three models from families outside the four being tested, calibrated against my own hand labels.

<!-- results-table:start -->
Best configuration: `combined-512-contextual-qwen8b-hibrida-k10-rerank`. 84 exam questions; one question is about 1.2 points.

Retrieval, changing one setting at a time from the best configuration:

| setting | value | hit_rate | vs best | recall | MRR | tokens |
|---|---|---|---|---|---|---|
| corpus | apuntes | 0.9643 | -0.0238 | 0.5694 | 0.7998 | 3347 |
| corpus | **combined** (best) | 0.9881 | +0.0000 | 0.6891 | 0.8152 | 3327 |
| cap | **512** (best) | 0.9881 | +0.0000 | 0.6891 | 0.8152 | 3327 |
| extras | base | 0.9881 | +0.0000 | 0.6821 | 0.8148 | 3329 |
| extras | **contextual** (best) | 0.9881 | +0.0000 | 0.6891 | 0.8152 | 3327 |
| extras | hype | 0.9762 | -0.0119 | 0.6910 | 0.8044 | 3304 |
| embedding | bgem3 | 0.9881 | +0.0000 | 0.6710 | 0.8085 | 3426 |
| embedding | openai3large | 0.9524 | -0.0357 | 0.5928 | 0.7999 | 3505 |
| embedding | qwen06b | 0.9643 | -0.0238 | 0.6346 | 0.8077 | 3273 |
| embedding | **qwen8b** (best) | 0.9881 | +0.0000 | 0.6891 | 0.8152 | 3327 |
| search | densa | 0.9524 | -0.0357 | 0.6869 | 0.8180 | 2968 |
| search | **hibrida** (best) | 0.9881 | +0.0000 | 0.6891 | 0.8152 | 3327 |
| k | **10** (best) | 0.9881 | +0.0000 | 0.6891 | 0.8152 | 3327 |
| k | 3 | 0.8690 | -0.1191 | 0.4929 | 0.7897 | 1019 |
| k | 5 | 0.9762 | -0.0119 | 0.6004 | 0.8135 | 1738 |
| rerank | False | 0.9762 | -0.0119 | 0.7146 | 0.7809 | 3230 |
| rerank | **True** (best) | 0.9881 | +0.0000 | 0.6891 | 0.8152 | 3327 |

Generation, each model on the best configuration:

| model | passed | mean score | abstentions | prompt | judge |
|---|---|---|---|---|---|
| sonnet5 | 83.3% (70/84) | 0.817 | 1 | generation_v2 | judge_v3 |
| haiku45 | 82.1% (69/84) | 0.770 | 1 | generation_v2 | judge_v3 |
| qwen9b | 67.9% (57/84) | 0.620 | 3 | generation_v2 | judge_v3 |
| qwen4b | 57.1% (48/84) | 0.600 | 3 | generation_v2 | judge_v3 |
<!-- results-table:end -->

Three things I did not expect:

- The reranker levels almost everything. In dense-only search, the embedding models differed by up to 8 points and the index extras by a couple. With the reranker in front, BGE-M3 ties the 8B Qwen embedding and plain chunks tie contextual ones. Here, most of what the fancier index extras bought in dense search, the reranker gets on its own.
- OpenAI's embedding groups by language. For a Spanish question it almost never surfaces the English manual, so it finishes last here, and it is the only one that needs an API.
- The local 9B model passes two thirds of the exam. That is 15 points behind Sonnet, but the model itself runs on the laptop; only the 3-turn condenser still calls an API. Measuring that gap was the point.

The table is generated from the rows in `results/` (one JSON per run, never overwritten):

```bash
uv run python -m divefy.evals.results_table                # rewrites the table above
uv run python -m divefy.evals.retrieval_evaluator --help   # search: hit_rate@k, recall, MRR
uv run python -m divefy.evals.llm_evaluator --help         # generation: LLM judge and abstention
uv run pytest                                              # full suite, about a minute, no network
```

The exam itself (`data/eval/golden.jsonl`) is never indexed.

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
  evals/             # retrieval_evaluator, llm_evaluator, judge, results_table
  prompts/           # versioned prompts (generation, judge, condenser)
data/raw/            # sources: the Navy manual (PDF) and the PADI notes (markdown)
data/processed/      # parsed corpus, chunks and enrichment (versioned)
data/chroma/         # Chroma collections (built locally, not versioned)
data/eval/           # golden dataset, labels and evaluation caches
data/guardrail/      # the table of safety constants the numeric guardrail checks against
results/             # one row of metrics per configuration
tests/               # unit (scaffolding) and acceptance (frozen per phase)
```

Stack: Python, uv, LangChain, Chroma, Ollama and HuggingFace embeddings, bge-reranker, mlx-lm, Gemini, LangSmith. The web layer is a stdlib HTTP server and one HTML file.

## License

MIT. The US Navy Diving Manual is in the public domain. The PADI notes are my own, paraphrased.
