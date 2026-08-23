# Aprendizajes del parseo de PDF (Fase 1 — ingesta)

Notas de lo que pasó al depurar `_parsear_capitulo` en `p1_ingest.py`, para no
repetirlo en fases futuras (chunking, o si algún día tocamos esto otra vez).

## Qué pasó, en corto

El mismo tipo de bug apareció dos veces seguidas, en la misma sesión:

1. **Primera vez**: el código decidía "¿esto es un encabezado de sección?" mirando
   `item.label` de Docling (`section_header`, `list_item`...). Docling no es
   consistente: algunos encabezados reales los etiqueta como `text` plano. Resultado:
   37 secciones reales (6.1% del manual) se perdían en silencio, fundidas en la
   sección anterior.
2. **Segunda vez, arreglando la primera**: al ampliar la detección a cualquier
   `TextItem` (no solo `section_header`/`list_item`), seguí decidiendo "¿el título
   trae el párrafo pegado en el mismo texto, o viene aparte?" mirando otra vez el
   label (`== list_item` sí, cualquier otro no). Docling tampoco es consistente en
   esto: hay títulos con el párrafo entero pegado etiquetados como `text` plano.
   Resultado: 13 secciones con el título convertido en "id + título + párrafo entero"
   y el cuerpo (`texto`) vacío.

## La lección de fondo

**El label de un item de Docling es una clasificación interna del modelo, no un
contrato fiable.** Se ve razonable en unos pocos ejemplos y se rompe en cuanto se
aplica al documento completo — porque el PDF real lo escribieron personas distintas
a lo largo de años, no una plantilla uniforme.

Docling ofrece una segunda vista del mismo documento que sí es uniforme:
`doc.export_to_markdown()`. Ahí un encabezado es siempre `#`/`##`/`###` + texto, sin
importar qué label interno le puso el modelo. `cargar_apuntes` ya usa exactamente ese
patrón (regex sobre `^## `) para los apuntes en Markdown, y ahí no ha aparecido nunca
este tipo de bug.

**Regla práctica para la próxima vez**: si una librería expone tanto una vista
"clasificada por el modelo" (labels, tipos, categorías inferidas) como una vista
"normalizada" (markdown, HTML, texto plano con estructura explícita), usar la
normalizada para decidir estructura (dónde empieza algo, qué es un título). La
clasificada sirve para lo que el modelo hizo bien de forma fiable (aquí: extraer
tablas), no para decisiones binarias sobre las que se construye todo lo demás.

No se aplicó este cambio ahora — el coste es reabrir la fase (rehacer la detección
de secciones sobre markdown, resolver aparte la página por sección, volver a
verificar todo). Queda como el primer sitio a mirar si aparece un tercer caso de
label inconsistente en esta fase, o como punto de partida de diseño en fases nuevas
que tengan que parsear estructura de un documento con esta misma clase de
herramienta.

## Lección secundaria: una regla que "se ve bien" hay que validarla contra todo

La regla rota ("solo `list_item` trae el cuerpo pegado") no era una suposición
arbitraria — venía de mirar ejemplos reales del cap 9 durante el diseño original.
Pero "mirar ejemplos" no es lo mismo que "comprobar contra el conjunto completo": la
regla se sostenía en los casos vistos y se rompió en cuanto corrió sobre los 10
capítulos completos. Con un documento heterogéneo (400+ páginas, sin plantilla
uniforme), cualquier regla de "así se ve normalmente X" necesita correrse contra todo
el dato antes de darla por buena, no contra una muestra representativa a ojo.

## Lección sobre tests: verde no es lo mismo que correcto

Los 48 tests de aceptación pasaron en verde con el bug de título+cuerpo pegado
todavía vivo. Ningún test comprobaba la invariante real: _una sección de prosa cuyo
título es una frase larga no puede tener el cuerpo vacío_ — el título largo era en sí
mismo la señal de que algo se había mezclado mal. El test verificaba que el parser
no se caía y que producía _algo_ con la forma correcta, no que ese _algo_ fuera
semánticamente coherente.

Para la próxima fase: además de tests de forma (¿existe el campo?, ¿tiene el tipo
correcto?), vale la pena uno de invariante sobre el contenido real generado — algo
del estilo "ningún título de más de N palabras tiene `texto` vacío" — que habría
pillado esto sin que Adolfo tuviera que abrir el markdown de revisión y verlo a ojo.
