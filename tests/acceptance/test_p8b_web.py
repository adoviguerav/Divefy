"""Acceptance tests for Fase 8b — API del chat web (divefy.api) sobre divefy.chat.

These tests are written BEFORE the implementation. On first run they must fail
RED with ImportError/AttributeError raised INSIDE the tests/fixtures — hence
every `divefy.*` import lives inside a test function or fixture, never at
module level.

HTTP se hace con stdlib (`http.client`), que no lanza en 400 y nos deja leer
el cuerpo de error con calma.
"""
import http.client
import json
import threading
from urllib.parse import urlparse

import pytest

PREGUNTA = "¿A qué profundidad se hace la parada de seguridad?"
RESPUESTA = "Haz una parada de seguridad de 3 min a 5 m."
CHUNK = {
    "id": "apuntes-owd#parada-3",
    "texto": "Haz una parada de seguridad de 3 min a 5 m.",
    "metadata": {"corpus": "apuntes", "titulo": "Parada de seguridad"},
}
RUN_ID_GANADORA = "combined-512-contextual-qwen8b-hibrida-k10-rerank"
MODELOS = {"sonnet5", "haiku45", "qwen9b", "qwen4b"}


class _FakeAnswer:
    """Paquete mínimo con la misma forma que el Answer real de p7_generate."""

    def __init__(self, pregunta, respuesta, chunks=(CHUNK,), abstencion=False):
        self.pregunta = pregunta
        self.respuesta = respuesta
        self.chunks = tuple(chunks)
        self.abstencion = abstencion


def _patch_run_turn_full(monkeypatch, respuesta=RESPUESTA):
    """Sustituye divefy.chat.run_turn_full por un muñeco y devuelve sus llamadas."""
    import divefy.chat as chat

    calls = []

    def fake(historial, model, pregunta, config=None):
        calls.append(
            {"historial": historial, "model": model, "pregunta": pregunta, "config": config}
        )
        answer = _FakeAnswer(pregunta, respuesta)
        return answer, list(historial) + [(pregunta, respuesta)]

    monkeypatch.setattr(chat, "run_turn_full", fake)
    return calls


@pytest.fixture(scope="module")
def base_url():
    """Levanta el servidor web en un puerto libre y lo apaga al terminar el módulo."""
    from divefy.api import make_server

    server = make_server(port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()


def _request(base_url, method, path, body=None, raw=None):
    """Devuelve (status, headers, cuerpo_bytes). `raw` manda texto tal cual."""
    parsed = urlparse(base_url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=10)
    try:
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


def _post_json(base_url, path, body=None, raw=None):
    status, _headers, data = _request(base_url, "POST", path, body=body, raw=raw)
    return status, json.loads(data)


def _pairs(historial):
    """Normaliza un historial a lista de listas para comparar tuplas y listas por igual."""
    return [list(par) for par in historial]


class TestPagina:
    def test_get_raiz_sirve_la_pagina(self, base_url):
        """GET / debe devolver la página HTML con lo mínimo para chatear: un sitio
        donde escribir la pregunta, un botón de enviar y otro de nueva conversación."""
        status, headers, data = _request(base_url, "GET", "/")
        assert status == 200, f"GET / devolvió {status}; sin página no hay chat"
        content_type = {k.lower(): v for k, v in headers.items()}.get("content-type", "")
        assert content_type.startswith("text/html"), (
            f"Content-Type {content_type!r}; el navegador no la pintará como página"
        )
        html = data.decode("utf-8", errors="replace").lower()
        assert "<textarea" in html or "<input" in html, (
            "no hay campo donde escribir la pregunta"
        )
        assert "enviar" in html, "falta el botón de enviar"
        assert "nueva conversaci" in html, "falta el botón de nueva conversación"


class TestTurno:
    def test_post_turn_devuelve_respuesta_historial_y_chunks(self, base_url, monkeypatch):
        """El test central: un POST /turn con historial vacío pasa por run_turn_full
        UNA vez y devuelve respuesta, historial actualizado y los chunks usados,
        que es lo que la página necesita para mostrar la fuente de cada respuesta."""
        calls = _patch_run_turn_full(monkeypatch)
        status, body = _post_json(
            base_url, "/api/chat", {"pregunta": PREGUNTA, "historial": [], "model": "haiku45"}
        )
        assert status == 200, f"POST /turn devolvió {status}: {body}"
        assert len(calls) == 1, "one question => exactly one run_turn_full call"
        assert calls[0]["model"] == "haiku45", "el modelo elegido no llegó al chat"
        assert calls[0]["pregunta"] == PREGUNTA, "la pregunta no llegó intacta"
        assert body["respuesta"] == RESPUESTA, "la respuesta no es la del modelo"
        assert body["historial"] == [[PREGUNTA, RESPUESTA]], (
            "el historial devuelto no es [[pregunta, respuesta]]"
        )
        assert body["chunks"] == [CHUNK], "los chunks devueltos no son los de la respuesta"

    def test_historial_viaja_de_ida_y_vuelta(self, base_url, monkeypatch):
        """El servidor no guarda estado: el historial que manda la página es el que
        recibe run_turn_full, y vuelve con el turno nuevo añadido."""
        calls = _patch_run_turn_full(monkeypatch)
        status, body = _post_json(
            base_url,
            "/api/chat",
            {"pregunta": PREGUNTA, "historial": [["q1", "a1"]], "model": "haiku45"},
        )
        assert status == 200, f"POST /turn devolvió {status}: {body}"
        assert len(calls) == 1, "one question => exactly one run_turn_full call"
        assert _pairs(calls[0]["historial"]) == [["q1", "a1"]], (
            "run_turn_full no recibió el historial que mandó la página"
        )
        assert _pairs(body["historial"]) == [["q1", "a1"], [PREGUNTA, RESPUESTA]], (
            "el historial devuelto debe ser el recibido más el turno nuevo"
        )


class TestConfig:
    def test_config_llega_a_run_turn(self, base_url, monkeypatch):
        """Los diales de la página (corpus, extras, embedding, búsqueda, k, rerank)
        se convierten en un RetrievalConfig y llegan a run_turn_full; sin diales,
        se usa la receta ganadora."""
        from divefy.config import RetrievalConfig

        calls = _patch_run_turn_full(monkeypatch)
        config = {
            "corpus": "apuntes",
            "extras": "base",
            "embedding": "bgem3",
            "search": "densa",
            "k": 5,
            "rerank": False,
        }
        status, body = _post_json(
            base_url,
            "/api/chat",
            {"pregunta": PREGUNTA, "historial": [], "model": "qwen4b", "config": config},
        )
        assert status == 200, f"POST /turn con config devolvió {status}: {body}"
        recibido = calls[0]["config"]
        assert isinstance(recibido, RetrievalConfig), (
            f"config llegó como {type(recibido).__name__}, no como RetrievalConfig"
        )
        for campo, valor in config.items():
            assert getattr(recibido, campo) == valor, (
                f"config.{campo}={getattr(recibido, campo)!r}, esperado {valor!r}"
            )

        status, body = _post_json(
            base_url, "/api/chat", {"pregunta": PREGUNTA, "historial": [], "model": "qwen4b"}
        )
        assert status == 200, f"POST /turn sin config devolvió {status}: {body}"
        assert len(calls) == 2, "two questions => two run_turn_full calls"
        assert calls[1]["config"].run_id == RUN_ID_GANADORA, (
            "sin config la página debe usar la receta ganadora"
        )


class TestValidacion:
    def test_body_invalido_400_sin_llamar(self, base_url, monkeypatch):
        """Cuerpos rotos o sin pregunta válida se rechazan con 400 y un error en
        JSON, sin tocar el modelo: no se gasta un turno de LLM en basura."""
        calls = _patch_run_turn_full(monkeypatch)
        casos = [
            ("sin pregunta", {"body": {"historial": [], "model": "haiku45"}}),
            ("pregunta no string", {"body": {"pregunta": 42, "historial": [], "model": "haiku45"}}),
            ("JSON roto", {"raw": b"{esto no es json"}),
        ]
        for nombre, kwargs in casos:
            status, body = _post_json(base_url, "/api/chat", **kwargs)
            assert status == 400, f"caso {nombre!r}: devolvió {status}, esperado 400"
            assert "error" in body, f"caso {nombre!r}: la respuesta no explica el error"
        assert calls == [], "un cuerpo inválido no debe llegar a run_turn_full"


class TestOpciones:
    def test_options_lista_modelos_y_diales(self, base_url):
        """GET /options alimenta los desplegables de la página: modelos y todos los
        valores posibles de cada dial del retrieval."""
        status, _headers, data = _request(base_url, "GET", "/api/options")
        assert status == 200, f"GET /options devolvió {status}"
        body = json.loads(data)
        esperado = {
            "models": MODELOS,
            "corpus": {"apuntes", "manual", "combined"},
            "extras": {"base", "contextual", "hype"},
            "embedding": {"bgem3", "qwen06b", "qwen8b", "openai3large"},
            "search": {"densa", "hibrida"},
            "k": {3, 5, 10},
            "rerank": {True, False},
        }
        for clave, valores in esperado.items():
            assert valores <= set(body.get(clave, [])), (
                f"options.{clave} = {body.get(clave)!r}; faltan {valores - set(body.get(clave, []))}"
            )


class TestTracing:
    def test_traceable_sin_clave_es_noop(self, monkeypatch):
        """run_turn_full va decorado con @traceable de LangSmith; sin variables de
        tracing el decorador no hace nada y run_turn funciona igual, sin red."""
        for var in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_API_KEY"):
            monkeypatch.delenv(var, raising=False)

        import divefy.chat as chat
        from divefy.pipeline import p7_generate, p8_condense

        assert getattr(chat.run_turn_full, "__langsmith_traceable__", False), (
            "run_turn_full no está decorado con @traceable"
        )

        def fake_condense(*args, **kwargs):
            return PREGUNTA

        def fake_answer(config, model, pregunta, *args, **kwargs):
            return _FakeAnswer(pregunta, RESPUESTA)

        monkeypatch.setattr(p8_condense, "condense", fake_condense)
        monkeypatch.setattr(p7_generate, "answer", fake_answer)

        respuesta, historial = chat.run_turn([], "haiku45", PREGUNTA)
        assert respuesta == RESPUESTA, "run_turn no devolvió la respuesta del modelo"
        assert _pairs(historial) == [[PREGUNTA, RESPUESTA]], (
            "run_turn no añadió el turno al historial"
        )
