"""Unit — p7_guardrail: extracción de pares, normalización y pertenencia.

El 5+5 del contrato vive en tests/acceptance/test_p7_generacion.py (congelado);
aquí van las tripas: variantes ortográficas, coma decimal, precedencia de
unidades compuestas y unidades fuera del set.
"""

from divefy.pipeline.p7_guardrail import extract_pairs, verify

CONSTANTES = [
    {"numero": "18", "unidad": "m/min"},
    {"numero": "10,3", "unidad": "m"},
    {"numero": "3", "unidad": "min"},
    {"numero": "12", "unidad": "h"},
    {"numero": "49", "unidad": "ºC"},
]


def test_compound_unit_wins_over_prefix():
    # "18 m/min" debe extraerse como m/min, no quedarse en (18, m).
    assert extract_pairs("sube a 18 m/min") == [("18", "m/min")]


def test_spelling_variants_normalize_to_canonical():
    assert extract_pairs("18 metros por minuto") == [("18", "m/min")]
    assert extract_pairs("espera 12 horas y para 3 minutos") == [("12", "h"), ("3", "min")]
    assert extract_pairs("agua a 49 °C") == [("49", "ºC")]


def test_decimal_point_matches_comma_row():
    # El modelo escribe "10.3 m"; la chuleta guarda "10,3".
    assert verify("en agua dulce son 10.3 m", CONSTANTES) == "ok"


def test_unknown_units_are_not_watched():
    # segundos/pies/psi fuera del set (decisión 16): sin par, sin veredicto.
    assert extract_pairs("no pasar de 3 m cada 10 segundos a 33 pies y 3000 psi") == [
        ("3", "m")
    ]


def test_unverified_pair_returns_reintento():
    assert verify("sube a 25 m/min", CONSTANTES) == "reintento"


def test_all_verified_returns_ok():
    assert verify("18 m/min, parada de 3 min, espera 12 h", CONSTANTES) == "ok"


def test_text_without_numbers_is_ok():
    assert verify("Avisa a tu compañero y ascended juntos con calma.", CONSTANTES) == "ok"
