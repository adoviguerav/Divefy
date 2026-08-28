# Divefy

Copiloto conversacional de seguridad en buceo: un chat (CLI) que responde en ES/EN apoyándose solo en un corpus verificado (US Navy Diving Manual Rev 7 + apuntes PADI propios), construido sobre un banco de experimentos que mide cada pieza del RAG y cada modelo contra un examen propio.

## Función core

Chat RAG con grounding estricto + banco de experimentos que compara técnicas × modelos × corpus para encontrar la config de máxima calidad (y ver si un modelo local pequeño alcanza a los de API).

## Stack

- Python ≥3.12 con **uv** (`uv sync`, `uv run pytest`).
- LangChain como librería (sin LangGraph). Chroma como vectorstore (embebido, colección por config).
- Modelos locales vía **mlx-lm** (Mac Apple Silicon); API vía SDK. Modelos del grid: Sonnet 5, Haiku 4.5, Qwen 3.5 9B/4B.
- Embeddings: BGE-M3 (base) vs Qwen3-Embedding-0.6B (medido). Reranker: bge-reranker-v2-m3.
- Enriquecedor de índice: Gemini Flash. Juez de evals: un GPT. Ambos fuera de la ablación.
- Observabilidad: LangSmith. Chat: Textual.

## Estructura

```
src/divefy/
  config.py          # config de experimento, global
  chat.py            # Fase 8 — entrypoint CLI (Textual)
  pipeline/          # un módulo por fase, prefijo pN_ para que el orden se vea en `ls`:
                     # p1_ingest → p2_chunking → p3_enrich → p4_indexing/p4_vectorstore →
                     # p5_retrieve → p6_rerank → p7_generate/p7_guardrail
  evals/             # corrector.py — banco de experimentos (config -> fila de métricas)
  llm/               # Fase 7 — proveedores API + modelos locales (mlx-lm) tras una
                     # interfaz única que p7_generate.py llama sin saber cuál es cuál;
                     # vacío hasta tener el segundo backend real
data/raw/            # fuentes: navy-diving-manual-rev7.pdf + PADI_course/ (apuntes, NO regenerables)
data/processed/      # salida de ingesta (regenerable)
data/eval/           # golden dataset (el examen), etiquetas y cachés del eval
results/             # una fila de métricas por config, nunca se sobreescriben
docs/                # idea original, limitaciones hardware, modelo de datos
.claude/plans/       # PRD.md y EXPERIMENTOS.md (locales, gitignored)
```

## Reglas inmutables

1. **El golden dataset NUNCA se indexa** (`data/eval/golden.jsonl`): es el examen. El corrector usa solo `uso=eval` (84 preguntas).
2. **PADI manda** en conflictos doctrinales con el manual Navy; se citan ambos cuando difieren.
3. **Números de seguridad textuales del corpus, jamás traducidos ni parafraseados**; todo número emitido pasa el guardarraíl determinista o se convierte en abstención.
4. **Sin soporte en el corpus → abstención plantilla**, nunca generación sin grounding.
5. Las decisiones de diseño pasan por Adolfo antes de escribirse; el PRD refleja lo decidido, no propuestas.
6. Los brazos del grid ya están cerrados en `.claude/plans/EXPERIMENTOS.md` — no añadir técnicas nuevas sin dato que lo justifique (los descartes tienen motivo escrito).

## Glosario

- **Golden**: las 186 Q-A del curso PADI (84 eval / 102 repaso). Examen, no corpus.
- **El corrector**: script de evals; una config → una fila de métricas versionada.
- **Receta**: combinación corpus + tope + extras + embedding + búsqueda (+rerank). La colección Chroma lleva su nombre canónico `corpus-tope-extras-embedding`.
- **Fija-y-barre**: barrer una dimensión cada vez desde la receta base; nunca el cruce completo.
- **section_id**: identificador estable de sección (`9-3.2`, `fichero#sección`) — las etiquetas del eval y el recall@k dependen de él.

## Referencias

- `docs/modelo-datos.md` — contrato de datos del pipeline: entidades, esquema de la fila de Chroma, invariantes. Los JSONL son el system of record; cada colección es vista materializada regenerable.
- `.claude/plans/PRD.md` — el plan completo, §7 con las 9 fases cerradas (orden de decisión = orden de implementación).
- `.claude/plans/EXPERIMENTOS.md` — cuaderno de laboratorio: base, variantes, resultados, descartes con motivo.
- Reglas universales (testing, security, git…) en `~/.claude/rules/`, cargadas por el CLAUDE.md global.
