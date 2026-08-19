# Buceo + IA — Ideas de proyecto

Pregunatar a la IA que preparó esto sobre cosas relacionadas con el ordenador de buceo, o si sobre la teoría que tenemos se le ocurre algún proyecto. A mi se me oucrre pillarme un ordenador de buceo, abrirlo y meterle el RAG y cualquier modeloq ue quiera. 


## Estado del arte (agosto 2026)

El agua mata las ondas de radio casi al instante y dispersa la luz, así que el sonido es el único vehículo real de comunicación. Persona a persona, corta distancia: máscara integral + conducción ósea, ya es estándar funcional — Talky-Divy de 52 Hertz (financiado por defensa francesa) sustituye la boquilla del regulador y transmite vibraciones por dientes y mandíbula al oído interno. Persona a vehículo/superficie, larga distancia: módems acústicos JANUS (estándar OTAN, hasta 28 km), en buceo militar/comercial.

El cuello de botella real no es el modelo, es el ancho de banda: enviar una imagen sin comprimir por canal acústico llevaría decenas de minutos. El MIT trabaja ahora en compresión agresiva bajo esas limitaciones. Consecuencia de diseño: cualquier IA aquí corre local, no en la nube.

Tendencia en hardware: los ordenadores de buceo van integrando sensores biométricos (HRV, temperatura, esfuerzo) para ajustar descompresión según la respuesta real del cuerpo.

## Los datos: qué causa más daño

~90% de las muertes en buceo vienen de error del buceador, no de fallo de equipo — casi todo es prevenible con la información correcta a tiempo.

| Causa | Peso |
|---|---|
| Ascenso rápido/emergencia | 31% de mecanismos de lesión, 26% de muertes, **96% de los AGE** |
| Problemas cardíacos | 15% de desencadenantes, ~25% de muertes, 45% en mayores de 40 |
| Quedarse sin aire | 14% de desencadenantes |
| Asfixia (resultado final) | 33% de lesiones incapacitantes |

Patrón clave: sin aire y pánico son el disparador; el ascenso descontrolado es el mecanismo que mata. Es una cadena, no causas sueltas.

## Los 3 proyectos, por impacto

**1. Alerta temprana de ascenso descontrolado + estrés.** Va primero porque ataca la cadena entera, no un punto: el disparador y el mecanismo que más mata (96% de los AGE). Solo pide el sensor más barato que hay (presión, ~30€) y es verificable en seco, sobre perfiles de profundidad-tiempo — sin bucear ni una vez. El criterio de alerta (velocidad de ascenso sobre umbral + predicción de trayectoria) es demostrable formalmente, en línea con agentes acotados de envelope verificable en vez de un modelo generativo opaco.

**2. RAG de emergencia local.** No ataca una causa de muerte directamente, pero reduce fricción y tiempo de reacción. Su fuerte es ser el más autocontenido y demostrable: se construye y prueba entero en seco, con hardware COTS barato (pantalla + botones estancos).

**3. Compresión semántica para el enlace acústico.** Mayor techo de impacto (arregla la comunicación entre compañeros, no solo seguridad individual), pero es investigación real, no un fin de semana — es lo que el MIT ataca ahora con AUVs: comprimir a la mínima información útil antes de meterla en un canal de kilobits.



## Plan de corpus (decidido)

Objetivo: RAG usable por mí para repaso y pre-inmersión, en el futuro sobre hardware, y compartible/monetizable sin fricción legal.

**Fuentes del corpus:**
- **US Navy Diving Manual Rev 7** — columna vertebral pública: actual, gratuito, dominio público. Descarga oficial de la Navy.
- **NOAA Diving Manual 4ª ed. (2001)** — dominio público confirmado (archive.org, Public Domain Mark). Le faltan apéndices y es de 2001, pero física y procedimientos no caducan.
- **NOAA Diving Manual 6ª ed. (2017)** — la más nueva que existe (~116$, Best Publishing, papel o ebook). Editorial privada, así que el dominio público ya no es limpio: comprada vale como capa privada de calidad, pero no para redistribuir sin revisar.
- **Mis apuntes** (estos documentos) — capa recreativa en mis palabras, sin restricción.

**Qué guardar del curso mientras avanzo:**
1. Apuntes en mis palabras (ya en marcha).
2. Pares pregunta-respuesta reformulados en mis palabras — formato nativo del RAG pregunta-contra-pregunta, semillas del índice.
3. Números y procedimientos críticos tal cual (presiones, velocidades de ascenso, profundidades) — donde parafrasear es peligroso.

**MVP:** RAG local sobre este corpus + contar la historia en Instagram/Twitter/LinkedIn ("me saco el Open Water construyéndome mi copiloto de buceo con IA").

Dudas a resolver antes de planificar: 
- si tenemos un golden tan bueno como el que tenemos, que hacemos realmente? merece la pena un rag clásico de corpus? o el corpus son las preguntas? que realmente queremos recuperar? realmente el golden dataset es evaluación o corpus? porque si es corpus, es una forma neuva de medir?
**Plan de evaluación (ablación de corpus):** correr el golden dataset (uso=eval) variando dimensiones y ver así cual funciona mejor. hacer un grid search vaya
- Corpus: solo navy rev, solo mis apuntes, ambos combinados
- tamaño de modelo: probar frontera, más pequeño, local, y minúsculo que quepa en un ordenador de buceo 

Con este plan de evaluación, creamos una tabla clara con resultados, es lo más visual


**Requisito de diseño: latencia por encima de todo.** El caso de uso es pre-inmersión y emergencia, con el buceador esperando la respuesta, así que la latencia es el criterio que manda sobre calidad marginal de retrieval. Consecuencias de arquitectura:

- **Todo precomputado en indexado**, nada en tiempo de consulta: las preguntas hipotéticas (HyPE) se generan offline y quedan embebidas apuntando a su chunk. En consulta solo hay: embeber la query + búsqueda vectorial.
- **Sin capa generativa en el camino crítico**: se muestra el chunk o la respuesta ya escrita, no se redacta nada. Esto elimina de golpe lo más lento del pipeline (y de paso la alucinación).
- **Modelo de embeddings pequeño y local** (tipo MiniLM multilingüe), cuantizado; nada de llamadas de red.
- **Índice pequeño y en memoria** (el corpus cabe de sobra), con búsqueda exacta o HNSW; sin reranker cross-encoder en el camino crítico.
- **Sin reformulación de query ni multi-hop**: la consulta va directa al índice.
- **Caché de las consultas frecuentes** (las del golden y las más usadas pre-inmersión), resueltas sin cómputo.
- **Interfaz de preguntas seleccionables** = latencia cero para el caso más común: no hay que teclear ni buscar, se toca la pregunta y aparece la respuesta ya asociada.
- **Métrica a medir junto a la precisión:** latencia p50 y p95 en el hardware objetivo, no solo en portátil.


#### CLAVE PARA QUE ADOLFO, EL CREADOR, TENGA CLARO COMO SE HA CREADO
la idea es que decidamos juntos los pasos del rag, desde que extraemos hasta que recuperamos. decidimos la opción par acada paso con sus tradeoffs. e incluso, guardamos alguna segunda opción para probar más adelante (ej: evaluar el retrieval con hybbrid o con semantic search)

otra duda que tengo: realmente hay que evaluar dos cosas no? la capacidad de recuperar la info correcta, y la capacidad del LLM de repsonder correctamente a la entrada del user?


## Insight aparte: RAG sobre preguntas, no sobre respuestas. SOLO PROPUESTO, no definitivo

El problema se llama recuperación asimétrica: una pregunta y su respuesta no comparten vocabulario, así que sus embeddings no se parecen. Matchear pregunta contra respuesta pelea contra esa asimetría.

Solución: indexar pares Q-A y buscar pregunta contra pregunta — dos formas de preguntar lo mismo sí se parecen semánticamente. Diseño estándar de sistemas FAQ, más robusto.

Encaja especialmente bien en emergencias porque con un conjunto cerrado y curado de pares Q-A, la respuesta es texto verificado, no generado — cero riesgo de alucinar un procedimiento. El modelo solo decide cuál de las N respuestas mostrar.

Consecuencia de interfaz: si el corpus ya es un conjunto finito de preguntas, la interfaz natural es mostrarlas en pantalla, seleccionables. La búsqueda semántica ordena cuáles aparecen primero según contexto (profundidad, tiempo, presión de botella), no genera nada. Recuperación pura, sin capa generativa: más simple, más rápido, sin alucinación — y funciona cuando no puedes hablar.



## PRÓXIMOS PASOS

Una vez tengamos el rag, investigar el estado del arte de los ordenadores de buceo, ver si podríamos comprar uno y chetarlo con IA por todos lados, incluyendo el RAG