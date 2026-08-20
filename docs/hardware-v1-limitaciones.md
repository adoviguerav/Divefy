# Hardware v1 — Limitaciones y Opciones

## Limitaciones físicas detectadas

Cada una viene con lo que obliga a hacer, no con una preferencia — son restricciones del mundo, no elecciones de diseño.

### 1. El RF no atraviesa el agua

La atenuación de radiofrecuencia (Bluetooth, WiFi) en agua salada es casi total en 15-20cm; a 1GHz se pierde ~90% de la potencia en el primer metro.

**Obliga a**: cualquier comunicación en vivo, bajo el agua, entre dos dispositivos separados, tiene que ser por cable o por vía acústica — RF queda descartado de raíz, no es una opción a valorar.

### 2. Los dive computers comerciales cerrados no se pueden ampliar

Confirmado con teardown real: el Garmin Fenix 8 lleva la RAM (5MB) integrada dentro del propio SoC (NXP MRT595SFF0C), sin chip externo — no hay margen físico para ampliarla. El Descent Mk3i comparte plataforma, así que es muy probable que aplique igual, aunque no está verificado modelo por modelo. Shearwater, aparte, no publica SDK ni esquemáticos — firmware completamente cerrado.

**Obliga a**: no se puede instalar cómputo nuevo dentro de un Garmin o un Shearwater existentes. Cualquier capacidad de IA nueva tiene que vivir en hardware separado del dive computer comercial.

### 3. El único dive computer abierto (OSTC) no tiene cómputo suficiente

Esquemático y firmware públicos, sí — pero el chip real es un STM32F427 (Cortex-M4 a 180MHz) con hasta 256KB de SRAM, sin NPU. Órdenes de magnitud por debajo de lo que necesitaría incluso el modelo más pequeño.

**Obliga a**: que OSTC sea "tocable" no resuelve el problema — resuelve la apertura, no el cómputo. Si se quiere usar como base, necesitaría un chip de compañía aparte con su propio cómputo, no una modificación del suyo.

### 4. Compartir la pantalla de un dispositivo existente es intervención de hardware, no de software

Las pantallas modernas (tipo AMOLED) suelen ir por un bus de vídeo dedicado (MIPI-DSI u otro). Interceptarlo para inyectar tu propia señal es una práctica real y documentada en otros dispositivos de consumo, pero implica abrir físicamente el aparato y manipular una línea de señal de alta velocidad.

**Obliga a**: usar la pantalla de un dispositivo existente no es un problema de permisos o de API — es un proyecto de hardware aparte, con riesgo real de dejar el dispositivo inservible si sale mal.

### 5. El hardware NPU de clase wearable pensado para LLMs es muy reciente

Coral NPU y Nordic con Axon NPU están recién apareciendo en 2026 — disponibilidad de muestras o muy temprana, no un componente maduro de compra directa todavía.

**Obliga a**: para un primer prototipo, la opción de cómputo realista es un dev kit de banco, no un chip ya empaquetado en formato wearable — eso llega después, no ahora.

### 6. La generación en microcontrolador sin NPU es posible pero muy lenta

Referencia real: un LLM pequeño corriendo a ~10 tokens/segundo en un ESP32 de bajo coste, sin NPU.

**Obliga a**: si se quiere generación en v1, hay que asumir esa lentitud (o un chip con NPU, todavía en fase temprana según el punto 5) — no obliga a excluir la generación, pero sí a decidir con los ojos abiertos sobre esa relación velocidad/hardware disponible ahora mismo.

### 7. El presupuesto de batería de un wearable es mucho más ajustado que el de un portátil

**Obliga a**: cualquier elección de cómputo se mide también en consumo, no solo en velocidad o capacidad — un chip más potente que agota la batería en minutos no es una opción real para uso en inmersión.

## Opciones de diseño para v1 — sin decidir todavía

- **¿Generación en el dispositivo, o solo retrieval?** Retrieval-only evita el problema de la limitación 6 por completo (nada que generar, nada que esperar). Con generación, hay que aceptar la lentitud de un MCU sin NPU o apostar por un dev kit con NPU aunque sea hardware temprano (limitación 5).
- **¿Módulo conectado al dive computer, o completamente independiente?** Conectado, solo por cable (limitación 1) — RF queda descartado. Independiente, evita también las limitaciones 2 y 4 enteras, a cambio de no tener datos en vivo del dive computer (profundidad, tiempo) si se necesitaran.
- **¿Pantalla propia o compartida con el dive computer existente?** Compartida implica el proyecto de intervención de hardware de la limitación 4. Propia lo evita, a cambio de un componente más en el diseño.
- **¿Qué dev kit de cómputo para el prototipo de banco?** Los candidatos disponibles ahora, dado el punto 5, son kits de desarrollo con NPU accesibles hoy, no todavía un chip final de wearable.
- **¿Sensor de presión en v1, o fuera de alcance?** Solo hace falta si alguna pregunta del sistema depende de la profundidad actual — si no, se puede dejar fuera del primer prototipo.
- **¿Estanqueidad en v1, o después?** Es la parte menos reversible del proyecto — hacerla antes de validar el cómputo significa repetirla si cambia la placa.
