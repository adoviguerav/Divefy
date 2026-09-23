"""Fase 8 — API local del chat: stdlib, un usuario, sin estado.

Endpoints:
  GET  /             la página (static/index.html)
  GET  /api/options  valores para los desplegables (modelos y diales de retrieval)
  POST /api/chat     un mensaje: {pregunta, historial, model, config} ->
                     {respuesta, abstencion, historial, chunks}

La memoria (historial) vive en el navegador y viaja en cada petición; la API solo
valida, llama a `chat.run_turn_full` y serializa.
"""

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import divefy.chat as chat
import divefy.llm as llm
from divefy import config as cfg

logger = logging.getLogger(__name__)

INDEX_PATH = Path(__file__).resolve().parent / "static" / "index.html"

OPTIONS = {
    "models": sorted(llm.API_MODELS) + sorted(llm.MLX_MODELS),
    "corpus": list(cfg.CORPUS_VALUES),
    "extras": list(cfg.EXTRAS_VALUES),
    "embedding": list(cfg.EMBEDDING_VALUES),
    "search": list(cfg.SEARCH_VALUES),
    "k": list(cfg.K_VALUES),
    "rerank": [True, False],
    # Preguntas de ejemplo para la pantalla vacía (frescas, no del golden).
    "ejemplos": [
        "¿A qué profundidad y cuánto tiempo se hace la parada de seguridad?",
        "¿Qué hago si no consigo compensar los oídos al bajar?",
        "¿A qué velocidad máxima debo ascender?",
        "¿Qué pasos sigo si mi compañero se queda sin aire?",
    ],
    "default": {
        "model": chat.DEFAULT_MODEL,
        "corpus": cfg.RECETA_GANADORA.corpus,
        "extras": cfg.RECETA_GANADORA.extras,
        "embedding": cfg.RECETA_GANADORA.embedding,
        "search": cfg.RECETA_GANADORA.search,
        "k": cfg.RECETA_GANADORA.k,
        "rerank": cfg.RECETA_GANADORA.rerank,
    },
}


class BadRequest(ValueError):
    pass


def _parse_model(body: dict, required: bool) -> str:
    model = body.get("model")
    if model is None and not required:
        model = chat.DEFAULT_MODEL
    if model not in OPTIONS["models"]:
        raise BadRequest(f"modelo desconocido {model!r}")
    return model


def _parse_config(body: dict) -> cfg.RetrievalConfig:
    config_raw = body.get("config")
    if config_raw is None:
        return cfg.RECETA_GANADORA
    if not isinstance(config_raw, dict):
        raise BadRequest("'config' debe ser un objeto")
    try:
        return cfg.RetrievalConfig(
            corpus=config_raw["corpus"], extras=config_raw["extras"],
            embedding=config_raw["embedding"], search=config_raw["search"],
            k=int(config_raw["k"]), rerank=bool(config_raw["rerank"]),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise BadRequest(f"config inválida: {e}") from e


def _parse_chat_request(body: dict) -> tuple[list[tuple[str, str]], str, str, cfg.RetrievalConfig]:
    """Valida el body del POST /api/chat (frontera de confianza: viene del navegador)."""
    pregunta = body.get("pregunta")
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise BadRequest("falta 'pregunta' o no es texto")
    historial_raw = body.get("historial", [])
    if not isinstance(historial_raw, list) or not all(
        isinstance(par, (list, tuple)) and len(par) == 2 and all(isinstance(x, str) for x in par)
        for par in historial_raw
    ):
        raise BadRequest("'historial' debe ser una lista de pares [pregunta, respuesta]")
    historial = [(q, a) for q, a in historial_raw]
    return historial, _parse_model(body, required=False), pregunta.strip(), _parse_config(body)


class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.debug("%s " + fmt, self.address_string(), *args)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/":
            self._send(HTTPStatus.OK, INDEX_PATH.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/options":
            self._json(HTTPStatus.OK, OPTIONS)
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "no existe"})

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"")
        if not isinstance(body, dict):
            raise BadRequest("el body debe ser un objeto JSON")
        return body

    def do_POST(self):
        routes = {"/api/chat": self._post_chat, "/api/warmup": self._post_warmup}
        handler = routes.get(self.path)
        if handler is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "no existe"})
            return
        try:
            body = self._read_json_body()
            handler(body)
        except (BadRequest, json.JSONDecodeError) as e:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
        except Exception as e:  # el error del pipeline se enseña en la página, no se traga
            logger.exception("petición fallida")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(e).__name__}: {e}"})

    def _post_chat(self, body: dict) -> None:
        historial, model, pregunta, config = _parse_chat_request(body)
        # Atributo resuelto en cada llamada (no `from ... import`): los tests
        # sustituyen chat.run_turn_full por un fake. Bajo el lock: si hay una
        # precarga en marcha, la pregunta espera a que termine.
        with chat.LOCK:
            resultado, nuevo_historial = chat.run_turn_full(historial, model, pregunta, config)
        self._json(HTTPStatus.OK, {
            "respuesta": resultado.respuesta,
            "abstencion": resultado.abstencion,
            "historial": nuevo_historial,
            "chunks": list(resultado.chunks),
        })

    def _post_warmup(self, body: dict) -> None:
        model = _parse_model(body, required=True)
        config = _parse_config(body)
        chat.warm_up(model, config)
        self._json(HTTPStatus.OK, {"ok": True})


def make_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ApiHandler)
