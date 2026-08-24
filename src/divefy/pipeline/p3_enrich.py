"""Fase 3 — Extras de índice: contextual retrieval y HyPE encadenado (Gemini Flash, offline, cacheado)."""

import hashlib
import json
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from divefy.pipeline.p2_chunking import cargar_tokenizer_bge_m3

# gemini-2.5-flash y gemini-2.5-flash-lite quedaron retirados para cuentas nuevas
# (verificado en vivo 2026-08-24, la propia API redirige al modelo actual).
# gemini-3.1-flash-lite: mismo trabajo (frase de contexto + preguntas simples) a
# $0.25/$1.50 por millón de tokens frente a $0.75/$3.75 de gemini-3.6-flash — probado
# en vivo sobre chunks reales del cap 9, calidad equivalente (ver plan de Fase 3).
MODELO_ENRIQUECEDOR = "gemini-3.1-flash-lite"

TOPE_CONTEXTO = 100  # tokens BGE-M3 — mismo tope que el resto del grid (Fase 2)
REINTENTOS = 1  # si el modelo no cumple el contrato, un solo reintento; si no, error


def _tokenizer():
    if not hasattr(_tokenizer, "_cache"):
        _tokenizer._cache = cargar_tokenizer_bge_m3()
    return _tokenizer._cache


def _contar_tokens(texto: str) -> int:
    return len(_tokenizer().tokenize(texto))


# Cliente perezoso: se construye la primera vez que de verdad hace falta (dentro de
# generar_contexto/generar_preguntas_hype), nunca en enriquecer. Así, cuando un test
# sustituye esas dos funciones por otras falsas (como el de determinismo con caché),
# genai.Client() no se construye nunca y el test no depende de tener una API key real.
_cliente_gemini: genai.Client | None = None


def _cliente() -> genai.Client:
    global _cliente_gemini
    if _cliente_gemini is None:
        load_dotenv()
        _cliente_gemini = genai.Client()
    return _cliente_gemini


_PROMPT_CONTEXTO = (
    "<chunk>\n{chunk_texto}\n</chunk>\n"
    "Please give a short succinct context to situate this chunk within the overall "
    "document for the purposes of improving search retrieval of the chunk. Answer "
    "only with the succinct context and nothing else."
)
_RECORDATORIO_CONTEXTO = "\n\nYour previous answer was too long — answer in ONE short sentence."

# documento (texto) -> nombre de la caché de Gemini ya creada para él. El documento
# padre es el mismo para decenas de chunks (todo un capítulo/fichero); sin esto se
# reenviaría entero en cada llamada de contexto — probado en vivo: dominaba el coste
# de la pasada completa (~9,6M de los ~9,8M tokens de entrada). Cachear el documento
# una vez (probado en vivo, funciona incluso con el fichero más pequeño, ~3k tokens —
# sin mínimo detectado) lo factura a $0.025/M en vez de $0.25/M. TTL 2h: de sobra para
# la pasada completa (el capítulo más grande tarda minutos, no horas) con margen.
_cache_de_documento: dict[str, str] = {}


def _cache_para(documento: str, cliente: genai.Client) -> str:
    clave = hashlib.sha256(documento.encode()).hexdigest()
    nombre = _cache_de_documento.get(clave)
    if nombre is None:
        cache = cliente.caches.create(
            model=MODELO_ENRIQUECEDOR,
            config={"contents": [f"<document>\n{documento}\n</document>"], "ttl": "7200s"},
        )
        nombre = cache.name
        _cache_de_documento[clave] = nombre
    return nombre


def generar_contexto(documento: str, chunk_texto: str, cliente: genai.Client | None) -> str:
    """Frase que sitúa el trozo dentro de su documento padre (prompt calcado del de
    Anthropic para contextual retrieval, ver Hallazgos del plan de Fase 3). Valida el
    tope de tokens contra el mismo tokenizador BGE-M3 del resto del grid; un
    incumplimiento se reintenta una vez antes de rendirse."""
    cliente = cliente or _cliente()
    prompt = _PROMPT_CONTEXTO.format(chunk_texto=chunk_texto)
    cache_nombre = _cache_para(documento, cliente)

    for intento in range(REINTENTOS + 1):
        respuesta = cliente.models.generate_content(
            model=MODELO_ENRIQUECEDOR,
            contents=prompt + (_RECORDATORIO_CONTEXTO if intento else ""),
            config={"cached_content": cache_nombre, "max_output_tokens": 300},
        )
        texto = (respuesta.text or "").strip()
        if texto and _contar_tokens(texto) <= TOPE_CONTEXTO:
            return texto

    raise ValueError(f"contexto fuera de contrato tras {REINTENTOS + 1} intentos: {texto!r}")


_PROMPT_HYPE = (
    "<chunk>\n{chunk_contextualizado}\n</chunk>\n"
    "Generate between 3 and 5 questions that a reader could ask, whose answer is "
    "found in this chunk."
)
_ESQUEMA_PREGUNTAS = types.Schema(type="ARRAY", items=types.Schema(type="STRING"), min_items=3, max_items=5)


def generar_preguntas_hype(chunk_contextualizado: str, cliente: genai.Client | None) -> list[str]:
    """3-5 preguntas hipotéticas que este trozo respondería. `chunk_contextualizado`
    es el texto del trozo con su frase de contexto (generar_contexto) ya delante —
    encadenado, no se vuelve a pasar el documento entero (ver Decisiones del plan).
    Salida forzada a JSON con schema (array de 3-5 strings); aun así se revalida antes
    de aceptarla — un schema hace más probable el contrato, no lo garantiza."""
    cliente = cliente or _cliente()
    prompt = _PROMPT_HYPE.format(chunk_contextualizado=chunk_contextualizado)

    for _intento in range(REINTENTOS + 1):
        respuesta = cliente.models.generate_content(
            model=MODELO_ENRIQUECEDOR,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": _ESQUEMA_PREGUNTAS,
            },
        )
        try:
            preguntas = [p.strip() for p in json.loads(respuesta.text or "[]")]
        except json.JSONDecodeError:
            preguntas = []
        preguntas = [p for p in preguntas if p]
        if 3 <= len(preguntas) <= 5 and len(set(preguntas)) == len(preguntas):
            return preguntas

    raise ValueError(f"preguntas fuera de contrato tras {REINTENTOS + 1} intentos: {preguntas!r}")


def documento_padre(chunks: list[dict], capitulo: int | None, fichero: str | None) -> str:
    """Concatena la prosa (tipo=='prosa') del mismo padre, en orden de lectura.

    El padre es (capitulo, fichero): para el manual, capitulo fija el capítulo y
    fichero es siempre None; para apuntes, al revés. Orden: por 'pagina' cuando existe
    (manual); los chunks de apuntes no tienen 'pagina' (None -> 0), así que el sort
    (estable) conserva su orden de aparición en la lista de entrada, que ya es el de
    lectura (ver Hallazgos del plan de Fase 3: los punteros de tabla se cuelan al final
    del fichero si no se filtra por tipo=='prosa' primero, por eso el filtro va antes)."""
    del_padre = [
        c
        for c in chunks
        if c["tipo"] == "prosa" and c["capitulo"] == capitulo and c["fichero"] == fichero
    ]
    ordenados = sorted(del_padre, key=lambda c: c["pagina"] or 0)
    return "\n\n".join(c["texto"] for c in ordenados)


def _huella(texto: str) -> str:
    """Fingerprint corto del texto del chunk: el id (por sección) es estable a través
    de un re-parseo trivial (un typo corregido), pero eso no debería significar que el
    caché sigue siendo válido. La huella detecta ese caso; el id solo identifica."""
    return hashlib.sha256(texto.encode()).hexdigest()[:16]


def _leer_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def enriquecer(chunks_path: Path, processed_dir: Path) -> None:
    """Genera contexto + preguntas HyPE para cada chunk de prosa de chunks_path,
    cacheando en processed_dir/enrich.jsonl: si un id ya tiene línea ahí Y su huella
    coincide con el texto actual, no se regenera (el id identifica la sección, la
    huella detecta si su texto cambió desde la última pasada). Cada fila se escribe en
    cuanto se genera (no se pierde si la pasada se corta a mitad); al terminar se
    reescribe el fichero ordenado por id y sin filas huérfanas (ids que ya no existen
    en chunks_path)."""
    if not chunks_path.exists():
        raise FileNotFoundError(f"no existe {chunks_path} — ¿ruta correcta? ¿corrió ya la Fase 2?")
    chunks = _leer_jsonl(chunks_path)

    enrich_path = processed_dir / "enrich.jsonl"
    cache = {fila["id"]: fila for fila in _leer_jsonl(enrich_path)}

    prosa = sorted((c for c in chunks if c["tipo"] == "prosa"), key=lambda c: c["id"])
    padres: dict[tuple, str] = {}

    processed_dir.mkdir(parents=True, exist_ok=True)
    with enrich_path.open("a", encoding="utf-8") as salida:
        for c in prosa:
            huella = _huella(c["texto"])
            if c["id"] in cache and cache[c["id"]].get("fingerprint") == huella:
                continue

            padre_clave = (c["capitulo"], c["fichero"])
            if padre_clave not in padres:
                padres[padre_clave] = documento_padre(chunks, c["capitulo"], c["fichero"])

            contexto = generar_contexto(padres[padre_clave], c["texto"], None)
            contextualizado = f"{contexto}\n\n{c['texto']}"
            preguntas = generar_preguntas_hype(contextualizado, None)

            fila = {"id": c["id"], "fingerprint": huella, "contexto": contexto, "preguntas": preguntas}
            cache[c["id"]] = fila
            salida.write(json.dumps(fila, ensure_ascii=False) + "\n")
            salida.flush()

    # Reescritura final ordenada por id: recorre solo `prosa` (los chunks vigentes de
    # chunks_path), así que cualquier fila de `cache` que venga de una pasada anterior
    # sobre un chunks_path distinto (ids que ya no existen) queda podada sola.
    with enrich_path.open("w", encoding="utf-8") as f:
        for c in prosa:
            f.write(json.dumps(cache[c["id"]], ensure_ascii=False) + "\n")


def main() -> None:
    enriquecer(Path("data/processed/chunks.jsonl"), Path("data/processed"))


if __name__ == "__main__":
    main()
