"""Unit — llm/ (transporte): dispatch por modelo, mapeo de ids y contrato de salida.

Todo con fakes inyectados en la caché de clientes perezosos — cero red, cero API key.
"""

from types import SimpleNamespace

import pytest


def _fake_client(captured, content):
    """ChatAnthropic falso: apunta los mensajes que recibe y devuelve `content` fijo."""

    def invoke(messages):
        captured["messages"] = messages
        return SimpleNamespace(content=content)

    return SimpleNamespace(invoke=invoke)


def test_generate_passes_prompts_and_maps_model_id(monkeypatch):
    import divefy.llm as llm

    captured = {}
    blocks = [
        {"type": "thinking", "thinking": "…"},
        {"type": "text", "text": "hola "},
        {"type": "text", "text": "mundo"},
    ]
    # La clave del fake ES el id mapeado: si el mapeo fallara, generate() no lo
    # encontraría y el test moriría intentando construir un cliente real sin key.
    monkeypatch.setitem(llm._clientes, "claude-sonnet-5", _fake_client(captured, blocks))

    out = llm.generate("sonnet5", "eres un copiloto", "¿profundidad máxima?")

    assert out == "hola mundo", "solo los bloques de texto, concatenados en orden"
    system, user = captured["messages"]
    assert system.content == "eres un copiloto"
    assert user.content == "¿profundidad máxima?"


def test_haiku_maps_its_own_id_and_plain_string_content(monkeypatch):
    import divefy.llm as llm

    captured = {}
    monkeypatch.setitem(llm._clientes, "claude-haiku-4-5", _fake_client(captured, "ok"))

    assert llm.generate("haiku45", "s", "u") == "ok"


def test_mlx_models_route_to_local_backend(monkeypatch):
    # T-06: las claves qwen* van al backend MLX con la MISMA firma que el de
    # API. Fake en la costura _generate_mlx: cero descarga, cero GPU.
    import divefy.llm as llm

    llamadas = []
    monkeypatch.setattr(
        llm, "_generate_mlx",
        lambda model, system, user: llamadas.append((model, system, user)) or "local",
    )
    assert llm.generate("qwen9b", "s", "u") == "local"
    assert llm.generate("qwen4b", "s", "u") == "local"
    assert llamadas == [("qwen9b", "s", "u"), ("qwen4b", "s", "u")]


def test_unknown_model_raises_value_error():
    import divefy.llm as llm

    with pytest.raises(ValueError, match="gpt5"):
        llm.generate("gpt5", "s", "u")


def test_import_does_not_build_a_real_client():
    import divefy.llm as llm

    # Los clientes son perezosos: importar el módulo no construye ninguno (ni
    # exige API key). Los fakes de arriba entran por monkeypatch.setitem, así
    # que fuera de esos tests la caché debe seguir sin clientes reales.
    assert all(isinstance(c, SimpleNamespace) or c is None for c in llm._clientes.values())
