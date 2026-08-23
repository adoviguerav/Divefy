"""Tests de aceptación de la Fase 1 (ingesta): corren contra los artefactos
generados por `python -m divefy.pipeline.p1_ingest` en data/processed/
(corpus.jsonl, manifiesto.json). Hasta que esos artefactos existan, las
pruebas que dependen de ellos fallan con FileNotFoundError — es el RED
esperado."""

import json
import re
from pathlib import Path

import pytest

from divefy.pipeline.p1_ingest import (
    cargar_apuntes,
    es_fila_distintiva,
    normalizar,
    parsear_manual,
)

APUNTES_DIR = Path("data/raw/PADI_course")
MANUAL_PDF = Path("data/raw/navy-diving-manual-rev7.pdf")
PROCESSED_DIR = Path("data/processed")
CORPUS_PATH = PROCESSED_DIR / "corpus.jsonl"
MANIFIESTO_PATH = PROCESSED_DIR / "manifiesto.json"

APUNTES_FILES = [
    "Buceo - Entornos y condiciones.md",
    "Buceo - Fisica.md",
    "Buceo - Fisiologia y salud.md",
    "Buceo - Gestion de problemas.md",
    "Buceo - Habilidades practicas.md",
    "Buceo - Material.md",
]

CAPITULOS_CURADOS = {2, 3, 4, 6, 7, 9, 10, 11, 14, 17}

SECTION_ID_MANUAL_RE = re.compile(r"^\d+-\d+(\.\d+)*$")


def _normalizar_espacios(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


@pytest.fixture(scope="module")
def corpus_records():
    records = []
    with CORPUS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


@pytest.fixture(scope="module")
def manifiesto():
    with MANIFIESTO_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def apuntes_records(corpus_records):
    return [r for r in corpus_records if r["corpus"] == "apuntes"]


@pytest.fixture(scope="module")
def manual_records(corpus_records):
    return [r for r in corpus_records if r["corpus"] == "manual"]


# --- 1. Apuntes completos ---------------------------------------------------

def test_apuntes_completos_conteo_por_fichero(apuntes_records):
    cargados = cargar_apuntes(APUNTES_DIR)
    total_esperado = 0
    for nombre in APUNTES_FILES:
        texto = (APUNTES_DIR / nombre).read_text(encoding="utf-8")
        total_esperado += len(re.findall(r"^## ", texto, flags=re.MULTILINE))

    assert len(cargados) == total_esperado
    assert len(apuntes_records) == total_esperado


def test_apuntes_registros_bien_formados(apuntes_records):
    assert apuntes_records
    for r in apuntes_records:
        assert r["corpus"] == "apuntes"
        assert r["section_id"]
        assert "#" in r["section_id"]
        assert r["titulo"]
        assert r["texto"]


def test_apuntes_fisica_no_divide_en_subheaders(apuntes_records):
    texto = (APUNTES_DIR / "Buceo - Fisica.md").read_text(encoding="utf-8")
    n_secciones = len(re.findall(r"^## ", texto, flags=re.MULTILINE))
    fisica_records = [r for r in apuntes_records if r["fichero"] == "Buceo - Fisica"]
    assert len(fisica_records) == n_secciones


# --- 2. Manual: secciones y metadatos ---------------------------------------

def test_manual_capitulos_curados_presentes(manual_records):
    capitulos_presentes = {r["capitulo"] for r in manual_records if r["tipo"] == "prosa"}
    assert CAPITULOS_CURADOS <= capitulos_presentes


def test_manual_prosa_metadatos_y_unicidad(corpus_records, manual_records):
    prosa = [r for r in manual_records if r["tipo"] == "prosa"]
    assert prosa

    section_ids_todos = [r["section_id"] for r in corpus_records]
    assert len(section_ids_todos) == len(set(section_ids_todos))

    for r in prosa:
        assert SECTION_ID_MANUAL_RE.match(r["section_id"]), r["section_id"]
        assert r["titulo"]
        assert r["pagina"] is not None
        assert "U.S. Navy Diving Manual" not in r["texto"]
        assert not re.search(r"(?m)^CHAPTER \d+$", r["texto"])


def test_manual_capitulo_9_volumen_y_warnings(manual_records):
    cap9_prosa = [r for r in manual_records if r["tipo"] == "prosa" and r["capitulo"] == 9]
    assert len(cap9_prosa) >= 85
    total_warning = sum(r["texto"].count("WARNING") for r in cap9_prosa)
    assert total_warning >= 4


def test_manual_capitulo_7_personal_minimo(manual_records):
    cap7_prosa = [r for r in manual_records if r["tipo"] == "prosa" and r["capitulo"] == 7]
    assert any("These are the minimum personnel levels allowed" in r["texto"] for r in cap7_prosa)


def test_manual_section_ids_especificos_existen(manual_records):
    por_id = {r["section_id"]: r for r in manual_records}
    for sid in ("9-1", "9-6.3", "9-3.2"):
        assert sid in por_id
    assert por_id["9-3.2"]["titulo"].startswith("Bottom Time")


# --- 3. Tablas lógicas como punteros ----------------------------------------

def test_manual_punteros_tabla_capitulo_9(corpus_records):
    punteros = [r for r in corpus_records if r["tipo"] == "puntero_tabla"]
    cap9_punteros = [r for r in punteros if r["capitulo"] == 9]
    assert len(cap9_punteros) == 9

    for r in punteros:
        assert r["titulo"]
        assert r["pagina"] is not None
        assert r["pagina_fin"] is not None
        assert r["pagina_fin"] >= r["pagina"]
        assert r["texto"]

    section_ids = [r["section_id"] for r in punteros]
    assert len(section_ids) == len(set(section_ids))


def test_manual_puntero_tabla_9_9_multipagina(corpus_records):
    tabla_9_9 = next(
        r for r in corpus_records
        if r["tipo"] == "puntero_tabla" and r["section_id"] == "table-9-9"
    )
    assert tabla_9_9["pagina_fin"] - tabla_9_9["pagina"] + 1 >= 10


# --- 4. Prosa sin filas de tabla --------------------------------------------

def test_manual_prosa_sin_filas_de_tabla(manual_records):
    prosa = [r for r in manual_records if r["tipo"] == "prosa"]
    for r in prosa:
        for linea in r["texto"].splitlines():
            assert not es_fila_distintiva(linea), (r["section_id"], linea)


@pytest.mark.parametrize(
    "linea, esperado",
    [
        ("50 2:20 AIR 31 34:00 1 N", True),
        (":15 + :30 = :45 = 100/45 N", False),
        ("ascent rate is 30 fsw/min", False),
    ],
)
def test_es_fila_distintiva_calibracion(linea, esperado):
    assert es_fila_distintiva(linea) is esperado


# --- 5. 10 hechos literales en su sección -----------------------------------

HECHOS = [
    ("one atmosphere is equal to 33 feet of sea water", "manual", "2-9.1"),
    ("14.7 psi divided by 33 feet equals 0.445 psi per foot", "manual", "2-9.1"),
    (
        "Bottom time is the total elapsed time from the time the diver leaves the surface to the time he leaves the bottom",
        "manual",
        "9-3.2",
    ),
    ("30 fsw/min (20 seconds per 10 fsw)", "manual", "9-6.3"),
    (
        "ascender despacio (18 m/min o lo que diga el ordenador)",
        "apuntes",
        "Buceo - Fisiologia y salud#Cómo funcionan los ordenadores y tablas de buceo",
    ),
    ("10 m: 219 min", "apuntes", "Buceo - Fisiologia y salud#Buceo sin paradas"),
    (
        "Máximo 18 m/min o lo que marque el ordenador",
        "apuntes",
        "Buceo - Fisiologia y salud#Buceo sin paradas",
    ),
    ("(5 m, 3 min)", "apuntes", "Buceo - Fisiologia y salud#Buceo sin paradas"),
    (
        "4 m más profunda",
        "apuntes",
        "Buceo - Fisiologia y salud#Inmersiones con frío o agotadoras",
    ),
    (
        "fondeado a 5-6 m",
        "apuntes",
        "Buceo - Entornos y condiciones#Bucear desde un barco",
    ),
]


@pytest.mark.parametrize("hecho, corpus, section_id", HECHOS)
def test_hechos_literales_en_su_seccion(corpus_records, hecho, corpus, section_id):
    candidatos = [
        r for r in corpus_records
        if r["corpus"] == corpus and r["section_id"] == section_id
    ]
    assert candidatos, f"no se encontró section_id={section_id!r} en corpus={corpus!r}"
    hecho_norm = _normalizar_espacios(hecho)
    assert any(hecho_norm in _normalizar_espacios(r["texto"]) for r in candidatos)


# --- 6. Texto normalizado ----------------------------------------------------

FORBIDDEN_CHARS = ["­", "‑", "‘", "’", "“", "”"]


def test_corpus_sin_caracteres_no_normalizados(corpus_records):
    for r in corpus_records:
        for campo in ("texto", "titulo"):
            valor = r[campo]
            for ch in FORBIDDEN_CHARS:
                assert ch not in valor, (r["section_id"], campo, repr(ch))


def test_normalizar_pliega_guion_blando():
    assert normalizar("chem­ical") == "chemical"
    assert normalizar("chem­\nical") == "chemical"


def test_normalizar_reemplaza_guion_no_separable():
    resultado = normalizar("Table 9‑9")
    assert "‑" not in resultado
    assert resultado == "Table 9-9"


def test_normalizar_no_altera_digitos():
    assert normalizar("33") == "33"


# --- 7. Conservación contable ------------------------------------------------

def test_manifiesto_conservacion_caracteres(manifiesto):
    for capitulo, datos in manifiesto.items():
        assert (
            datos["chars_prosa"] + datos["chars_tablas"] + datos["chars_descartados"]
            == datos["chars_entrada"]
        ), capitulo


def test_manifiesto_secciones_detectadas_emitidas(manifiesto):
    for capitulo, datos in manifiesto.items():
        assert datos["secciones_detectadas"] == datos["secciones_emitidas"], capitulo


def test_manifiesto_secciones_emitidas_coincide_con_corpus(manifiesto, manual_records):
    for capitulo, datos in manifiesto.items():
        n_registros = sum(1 for r in manual_records if r["capitulo"] == int(capitulo) and r["tipo"] == "prosa")
        assert n_registros == datos["secciones_emitidas"], capitulo


def test_manifiesto_descartes_altos_es_bool_si_presente(manifiesto):
    for datos in manifiesto.values():
        if "descartes_altos" in datos:
            assert isinstance(datos["descartes_altos"], bool)


# --- 8. Parser vivo (slow) ---------------------------------------------------

@pytest.mark.slow
def test_parsear_manual_capitulo_10_en_vivo():
    registros, manifiesto_cap = parsear_manual(MANUAL_PDF, solo_capitulos={10})

    assert registros
    assert any(r.tipo == "prosa" for r in registros)

    prosa = [r for r in registros if r.tipo == "prosa"]
    for r in prosa:
        for linea in r.texto.splitlines():
            assert not es_fila_distintiva(linea)

    assert manifiesto_cap
    datos_cap10 = manifiesto_cap.get("10", manifiesto_cap.get(10))
    assert datos_cap10 is not None
    assert (
        datos_cap10["chars_prosa"] + datos_cap10["chars_tablas"] + datos_cap10["chars_descartados"]
        == datos_cap10["chars_entrada"]
    )

    section_ids = [r.section_id for r in registros]
    assert len(section_ids) == len(set(section_ids))
