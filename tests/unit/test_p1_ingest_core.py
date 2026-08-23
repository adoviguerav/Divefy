"""Andamiaje del implementador para las funciones puras del núcleo de Fase 1.
No es el examen — tests/acceptance es lo que congela y evalúa /verify."""

from divefy.pipeline.p1_ingest import es_fila_distintiva, normalizar, plegar_caption


def test_normalizar_guion_blando_misma_linea():
    assert normalizar("chem­ical") == "chemical"


def test_normalizar_guion_blando_a_traves_de_salto_de_linea():
    assert normalizar("chem­\nical") == "chemical"


def test_normalizar_guion_no_separable():
    assert normalizar("Table 9‑‑9") == "Table 9--9"


def test_normalizar_comillas_curvas():
    assert normalizar("‘hola’ “mundo”") == "'hola' \"mundo\""


def test_normalizar_colapsa_espacios_por_linea_conserva_saltos():
    assert normalizar("a   b\nc    d") == "a b\nc d"


def test_normalizar_no_toca_digitos():
    assert normalizar("33") == "33"


def test_es_fila_distintiva_calibracion():
    assert es_fila_distintiva("50 2:20 AIR 31 34:00 1 N") is True
    assert es_fila_distintiva(":15 + :30 = :45 = 100/45 N") is False
    assert es_fila_distintiva("ascent rate is 30 fsw/min") is False


def test_es_fila_distintiva_linea_vacia():
    assert es_fila_distintiva("") is False


def test_plegar_caption_pliega_continuacion():
    assert plegar_caption("Table 9-9. Some caption text (Continued).") == "Table 9-9. Some caption text"


def test_plegar_caption_sin_continuacion():
    assert plegar_caption("Table 9-1") == "Table 9-1"
