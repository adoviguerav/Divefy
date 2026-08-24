"""Andamiaje del implementador para las funciones puras de Fase 3 (enriquecimiento).
No es el examen — tests/acceptance es lo que congela y evalúa /verify."""

import json

from divefy.pipeline import p3_enrich
from divefy.pipeline.p3_enrich import documento_padre


def _c(id, texto, tipo="prosa", capitulo=None, fichero=None, pagina=None):
    return {
        "id": id,
        "corpus": "manual" if fichero is None else "apuntes",
        "tipo": tipo,
        "texto": texto,
        "capitulo": capitulo,
        "fichero": fichero,
        "pagina": pagina,
    }


def test_documento_padre_concatena_solo_la_prosa_del_mismo_capitulo():
    a = _c(0, "primero", capitulo=9, pagina=1)
    b = _c(1, "segundo", capitulo=9, pagina=2)
    otro_capitulo = _c(2, "de otro capítulo", capitulo=10, pagina=1)
    doc = documento_padre([a, b, otro_capitulo], capitulo=9, fichero=None)
    assert doc == "primero\n\nsegundo"


def test_documento_padre_ordena_por_pagina_no_por_orden_de_entrada():
    b = _c(0, "segundo", capitulo=9, pagina=5)
    a = _c(1, "primero", capitulo=9, pagina=1)
    doc = documento_padre([b, a], capitulo=9, fichero=None)
    assert doc == "primero\n\nsegundo"


def test_documento_padre_excluye_punteros_de_tabla():
    prosa = _c(0, "texto real", capitulo=9, pagina=1)
    puntero = _c(1, "Table 9-9", tipo="puntero_tabla", capitulo=9, pagina=1)
    doc = documento_padre([prosa, puntero], capitulo=9, fichero=None)
    assert doc == "texto real"


def test_documento_padre_apuntes_usa_fichero_y_conserva_orden_de_entrada():
    a = _c(0, "primero", fichero="Física")
    b = _c(1, "segundo", fichero="Física")
    otro_fichero = _c(2, "de otro fichero", fichero="Material")
    doc = documento_padre([a, b, otro_fichero], capitulo=None, fichero="Física")
    assert doc == "primero\n\nsegundo"


def test_enriquecer_regenera_si_el_texto_cambia_aunque_el_id_se_mantenga(tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setattr(p3_enrich, "generar_contexto", lambda d, t, c: (llamadas.append(t), "ctx")[1])
    monkeypatch.setattr(p3_enrich, "generar_preguntas_hype", lambda cc, c: ["a?", "b?", "c?"])

    fila = {
        "id": "9-1", "corpus": "manual", "section_ids": ["9-1"], "titulo": "t",
        "tipo": "prosa", "texto": "texto original", "fichero": None,
        "capitulo": 9, "pagina": 1, "pagina_fin": None,
    }
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(json.dumps(fila) + "\n", encoding="utf-8")

    p3_enrich.enriquecer(chunks_path, tmp_path)
    assert len(llamadas) == 1

    # mismo id, texto retocado: debe regenerar, no reusar el caché
    fila["texto"] = "texto retocado"
    chunks_path.write_text(json.dumps(fila) + "\n", encoding="utf-8")
    p3_enrich.enriquecer(chunks_path, tmp_path)
    assert len(llamadas) == 2

    # sin cambios: no debe volver a llamar
    p3_enrich.enriquecer(chunks_path, tmp_path)
    assert len(llamadas) == 2
