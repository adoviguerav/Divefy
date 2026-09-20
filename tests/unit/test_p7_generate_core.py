"""Unit — p7_generate: prompt versionado, interpolación de plantilla y logs de estado.

El contrato gordo (estado completo, abstención, reintentos) vive en los tests de
aceptación congelados; aquí van las tripas que aquellos no miran.
"""

import logging

from divefy.pipeline import p7_generate


def test_prompt_version_comes_from_filename():
    # La propiedad, no el literal: la versión estampada deriva SIEMPRE del
    # nombre del fichero vigente, y ese fichero existe.
    assert p7_generate.PROMPT_VERSION == p7_generate.GENERATION_PROMPT_PATH.stem
    assert p7_generate.GENERATION_PROMPT_PATH.is_file()


def test_system_prompt_instructs_sentinel_not_template():
    # Diseño 2026-09-17: el modelo emite la palabra centinela y el CÓDIGO pone
    # la plantilla — el texto sagrado nunca viaja por el LLM.
    system = p7_generate._system_prompt()
    assert p7_generate.ABSTENTION_SENTINEL in system, "el prompt debe enseñar la palabra"
    assert p7_generate.ABSTENTION_TEMPLATE not in system, (
        "la plantilla no debe estar en el prompt: la emite p7_generate.answer()"
    )


def test_user_prompt_carries_chunks_and_question():
    chunks = (
        {"id": "c1", "texto": "texto uno", "metadata": {"corpus": "apuntes", "titulo": "T1"}},
        {"id": "c2", "texto": "texto dos", "metadata": {"corpus": "manual", "titulo": "T2"}},
    )
    user = p7_generate._user_prompt(chunks, "¿pregunta?")
    assert "texto uno" in user and "texto dos" in user
    assert "¿pregunta?" in user
    assert user.index("texto uno") < user.index("texto dos"), "orden del retrieval respetado"


def test_state_logs_emit_json_at_debug(caplog):
    with caplog.at_level(logging.DEBUG, logger="divefy.pipeline.p7_generate"):
        p7_generate._log_estado("retrieval", {"pregunta": "p", "chunks": ["a"]})
    assert any("[retrieval]" in r.message and '"chunks"' in r.message for r in caplog.records)


def test_state_logs_silent_without_debug(caplog):
    with caplog.at_level(logging.INFO, logger="divefy.pipeline.p7_generate"):
        p7_generate._log_estado("generate", {"respuesta": "r"})
    assert not caplog.records
