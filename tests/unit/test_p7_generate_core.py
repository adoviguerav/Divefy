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


def test_system_prompt_interpolates_abstention_template():
    system = p7_generate._system_prompt()
    assert "{abstention_template}" not in system, "el placeholder debe interpolarse"
    assert p7_generate.ABSTENTION_TEMPLATE in system, (
        "la plantilla del prompt y la constante deben ser la MISMA cadena — "
        "si divergen, la comparación exacta de abstención se rompe"
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
