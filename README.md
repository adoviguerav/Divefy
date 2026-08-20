# Divefy

Copiloto de buceo con IA: un chat que responde dudas de seguridad en buceo (ES/EN) apoyándose **solo** en un corpus verificado, construido sobre un banco de experimentos que mide cada pieza del RAG.

## Qué es

Dos cosas a la vez:

1. **Un chat conversacional** (CLI con estética de ordenador de buceo) que responde desde el US Navy Diving Manual Rev 7 y mis apuntes del Open Water PADI — con cita de fuente, números de seguridad textuales verificados dígito a dígito, y abstención explícita cuando el corpus no cubre la pregunta.
2. **Un banco de experimentos** que compara técnicas de RAG (híbrida, contextual retrieval, HyPE, rerank…), modelos (Sonnet 5, Haiku 4.5, Qwen 3.5 9B/4B local) y corpus contra un examen propio de preguntas del curso PADI. El resultado es una tabla: qué configuración responde mejor, a qué latencia y a qué coste — y si un modelo local pequeño alcanza a los de API.

## Stack

Python + uv · LangChain · Chroma · BGE-M3 · mlx-lm (Apple Silicon) · LangSmith · Textual

## Estructura

```
src/divefy/       # un módulo por fase del pipeline RAG + el corrector (evals)
data/raw/         # fuentes: manual Navy (PDF) + apuntes PADI (markdown)
data/processed/   # salida de la ingesta (regenerable)
data/eval/        # etiquetas y cachés de evaluación
results/          # una fila de métricas por configuración
docs/             # golden dataset, documento de idea, limitaciones de hardware
```

## Quick start

```bash
uv sync          # instala dependencias
uv run pytest    # corre los tests
```

(Los comandos de ingesta, indexado, corrector y chat se añaden aquí según se implementan las fases.)

## Estado

Plan cerrado (9 fases: ingesta → chunking → extras de índice → embeddings → retrieval → rerank → generación → chat → grid). Implementación empezando por la Fase 1: bake-off de parsers sobre el manual.

## Documentación interna

- `CLAUDE.md` — contexto del proyecto para Claude Code (reglas inmutables, glosario).
- Plan y cuaderno de experimentos: locales en `.claude/plans/` (no versionados).
