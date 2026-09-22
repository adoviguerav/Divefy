"""Backend local (T-06) vía mlx-lm: modelos 4-bit de mlx-community corriendo
en el propio Mac, sin llamada de red.
"""

import re

from .api import MAX_TOKENS

# Builds de texto 4-bit de mlx-community (T-06, verificados en HF 2026-09-17);
# los "-MLX-4bit" son conversiones mlx-vlm (visión) — estos "-4bit" cargan con mlx-lm.
MLX_MODELS = {
    "qwen9b": "mlx-community/Qwen3.5-9B-4bit",
    "qwen4b": "mlx-community/Qwen3.5-4B-4bit",
}

# Modelo+tokenizer perezosos por clave.
_mlx_backends: dict[str, tuple] = {}


def _mlx_load(model: str):
    if model not in _mlx_backends:
        from mlx_lm import load

        _mlx_backends[model] = load(MLX_MODELS[model])
    return _mlx_backends[model]


def _chat_tokens(tokenizer, mensajes: list[dict]) -> list[int]:
    """Tokens del template de chat, con el thinking de Qwen apagado (queremos
    la respuesta directa; el except cubre plantillas sin ese kwarg)."""
    try:
        return tokenizer.apply_chat_template(
            mensajes, add_generation_prompt=True, enable_thinking=False
        )
    except TypeError:
        return tokenizer.apply_chat_template(mensajes, add_generation_prompt=True)


def _generate_mlx(model: str, system: str, user: str) -> str:
    from mlx_lm import generate as mlx_generate

    modelo, tokenizer = _mlx_load(model)
    tokens = _chat_tokens(
        tokenizer,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    texto = mlx_generate(modelo, tokenizer, prompt=tokens, max_tokens=MAX_TOKENS)

    # Defensivo: si la plantilla ignoró enable_thinking, fuera el bloque <think>.
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------
# Caché KV del system prompt — investigado y funcionando, no activado.
#
# Se implementó (clonar una caché ya calentada con el system, una copia
# desechable por pregunta, en vez de reutilizar-y-recortar: ArraysCache, la
# que usa Qwen3.5, no soporta recortar). Verificado correcto: texto idéntico
# a generar sin caché para respuestas cortas; para respuestas largas puede
# no ser bit a bit idéntico por reordenar operaciones de coma flotante entre
# prefijo+resto — fenómeno normal de cualquier caché de prefijos en IA, no
# un fallo. Medido con el prompt real: ahorro de solo ~2% (20.5s vs 21.0s en
# 8 preguntas), porque el cuello de botella es generar la respuesta (decode,
# secuencial, ninguna caché lo toca), no procesar el prompt (prefill, ya
# rápido) — y el contexto del RAG, que sí pesa mucho, cambia en cada
# pregunta y no se puede cachear. No compensa el código extra ni el ruido de
# no-determinismo para este pipeline. Explicado con código completo en
# docs/conocimiento.md ("Caché KV en MLX").
#
# import mlx.core as mx
# from mlx_lm.generate import generate_step
# from mlx_lm.models.cache import make_prompt_cache
#
# def _prefix_tokens(tokenizer, system): ...   # aísla el prefijo sin tokenizar
#                                                # el system solo (la plantilla
#                                                # exige un turno de usuario)
# def _prime_cache(modelo, prefijo): ...        # generate_step(max_tokens=0)
# def _clone_cache(modelo, cache_base): ...     # copia superficial del .state
# ---------------------------------------------------------------------------
