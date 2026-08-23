El proceso de convertir documentos en información que una máquina pueda entender y trabajar con ella (para RAG o para info estructurada)


## PASO 0: Entender lo básico

Dos preguntas
### ¿Qué tipo de documento es?

- **Nativo**: tiene texto real debajo (se selecciona y copia).
- **Escaneado**: es imagen, hace falta OCR.
- **Mixto**: partes de cada tipo.

Se comprueba abriendo 3-5 páginas, no hace falta más.

### 2. ¿Qué salida necesitas?

- **Documento legible**: reconstruir el contenido en markdown, para lectura humana o RAG. Estructura (capítulos, tablas) preservada como bloques.
- **Datos estructurados**: rellenar un esquema fijo que se repite (facturas, shipments, formularios). Destino es una base de datos, no un documento.

Esta pregunta pesa más que la primera: si la fallas, da igual que hayas acertado el tipo de documento.


### Algún detalle más?
Nada de esto sustituye mirar el documento de verdad: páginas de muestra, los campos que quieres extraer, cómo vienen las tablas. Todo lo que sigue es qué hacer con lo que veas, no un atajo para no mirarlo.
- fijarte en como está estructurado, si hay patrones que pueden aprovecharse, si hay complicaciones como tablas partidas...


## Paso 1: Elijo mi situación base

De donde parto, vaya. La idea es elegir e implementar lo más simple. Incluso elegir dos, y probar.

| Tipo de documento                                          | → Documento legible (md para RAG)                             | → Datos estructurados                                                             |
| ---------------------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Texto puro, layout simple                                  | PyMuPDF4LLM / pdfplumber                                      | Extraer texto en md + LLM con schema (sin visión, barato)                         |
| Texto puro, layout complejo (multi-columna, tablas densas) | Docling / Marker                                              | VLM por página + schema, o LlamaParse Extract / Reducto si no quieres montarlo tú |
| Escaneado                                                  | Docling con OCR, o VLM si el layout es difícil                | VLM + schema (obligatorio, no hay texto nativo)                                   |
| Mixto                                                      | Routing: clásico por defecto, VLM solo en páginas donde falla | Igual: clásico por defecto, VLM solo en páginas donde falla                       |
- **PyMuPDF4LLM / pdfplumber** (fila "nativo, layout simple"): librerías de Python, sin IA de ningún tipo, leen el texto que ya está dentro del PDF. Gratis, instantáneo.
- **Docling** (fila "nativo, layout complejo" y "escaneado"): librería gratuita de IBM. Detecta columnas, tablas y títulos con sus propios modelos entrenados para eso, sin necesitar un LLM. Con su modo OCR activado, también convierte una página escaneada en texto.
- **VLM** (cuando Docling no basta, o en la columna "datos estructurados"): un modelo de IA al que le enseñas la imagen de la página y "la mira" como lo haría una persona, devolviendo lo que le pidas — texto en orden, o campos concretos si le das un schema. Puede ser uno grande de propósito general (Gemini, GPT, Claude) o uno especializado y más barato (PaddleOCR-VL).
- **LlamaParse / Reducto** (si no quieres montar tú nada de lo anterior): servicios de pago. Les mandas el PDF por API, ellos deciden por dentro si usan la técnica clásica o un VLM, y te devuelven el resultado ya parseado. Pagas por ahorrarte programar el pipeline.

#### ojo 
Layout simple vs complejo. El simple es si el texto extraido ennplano sale en el orden que lo lees visualmente.  Un PDF puede dejarte seleccionar texto con el cursor y aun así ser complejo, si está posicionado como grid (columnas, campos en paralelo) sin que el PDF lo marque como tabla. Bloques apilados (uno encima de otro) tienen mucho menos riesgo que columnas lado a lado: leer de arriba a abajo suele respetar el orden del stream, el fallo clásico es izquierda-derecha. 
- La prueba es barata: extrae texto plano de 2-3 páginas con `extract_text()` y mira si sale legible o mezclado; si sale limpio, texto + LLM con schema basta, sin visión

## Decisiones de diseño (antes de programar nada)

- **¿Y si solo quiero unas páginas concretas?**: si solo necesitas unas páginas o capítulos, contiguos o sueltos, corta el PDF antes de parsear, no después. Localiza los rangos con el índice/outline embebido (`get_toc()` en PyMuPDF, `get_outline()` en pypdf), construye un PDF nuevo solo con esas páginas (`.select()` / `PdfWriter`), y parsea ese subconjunto. El parser no necesita saber que hubo páginas fuera.

- **¿Y si no se si guardar las tablas o no?**: nunca decidas en el momento de parsear qué te quedas (tablas sí, tablas no, cualquier otro filtro). Parsea una vez a una estructura completa con todo etiquetado, y aplica el filtro cada vez que lees esa estructura. Si tiras algo al parsear, recuperarlo significa parsear el documento entero otra vez.

- **¿Como guardo la página de origen del documento?**: vive en el objeto parseado (`item.prov` en Docling), no en el markdown exportado — el markdown no lleva metadata. Si necesitas trazabilidad, construye tu propia lista de {texto, página} iterando los items, no dependas de exportar por página (eso corta párrafos y tablas que cruzan el salto).

- **Tablas partidas entre páginas**: no esperes que el parser las una solo. Docling, por ejemplo, no fusiona por defecto una tabla que cruza el salto de página (limitación conocida, igual en Azure Document Intelligence); te da dos tablas separadas. Si la necesitas entera, detectas la continuación tú (mismas columnas, sin cabecera repetida) y concatenas a mano. MinerU es la excepción: fusiona por defecto, aunque solo conserva la página del primer trozo, perdiendo granularidad de a qué página pertenece cada fila de la continuación.

- **Ruido repetido** (cabeceras, pies de página, numeración): descártalo antes de chunkear, no lo dejes colarse en cada chunk. Se detecta fácil porque se repite casi igual en cada página.

## Cómo saber si funcionó

**¿Qué hacer al detectar un fallo?** (en el momento, sin ground truth de ese documento)

Señales gratis:

- Confidence score del parser/OCR, si lo expone (Docling, LlamaParse, Textract).
- Texto vacío o gibberish en una página con contenido visible.
- Tabla con número de columnas inconsistente entre filas.
- Campo obligatorio vacío o de tipo incorrecto, si extraes a schema.
- Reconciliación de negocio: si la suma de líneas no cuadra con el total, esa página está mal sin mirarla.
- Cross-check: la misma página con dos técnicas distintas; donde coinciden, confianza sin revisar; donde discrepan, exactamente ahí se mira.

Si salta alguna, escalas esa página (no el documento entero), nunca reintentas a ciegas: clásico falla → especializado, especializado falla → frontera. Es el mecanismo real detrás del "Cost Optimizer" de LlamaParse. Tope de 2-3 intentos — sin eso, una página genuinamente rota te deja en un loop que nunca resuelve. El paso final no siempre es un modelo más fuerte: es revisión humana de lo que produjo el modelo, y para lo que de verdad no puede fallar (un dato de seguridad, por ejemplo), a veces ni siquiera eso — es transcripción manual de ese fragmento, sin pasar por ningún modelo. La revisión humana tampoco es toda muestreo: la porción de la que depende una decisión crítica se revisa al 100%, el resto se muestrea. Ningún modelo ni ningún loop da 100%: un pipeline bien montado da un porcentaje automático alto más una vía de revisión humana para lo que falla validación o se muestrea; el 100% es la suma de ambas cosas.

**¿Es bueno mi pipeline en general?** (evaluación, necesita ground truth)

- Precision (penaliza inventar) y recall (penaliza dejarte algo), no "se parece al original".
- En tablas, compara celda a celda por clave, no por posición.
- TEDS solo penaliza salidas estructuralmente distintas aunque el contenido sea idéntico.
- LLM-as-judge correlaciona mejor con juicio humano que las métricas de texto puro, pero se muestrea, no se aplica a cada documento.

Última red, aparte de todo lo anterior: un error que se cuela en la ingesta no hace falta que nadie lo cace a propósito. Se manifiesta solo, más adelante, como una respuesta mal en producción. Verificar la ingesta y monitorizar el sistema en uso acaban siendo, en la práctica, la misma red de seguridad.

## Reglas prácticas

- Define el esquema (Pydantic o similar) antes de tocar el documento, si la salida es estructurada. El esquema decide qué extraer, no al revés.
- A partir de unos cientos de páginas, usa Batch API en vez de llamadas en tiempo real: mitad de coste.
- Desconfía de benchmarks publicados por la empresa que vende la herramienta (ParseBench de LlamaIndex, por ejemplo). No los descartes, no los trates como neutrales.
- La ventaja de un modelo de visión sobre el pipeline clásico crece con la degradación real del documento (escaneo torcido, mala luz, foto de móvil); en PDFs nativos limpios, la diferencia práctica suele ser pequeña.