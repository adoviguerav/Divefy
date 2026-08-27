# Modelo de datos

Contrato de datos del pipeline (F1→F4) y de sus consumidores (F5→F8, corrector).
Decidido con Adolfo el 2026-08-27 (decisiones D1–D3 al final; D3 revisada el
2026-08-28). Si el código y este documento discrepan, gana este documento o se
re-decide — nunca se deja en silencio.

## Principio rector

Los JSONL de `data/processed/` son el **system of record**. Cada colección Chroma es
una **vista materializada** de (chunks + enrich) × (corpus, tope, extras, modelo):
autocontenida para leer — F5 y el corrector no tocan JSONL en runtime — pero borrable
y 100 % regenerable siempre. La verdad nunca vive en el índice (Kleppmann, DDIA:
system of record vs. derived data).

## Entidades

| Entidad             | Fichero             | PK                     | Fuente de verdad de                                             | Derivada de             |
| ------------------- | ------------------- | ---------------------- | --------------------------------------------------------------- | ----------------------- |
| **Sección**         | `corpus.jsonl` (F1) | `(corpus, section_id)` | texto parseado + procedencia (fichero/capítulo, página, título) | los raw (`data/raw/`)   |
| **Chunk**           | `chunks.jsonl` (F2) | `id`                   | texto empaquetado + atribución `section_ids` + `n_tokens`       | Secciones               |
| **Enriquecimiento** | `enrich.jsonl` (F3) | `id` (FK→Chunk, 1:1)   | `contexto` y `preguntas` generados                              | Chunk + Gemini          |
| **Fila de índice**  | Chroma (F4)         | `id` de fila           | **nada** — 100 % derivada                                       | Chunk + Enriquecimiento |

Relaciones:

- Chunk **N:M** Sección vía `section_ids` (solapamiento por posición de caracteres).
- Enriquecimiento **1:1** Chunk de prosa (`id` compartido; `fingerprint` es clave de
  caché de F3 sobre `texto`, no un dato del chunk — no sale de `enrich.jsonl`).
- Fila hype **N:1** Chunk vía `parent_chunk_id`.

## Esquemas por entidad

### Sección — `corpus.jsonl`

`corpus` (`apuntes`/`manual`) · `section_id` (`fichero#sección` en apuntes, `9-3.2` en
manual) · `titulo` · `tipo` (`prosa`/`puntero_tabla`) · `texto` · `fichero` (null en
manual) · `capitulo`, `pagina`, `pagina_fin` (null en apuntes).

### Chunk — `chunks.jsonl`

`id` (de contenido: section_ids unidas por `|`, sufijo `#i` si el splitter partió) ·
`corpus` · `section_ids` (lista, nunca vacía) · `titulo` (de la primera sección de
origen) · `tipo` · `texto` · `fichero` · `capitulo` · `pagina` · `pagina_fin` ·
**`n_tokens`** (tokens BGE-M3 de `texto`, contados en F2 con el mismo tokenizador del
tope — sirve a la métrica "tokens recuperados" del corrector sin re-tokenizar en eval).

### Enriquecimiento — `enrich.jsonl`

`id` (FK→Chunk) · `fingerprint` (caché F3) · `contexto` (str) · `preguntas` (lista).

### Fila de índice — Chroma

Colección canónica `{corpus}-{tope}-{extras}-{modelo}` (`p4_vectorstore.canonical_name`).
Cada fila tiene tres caras que **no tienen por qué coincidir**:

- `embedding` — con qué te encuentran. Vector de `embed_text`, que es **efímero**: no
  se persiste. En contextual/hype-chunk es `contexto + "\n\n" + texto`; en hype-pregunta
  es la pregunta.
- `document` — qué devuelves. **Siempre el `texto` crudo del chunk** — en filas
  hype-pregunta, el del chunk padre (la pregunta nunca se le enseña a nadie: vive en
  metadata para el modo dev).
- `metadata` — qué sabes del resultado sin ir a ningún otro sitio.

Metadata de **fila chunk** (base/contextual/hype), cada campo con su consumidor:

| Campo                              | Tipo en Chroma             | Consumidor                                                                          |
| ---------------------------------- | -------------------------- | ----------------------------------------------------------------------------------- |
| `entry_type` = `"chunk"`           | str                        | F5: regla HyPE→padre                                                                |
| `corpus`                           | str                        | corrector: recall por corpus · guardarraíl: procedencia PADI/Navy · filtros `where` |
| `section_ids`                      | str (JSON)                 | corrector: recall@k por sección · citas                                             |
| `titulo`                           | str                        | F7/F8: cita de fuente, `/fuentes`                                                   |
| `fichero`                          | str — omitido en manual    | cita de fuente                                                                      |
| `capitulo`, `pagina`, `pagina_fin` | int — omitidos en apuntes  | cita de fuente                                                                      |
| `n_tokens`                         | int                        | corrector: tokens recuperados                                                       |
| `contexto`                         | str — solo contextual/hype | F8 modo dev                                                                         |

Metadata de **fila hype-pregunta** (D3): la misma metadata que la fila chunk de su
padre en esa colección (incluido `contexto`), más tres campos propios:
`entry_type` = `"hype"`, `parent_chunk_id` (clave de dedup en F5) y `pregunta` (la
pregunta que se embebió — consumidor: F8 modo dev, ver _por qué_ hizo match). La fila
es autocontenida: un match devuelve directamente el texto del padre y toda su
procedencia, sin segundo `get`. La regla HyPE→padre queda reducida a dedup por
`parent_chunk_id` conservando la mejor posición.

Reglas de codificación (restricción dura de Chroma: metadata solo escalar, sin listas
ni `None`):

- Listas → JSON string (`json.dumps`); el consumidor decodifica con `json.loads`.
- Campos a `None` → **se omiten** en esa fila, nunca se escriben como null/centinela.
- `tipo` NO va en metadata: todo lo indexado es prosa, campo constante sin consumidor
  (test que lo garantiza: `test_no_row_in_any_collection_uses_a_metadata_key_called_tipo`).

## Invariantes

1. Chroma se puede borrar y reconstruir por completo desde `chunks.jsonl` +
   `enrich.jsonl`. Jamás es fuente de verdad.
2. `|base| == |contextual| ==` nº de chunks de prosa del corpus;
   `|hype| ==` eso `+ Σ preguntas`.
3. `section_ids` nunca vacío en filas chunk (el recall@k de F5 depende de él).
4. Todo chunk de prosa tiene enriquecimiento (lo valida `build_rows` con error ruidoso).
5. Ids únicos por colección; ids hype = `{parent_id}::hype::{i}`.

## Decisiones (Adolfo, 2026-08-27)

- **D1 — Chroma es vista materializada, no system of record.** Autocontenida para
  leer, regenerable siempre. Motivo: 36 colecciones = 36 vistas del mismo record; los
  vectores solo tienen sentido relativos a su modelo de embedding, y el grid cambia de
  modelo. Práctica estándar (DDIA; "vector DB as cache").
- **D2 — Todo campo de metadata entra con consumidor nombrado.** Fuera `fingerprint`
  (clave de caché de F3, sin consumidor de retrieval); dentro `n_tokens` (consumidor:
  métrica de tokens del corrector). Guardar "por si acaso" es el mismo error de modelo
  en dirección contraria.
- **D3 — Filas hype autocontenidas** (revisada 2026-08-28, decisión de Adolfo —
  supersede la versión "filas mínimas" del 27): `document` = texto crudo del chunk
  padre, `embedding` = la pregunta, metadata = la del padre + `entry_type`/
  `parent_chunk_id`/`pregunta`. Motivo: la pregunta no se le enseña a nadie — guardarla
  como `document` obligaba a un `get` al padre en cada match; con el texto del padre
  como `document` la fila devuelve directamente lo útil, igual que hacen las
  implementaciones de referencia de HyPE (vector de la pregunta + chunk como payload).
  El riesgo de desincronía de las copias es nulo: cada colección se regenera entera
  (atómica) desde el system of record en cada indexado (invariante 1).
