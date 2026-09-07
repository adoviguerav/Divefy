"""Fase 7 — Guardarraíl numérico determinista (v1: solo pertenencia, decisión 16).

`verify()` extrae cada par número+unidad de la respuesta generada, normaliza la
ortografía de la unidad (minutos→min, horas→h — el mismo criterio con el que se
curó la chuleta) y comprueba que el par existe en `data/guardrail/constantes.jsonl`.
Sin contexto y sin fuente en v1; unidades fuera del set (segundos, pies, psi…)
no se vigilan. La política reintento-una-vez y la abstención final
(`abstener_cifra`) las orquesta `p7_generate.answer()` (T-04): verify es puro y
sin memoria — devuelve `ok` o `reintento`.
"""

import re

# Variante escrita → unidad canónica de la chuleta. Las compuestas ("metros por
# minuto") van en el mismo mapa; el regex prueba las más largas primero para que
# "18 m/min" no se quede en "18 m".
_VARIANTES_UNIDAD = {
    "m/min": ("m/min", "metros por minuto", "m por minuto"),
    "fsw/min": ("fsw/min", "fsw por minuto"),
    "fsw": ("fsw",),
    "m": ("m", "metros", "metro"),
    "min": ("min", "minutos", "minuto"),
    "h": ("h", "horas", "hora"),
    "bar": ("bar",),
    "atm": ("atm", "atmósferas", "atmósfera", "atmosferas", "atmosfera"),
    "%": ("%", "por ciento"),
    "ºC": ("ºc", "°c"),
}
_CANONICA = {
    variante.lower(): canonica
    for canonica, variantes in _VARIANTES_UNIDAD.items()
    for variante in variantes
}
_ALTERNATION = "|".join(
    re.escape(v) for v in sorted(_CANONICA, key=len, reverse=True)
)
_RE_PAR = re.compile(
    rf"(?<![\w/,.])(\d+(?:[.,]\d+)?)\s*({_ALTERNATION})(?![\w/º°%])",
    re.IGNORECASE,
)


def _numero_canonico(numero: str) -> str:
    """La chuleta usa coma decimal ("10,3"); el modelo puede escribir punto."""
    return numero.replace(".", ",")


def extract_pairs(texto: str) -> list[tuple[str, str]]:
    """Pares (número, unidad canónica) presentes en el texto, en orden."""
    return [
        (_numero_canonico(numero), _CANONICA[unidad.lower()])
        for numero, unidad in _RE_PAR.findall(texto)
    ]


def verify(respuesta: str, constantes: list[dict]) -> str:
    """`ok` si todo par número+unidad de la respuesta existe en la chuleta;
    `reintento` al primer par no verificado. Números sin unidad reconocida no
    se vigilan (v1, decisión 16)."""
    permitidos = {
        (_numero_canonico(str(fila["numero"])), _CANONICA.get(str(fila["unidad"]).lower(), str(fila["unidad"])))
        for fila in constantes
    }
    for par in extract_pairs(respuesta):
        if par not in permitidos:
            return "reintento"
    return "ok"
