# Métricas de retrieval y framework — decidido

**Estado**: validado por Adolfo (2026-08-28) y **aplicado al código** (2026-08-30):
`uv add ranx`, `evaluate` reescrito, tests rehechos RED→GREEN, suite completa 143
passed con el acceptance congelado intacto.
**Decidido en la revisión por primeros principios del gate previo al Paso 0.**

## El menú completo — Familia A: con etiquetas (deterministas, gratis)

Es nuestra familia: tenemos etiquetas auditadas. La última columna es la que
decide — qué perilla ajusta cada métrica en Divefy (y por qué entra o no):

| Métrica | Qué mide | Qué detecta que las otras no | Qué decisión alimenta en Divefy |
| --- | --- | --- | --- |
| **Hit Rate@K** (en jerga RAG la llaman "recall@k" — de ahí media confusión nuestra) | ¿Hay ≥1 trozo correcto en el top K? (sí/no por pregunta) | Lo mínimo: ¿puede encontrar lo necesario? | **ELEGIDA — la principal.** Mide la cadena entera (troceo + embeddings + búsqueda) de punta a punta: es EL número con el que se compara cada dimensión del grid; si no se mueve entre dos brazos, esa dimensión no importa |
| **Recall@K clásico** (proporcional) | De TODAS las secciones etiquetadas, ¿qué fracción trajiste? | Completitud — importa si la respuesta necesita varias secciones a la vez | **ELEGIDA.** ¿Cubres las dos doctrinas cuando PADI y Navy difieren (hay que citar ambas)? Y en la ablación: si sube al añadir el manual, el manual aporta cobertura real, no redundancia. Denominador = lo que lista la etiqueta |
| **Precision@K** | De los K trozos, ¿qué fracción es relevante? | Cuánto ruido entra al contexto del generador | **ELEGIDA.** Cuánta distracción tolerará F7; y junto a hit_rate, el codo del barrido de k (al subir k, hit_rate sube y precision baja — donde se cruzan las curvas eliges k). Ojo: 3/5 relevantes NO significa que estén en los puestos 1-3 — eso lo dice MRR |
| **F1@K** | Media armónica de P y R | Un solo número si quieres balancear ambas | Fuera — redundante: preferimos leer P y R por separado |
| **MRR** | 1/posición del primer acierto | Acierta arriba vs acierta de milagro — clave si barres k | **ELEGIDA.** Si es alto, puedes bajar k sin perder aciertos; y en F6 es lo que el reranker debe subir — si ya está alto, el reranker sobra |
| **MAP** | Precisión media en cada posición con acierto | Calidad del ranking _completo_, no solo el primero | Fuera — al generador le entra todo el top-k igual; no cambia decisiones hoy |
| **nDCG@K** | Ganancia descontada por posición; admite relevancia graduada | Con etiquetas graduadas es la reina; con binarias ≈ MAP | Fuera hoy — **apuntada para F6**: es la métrica estándar de rerankers |
| **R-Precision, Bpref** | Variantes robustas (etiquetas incompletas, R variable) | Nicho TREC; Bpref si sospechas que faltan etiquetas | Fuera — nicho con nuestras etiquetas |

Más una métrica de sistema que ninguna familia trae: **tokens recuperados** —
**ELEGIDA**, es la policía de la tabla: hit_rate y recall suben *mecánicamente*
con k y con el tope (más texto siempre "encuentra" más); sin tokens al lado, la
tabla siempre votaría "trae más". Con tokens la pregunta se vuelve honesta: ¿ese
+2 de hit_rate justifica +800 tokens por consulta en F7?

En una frase cada elegida: **hit_rate** decide *qué config gana* · **MRR** decide
*si puedes bajar k y si el reranker pinta algo* · **precision** decide *cuánto
ruido tolerarás en F7* · **recall** decide *si cubres las dos doctrinas* ·
**tokens** decide *si el precio vale la mejora*.

Desglose extra: `hit_rate` por corpus (apuntes / manual), solo sobre preguntas cuya
etiqueta tiene secciones de ese corpus — el número de la ablación "¿aporta algo el
manual?". También fuera, con motivo: **match numérico** (estaba en el plan; Adolfo
lo cortó en esta revisión — si el guardarraíl de F7 lo necesita como insumo, se
re-decide entonces con dato) y latencia (F6/F8).

## Familia B — si solo hay respuesta esperada: comparar por contenido

Sin un ID exacto contra el que comparar, hace falta decidir si el chunk recuperado
"contiene" o "sustenta" la respuesta esperada, mirando el texto. Es la familia que
RAGAS y deepeval implementan como núcleo — nosotros no la necesitamos porque
etiquetamos (la milla extra), pero queda el mapa:

| Técnica | Cómo compara | Coste | Cuándo falla |
| --- | --- | --- | --- |
| **Coincidencia literal** | Busca si el hecho o dato exacto de la respuesta esperada aparece tal cual en el texto recuperado | Gratis, determinista | Si la respuesta correcta está parafraseada de forma distinta en el corpus, no la encuentra aunque el chunk sea el correcto |
| **Similitud por embeddings** | Compara el vector del chunk recuperado contra el vector de la respuesta esperada | Barato | Es un proxy — alta similitud no garantiza que el chunk contenga el dato exacto, solo que habla de algo parecido |
| **LLM como juez** | Se le pasa al LLM el chunk recuperado + la respuesta esperada y se le pregunta si el primero sustenta la segunda | El más caro | Puede acertar en casos que los dos anteriores no pillan (paráfrasis, razonamiento), pero hereda el riesgo de sesgo o alucinación del propio juez |

## La regla única: la métrica sigue la etiqueta

La **etiqueta** es la única verdad terreno: para cada pregunta lista las secciones
que sostienen la respuesta (auditadas, 3 pasadas). Todo lo demás se deriva de ahí:

- Un chunk **cuenta** para una pregunta si su procedencia toca la etiqueta.
- `section_ids` en la metadata de cada chunk juega **dos papeles que no hay que
  mezclar**: es *procedencia* (de dónde viene el trozo — cosa del producto, para
  citar fuentes) y es el *puente* con el que un chunk demuestra que casa con la
  etiqueta (cosa de la métrica). Mismo campo, dos consumidores.

Con eso, cada métrica en humano:

- `hit_rate`, `precision`, `mrr` miran **lo que trajiste**: los k chunks, en su
  orden. Un chunk es bueno si toca la etiqueta. Aritmética sobre los k.
- `recall` mira **lo que existe**: la etiqueta dice "para esta pregunta hay N
  sitios"; se cuenta cuántos de esos N quedaron cubiertos por los k chunks.
  **El denominador es lo que lista la etiqueta.** Ni más ni menos.

### Por qué el denominador del recall NO puede ser "chunks"

Dato real del corpus (medido 2026-08-28): de las 129 secciones etiquetadas, **55
(43%) viven partidas en más de un chunk** — hay una repartida en 10. Si el recall
dividiera entre chunks: traes 1 de esos 10, ya tienes la respuesta… y puntúas
1/10. Para el 100% tendrías que traer las 10 copias parciales. Absurdo.

Segundo motivo: el barrido de tope de F9 (256/1024). Con tope más pequeño las
secciones se parten en MÁS chunks → un denominador en chunks crece solo → el
recall bajaría mecánicamente sin que el recuperador sea peor. Incomparable entre
topes. El denominador de la etiqueta es la misma vara para todos — la misma razón
por la que las etiquetas se hicieron sobre secciones: sobreviven a cualquier
re-chunking.

### Un caso borde, decidido

Una pregunta cuya etiqueta vive entera en el OTRO corpus (hoy: q140, solo manual)
evaluada sobre una colección de apuntes **cuenta como fallo, no se excluye**: que
un corpus no pueda responder una pregunta es exactamente lo que la ablación de
corpus tiene que medir.

`sin_respuesta` (hoy: 0 preguntas): sin sección correcta no hay métrica de
ranking definible — fuera de los agregados, presente en el `detalle`.

## Framework: ranx

| Métrica elegida | RAGAS | DeepEval | ranx |
| --- | --- | --- | --- |
| hit_rate@k | ✗ | ✗ | ✓ |
| recall@k | ~ (por IDs, sin ranking) | solo juez LLM | ✓ |
| precision@k | ~ (por IDs) | solo juez LLM | ✓ |
| mrr@k | ✗ (no existe) | ✗ | ✓ |

- RAGAS y deepeval son frameworks de eval RAG que **asumen que no tienes
  etiquetas** — por eso su núcleo es juez LLM o similitud de strings. Nosotros
  fuimos la milla extra: etiquetas auditadas → familia clásica de IR, gratis y
  determinista. RAGAS cubriría solo 2 de las 5 → dos frameworks para cuatro
  números, más su peso de dependencias. Descartado por eso, no por manía.
- **ranx** es la reimplementación moderna de la familia trec_eval (el estándar
  académico desde los 90; `pytrec_eval` es el envoltorio del original, lo usan
  BEIR y MTEB). Mismos números, API cómoda, y de regalo comparación de runs y
  tests estadísticos para la tabla del grid. Docs: <https://amenra.github.io/ranx/>.
- Tokens no lo trae ningún framework: métrica de sistema, 3 líneas nuestras.

Regla de la casa que esto respeta (y queda para el futuro): **librería estándar
siempre que exista; código propio solo cuando es lo único posible.** Aquí lo
único sin librería posible es tokens y el pegamento etiqueta↔chunk.

## El código (lo que se aplicará a `corrector.py`)

Una sola fuente de cálculo: los agregados salen SOLO de ranx (nada de recalcular
a mano en paralelo — dos cálculos de lo mismo es esperar una discrepancia). El
`detalle` por pregunta queda en crudo: `{id, recuperados, tokens, sin_respuesta}`.

```python
from ranx import Qrels, Run, evaluate as ranx_evaluate

def evaluate(golden, labels_by_id, retrieved_by_id, chunk_sections, chunk_tokens, k):
    """chunk_sections: {chunk_id: set(section_ids)} de las filas chunk de la
    colección (una sola llamada collection.get() en run()); chunk_tokens: ídem
    con n_tokens. La métrica sigue la etiqueta (ver arriba)."""
    detalle, qrels_c, run_c, qrels_s, run_s = [], {}, {}, {}, {}
    tokens_total = 0
    for pregunta in golden:
        qid, label = pregunta["id"], labels_by_id[pregunta["id"]]
        recuperados = retrieved_by_id[qid]
        tokens = sum(chunk_tokens[cid] for cid in recuperados)
        tokens_total += tokens
        detalle.append({"id": qid, "recuperados": recuperados, "tokens": tokens,
                        "sin_respuesta": label["sin_respuesta"]})
        etiquetadas = set(label["secciones_apuntes"]) | set(label["secciones_manual"])
        if not etiquetadas:          # sin_respuesta: fuera de los agregados
            continue
        relevantes = {cid: 1 for cid, secs in chunk_sections.items() if secs & etiquetadas}
        # etiqueta entera en otro corpus → ningún chunk de ESTA colección puede ser
        # relevante; centinela para que la pregunta cuente como fallo, no como crash
        qrels_c[qid] = relevantes or {"__sin_cobertura__": 1}
        run_c[qid] = {cid: 1.0 / rank for rank, cid in enumerate(recuperados, 1)}
        qrels_s[qid] = {sid: 1 for sid in etiquetadas}       # el denominador ES la etiqueta
        cubiertas = {}
        for rank, cid in enumerate(recuperados, 1):
            for sid in chunk_sections.get(cid, ()):
                cubiertas.setdefault(sid, 1.0 / rank)         # mejor posición
        run_s[qid] = cubiertas

    scores = ranx_evaluate(Qrels(qrels_c), Run(run_c),
                           [f"hit_rate@{k}", f"precision@{k}", f"mrr@{k}"])
    resumen = {
        "hit_rate": round(scores[f"hit_rate@{k}"], 4),
        "recall": round(ranx_evaluate(Qrels(qrels_s), Run(run_s), "recall"), 4),
        "precision": round(scores[f"precision@{k}"], 4),
        "mrr": round(scores[f"mrr@{k}"], 4),
        # + hit_rate_apuntes / hit_rate_manual: mismas dos líneas con la etiqueta
        #   filtrada a un corpus, solo preguntas con secciones de ese corpus
        "tokens_recuperados_media": round(tokens_total / len(golden), 2),
        "n_preguntas": len(golden),
    }
    return resumen, detalle
```

## Qué cambia al aplicar (y qué no)

- `uv add ranx` (única dependencia nueva).
- `corrector.py`: el interior de `evaluate` (arriba); `run()` pasa a una sola
  llamada `collection.get()` (saca procedencia y `n_tokens` de las filas chunk);
  muere `extract_numbers`. `write_result`, CLI: sin cambios.
- `tests/unit/test_corrector_core.py`: se rehacen contra las claves nuevas,
  mismo fixture a mano con los valores esperados recalculados a mano.
- **El acceptance congelado no se toca**: solo verifica determinismo byte a byte
  y nº de entradas del detalle — inmune al cambio de métricas.
- Sync de papeles: PRD y EXPERIMENTOS (línea del juez de F5), Notas del plan.
- Determinismo intacto: ranx es determinista con las mismas entradas.
