"""Andamiaje del implementador para las funciones puras de Fase 2 (chunking).
No es el examen — tests/acceptance es lo que congela y evalúa /verify.
Usa un `contar` de palabras (no el tokenizador BGE-M3 real) para correr rápido y sin red."""

from divefy.pipeline.p1_ingest import Record
from divefy.pipeline.p2_chunking import escribir_chunks, fundir_minusculas, trocear_registros

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


def test_fundir_no_funde_secciones_grandes():
    grande_a = _r("1-1", "palabra " * 60)
    grande_b = _r("1-2", "palabra " * 60)
    resultado = fundir_minusculas([grande_a, grande_b], contar, umbral=50)
    assert [len(g) for g in resultado] == [1, 1]


def test_fundir_funde_seccion_minuscula_con_la_anterior():
    grande = _r("1-1", "palabra " * 60)
    minuscula = _r("1-2", "palabra " * 5)
    resultado = fundir_minusculas([grande, minuscula], contar, umbral=50)
    assert len(resultado) == 1
    assert [r.section_id for r in resultado[0]] == ["1-1", "1-2"]


def test_fundir_primera_minuscula_sin_anterior_se_pega_hacia_adelante():
    minuscula = _r("1-1", "palabra " * 5)
    grande = _r("1-2", "palabra " * 60)
    resultado = fundir_minusculas([minuscula, grande], contar, umbral=50)
    assert len(resultado) == 1
    assert [r.section_id for r in resultado[0]] == ["1-1", "1-2"]


def test_fundir_cadena_de_minusculas_consecutivas_en_un_solo_grupo():
    secciones = [_r(f"1-{i}", "palabra " * 5) for i in range(5)]
    resultado = fundir_minusculas(secciones, contar, umbral=50)
    assert len(resultado) == 1
    assert len(resultado[0]) == 5


def test_seccion_grande_se_parte_y_cada_trozo_apunta_a_la_misma_seccion():
    grande = _r("1-1", "palabra " * 200)
    chunks = trocear_registros([grande], tope=50, contar=contar)
    assert len(chunks) > 1
    for c in chunks:
        assert contar(c.texto) <= 50
        assert c.section_ids == ["1-1"]


def test_no_funde_a_traves_de_frontera_de_capitulo():
    fin_cap1 = _r("1-9", "palabra " * 5, capitulo=1)
    inicio_cap2 = _r("2-1", "palabra " * 60, capitulo=2)
    resultado = fundir_minusculas([fin_cap1, inicio_cap2], contar, umbral=50)
    # sin hermana anterior en su propio capítulo (es la única sección del cap 1 en
    # este ejemplo): no le queda más remedio que quedar como su propio grupo
    assert len(resultado) == 2
    assert [r.section_id for r in resultado[0]] == ["1-9"]
    assert [r.section_id for r in resultado[1]] == ["2-1"]


def test_no_funde_a_traves_de_frontera_de_fichero_apuntes():
    a = _r("a#sec", "palabra " * 5, corpus="apuntes", fichero="a")
    b = _r("b#sec", "palabra " * 60, corpus="apuntes", fichero="b")
    resultado = fundir_minusculas([a, b], contar, umbral=50)
    assert len(resultado) == 2


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


def test_id_de_chunk_es_de_contenido_no_de_posicion():
    a = _r("1-1", "palabra " * 5)
    b = _r("1-2", "palabra " * 5)
    chunks = trocear_registros([a, b], tope=100, contar=contar)
    # una sola sección fundida en un trozo: id = sus section_ids unidos, sin sufijo
    assert chunks[0].id == "1-1|1-2"


def test_id_de_chunk_partido_lleva_sufijo_por_parte():
    grande = _r("1-1", "palabra " * 200)
    chunks = trocear_registros([grande], tope=50, contar=contar)
    assert len(chunks) > 1
    assert [c.id for c in chunks] == [f"1-1#{i}" for i in range(len(chunks))]


def test_id_de_puntero_es_su_propio_section_id():
    puntero = Record(
        corpus="manual", section_id="table-9-9", titulo="Table 9-9", tipo="puntero_tabla",
        texto="Table 9-9.", fichero=None, capitulo=9, pagina=480, pagina_fin=490,
    )
    chunks = trocear_registros([puntero], tope=512, contar=contar)
    assert chunks[0].id == "table-9-9"


def test_escribir_chunks_revienta_si_hay_ids_repetidos(tmp_path):
    a = _r("1-1", "palabra " * 5)
    chunks = trocear_registros([a], tope=100, contar=contar)
    chunks = chunks + chunks  # fuerza la colisión a propósito
    try:
        escribir_chunks(chunks, tmp_path)
        assert False, "debería haber levantado ValueError"
    except ValueError:
        pass
