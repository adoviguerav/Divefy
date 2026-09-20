"""Fase 7 — transporte puro: los 4 modelos del experimento tras una firma única.

`p7_generate` llama a `generate(model, system, user)` sin saber qué backend hay
detrás (decisión 1 del plan de F7). El juez de evals NO pasa por aquí: es fijo y
fuera de la ablación (decisión 12) — vive en `evals/judge.py`.

Backend API vía langchain-anthropic (decisión del plan, confirmada por Adolfo
2026-09-07): coherente con el stack LangChain del PRD y con trazado automático
en LangSmith al llegar F8.
"""

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# IDs confirmados contra la referencia vigente de la API (2026-09-07) — exactos,
# sin sufijos de fecha. Los Qwen llegan con el backend mlx (T-06, gated al repaso
# de teoría de IA local).
API_MODELS = {
    "sonnet5": "claude-sonnet-5",
    "haiku45": "claude-haiku-4-5",
}
# Builds de texto 4-bit de mlx-community (T-06, verificados en HF 2026-09-17);
# los "-MLX-4bit" son conversiones mlx-vlm (visión) — estos "-4bit" cargan con mlx-lm.
MLX_MODELS = {
    "qwen9b": "mlx-community/Qwen3.5-9B-4bit",
    "qwen4b": "mlx-community/Qwen3.5-4B-4bit",
}

MAX_TOKENS = 4096  # holgado: en Sonnet 5 el thinking adaptativo cuenta contra este tope

# Clientes perezosos por id de modelo (patrón de p3_enrich): se construyen en la
# primera llamada real, nunca al importar — los tests inyectan fakes aquí y no
# necesitan API key.
_clientes: dict[str, ChatAnthropic] = {}


def _cliente(model_id: str) -> ChatAnthropic:
    if model_id not in _clientes:
        load_dotenv()
        _clientes[model_id] = ChatAnthropic(model=model_id, max_tokens=MAX_TOKENS)
    return _clientes[model_id]


def _solo_texto(content) -> str:
    """LangChain devuelve str, o lista de bloques cuando hay thinking (Sonnet 5
    adaptativo): de la lista solo cuentan los bloques de texto, en orden."""
    if isinstance(content, str):
        return content
    return "".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


# Backend MLX (T-06): modelo+tokenizer perezosos por clave.
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
    import re

    from mlx_lm import generate as mlx_generate

    modelo, tokenizer = _mlx_load(model)
    tokens = _chat_tokens(
        tokenizer,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    # ponytail: sin caché KV del system prompt — la plantilla de chat de Qwen
    # exige un mensaje de usuario para renderizar, así que no se puede aislar
    # el prefijo del system sin arriesgar un recorte de tokens mal alineado
    # (bug silencioso en las respuestas). Añadir cuando 84 generaciones
    # seguidas midan lento de verdad — hoy no hay dato que lo pida.
    texto = mlx_generate(modelo, tokenizer, prompt=tokens, max_tokens=MAX_TOKENS)

    # Defensivo: si la plantilla ignoró enable_thinking, fuera el bloque <think>.
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()


def generate(model: str, system: str, user: str) -> str:
    """Una firma para los 4 modelos. `model` es la clave del experimento
    (sonnet5/haiku45/qwen9b/qwen4b), no el id del proveedor."""
    if model in API_MODELS:
        respuesta = _cliente(API_MODELS[model]).invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return _solo_texto(respuesta.content)
    if model in MLX_MODELS:
        return _generate_mlx(model, system, user)
    raise ValueError(
        f"modelo desconocido {model!r}; válidos: {sorted(API_MODELS) + sorted(MLX_MODELS)}"
    )
