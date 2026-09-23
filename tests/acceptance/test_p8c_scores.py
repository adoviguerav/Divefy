"""Aceptación Fase 8c — precarga, scores por chunk y escritura progresiva.

Todo import de `divefy.*` va dentro de los cuerpos para que el fallo (ImportError /
AttributeError) salte en RED dentro de cada test y no al recoger el módulo.
"""

import http.client
import json
import threading
from urllib.parse import urlparse

import pytest


# ---------------------------------------------------------------- helpers ----


def _post(base_url, path, body):
    """POST crudo con http.client. `body` puede ser dict (se serializa) o bytes."""
    parsed = urlparse(base_url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=10)
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    conn.request("POST", path, body=raw, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


def _get(base_url, path):
    parsed = urlparse(base_url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=10)
    conn.request("GET", path)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, data


@pytest.fixture
def server():
    """Levanta `make_server(port=0)` en un hilo daemon y devuelve la URL base."""
    from divefy.api import make_server

    srv = make_server(port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    host, port = srv.server_address[:2]
    yield f"http://{host}:{port}"
    srv.shutdown()
    srv.server_close()


# ---------------------------------------------------------- criterio 1 -------


class TestRerankScored:
    def test_scored_y_wrapper_coinciden(self, monkeypatch):
        """rerank_scored devuelve los k mejores (id, score) ordenados por score
        descendente, y el wrapper rerank() sigue devolviendo exactamente esos ids en
        el mismo orden: una sola fuente de verdad para el ranking."""
        from divefy.pipeline import p6_rerank

        class FakeModel:
            def predict(self, pairs, batch_size=8):
                return [float(len(text)) for (_q, text) in pairs]

        monkeypatch.setattr(p6_rerank, "_model", lambda: FakeModel())

        candidates = [("a", "xx"), ("b", "xxxxxx"), ("c", "xxxx"), ("d", "x")]
        scored = p6_rerank.rerank_scored("q", candidates, 3)

        assert len(scored) == 3, f"rerank_scored debe devolver k=3 pares, devolvió {scored}"
        assert [cid for cid, _ in scored] == ["b", "c", "a"], (
            f"orden de ids incorrecto (esperado b,c,a por score desc): {scored}"
        )
        assert [s for _, s in scored] == [6.0, 4.0, 2.0], (
            f"scores no coinciden con los del cross-encoder: {scored}"
        )
        assert p6_rerank.rerank("q", candidates, 3) == ["b", "c", "a"], (
            "rerank() debe devolver los mismos ids que rerank_scored()"
        )


# ---------------------------------------------------------- criterio 2 -------


class TestRrfScored:
    def test_score_rrf_a_mano(self):
        """rrf_fuse_scored calcula Σ 1/(k_rrf + rank) con rank 1-based, empata por id
        ascendente, y rrf_fuse() devuelve la misma lista de ids: el score expuesto es el
        mismo que se usa para ordenar."""
        from divefy.pipeline import p5_retrieve

        rankings = [["a", "b", "c"], ["b", "a", "d"]]
        expected = [
            ("a", 1 / 61 + 1 / 62),
            ("b", 1 / 62 + 1 / 61),
            ("c", 1 / 63),
            ("d", 1 / 63),
        ]

        scored = p5_retrieve.rrf_fuse_scored(rankings, k_rrf=60)

        assert [cid for cid, _ in scored] == [cid for cid, _ in expected], (
            f"orden de ids RRF incorrecto (empates por id asc): {scored}"
        )
        for (cid, got), (_, want) in zip(scored, expected):
            assert got == pytest.approx(want), f"score RRF de {cid}: {got} != {want}"
        assert p5_retrieve.rrf_fuse(rankings) == [cid for cid, _ in expected], (
            "rrf_fuse() debe devolver los mismos ids que rrf_fuse_scored()"
        )


# ---------------------------------------------------------- criterio 3 -------


class TestAnswerScores:
    def test_chunks_llevan_score_y_tipo(self, monkeypatch):
        """answer() propaga a cada chunk el score que devolvió retrieve_scored y etiqueta
        su tipo con score_kind(config): rerank si hay reranker, rrf si híbrida sin
        rerank, distancia si densa."""
        import divefy.llm as llm
        from divefy.config import RetrievalConfig
        from divefy.pipeline import p4_vectorstore, p5_retrieve, p7_generate

        config = RetrievalConfig("combined", "contextual", "bgem3", "hibrida", 5, rerank=True)

        monkeypatch.setattr(
            p5_retrieve, "retrieve_scored", lambda cfg, q, query_vector=None: [("c1", 0.9), ("c2", 0.4)]
        )

        class FakeCollection:
            def get(self, ids=None, **kw):
                return {
                    "ids": ["c1", "c2"],
                    "documents": ["texto uno", "texto dos"],
                    "metadatas": [
                        {"corpus": "apuntes", "titulo": "T1"},
                        {"corpus": "manual", "titulo": "T2"},
                    ],
                }

        monkeypatch.setattr(p4_vectorstore, "get_collection", lambda *a, **kw: FakeCollection())
        monkeypatch.setattr(llm, "generate", lambda model, system, user: "Respuesta sin cifras.")
        monkeypatch.setattr(p7_generate, "_constantes", lambda: [])

        result = p7_generate.answer(config, "fake-model", "¿pregunta?")

        chunks = list(result.chunks)
        assert len(chunks) == 2, f"esperaba 2 chunks, hay {len(chunks)}"
        assert "texto uno" in chunks[0].values(), f"el primer chunk debía ser c1: {chunks[0]}"
        assert "texto dos" in chunks[1].values(), f"el segundo chunk debía ser c2: {chunks[1]}"
        assert chunks[0]["score"] == 0.9, f"score del primer chunk: {chunks[0]}"
        assert chunks[1]["score"] == 0.4, f"score del segundo chunk: {chunks[1]}"
        for c in chunks:
            assert c["score_kind"] == "rerank", f"score_kind debía ser 'rerank': {c}"

        assert p5_retrieve.score_kind(config) == "rerank"
        assert (
            p5_retrieve.score_kind(RetrievalConfig("combined", "contextual", "bgem3", "hibrida", 5))
            == "rrf"
        ), "híbrida sin rerank debe etiquetarse 'rrf'"
        assert (
            p5_retrieve.score_kind(RetrievalConfig("combined", "contextual", "bgem3", "densa", 5))
            == "distancia"
        ), "densa sin rerank debe etiquetarse 'distancia'"


# ---------------------------------------------------- criterios 4 y 5 -------


class TestWarmup:
    def test_endpoint_llama_warm_up(self, server, monkeypatch):
        """POST /api/warmup valida el cuerpo, construye un RetrievalConfig y delega en
        divefy.chat.warm_up(model, config); cuerpos inválidos devuelven 400 con
        "error" y no tocan warm_up."""
        import divefy.chat as chat
        from divefy.config import RetrievalConfig

        calls = []
        monkeypatch.setattr(chat, "warm_up", lambda model, config: calls.append((model, config)))

        cfg = {
            "corpus": "apuntes",
            "extras": "base",
            "embedding": "bgem3",
            "search": "densa",
            "k": 3,
            "rerank": False,
        }
        status, data = _post(server, "/api/warmup", {"model": "qwen4b", "config": cfg})
        assert status == 200, f"esperaba 200, got {status}: {data!r}"
        body = json.loads(data)
        assert body["ok"] is True, f"cuerpo inesperado: {body}"

        assert len(calls) == 1, f"warm_up debía llamarse una vez, llamadas: {calls}"
        model, config = calls[0]
        assert model == "qwen4b"
        assert isinstance(config, RetrievalConfig), f"config no es RetrievalConfig: {config!r}"
        assert (config.corpus, config.extras, config.embedding, config.search, config.k, config.rerank) == (
            "apuntes", "base", "bgem3", "densa", 3, False
        ), f"campos del config no coinciden: {config}"

        status, data = _post(server, "/api/warmup", {"config": cfg})
        assert status == 400, f"sin model debía ser 400, got {status}: {data!r}"
        assert "error" in json.loads(data), f"400 sin clave error: {data!r}"

        status, data = _post(server, "/api/warmup", b"{nope")
        assert status == 400, f"JSON roto debía ser 400, got {status}: {data!r}"
        assert "error" in json.loads(data), f"400 sin clave error: {data!r}"

        assert len(calls) == 1, f"los cuerpos inválidos no deben llamar a warm_up: {calls}"

    def test_warm_up_carga_lo_que_toca(self, monkeypatch):
        """warm_up precalienta el retrieval siempre (una query fija no vacía) y solo
        carga el modelo MLX cuando el modelo es local; con un modelo de API no toca
        _mlx_load."""
        import divefy.chat as chat
        import divefy.llm as llm
        from divefy.config import RECETA_GANADORA
        from divefy.pipeline import p5_retrieve

        retrieve_calls, load_calls = [], []

        def fake_retrieve(config, query, *a, **kw):
            retrieve_calls.append((config, query))
            return []

        def fake_load(model_key):
            load_calls.append(model_key)
            return (None, None)

        monkeypatch.setattr(p5_retrieve, "retrieve", fake_retrieve)
        monkeypatch.setattr(llm, "_mlx_load", fake_load)

        chat.warm_up("qwen4b", RECETA_GANADORA)

        assert len(retrieve_calls) == 1, f"retrieve debía llamarse una vez: {retrieve_calls}"
        config, query = retrieve_calls[0]
        assert config is RECETA_GANADORA, "warm_up debe pasar el config recibido a retrieve"
        assert isinstance(query, str) and query.strip(), f"query de precalentamiento vacía: {query!r}"
        assert load_calls == ["qwen4b"], f"_mlx_load debía llamarse una vez con qwen4b: {load_calls}"

        retrieve_calls.clear()
        load_calls.clear()

        chat.warm_up("haiku45", RECETA_GANADORA)

        assert len(retrieve_calls) == 1, f"retrieve debía llamarse una vez: {retrieve_calls}"
        assert load_calls == [], f"modelo de API no debe cargar MLX: {load_calls}"


# ---------------------------------------------------------- criterio 6 -------


class TestStreaming:
    def test_pagina_tiene_escritura_progresiva(self, server):
        """GET / sirve la página del chat con la escritura progresiva implementada en
        el front: el literal CHARS_PER_SECOND es el nudo de esa lógica."""
        status, data = _get(server, "/")
        assert status == 200, f"GET / devolvió {status}"
        html = data.decode("utf-8", errors="replace")
        assert "CHARS_PER_SECOND" in html, "la página no contiene CHARS_PER_SECOND"
