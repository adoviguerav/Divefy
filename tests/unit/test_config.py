"""Andamiaje del implementador para RetrievalConfig (T-02, Fase 5).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Mismo estilo que test_p4_indexing_core.py: fixtures a mano, sin Chroma ni modelos."""

import dataclasses

import pytest

from divefy.config import RetrievalConfig


def base_config(**overrides):
    values = dict(
        corpus="apuntes", cap=512, extras="base", embedding="bgem3", search="densa", k=5
    )
    return RetrievalConfig(**{**values, **overrides})


def test_collection_es_el_nombre_canonico_de_fase_4():
    from divefy.pipeline.p4_vectorstore import canonical_name

    assert base_config().collection == canonical_name("apuntes", 512, "base", "bgem3")


def test_run_id_concatena_coleccion_busqueda_y_k():
    assert base_config(search="hibrida").run_id == "apuntes-512-base-bgem3-hibrida-k5"
    assert base_config(k=10).run_id == "apuntes-512-base-bgem3-densa-k10"


def test_cap_es_libre_con_default_512():
    # Decisión de Adolfo (Notas del plan, 2026-08-28): cap no se valida — la
    # validez real de un cap la impone el marcador .complete en runtime.
    sin_cap = RetrievalConfig(
        corpus="apuntes", extras="base", embedding="bgem3", search="densa", k=5
    )
    assert sin_cap.cap == 512
    assert base_config(cap=1024).collection == "apuntes-1024-base-bgem3"


def test_es_inmutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        base_config().k = 3


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("corpus", "todo"),
        ("extras", "ninguno"),
        ("embedding", "bge"),
        ("search", "dense"),
        ("k", 7),
    ],
)
def test_valor_categorico_invalido_lanza_error_ruidoso(campo, valor):
    with pytest.raises(ValueError, match=campo):
        base_config(**{campo: valor})
