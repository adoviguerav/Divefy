"""Acceptance tests for Fase 8 — condensación de historial (p8_condense) y CLI chat.

Scope (una clase por criterio de aceptación):
  1. TestRecetaGanadora    — la config ganadora existe en divefy.config y su run_id
                             es exactamente el string acordado.
  2. TestCondenseHistorial — condense() solo debe pasar al backend Gemini los
                             últimos 3 pares de historial, nunca los más antiguos.
  3. TestChatRunTurnCondensa — sesión de 2 turnos: en el turno 2, run_turn() debe
                             pasar a p7_generate.answer() la query CONDENSADA, no
                             el texto ambiguo original del usuario.
  4. TestChatRunTurnEstado — run_turn() devuelve (respuesta, historial_actualizado)
                             sin mutar la lista de historial que recibió.

Estos tests están escritos ANTES de la implementación. En la primera ejecución
deben fallar RED con ImportError/AttributeError lanzado DENTRO de los tests o
fixtures — por eso todos los imports de `divefy.*` viven dentro del cuerpo de
la función de test/fixture, nunca a nivel de módulo. Los tests nunca escriben
en data/, results/ ni data/chroma/.
"""

import pytest


class TestRecetaGanadora:
    def test_run_id_es_exactamente_el_string_acordado(self):
        """RECETA_GANADORA debe existir como instancia de RetrievalConfig en
        divefy.config y su .run_id debe ser EXACTAMENTE
        'combined-512-contextual-qwen8b-hibrida-k10-rerank' — este string es el
        nombre canónico de la colección Chroma que usa todo el pipeline de
        generación, así que un desajuste aquí rompe silenciosamente el
        retrieval de producción."""
        from divefy.config import RECETA_GANADORA, RetrievalConfig

        assert isinstance(RECETA_GANADORA, RetrievalConfig), (
            "RECETA_GANADORA debe ser una instancia de RetrievalConfig, no otro tipo"
        )
        assert RECETA_GANADORA.run_id == "combined-512-contextual-qwen8b-hibrida-k10-rerank", (
            f"run_id inesperado: {RECETA_GANADORA.run_id!r} — cualquier cambio aquí "
            "apunta a una colección Chroma distinta de la ganadora"
        )


def _fake_cliente_capturando(respuesta_texto):
    """Devuelve (fake_cliente, calls). fake_cliente imita la forma del SDK
    google-genai: .models.generate_content(**kwargs) -> objeto con .text."""
    calls = []

    class _Respuesta:
        text = respuesta_texto

    class _Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return _Respuesta()

    class _FakeCliente:
        def __init__(self):
            self.models = _Models()

    return _FakeCliente(), calls


class TestCondenseHistorial:
    def test_solo_envia_los_ultimos_3_pares_al_backend(self, monkeypatch):
        """Con 5 pares de historial, condense() debe construir un prompt que
        contenga solo los últimos 3 pares (los más recientes) y NO los 2 más
        antiguos — si se cuela historial de más de 3 turnos atrás, el modelo
        de condensación puede generar una query de retrieval contaminada con
        contexto irrelevante o ya cerrado."""
        historial = [
            ("¿Qué es la narcosis por nitrógeno?", "respuesta_muy_antigua_uno"),
            ("¿A qué profundidad ocurre?", "respuesta_muy_antigua_dos"),
            ("¿Cuánto dura un tanque de aire?", "respuesta_reciente_tres"),
            ("¿Qué es la parada de seguridad?", "respuesta_reciente_cuatro"),
            ("¿Cuánto tiempo dura la parada?", "respuesta_reciente_cinco"),
        ]

        fake_cliente, calls = _fake_cliente_capturando("query condensada de prueba")

        import divefy.pipeline.p8_condense as p8_condense

        monkeypatch.setattr(p8_condense, "_cliente", lambda: fake_cliente)

        p8_condense.condense(historial, "¿Y si tengo poco aire?")

        assert len(calls) == 1, "condense() debe llamar al backend Gemini exactamente una vez"

        prompt_enviado = str(calls[0])

        for pregunta_antigua in (
            "¿Qué es la narcosis por nitrógeno?",
            "¿A qué profundidad ocurre?",
        ):
            assert pregunta_antigua not in prompt_enviado, (
                f"el par antiguo {pregunta_antigua!r} no debería estar en el prompt: "
                "condense() solo debe usar los últimos 3 pares de historial"
            )

        for pregunta_reciente in (
            "¿Cuánto dura un tanque de aire?",
            "¿Qué es la parada de seguridad?",
            "¿Cuánto tiempo dura la parada?",
        ):
            assert pregunta_reciente in prompt_enviado, (
                f"el par reciente {pregunta_reciente!r} falta en el prompt: "
                "condense() debe incluir los últimos 3 pares de historial"
            )


class _RespuestaFalsa:
    """Imita el objeto que p7_generate.answer() devuelve realmente (tiene un
    atributo .respuesta con el texto final del modelo)."""

    def __init__(self, respuesta):
        self.respuesta = respuesta


class TestChatRunTurnCondensa:
    def test_turno_2_usa_query_condensada_no_texto_ambiguo(self, monkeypatch):
        """El test más importante: en un follow-up ambiguo ('¿Y si tengo poco
        aire?' sin contexto propio), run_turn() debe condensar el historial
        primero y pasar esa query condensada a p7_generate.answer() — si en
        cambio pasara el texto crudo del usuario, el retrieval buscaría por
        'aire' sin saber que la pregunta es sobre la parada de seguridad, y
        la respuesta perdería el contexto de la conversación."""
        import divefy.pipeline.p7_generate as p7_generate
        import divefy.pipeline.p8_condense as p8_condense
        from divefy import chat

        condense_calls = []

        def fake_condense(historial, pregunta):
            condense_calls.append({"historial": list(historial), "pregunta": pregunta})
            if pregunta == "¿Y si tengo poco aire?":
                return "profundidad de la parada de seguridad si tengo poco aire"
            return pregunta

        answer_calls = []

        def fake_answer(retrieval_config, model, query):
            answer_calls.append(
                {"retrieval_config": retrieval_config, "model": model, "query": query}
            )
            if query == "¿A qué profundidad se hace la parada de seguridad?":
                return _RespuestaFalsa("La parada de seguridad se hace a 5 metros durante 3 minutos.")
            return _RespuestaFalsa("Asciende con calma compartiendo aire si hace falta.")

        monkeypatch.setattr(p8_condense, "condense", fake_condense)
        monkeypatch.setattr(p7_generate, "answer", fake_answer)

        historial = []
        _, historial = chat.run_turn(
            historial, "modelo-fake", "¿A qué profundidad se hace la parada de seguridad?"
        )
        _, historial = chat.run_turn(historial, "modelo-fake", "¿Y si tengo poco aire?")

        assert len(answer_calls) == 2, "run_turn() debe llamar a p7_generate.answer() una vez por turno"
        assert answer_calls[1]["query"] == "profundidad de la parada de seguridad si tengo poco aire", (
            f"turno 2 llamó a p7_generate.answer() con {answer_calls[1]['query']!r}: "
            "debe recibir la QUERY CONDENSADA (que contiene 'profundidad'), no el "
            "texto ambiguo original '¿Y si tengo poco aire?'"
        )
        assert "profundidad" in answer_calls[1]["query"], (
            "la query pasada a p7_generate.answer() en el turno 2 debe contener "
            "'profundidad' — prueba de que viene de la condensación, no del texto crudo"
        )


class TestChatRunTurnEstado:
    def test_devuelve_respuesta_y_historial_actualizado_sin_mutar_el_original(self, monkeypatch):
        """run_turn() debe devolver una tupla (texto_respuesta, historial_actualizado)
        donde texto_respuesta coincide exactamente con answer.respuesta simulado,
        el historial actualizado añade el nuevo par (pregunta, respuesta) al final,
        y la lista de historial ORIGINAL que se pasó como argumento queda intacta
        (ni se le añade el nuevo turno ni se modifica en sitio) — si run_turn()
        mutara el historial de entrada, cualquier código que aún tenga una
        referencia al historial anterior vería el nuevo turno sin haberlo pedido."""
        import divefy.pipeline.p7_generate as p7_generate
        import divefy.pipeline.p8_condense as p8_condense
        from divefy import chat

        monkeypatch.setattr(p8_condense, "condense", lambda historial, pregunta: pregunta)
        monkeypatch.setattr(
            p7_generate,
            "answer",
            lambda retrieval_config, model, query: _RespuestaFalsa("respuesta simulada final"),
        )

        historial_original = [("pregunta previa", "respuesta previa")]
        longitud_original = len(historial_original)

        respuesta_texto, historial_actualizado = chat.run_turn(
            historial_original, "modelo-fake", "¿nueva pregunta?"
        )

        assert respuesta_texto == "respuesta simulada final", (
            "el texto de respuesta devuelto debe ser exactamente answer.respuesta"
        )
        assert historial_actualizado[-1] == ("¿nueva pregunta?", "respuesta simulada final"), (
            "el historial actualizado debe tener el nuevo par (pregunta, respuesta) al final"
        )
        assert len(historial_actualizado) == longitud_original + 1, (
            "el historial actualizado debe tener exactamente un turno más que el original"
        )
        assert len(historial_original) == longitud_original, (
            "la lista de historial ORIGINAL no debe mutarse: run_turn() debe construir "
            "una lista nueva, no hacer .append() sobre la que recibió"
        )
