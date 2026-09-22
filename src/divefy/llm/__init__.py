"""Fase 7 — transporte puro: los 4 modelos del experimento tras una firma única.

`p7_generate` llama a `generate(model, system, user)` sin saber qué backend hay
detrás (decisión 1 del plan de F7). El juez de evals NO pasa por aquí: es fijo y
fuera de la ablación (decisión 12) — vive en `evals/judge.py`.

Un backend por fichero (`api.py`, `mlx_backend.py`): dos responsabilidades bien
distintas (llamar a una API vs cargar pesos y generar en local) que ya no cabían
cómodas juntas. `_clientes` y `_generate_mlx` se re-exportan aquí a propósito:
los tests los sustituyen por fakes a través de `divefy.llm` (`monkeypatch.setitem`/
`setattr`), y para que eso funcione `generate()` tiene que resolver esos nombres
en el propio espacio de nombres de este módulo, no en el de los submódulos.
"""

from .api import API_MODELS, MAX_TOKENS, _clientes, generate_api
from .mlx_backend import MLX_MODELS, _generate_mlx

__all__ = ["API_MODELS", "MLX_MODELS", "MAX_TOKENS", "generate"]


def generate(model: str, system: str, user: str) -> str:
    """Una firma para los 4 modelos. `model` es la clave del experimento
    (sonnet5/haiku45/qwen9b/qwen4b), no el id del proveedor."""
    if model in API_MODELS:
        return generate_api(API_MODELS[model], system, user)
    if model in MLX_MODELS:
        return _generate_mlx(model, system, user)
    raise ValueError(
        f"modelo desconocido {model!r}; válidos: {sorted(API_MODELS) + sorted(MLX_MODELS)}"
    )
