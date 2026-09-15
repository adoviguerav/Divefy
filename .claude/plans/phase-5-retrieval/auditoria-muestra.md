# Auditoría de etiquetas — muestra de 28 (T-03, Fase 5)

Regla: ≤2 mal para dar por buena la pasada. Una etiqueta está MAL si la sección
no sostiene la respuesta esperada, o si falta una sección que claramente la sostiene.
Las 8 primeras son los casos especiales (regla doctrinal / requiere_tool / manual-only);
las 20 siguientes, azar con semilla 42.

## q013 — ¿Cómo calculo a qué presión del manómetro tenemos que dar la vuelta?
**Esperada:** Se resta de la presión inicial la reserva y el aire de la parada de seguridad para obtener el disponible; se aplica la fracción acordada en el plan (mitad, o un tercio si es conservador) y esa cantidad se resta de la presión inicial: esa lectura es el punto de vuelta, siempre referenciando al compañero con menos aire
**Notas:** requiere_tool: la respuesta pide aritmética (fracción sobre presiones); etiquetada la sección PADI que da el método. Regla doctrinal: Navy 7-3.1 y 7-8.1 descartadas (terminación a 500/250 psi fijos, distinta del método PADI de fracción mitad/tercio).
**Apuntes:**
- `Habilidades prácticas#Sistema de compañeros` — «Presión inicial (ej. 200 bar) − reserva de seguridad (ej. 60 bar) − reserva de ascenso/parada de seguridad (ej. 30 bar) = presión disponible para la inmersión ... Punto de inflexión (presión a la que dar la vuelta) = presión inicial − mitad del disponible = 20…»

## q023 — Voy a empezar el ascenso, ¿cómo lo hago bien?
**Esperada:** Señal al compañero, sube nadando (sin hinchar el chaleco para arrancar), a 18 m/min máximo o lo que marque el ordenador, soltando aire del chaleco en pequeñas cantidades y con frecuencia, y parada de seguridad de 3 min a ~5 m
**Notas:** Regla doctrinal: 9-6.3, 9-11 y 7-9.1 descartadas — velocidad de ascenso Navy 30 fsw/min (~9 m/min), distinta de los 18 m/min PADI.
**Apuntes:**
- `Fisiología y salud#Buceo sin paradas` — «Máximo 18 m/min o lo que marque el ordenador: el más restrictivo de los dos. La parada de seguridad (5 m, 3 min) no es exigida por la mayoría de modelos: se hace igualmente por conducta conservadora y margen»
- `Habilidades prácticas#Ascensos en aguas abiertas` — «5 puntos de ascenso: señal de "subir" + confirmar compañeros listos → ... mirar hacia arriba, sujetar la tráquea del chaleco sin añadir aire, empezar a nadar hacia arriba si la flotabilidad ya es neutra → ascender despacio sin superar la velocidad máxima, solt…»
- `Habilidades prácticas#Ascensos y regreso a la superficie` — «Señal de "subir" al compañero. Nadar hacia arriba; no debería hacer falta hinchar el chaleco para subir ... Ascender despacio. Vaciar el aire en expansión del chaleco en pequeñas cantidades y con frecuencia»
**Manual:**
- `7-3.4` — «The diver must vent air from the compensator during ascent to maintain proper control.»

## q140 — Llevo tiempo sin bucear, ¿puedo ir directamente?
**Esperada:** Si llevas seis meses o más sin bucear, conviene refrescar conocimientos y habilidades antes (programa ReActivate con instructor). Bucear con frecuencia es el mejor mantenimiento; si no hay aguas abiertas cerca, vale practicar en piscina con equipo y compañero
**Notas:** Los apuntes no cubren la inactividad/ReActivate; soporte solo en manual (6-5.1, sin plazo numérico).
**Manual:**
- `6-5.1` — «Work up dives shall be conducted if divers have been inactive, will be working with unfamiliar equipment (dredges, dry suits, MK-16, etc), or
diving deep. Work up dives are performed with the goal of acclimating the divers to the environment and their equipmen…»

## q169 — ¿Cuánto tengo que esperar para volar después de bucear?
**Esperada:** 12 horas tras una inmersión simple sin paradas, 18 horas tras sucesivas o varios días seguidos buceando, y más de 18 horas si hubo paradas de descompresión de emergencia. El motivo es que en altitud hay menos presión y el nitrógeno residual puede formar burbujas más fácilmente. Para subir a altitud por carretera no hay recomendación formal, pero conviene ser igual de conservador. Las recomendaciones cambian con la investigación: consulta fuentes actualizadas como DAN
**Notas:** Regla doctrinal: 9-14 y 9-15 descartadas — intervalos de vuelo Navy (Tabla 9-6 por grupo; 24 h con deco) distintos de los 12/18 h PADI.
**Apuntes:**
- `Fisiología y salud#Volar después de bucear y buceo en altitud` — «Recomendaciones para volar tras bucear: inmersión simple sin paradas → mínimo 12 h de intervalo; sucesivas o varios días seguidos buceando → 18 h; si hubo paradas de descompresión de emergencia → más de 18 h. ... La altitud reduce la presión ambiente, así que …»

## q171 — He pasado frío o me he esforzado mucho en la inmersión, ¿cambia algo?
**Esperada:** Sí: absorbes más nitrógeno del que calcula el ordenador, así que sube el riesgo de ED. Sé más conservador: margen amplio sobre los límites sin paradas durante toda la inmersión (algunos ordenadores tienen ajuste de conservadurismo, a configurar antes de bucear), con tablas planifica como si la inmersión fuera 4 metros más profunda, y haz la parada de seguridad sin falta
**Notas:** Regla doctrinal: 9-6.1 descartada — la doctrina Navy no aplica ajuste por frío/esfuerzo, frente al ajuste PADI de planificar 4 m más profundo.
**Apuntes:**
- `Fisiología y salud#Inmersiones con frío o agotadoras` — «Enfriarse o esforzarse mucho hace que el cuerpo absorba más nitrógeno del que calcula el ordenador o la tabla, subiendo el riesgo de ED. Respuesta: ser más conservador de lo normal — margen amplio sobre los NDL durante toda la inmersión (algunos ordenadores ti…»
**Manual:**
- `11-5.3` — «When diving in cold water, hypothermia may predispose the diver to decompression sickness.»
- `2-8.3` — «A chilled diver cannot work efficiently or think clearly, and is more susceptible to decompression sickness.»
- `3-10` — «The diver's thermal status affects the rate of inert gas uptake and elimination. Divers who are warm on the bottom will absorb more inert gas than divers who are cold. [...] divers who are warm during decompression stops will lose more inert gas and have a low…»
- `6-4.2` — «listing DCS as a hazard when the real hazard is diving deep in warm water and working hard»

## q176 — No tengo aire suficiente para completar la parada de descompresión, ¿qué hago?
**Esperada:** Párate lo máximo posible pero guarda aire para subir y salir con seguridad; no te quedes sin aire abajo por intentar completarla. Ya arriba: relájate, respira oxígeno al 100% si hay, vigila síntomas de ED y no vuelvas a bucear en al menos 24 horas (muchos ordenadores se bloquean en modo error si lo intentas antes)
**Notas:** Regla doctrinal: 9-12.10 descartada — el procedimiento Navy devuelve al buceador a la parada (<1 min) o a cámara, frente al PADI de no volver a bajar y 24 h sin bucear.
**Apuntes:**
- `Fisiología y salud#Paradas de descompresión de emergencia` — «con poco aire, párate lo máximo posible pero guarda aire suficiente para subir y salir con seguridad (no te quedes sin aire abajo por intentar la parada). Ya en superficie: relajarse, respirar oxígeno al 100% si hay, vigilar síntomas de ED, y no volver a bucea…»
**Manual:**
- `7-5` — «The deeper the dive, the more critical it is to ensure divers have sufficient air to reach the surface in the event of a mishap.»

## q181 — Me cuesta pensar con claridad bajo el agua, ¿qué hago?
**Esperada:** Probable narcosis por gas: señal al compañero y ascender de inmediato a menor profundidad, donde desaparece rápido; luego seguir ahí o terminar la inmersión. Si es el compañero quien la muestra, súbelo tú. Aparece típicamente hacia los 30 metros y la agravan cansancio, deshidratación, alcohol, medicamentos, frío y mala visibilidad
**Notas:** Regla doctrinal: 3-9.1 descartada — sitúa la aparición de la narcosis hacia 130 fsw (~40 m), distinto de los ~30 m PADI.
**Apuntes:**
- `Fisiología y salud#Narcosis por gas` — «Signos y síntomas: sensación de embriaguez o "colocón", pérdida de coordinación, razonamiento y reacción más lentos ... Si la notas: ascender de inmediato a menos profundidad — desaparece rápido; luego continuar ahí o terminar. Si tu compañero parece narcotiza…»
**Manual:**
- `2-10.3` — «Nitrogen narcosis, a disorder resulting from the anesthetic properties of nitrogen breathed under pressure, can result in a loss of orientation and judgment by the diver. For this reason, compressed air, with its high nitrogen content, is not used below a spec…»
- `7-8.8` — «Nitrogen narcosis or other complications involving the breathing mixture, which can result in confusion, dizziness, anxiety, or panic, are common in recovered lost divers.»

## q186 — ¿Hasta qué profundidad puedo bucear con mi certificación?
**Esperada:** Como Open Water Diver, hasta 18 metros (o la máxima alcanzada en el curso, si fue menor). Con formación y experiencia adicionales, el máximo del buceo recreativo son 40 metros. Además se bucea en condiciones iguales o mejores que las conocidas, y los límites de cada inmersión los pones tú según tus habilidades, confianza y las condiciones
**Notas:** Regla doctrinal: 7-2.1 descartada — límites operativos Navy (130/190 fsw) distintos de los límites recreativos PADI (18/40 m).
**Apuntes:**
- `Fisiología y salud#Narcosis por gas` — «no bucear demasiado profundo (con Open Water el límite son 18 m; el máximo recreativo con más formación es 40 m)»

## q002 — ¿Las cosas se ven más grandes o más pequeñas bajo el agua?
**Esperada:** Más grandes y más cercanas, aproximadamente un tercio, por la refracción de la luz al pasar del agua al aire de la máscara
**Apuntes:**
- `Física#Ver y oír bajo el agua` — «Al pasar del agua al bolsillo de aire de la máscara, la luz se dobla en el cristal. El factor de aumento es la razón entre índices: n_agua/n_aire = 1,33 → los objetos parecen ~33% más grandes, o ~25% más cerca de lo real (1/1,33 ≈ 0,75).»
- `Material y equipo#Máscara` — «con poca miopía puede no hacer falta nada (el agua agranda los objetos)»
**Manual:**
- `2-6.1` — «Refraction can make objects appear closer
than they really are. A distant object will appear to be approximately three-quarters of its actual distance. ... Generally, underwater objects appear to be about 30 percent larger than they actually are.»
- `7-8.7` — «Depth perception is altered so that an object appearing to be 3 feet away is actually 4 feet away, and objects appear larger than they actually are.»

## q007 — No paro de tiritar buceando, ¿qué hago?
**Esperada:** Salir del agua ya, secarse y entrar en calor; tiritar sin control es signo de hipotermia y no se espera al final planificado de la inmersión
**Apuntes:**
- `Habilidades prácticas#Mantenerse caliente` — «Hipotermia: cuerpo tan frío que deja de funcionar bien. Señal clave: tiritar de forma incontrolable — si pasa, salir del agua ya, secarse y entrar en calor.»
**Manual:**
- `11-4.5` — «A dive should be terminated upon the onset of involuntary shivering or severe impairment of manual dexterity.»
- `11-4.6` — «The diver should remove any wet dress, dry off, and don warm protective clothing as soon as possible.»
- `3-10.2` — «In mild cases, the victim will experience uncontrolled shivering, slurred speech, imbalance, and/or poor judgment. [...] To treat mild hypothermia, passive and active rewarming measures may be used and should be continued until the victim is sweating. Rewarmin…»

## q009 — Estoy nadando contra corriente, me fatigo, respiro con dificultad y siento que me falta el aire, ¿qué hago?
**Esperada:** Parar toda actividad, señal al compañero y descansar recuperando una respiración lenta y profunda hasta poder gestionar la situación; en superficie hinchar el chaleco, bajo el agua sujetarse a algo fijo si es posible. Subir o cambiar de fuente de aire no arregla el sobreesfuerzo
**Apuntes:**
- `Gestión de problemas#Problemas bajo el agua` — «Sobreesfuerzo bajo el agua: el más común. Puede sentirse como "el regulador no me da aire" ... Si pasa: parar toda actividad sin ignorar la sensación, señal de "para/espera", descansar y respirar despacio hasta recuperarte, seguir más lento.»
- `Gestión de problemas#Problemas en superficie (buceador consciente)` — «Problemas típicos en superficie: sobreesfuerzo (flotabilidad, parar, descansar, señal)»
- `Habilidades prácticas#Respirar de forma eficaz` — «Sobreesfuerzo: Síntomas: cansancio, respiración forzosa, sofoco/falta de aire ... Causa: desgaste prolongado (nadar contra corriente) ... Si ocurre: parar toda actividad, señal al compañero, descansar. En superficie: hinchar chaleco o soltar lastre para no esf…»
**Manual:**
- `3-5.2` — «Hypercapnia is treated by: n Decreasing the level of exertion to reduce CO 2 production»
- `3-5.6` — «Hyperventilation victims should be encouraged to relax and slow their breathing rates. The body will correct hyperventilation naturally.»
- `3-5.7` — «If excessive breathing resistance is encountered, slow or stop the pace of work until a respiratory comfort level is achieved. If respiratory distress occurs following an abrupt increase in workload, stop work and take even controlled breaths until the sensati…»
- `7-8.1` — «If a diver is breathing too hard, he should pause in the work until breathing returns to normal. If normal breathing is not restored, the affected diver signals the dive partner to abort the dive.»

## q027 — ¿Cómo me mantiene caliente un traje húmedo y cómo uno seco?
**Esperada:** El húmedo deja que el cuerpo caliente una capa fina de agua pegada a la piel (por eso el ajuste importa: que no entre ni escape demasiada agua); el seco hace lo mismo con una capa fina de aire, con aislamiento extra de la prenda interior
**Apuntes:**
- `Material y equipo#Trajes de protección` — «Húmedo: el más común, neopreno, deja entrar agua pero la atrapa — cuerpo la calienta y el neopreno frena la pérdida de calor. Debe quedar ajustado (ni holgado, que deja entrar/salir agua, ni apretado) ... Seco: el más aislante, te mantiene seco de verdad, cier…»
**Manual:**
- `11-2.9` — «Variable volume dry suits provide superior thermal protection to the surface -supplied or SCUBA diver in the water and on the surface. ... The level of thermal protection can be varied through careful selection of the type and thickness of long underwear.»
- `7-4.1` — «The suit traps a thin layer of water next to the diver's skin, where it is warmed by the diver's body. ... The dry suit keeps the diver dry, but it is the thermal insulation worn under the suit that insulates the diver and provides warmth.»

## q029 — Hace mucho calor y todavía no hemos entrado al agua, ¿qué riesgo tengo con el traje puesto y qué hago?
**Esperada:** Sobrecalentamiento (los trajes aíslan igual de bien fuera del agua); ponerse el traje lo más tarde posible, poca actividad con él puesto, capucha atrás y cremallera abierta hasta el final, y mojarse o quitárselo si empieza a notarse
**Apuntes:**
- `Material y equipo#Trajes de protección` — «Sobrecalentamiento: riesgo real en día caluroso antes de la inmersión. Prevención: ponerse el traje lo último posible, poca actividad una vez puesto, capucha echada atrás, cremallera cerrada lo más tarde posible, mojarse o quitarse el traje si empieza a notars…»
**Manual:**
- `11-4.4` — «Suited divers should be protected from overheating and associated perspiring before entering the water. Overheating easily occurs ... The divers' comfort can be improved and sweating delayed before entering the water by cooling the divers face with a damp clot…»
- `3-10.4` — «Divers are susceptible to hyperthermia when they are unable to dissipate their body heat. This may result from high water temperatures, protective garments, rate of work, and the duration of the dive. [...] cooling should be started immediately by removing the…»

## q031 — ¿Dónde me coloco la herramienta cortante?
**Esperada:** En un sitio alcanzable con cualquiera de las dos manos (tráquea del chaleco, cintura, pierna, consola...), porque si un brazo queda enredado tienes que poder llegar con el otro
**Apuntes:**
- `Material y equipo#Herramientas cortantes` — «Sujeción: donde prefieras (tráquea del chaleco, cintura, pierna, consola, muñeca), pero siempre en un sitio alcanzable con cualquiera de las dos manos, por si un brazo queda enredado.»
**Manual:**
- `7-3.6` — «The knife must be carried in a suitable scabbard and worn on the diver's hip, thigh, or calf. The knife must be readily accessible, must not interfere with body movement, and must be positioned so that it will not become fouled while swimming or working.»

## q033 — ¿Cómo cambia la densidad del aire que respiro con la profundidad?
**Esperada:** Es proporcional a la presión absoluta: el doble a 10 m (2 bar), el triple a 20 m (3 bar), porque el regulador entrega el aire a la presión ambiente
**Apuntes:**
- `Física#Física de la inmersión — por fase` — «Presión absoluta por profundidad: 0 m = 1 atm, 10 m = 2 atm, 20 m = 3 atm ... Y la densidad del aire respirado es proporcional a esa presión absoluta: 2× a 10 m, 3× a 20 m, 4× a 30 m (el regulador entrega el aire a presión ambiente).»
**Manual:**
- `2-10.9` — «As the container volume is decreased (b), the molecules per unit volume (density) increase and so does the pressure.»
- `2-11.1` — «Boyle's law states that at constant temperature, the absolute pressure and the volume of gas are inversely proportional. As pressure increases the gas volume is reduced; as the pressure is reduced the gas volume increases. Boyle's law is important to divers be…»
- `2-9.3` — «The pressure of seawater at a depth of 33 feet equals one atmosphere. The absolute pressure, which is a combination of atmospheric and water pressure for that depth, is two atmospheres. For every additional 33 feet of depth, another atmosphere of pressure (14.…»
- `3-4.8` — «At 33 fsw, the diver still inhales 20 l/min at BTPS, but the gas is twice as dense; thus, the inhalation would be approxi mately 40 standard l/min and the cylinder would last only half as long, or 50 minutes. At three atmospheres, the same cylinder would last …»

## q039 — ¿Cada cuánto tengo que compensar al bajar?
**Esperada:** Cada metro más o menos, desde el principio del descenso y antes de notar molestia: si esperas a que moleste, compensar se vuelve difícil o imposible
**Apuntes:**
- `Física#Física de la inmersión — por fase` — «Cada metro más o menos, antes de sentir molestia — si esperas a que duela, ya es tarde.»
- `Habilidades prácticas#Descenso y compensación` — «Compensar suave y frecuente (cada metro/par de pies).»
- `Habilidades prácticas#Descensos en aguas abiertas` — «Compensar en cuanto la cabeza queda bajo el agua, y cada metro/pocos pies de ahí en adelante»
**Manual:**
- `3-6.2` — «While descending, stay ahead of the pressure. To avoid collapse of the eustachian tube and to clear the ears, frequent adjustments of middle ear pressure must be made by adding gas through the eustachian tubes from the back of the nose. [...] If too large a re…»

## q058 — ¿En qué me fijo para elegir una pieza de equipo?
**Esperada:** Primero idoneidad (apropiado para el tipo de inmersión), ajuste (tu talla) y comodidad (llevarlo sin que moleste); solo cuando eso está cubierto, lo secundario: precio y características, funcionabilidad, color/estilo y accesorios
**Apuntes:**
- `Material y equipo#Elegir y cuidar el equipo — clave general` — «3 consideraciones principales: idoneidad (apropiado para el tipo de inmersión y entorno que vas a hacer), ajuste (de tu talla: ni aprieta ni queda holgado), comodidad (puedes llevarlo puesto 1h+ sin que moleste ni distraiga ...). 4 consideraciones secundarias …»

## q060 — Estoy montando el equipo y noto que me cuesta respirar por el regulador más de lo normal, ¿qué hago?
**Esperada:** No bucear con él; inspección y arreglo por un profesional antes de usarlo. Ni limitar profundidad ni lavarlo y probar sustituyen la revisión
**Apuntes:**
- `Material y equipo#Regulador` — «Nunca usar un regulador si cuesta respirar, pierde agua o parece dañado — llevarlo a revisar. ... revisión profesional obligatoria cada 1-2 años aunque parezca que funciona bien.»

## q067 — Oigo un ruido bajo el agua pero no sé de dónde viene, ¿es normal?
**Esperada:** Sí; el sonido viaja unas 4 veces más rápido en el agua que en el aire y el oído no consigue determinar la dirección, parece venir de todas partes o de encima de tu cabeza
**Apuntes:**
- `Física#Ver y oír bajo el agua` — «velocidad del sonido ≈343 m/s en aire, ≈1481 m/s en agua (~4,3× más rápido) ... Resultado: se detecta que algo suena y si se acerca/aleja (por intensidad), pero no la dirección — parece venir de todas partes o de encima.»
**Manual:**
- `2-7.2` — «Because sound travels so quickly underwater (4,921 feet per second), human ears cannot detect the difference in time of arrival of a sound at each ear. Consequently, a diver cannot always locate the direction of a sound source.»

## q069 — ¿Cómo respiro bien con el regulador?
**Esperada:** Lento, profundo y continuo, sin parar nunca de respirar; y con control de vías aéreas (inhalar despacio, lengua al paladar) para que las gotas de agua que queden en el regulador no pasen a la garganta
**Apuntes:**
- `Física#Física de la inmersión — por fase` — «Respirar regularmente y nunca jamás aguantar la respiración. Respirar lenta y profundamente.»
- `Habilidades prácticas#Respirar de forma eficaz` — «Respirar lento y profundo reduce esa proporción ... Control de vías aéreas ... Técnica 1: inhalar despacio — el agua se queda en la boquilla, el aire pasa ... Técnica 2: lengua contra el paladar en cada inhalación — bloquea el agua, deja pasar el aire.»
**Manual:**
- `3-4.5` — «Parts of a diver's breathing apparatus can add to the volume of the dead space and thus reduce the proportion of the tidal volume that serves the purpose of respira tion. To compensate, the diver must increase his tidal volume.»
- `3-5.2` — «Inadequate lung ventilation in relation to exercise level. The latter may be caused by skip breathing, increased apparatus dead space, excessive breathing resistance, or increased oxygen partial pressure.»
- `7-8.1` — «The diver must learn to breathe in an easy, slow rhythm at a steady pace. ... Skip breathing occurs when a long unnatural pause is inserted between each breath and shall not be practiced.»

## q076 — ¿Cada cuánto llevo la botella a inspeccionar?
**Esperada:** Inspección visual una vez al año (corrosión interna, daños, contaminación) y prueba hidrostática cada 2-5 años según normativa local
**Apuntes:**
- `Material y equipo#Botellas` — «Mantenimiento: prueba hidrostática cada 2-5 años (según región), inspección visual cada año — sin estos dos al día, no te la cargan.»
**Manual:**
- `7-3.1` — «Be visually inspected at least once every 12 months and every time water or particulate matter is suspected in the cylinder. ... Be hydrostatically tested at least every five years in accordance with DOT regulations and Compressed Gas Association (CGA) pamphle…»

## q083 — Hay corriente, ¿en qué dirección empiezo a nadar?
**Esperada:** Contra la corriente en la primera parte de la inmersión y por el fondo, donde es más débil, para que a la vuelta te empuje hacia el punto de salida. Nunca luchar de frente contra una corriente fuerte
**Apuntes:**
- `Entornos y condiciones#Bucear desde un barco` — «anotar la dirección de la corriente (se nada hacia ella; el barco suele apuntar hacia ella ...) ... Nadar hacia la corriente al principio y quedarse por delante del barco.»
- `Entornos y condiciones#Entornos y condiciones` — «Las corrientes son más fuertes en superficie y se debilitan con la profundidad: minimizar la natación en superficie y avanzar por el fondo. Empezar la inmersión nadando despacio contra la corriente, para que a la vuelta te empuje hacia el punto de salida. ... …»
- `Entornos y condiciones#Oleaje, corrientes de playa y mareas` — «Planificación: entrar corriente arriba y salir corriente abajo, o nadar contra ella al principio para que te devuelva; lo clave es saber cómo afectará a tu salida.»
**Manual:**
- `7-8.7` — «If practical, swim against a current to approach a job site. The return swim with the current will be easier and will offset some of the fatigue caused by the job.»

## q097 — ¿Cómo evito que me pique o muerda algo bajo el agua?
**Esperada:** Conocer las especies peligrosas del sitio y dónde viven, no tocar ni provocar nada (ni siquiera muerto: las medusas y sus tentáculos siguen picando), vigilar dónde pones manos, rodillas y pies, flotabilidad neutra con distancia del fondo, traje y guantes como protección parcial, cuidado extra en agua turbia, y saber dar primeros auxilios. Casi todas las lesiones vienen de un descuido humano
**Apuntes:**
- `Entornos y condiciones#Vida acuática` — «Prevención (9 pasos): conocer las criaturas locales y cómo hacen daño; respeto total, sin tocar ni provocar ... atención a dónde pones manos y pies (el traje protege a medias ...); flotabilidad neutra con distancia prudencial y movimiento lento; cuidado extra …»
**Manual:**
- `7-4.1` — «A diver needs some form of protection from cold water to counter heat loss during long exposure in water of moderate temperature and from the hazards posed by marine life and underwater obstacles. ... Gloves shield the hands from cuts and chafing, and provide …»
- `7-8.7` — «Avoid coral or rocky bottoms, which may cause cuts and abrasions.»

## q116 — Hay un buceador en pánico en superficie, ¿qué hago?
**Esperada:** Primero flotabilidad, la tuya y la suya (lo ideal es alcanzarle un flotador; si hay contacto, tu flotabilidad va antes). Luego tranquilizarlo (el pánico suele ceder al ganar flotabilidad), ayudarle a recuperar una respiración lenta y profunda, y llevarlo al barco u orilla si lo necesita. Se reconoce el pánico porque no establece flotabilidad, lleva la máscara quitada o en la frente, tiene los ojos muy abiertos sin ver, se mueve de forma errática y no sigue instrucciones
**Apuntes:**
- `Gestión de problemas#Problemas en superficie (buceador consciente)` — «En pánico — miedo irracional ... sin flotabilidad establecida, máscara en la frente o fuera ... ojos muy abiertos que "no ven", movimientos erráticos, no sigue instrucciones ... Asistir a un buceador consciente en superficie (4 pasos): 1. Flotabilidad: primero…»

## q156 — ¿Por qué tengo menos tiempo de fondo en la segunda inmersión del día?
**Esperada:** Por el nitrógeno residual: tras la primera inmersión aún queda nitrógeno disuelto en los tejidos y el ordenador lo descuenta, acortando los límites sin paradas a cada profundidad. Cuanto más largo el intervalo de superficie, más se elimina y más tiempo tendrás; a partir de unas 12 horas vuelve a contar como primera inmersión. En una sucesiva el limitante puede pasar de ser el aire a ser el tiempo sin paradas
**Apuntes:**
- `Fisiología y salud#Inmersiones sucesivas` — «Una inmersión hecha con nitrógeno residual es una inmersión sucesiva, y sus límites sin paradas son más cortos. Tras un intervalo suficiente (mínimo ~12 h) los niveles vuelven a lo normal y la siguiente vuelve a ser "primera" o "limpia". Intervalo de superfici…»
**Manual:**
- `3-9.3` — «Some parts of the body desaturate more slowly than others for the same reason that they saturate more slowly: poor blood supply or a greater capacity to store inert gas. Washout of excess inert gas from these 'slow' tissues will lag behind washout from the fas…»
- `9-3.15` — «Residual nitrogen is the excess nitrogen gas still dissolved in a diver's tissues after surfacing. This excess nitrogen is gradually eliminated during the surface interval. If a second dive is performed before all the residual nitrogen has been eliminated, the…»
- `9-3.19` — «Residual nitrogen time is the time that must be added to the bottom time of a repetitive dive to compensate for the nitrogen still in solution in a diver's tissues from a previous dive.»
- `9-9` — «If the diver makes a second dive before the residual nitrogen has been dissipated (a repetitive dive), he must consider his residual nitrogen level when planning for the second dive. … As nitrogen passes out of the diver's body during the surface interval, the…»
- `9-9.1` — «Add the residual nitrogen time to the actual bottom time of the repetitive dive to get the Equivalent Single Dive Time (ESDT). … If the surface interval exceeds the longest time shown in the row, the dive is not a repetitive dive. No correction for residual ni…»

## q173 — He excedido el límite sin paradas, ¿qué hago?
**Esperada:** Parada de descompresión de emergencia, que es obligatoria a diferencia de la de seguridad: el ordenador entra en modo descompresión y te indica a qué profundidad pararte y cuánto tiempo. Nunca asciendas por encima de esa profundidad; quedarte algo por debajo sí vale. Con tablas, los procedimientos vienen impresos en la propia RDP o eRDPML
**Apuntes:**
- `Fisiología y salud#Buceo sin paradas` — «Si lo excedes: parada de descompresión de emergencia — detenerse a profundidades concretas el tiempo indicado para liberar nitrógeno antes de seguir subiendo. ... La parada de descompresión sí es obligatoria: solo existe si excediste el NDL, y saltártela deja …»
- `Fisiología y salud#Paradas de descompresión de emergencia` — «Obligatorias si excediste el NDL: mientras la parada de seguridad te mantiene con margen dentro de los límites, la de descompresión te devuelve a ellos tras haberlos superado. ... el ordenador entra en modo descompresión y te indica a qué profundidad pararte y…»
**Manual:**
- `7-9.3` — «Based upon the time and depth of the dive, the required decompression profile from the tables presented in Chapter 9 shall be computed. ... With the stage being handled from the surface, the divers will be taken through the appropriate stops while the timekeep…»
- `9-15` — «Once a diver exceeds the no-decompression limit, the decompression obligation prescribed by the Air III will build rapidly and may result in the diver running out of air before the decompression time can be completed. If a diver does develop a decompression ob…»
- `9-7` — «If a diver exceeds the limits given in the No-Decompression Table, then the decompression stop requirement must be calculated using Table 9-9.»
- `9-8.1` — «Enter the table at the depth that is exactly equal to or next deeper than the diver's maximum depth. Select the schedule for the bottom time that is exactly equal to or next longer than the diver's actual bottom time. Read across the row to obtain the required…»

## q179 — Creo que mi compañero tiene enfermedad descompresiva, ¿qué hago?
**Esperada:** Que interrumpa toda actividad de buceo; comprobar respiración y RCP si hace falta; llamar a emergencias (y al servicio de emergencias de buceo local si existe); mantenerlo tumbado con oxígeno de emergencia; vigilarlo y prevenir el shock; y si está inconsciente pero respira bien, de costado izquierdo con la cabeza apoyada y con oxígeno. Casi todos los casos necesitan cámara hiperbárica: nunca intentes recomprimirlo metiéndolo otra vez en el agua y no retrases el traslado
**Apuntes:**
- `Fisiología y salud#Lesiones disbáricas (LD) y primeros auxilios` — «Ayudar a un buceador con posible LD: interrumpir toda actividad de buceo → comprobar respiración y RCP si hace falta → llamar a emergencias (y al servicio de emergencias de buceo de la zona si existe) → mantenerlo acostado con oxígeno de emergencia → vigilarlo…»
- `Gestión de problemas#Primeros auxilios (buceador que ha estado o está inconsciente)` — «si está inconsciente pero respira, posición lateral de seguridad sobre el costado izquierdo ... → oxígeno de emergencia lo antes posible ... contactar emergencias — primero el servicio médico local, después el servicio de emergencias de buceo si existe en la z…»
**Manual:**
- `17-12.1` — «Surface oxygen should be used for all cases of DCS until the diver can be recom pressed.»
- `17-3.3` — «Immediate CPR and application of an Automated External Defibrillator (AED) is indicated for a diver with no pulse or respirations (cardiopulmonary arrest).»
- `17-4` — «Any decompression sickness that occurs must be treated by recompression.»
- `17-5.2` — «Treat promptly and adequately. … The effectiveness of treatment decreases as the length of time between the onset of symptoms and the treatment increases.»
- `17-5.4` — «First and foremost, the patient with suspected DCS or AGE should be administered 100% oxygen during transport, if available. … the patient should be kept supine (lying horizontally). Do not put the patient head-down. Additionally, the patient should be kept wa…»
- `3-9.3` — «Treatment of decompression sickness is accomplished by recompression. [...] Treatment is done in a recompression chamber, but can sometimes be accomplished in the water if a chamber cannot be reached in a reasonable period of time. Recompression in the water i…»
- `7-8.8` — «Begin basic life support measures and transport the diver to the recompression chamber or medical facility»
- `9-12.11` — «If the diver is symptom-free upon surfacing, place the diver on oxygen, transport to the nearest appropriate recompression chamber, and treat on Treatment Table 5. … If the diver is not symptom-free upon surfacing, transport the diver to the nearest chamber an…»

## q184 — ¿Cómo uso la brújula para nadar en línea recta?
**Esperada:** Apunta la línea de fe en la dirección que quieres ir, deja que la aguja se fije al norte magnético y gira el bisel hasta encuadrar la aguja con las marcas índice. Luego nada siguiendo la línea de fe manteniendo la aguja dentro de los índices; si te desvías, gira el cuerpo (nunca los brazos) hasta recuperar el rumbo. Sujétala nivelada, alineada con el centro del cuerpo y mirando por encima de ella, no hacia abajo
**Apuntes:**
- `Habilidades prácticas#Navegación con brújula` — «Rumbo recto: apuntar la línea de fe a donde quieres ir → dejar que la aguja se fije al norte → girar el bisel hasta encuadrar la aguja con los índices → nadar siguiendo la línea de fe manteniendo la aguja dentro de los índices. Si te desvías, la aguja se sale:…»
