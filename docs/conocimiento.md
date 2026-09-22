# Cuaderno de conocimiento

Explicaciones y decisiones que costó entender o decidir, para releer sin tener
que volver a preguntarlas. Se lee, no se ejecuta — nada pensado para que lo
consuma una IA. Un tema por `##`, una explicación por `###`.

## Arquitectura del paquete `llm`

### ¿Por qué la gente pone la interfaz pública en `__init__.py`? — 2026-09-21

`__init__.py` es el código que corre cuando alguien importa el paquete. Por
convención de Python se usa para exponer la **interfaz pública** — lo que
quieres que la gente use — y no para esconder ahí toda la implementación. Con
`from divefy.llm import generate`, quien lo usa no necesita saber que por
dentro hay `api.py` (Anthropic) y `mlx_backend.py` (MLX local); solo ve una
función. Es una fachada: por fuera una puerta, por dentro las tuberías se
reparten como convenga.

El riesgo es meter la implementación entera dentro del `__init__.py` en vez de
solo reexportarla: crece sin límite y deja de ser una fachada, se convierte en
el edificio entero metido en la puerta. El patrón sano: implementación en
submódulos, `__init__.py` solo importa y expone.

**Consecuencia práctica**: `src/divefy/llm/__init__.py` se separó en
`api.py` (backend Anthropic) + `mlx_backend.py` (backend MLX local), dejando
`__init__.py` en 30 líneas — solo las tablas `API_MODELS`/`MLX_MODELS` y el
despachador `generate()`.

### Reparto de un módulo cuando los tests hacen monkeypatch — 2026-09-21

Al separar `llm/__init__.py` en submódulos, dos tests exigían que ciertos
nombres siguieran siendo accesibles y sustituibles **a través del propio
`divefy.llm`**, no de los submódulos:

- `monkeypatch.setitem(llm._clientes, ...)` — muta un diccionario en sitio; da
  igual en qué módulo viva de verdad el diccionario, porque es el mismo objeto
  en memoria visto desde cualquier sitio que lo importe.
- `monkeypatch.setattr(llm, "_generate_mlx", fake)` — esto es distinto: **reemplaza
  el nombre entero** en el espacio de nombres de `divefy.llm`. Para que el
  parche surta efecto, la función `generate()` tiene que estar definida
  físicamente **dentro** de `__init__.py` (no en un submódulo) y llamar a
  `_generate_mlx(...)` como nombre libre — Python resuelve esa referencia en el
  momento de la llamada, contra el espacio de nombres del propio módulo donde
  vive `generate()`. Si `generate()` viviera en `mlx_backend.py`, el parche
  sobre `divefy.llm._generate_mlx` no lo vería nunca.

## Patrones de diseño Python

### Inicialización perezosa (lazy) — 2026-09-21

No construyas algo hasta el momento exacto en que lo necesitas, en vez de
construirlo "por si acaso" al arrancar. Lo contrario es la inicialización
"ansiosa" (eager): construir todo al principio, se use o no.

En `divefy.llm.api`, `_clientes = {}` empieza vacío; la primera vez que se pide
un modelo, `_cliente()` lo crea y lo guarda en el diccionario — las siguientes
llamadas reutilizan el mismo cliente. Igual en `mlx_backend` con
`_mlx_backends` y los pesos del modelo.

Por qué importa aquí en concreto:

1. **Los tests importan el módulo sin necesitar claves de API ni GPU.** Si el
   cliente se creara al importar el fichero, cualquier test fallaría por falta
   de `ANTHROPIC_API_KEY` aunque no le importe esa parte. Con carga perezosa,
   importar es gratis; solo se paga al llamar de verdad a `generate()`.
2. **Reutilización entre llamadas.** Sin la caché, cada pregunta del examen (84
   por pasada) recargaría 6GB de pesos desde cero. Con ella, se carga una vez y
   el resto es instantáneo en esa parte.

## Caché KV en MLX — framework, código y por qué no nos sirvió aquí

### La base conceptual: por qué existe una caché KV — 2026-09-21

Cuando un transformer genera texto, cada palabra nueva se calcula mirando
**todas** las palabras anteriores. Por dentro, para cada palabra ya leída el
modelo calcula dos vectores llamados **Key** (K) y **Value** (V) — la huella
de esa palabra vista desde la atención del modelo. Para predecir la palabra
siguiente, el modelo compara la palabra actual contra las Keys de todo lo
anterior, y mezcla las Values según ese parecido.

Punto clave: las K/V de una palabra ya procesada **no cambian nunca**, venga
lo que venga después. Recalcularlas en cada paso sería trabajo tirado — se
guardan la primera vez que se calculan. Esa tabla guardada es la caché KV.

Dos fases de cualquier generación:
- **Prefill**: procesar el prompt de entrada, de una vez, en paralelo sobre
  todos sus tokens — rápido.
- **Decode**: producir cada palabra nueva, una a una; la palabra N necesita el
  resultado de la N-1, así que es forzosamente secuencial — una pasada entera
  del modelo por palabra. Esto es lo lento de verdad, y ninguna caché lo
  acelera (ver más abajo).

### El framework: `mlx_lm.models.cache` — 2026-09-21

Interfaz común de la que heredan todos los tipos de caché:

```python
class _BaseCache:
    state: ...          # los datos crudos guardados (getter/setter)
    def is_trimmable(self) -> bool: return False   # por defecto NO
    def trim(self, n): ...   # solo tiene sentido si is_trimmable() es True
    def size(self) -> int: ...
    def empty(self) -> bool: ...
```

Tipos concretos que aparecieron al investigar:
- **`KVCache`**: el caso estándar — Key/Value que crecen token a token con un
  contador `.offset`. Es trimmable.
- **`ArraysCache`**: lo que construye Qwen3.5 (`model.make_cache()` decide el
  tipo, no se elige a mano). Guarda una lista de arrays sin el concepto de
  offset creciente de `KVCache`, y **no sobreescribe `is_trimmable()`** — se
  queda en `False`. Confirmado leyendo su código fuente completo: no hay
  ningún método `.trim()` en la clase.
- **`RotatingKVCache`**: solo guarda los últimos N tokens (contextos largos) —
  no se usó aquí.

Funciones de la librería:

```python
make_prompt_cache(modelo)        # construye la caché del TIPO que pida el modelo
can_trim_prompt_cache(cache)     # ¿todas las capas son trimmable?
trim_prompt_cache(cache, n)      # recorta n tokens si se puede; si no, no-op
save_prompt_cache(fichero, cache)  # serializa la caché entera a .safetensors
load_prompt_cache(fichero)         # y la recupera, para reusarla en OTRA ejecución
```

El generador de bajo nivel, la pieza que resuelve "calentar sin generar nada
de más" (técnica de la CLI oficial `mlx_lm.cache_prompt`):

```python
from mlx_lm.generate import generate_step
for _ in generate_step(tokens, modelo, max_tokens=0, prompt_cache=cache):
    pass
# max_tokens=0: procesa `tokens` (los mete en la caché) y NO genera nada.
# Es la fase de prefill aislada, sin decode.
```

### La solución: clonar en vez de recortar — 2026-09-21

Como `ArraysCache` no sabe recortarse, la idea (de Adolfo) fue: calentar la
caché **una vez** con el system prompt, y para cada pregunta usar una
**copia** de ese estado — se tira después de usarla, nunca hace falta
recortar nada.

```python
_MARCADOR = "\x00PLACEHOLDER\x00"

def _prefix_tokens(tokenizer, system: str) -> list[int] | None:
    """La plantilla de Qwen exige un turno de usuario para renderizar —
    apply_chat_template con solo `system` revienta ('No user query found in
    messages'). Se renderiza con un usuario marcador, se corta el STRING justo
    antes de su contenido, y ese trozo se tokeniza directo con encode() — sin
    pasar por la validación de roles. Se verifica contra un render real antes
    de fiarse; si no coincide, se descarta (correctness first)."""
    render = tokenizer.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": _MARCADOR}],
        add_generation_prompt=True, tokenize=False,
    )
    if _MARCADOR not in render:
        return None
    prefijo = tokenizer.encode(render[: render.index(_MARCADOR)])
    real = tokenizer.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": "x"}],
        add_generation_prompt=True,
    )
    return prefijo if real[: len(prefijo)] == prefijo else None


def _prime_cache(modelo, prefijo):
    cache = make_prompt_cache(modelo)
    for _ in generate_step(mx.array(prefijo), modelo, max_tokens=0, prompt_cache=cache):
        pass
    return cache


def _clone_cache(modelo, cache_base):
    """Copia superficial: basta, porque MLX nunca muta un array existente —
    cualquier operación crea uno nuevo (como en JAX). Verificado: generar con
    la copia no toca el estado de la base (comparado array a array)."""
    copia = make_prompt_cache(modelo)  # objeto vacío del tipo correcto, sin cómputo
    for dst, src in zip(copia, cache_base):
        v = src.state
        dst.state = list(v) if isinstance(v, list) else v
    return copia
```

**Comprobado con dato, no solo con teoría**: generar con la copia da texto
idéntico byte a byte a generar sin caché desde cero, para preguntas de
respuesta corta y única. Con preguntas largas y abiertas, no siempre sale
idéntico — no es un fallo, ver la nota de coma flotante más abajo.

### El trade-off: qué se valoró y qué se decidió — 2026-09-21

Medido con el system prompt real (`generation_v2.txt`, 3552 caracteres) y 8
preguntas reales: **20.5s con caché vs 21.0s sin caché — ahorro del 2%.**
Prácticamente nada, pese a que la implementación funcionaba bien.

Por qué: el cuello de botella no es procesar el prompt (prefill, lo que se
cacheaba), es generar la respuesta (decode, secuencial por naturaleza —
ninguna caché lo toca). Y en el pipeline real, el prompt de usuario no es solo
la pregunta: lleva pegados los 10 fragmentos recuperados del RAG, mucho más
texto que el system fijo, y esos no se pueden cachear porque cambian en cada
pregunta. La caché del system solo cubría una fracción pequeña del trabajo
real de cada llamada.

Coste añadido a cambio de ese 2%: más código (unas 60 líneas), y una fuente
real de no-determinismo — dividir el cálculo en prefijo+resto cambia
ligeramente el orden de las operaciones de coma flotante; con `temp=0`
(voraz) esto en teoría no debería cambiar el resultado, pero en un empate muy
ajustado entre dos palabras candidatas ese ruido mínimo puede volcar la
elección hacia otra — una vez que una palabra difiere, el resto de la
respuesta diverge desde ahí. Fenómeno conocido y aceptado en cualquier
sistema de caché de prefijos en IA (vLLM, TGI, etc. lo tienen igual); no
invalida la respuesta, solo significa que dos generaciones "iguales" no
siempre son bit a bit idénticas.

**Decisión**: no compensa mantenerlo para este pipeline (prompt moderado,
contexto RAG variable, respuestas largas). Quedaría bien en un caso con la
forma contraria: prompt grande y fijo, respuestas cortas. Código comentado
en `mlx_backend.py` para no perder el trabajo si algún día cambia la forma
del problema.
