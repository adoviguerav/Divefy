"""Andamiaje del implementador para las funciones puras de Fase 2 (chunking).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Usa un `contar` de palabras (no el tokenizador BGE-M3 real) para correr rápido y sin red."""

from divefy.pipeline.p1_ingest import Record
from divefy.pipeline.p2_chunking import trocear_registros

contar = lambda t: len(t.split())


def _r(section_id, texto, corpus="manual", fichero=None, capitulo=1, titulo=None):
    return Record(
        corpus=corpus,
        section_id=section_id,
        titulo=titulo or section_id,
        tipo="prosa",
        texto=texto,
        fichero=fichero,
        capitulo=capitulo if corpus == "manual" else None,
        pagina=1 if corpus == "manual" else None,
        pagina_fin=None,
    )


def test_dos_secciones_pequenas_que_caben_juntas_se_empaquetan_en_un_trozo():
    a = _r("1-1", "palabra " * 20, titulo="Purpose")
    b = _r("1-2", "palabra " * 20, titulo="Scope")
    chunks = trocear_registros([a, b], tope=100, contar=contar)
    assert len(chunks) == 1
    assert chunks[0].section_ids == ["1-1", "1-2"]


def test_seccion_que_no_cabe_con_la_siguiente_queda_en_su_propio_trozo():
    a = _r("1-1", "palabra " * 80)
    b = _r("1-2", "palabra " * 80)
    chunks = trocear_registros([a, b], tope=100, contar=contar)
    assert len(chunks) == 2
    assert chunks[0].section_ids == ["1-1"]
    assert chunks[1].section_ids == ["1-2"]


def test_seccion_grande_se_parte_y_cada_trozo_apunta_a_la_misma_seccion():
    grande = _r("1-1", "palabra " * 200)
    chunks = trocear_registros([grande], tope=50, contar=contar)
    assert len(chunks) > 1
    for c in chunks:
        assert contar(c.texto) <= 50
        assert c.section_ids == ["1-1"]


def test_no_empaqueta_a_traves_de_frontera_de_capitulo():
    fin_cap1 = _r("1-9", "palabra " * 5, capitulo=1)
    inicio_cap2 = _r("2-1", "palabra " * 5, capitulo=2)
    chunks = trocear_registros([fin_cap1, inicio_cap2], tope=100, contar=contar)
    assert len(chunks) == 2
    assert chunks[0].section_ids == ["1-9"]
    assert chunks[1].section_ids == ["2-1"]


def test_no_empaqueta_a_traves_de_frontera_de_fichero_apuntes():
    a = _r("a#sec", "palabra " * 5, corpus="apuntes", fichero="a")
    b = _r("b#sec", "palabra " * 5, corpus="apuntes", fichero="b")
    chunks = trocear_registros([a, b], tope=100, contar=contar)
    assert len(chunks) == 2


def test_trocear_pasa_punteros_de_tabla_sin_tocar():
    puntero = Record(
        corpus="manual",
        section_id="table-9-9",
        titulo="Table 9-9",
        tipo="puntero_tabla",
        texto="Table 9-9 (capítulo 9, páginas 480-490).",
        fichero=None,
        capitulo=9,
        pagina=480,
        pagina_fin=490,
    )
    chunks = trocear_registros([puntero], tope=512, contar=contar)
    assert len(chunks) == 1
    assert chunks[0].tipo == "puntero_tabla"
    assert chunks[0].texto == puntero.texto
    assert chunks[0].section_ids == ["table-9-9"]


def test_ningun_trozo_vacio_ni_sobre_tope():
    secciones = [_r(f"1-{i}", "palabra " * (3 * i + 1)) for i in range(1, 20)]
    chunks = trocear_registros(secciones, tope=50, contar=contar)
    assert chunks
    for c in chunks:
        assert c.texto.strip()
        assert contar(c.texto) <= 50
