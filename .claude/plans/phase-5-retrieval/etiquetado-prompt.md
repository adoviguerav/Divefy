# Prompt de etiquetado — labels.jsonl (T-03, Fase 5)

Artefacto versionado de la fase (Decision 4): el prompt es el entregable; la sesión
que lo ejecuta, no. Ejecutado el 2026-08-28 por una sesión de Claude (agentes por
lote + reconciliación), auditado por Adolfo (regla ≤2 mal sobre ~25-30).

## Mecánica de ejecución

El corpus completo (~818K chars) no cabe en una sesión con atención decente, así que
la sesión se parte en **6 lotes** que juntos SÍ leen el corpus completo (sin
retriever de por medio → sin circularidad con el sistema evaluado):

| Lote | Contenido                    | Tamaño aprox. |
| ---- | ---------------------------- | ------------- |
| A    | apuntes completos            | 117K chars    |
| M1   | manual caps 2, 4, 6          | 161K chars    |
| M2   | manual cap 3                 | 157K chars    |
| M3   | manual caps 9, 10, 14        | 150K chars    |
| M4   | manual caps 7, 11            | 133K chars    |
| M5   | manual cap 17                | 101K chars    |

Cada lote recibe: las 84 preguntas de eval (id, pregunta, respuesta esperada) + sus
secciones (solo las **alcanzables**: presentes en `section_ids` de algún chunk de
prosa de `chunks.jsonl` — una etiqueta sobre una sección solo-tabla sería
irrecuperable por construcción). Después, una pasada de **reconciliación** fusiona
los lotes, aplica la regla doctrinal y decide `sin_respuesta`.

## Prompt por lote

> Eres una sesión de etiquetado para el eval de un RAG de seguridad en buceo. Tu
> trabajo produce la clave de corrección del examen: la calidad manda sobre la
> velocidad.
>
> Entrada (dos ficheros que debes leer enteros):
>
> - `preguntas.json` — las 84 preguntas del eval: `id`, `pregunta`,
>   `respuesta_esperada` (la respuesta correcta según doctrina PADI).
> - `secciones-{LOTE}.json` — las secciones de tu lote: `section_id`, `titulo`,
>   `texto`.
>
> Tarea: para CADA una de las 84 preguntas, en orden, encuentra las secciones de tu
> lote cuyo TEXTO contiene la información necesaria para dar la respuesta esperada.
>
> Reglas duras:
>
> 1. **Evidencia o nada.** Una sección solo se etiqueta si puedes citar el pasaje
>    textual que sostiene la respuesta. "Habla del tema" no es evidencia; la cita
>    debe permitir responder lo que la pregunta pregunta.
> 2. **Trabajo sistemático**: pregunta a pregunta, las 84, en orden. Ninguna se
>    salta; si en tu lote no hay soporte para una pregunta, su lista queda vacía.
> 3. **Todas las secciones que sostengan la respuesta**, no solo la mejor: el
>    recall@k acierta si CUALQUIERA de ellas aparece — omitir una válida penaliza
>    injustamente al retriever.
> 4. **`section_id` literal** del fichero de entrada, copiado tal cual. Nunca
>    inventes ni recortes ids.
> 5. **Números**: si la pregunta o la respuesta esperada llevan un valor numérico
>    (velocidad, profundidad, tiempo, presión, proporción), extrae en `valor` el
>    valor que da TU sección (con unidades, literal). Si tu sección da un valor
>    DISTINTO al de la respuesta esperada, etiquétala igualmente y dilo en
>    `valor` — la reconciliación decide con la regla doctrinal, tú no.
>
> Salida: escribe `labels-{LOTE}.json` — una lista JSON con exactamente 84
> entradas, en el orden de `preguntas.json`:
>
> ```json
> {
>   "id": "q001",
>   "matches": [
>     { "section_id": "…", "cita": "pasaje textual copiado", "valor": null }
>   ]
> }
> ```
>
> `matches` vacío si tu lote no sostiene la pregunta. Devuelve como mensaje final
> solo un resumen de dos líneas (nº de preguntas con matches, nº total de matches).

## Reconciliación (una pasada, con toda la evidencia delante)

1. Fusionar los 6 lotes por pregunta: `secciones_apuntes` = matches del lote A,
   `secciones_manual` = matches de M1–M5 (deduplicadas, orden estable por
   section_id).
2. **Regla doctrinal (PADI manda)**: si la pregunta pide un número y la sección
   Navy da un valor DISTINTO al PADI de la respuesta esperada, esa sección Navy
   **NO se etiqueta** (el guardarraíl jamás dejará citar ese número como respuesta
   PADI; etiquetarla premiaría recuperarlo). Se anota en `notas`. Si el valor
   coincide (misma cantidad, aunque otras unidades), se etiqueta.
3. Descartar matches cuya cita no sostenga la respuesta (control de calidad sobre
   la evidencia, no sobre la impresión).
4. `sin_respuesta = true` ⇔ tras 1–3 ambas listas quedan vacías. `notas` explica
   por qué (fuera del corpus, requiere tabla/tool, doctrinal…).
5. `q013` (`requiere_tool=true`): marcarla coherentemente — `sin_respuesta` o
   etiquetada — con el motivo en `notas`.
6. Salida final `data/eval/labels.jsonl`, una fila por pregunta, orden del golden:
   `{"id", "pregunta", "secciones_apuntes": [...], "secciones_manual": [...],
   "sin_respuesta": bool, "notas": str|null}` (sin campo `valor` ni citas — la
   evidencia es material de trabajo, no parte del contrato).

## Invariantes que el check de etiquetas fuerza (`tests/unit/test_labels.py`)

- Exactamente una fila por pregunta `uso=eval` del golden, mismos ids.
- Todo `section_id` etiquetado existe en `chunks.jsonl` y es alcanzable (aparece
  en algún chunk de prosa).
- `sin_respuesta=true` ⇔ ambas listas vacías.
- Esquema exacto: claves y tipos de la Decision 6, `notas` str o null.
