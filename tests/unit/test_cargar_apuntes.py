"""Andamiaje del implementador para cargar_apuntes. No es el examen."""

from pathlib import Path

from divefy.pipeline.p1_ingest import cargar_apuntes

APUNTES_DIR = Path("data/raw/PADI_course")


def test_cargar_apuntes_devuelve_registros():
    registros = cargar_apuntes(APUNTES_DIR)
    assert registros
    assert all(r.corpus == "apuntes" for r in registros)
    assert all(r.tipo == "prosa" for r in registros)
    assert all(r.texto for r in registros)


def test_cargar_apuntes_section_id_formato():
    registros = cargar_apuntes(APUNTES_DIR)
    assert any(r.section_id.startswith("Buceo - Fisica#") for r in registros)


def test_cargar_apuntes_descarta_preambulo():
    registros = cargar_apuntes(APUNTES_DIR)
    fisica = [r for r in registros if r.fichero == "Buceo - Fisica"]
    assert not any("Buceo — Física" in r.texto for r in fisica)
