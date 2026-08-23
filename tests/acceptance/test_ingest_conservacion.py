"""C2: chars_entrada (derivado de la propia clasificación de Docling) frente a una
medición GENUINAMENTE independiente (pdfplumber, sin pasar por Docling). El test de
igualdad exacta en test_ingest.py sigue vivo y frozen — este es un chequeo aparte,
con tolerancia, porque dos pipelines de extracción distintos jamás van a coincidir
carácter a carácter (cabeceras/pies, tablas y espacios se tratan distinto).

Tolerancia fijada con datos reales de los 10 capítulos curados tras corregir C1/C3
(ver manifiesto.json): el diff máximo observado fue 12.6% (cap 17); el resto está
entre 0.1% y 5.1%. 20% deja margen sobre esa variación de formato normal y sigue
atrapando el escenario que este chequeo existe para atrapar — un parser que se traga
un tercio del texto en silencio (motivo original del manifiesto, CLAUDE.md/plan)."""

import json
from pathlib import Path

PROCESSED_DIR = Path("data/processed")
MANIFIESTO_PATH = PROCESSED_DIR / "manifiesto.json"

TOLERANCIA_RELATIVA = 0.20


def _manifiesto() -> dict:
    with MANIFIESTO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_manifiesto_tiene_medicion_independiente():
    for capitulo, datos in _manifiesto().items():
        assert "chars_entrada_pdfplumber" in datos, capitulo
        assert datos["chars_entrada_pdfplumber"] > 0, capitulo


def test_chars_entrada_cerca_de_medicion_independiente():
    for capitulo, datos in _manifiesto().items():
        independiente = datos["chars_entrada_pdfplumber"]
        diff_relativo = abs(datos["chars_entrada"] - independiente) / independiente
        assert diff_relativo <= TOLERANCIA_RELATIVA, (
            f"cap{capitulo}: chars_entrada={datos['chars_entrada']} vs "
            f"pdfplumber={independiente} ({diff_relativo:.1%} de diferencia, "
            f"tolerancia {TOLERANCIA_RELATIVA:.0%})"
        )
