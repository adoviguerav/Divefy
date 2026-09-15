# Guía de uso — skills y comandos

Qué hace cada pieza, qué entra, qué sale, y en qué orden. Si dudas de algo, la pregunta
correcta es siempre "¿qué cierra esta pieza?".

**Regla que gobierna todo:** cada pieza cierra lo que abre. Ninguna deja a medias algo
que otra tenga que terminar.

---

## El camino principal

```
IDEA (dos frases o un documento)
  │
  ├─ /ceo-thinking ──────────► .claude/plans/IDEA.md
  │                            ¿merece la pena? ¿para quién? ¿qué tipo de proyecto?
  │
  ├─ /prd ───────────────────► .claude/plans/PRD.md + CLAUDE.md + README.md
  │  (lee el IDEA.md)          features, actores, restricciones, fases, riesgos
  │
  ├─ /system-design ─────────► .claude/plans/SYSTEM-DESIGN.md + .claude/plans/decisiones/NNN-*.md
  │  (lee el PRD)              requisitos, escala, modelo, arquitectura, riesgo, despliegue
  │
  └─ por cada fase del PRD:
       /explore ─────────────► evidencia + recomendación; tú decides: ¿plan, directo, nada?
       /plan <n> ────────────► plan corto en prosa + contrato de aceptación
       /plan-eng-review ─────► (solo si la fase es gorda)
       /implement <n> ───────► tests ciegos en RED → código hasta GREEN, contigo mirando
       /review <n> ──────────► (a demanda) revisión adversarial a ciegas
       /verify <n> ──────────► corre la suite acumulada entera, da evidencia, cierra la fase
```

Una sola vez: ceo-thinking, prd, system-design. En bucle: el resto. El workflow completo
del bucle está especificado en `~/.claude/workflow-v2.md`.

---

## Las tres del arranque

### `/ceo-thinking` (antes `/office-hours`)

**Entra:** tu idea, desde dos frases hasta un documento.
**Sale:** `.claude/plans/IDEA.md`.

Te elige modo según tu objetivo — startup, proyecto interno, hackathon, open source,
aprender, o por gusto — y eso cambia el resto de la sesión. Luego seis preguntas duras,
de una en una: qué evidencia real tienes de que alguien lo quiere, cómo lo resuelven hoy
sin ti, quién es la persona concreta que lo sufre, cuál es lo mínimo por lo que alguien
pagaría ya, qué te sorprendió al ver a alguien usarlo, y si el mundo cambia en tres años
esto vale más o menos.

Después reta tus premisas una a una, te trae una segunda opinión de un agente
independiente, y te obliga a considerar dos o tres caminos distintos antes de elegir.

**Cierra:** el problema y si merece la pena construirlo. No escribe código. Ni una línea.

### `/prd` (antes `/define_project`)

**Entra:** `.claude/plans/IDEA.md` y cualquier documento que le pases a mano. No escanea
nada que no le nombres.
**Sale:** `.claude/plans/PRD.md`, `CLAUDE.md`, `README.md`.

Q&A guiada: features con sus criterios de aceptación, lo que NO va a hacer, roles humanos
**y actores técnicos** (quién mete carga, quién consume la salida, de qué sistemas
depende, quién lo opera), dónde vive la lógica de cada cosa, orden de construcción por
valor/riesgo/dependencias/coste/aprendizaje, cuál es el caso de uso principal,
**restricciones del proyecto** (presupuesto, plazo, equipo, stack impuesto, infra
existente, regulación) marcadas como duras o negociables, y riesgos.

**Cierra:** qué es el producto y bajo qué condiciones se construye.

> El PRD vive en `.claude/plans/PRD.md` y ya existe como plantilla. `/prd` la
> **rellena en su sitio**, no la sustituye. Su numeración es un contrato con `/plan`, que
> lee por número: §4 features con criterios, §5 arquitectura, §7 fases, §8 métricas, §10
> dependencias. Lo único añadido es la **§11 restricciones del proyecto**, al final, para
> no mover ningún número.

### `/system-design`

**Entra:** el PRD. Concretamente §2 actores, §4 features y el caso principal, §5 lo que
ya esté decidido, §7 fases, §10 dependencias, §11 restricciones.
**Sale:** `.claude/plans/SYSTEM-DESIGN.md` y un ADR por decisión relevante en `.claude/plans/decisiones/`.

Primero te pregunta el **tamaño** —herramienta de un proceso, un servicio, o sistema
distribuido— y según eso enruta qué fases corre. No te hace calcular capacidad para una
CLI. Luego propone qué **ramas** activar: distribuido, tiempo real, IA/ML, servir LLMs,
RAG, agentes, edge sin conexión, crítico con riesgo físico. Cada rama inyecta preguntas
dentro de las fases, no fases nuevas.

Después recorre: restricciones → problema y frontera → requisitos funcionales y atributos
de calidad medibles → cuantificar la escala → modelo lógico del flujo → construir o
comprar → arquitectura → riesgo → detalle donde el riesgo lo justifica → validar →
desplegar y operar. Con un registro de decisiones en paralelo, cada una con su señal de
caducidad.

**Cierra:** qué garantías da el sistema, cuánta carga aguanta, cómo funciona por dentro,
dónde está el riesgo y cómo se opera.

**Lo que la hace distinta:** te pregunta a ti antes de opinar, no calcula por ti —te da
la fórmula y te pide los números—, y **cada fase termina con una puerta que narras tú**.
Decir "sí" a un resumen suyo no cuenta como narrar. Es a propósito: la skill existe para
entrenarte, no para pensar por ti.

Al terminar te lista lo que contradice al PRD, una contradicción por pregunta, y solo lo
edita si lo apruebas.

---

## El bucle por fase

Cinco comandos: `/explore` → `/plan 2` → `/implement 2` → `/review 2` (a demanda) →
`/verify 2`. Existen por separado por una sola razón: **el que escribe el código no puede
ser el que dice si está bien.** Cada juez arranca limpio, sin ver lo que el anterior se
dijo a sí mismo. La profundidad de todo el bucle la decide lo que el explore encuentre,
no una plantilla. Espec completa: `~/.claude/workflow-v2.md`.

### `/explore <algo>` — el que mira antes de decidir

Explorar sin compromiso: un módulo, una librería, una fase, un problema. Lee el código y
los datos reales, corre sondas pequeñas (fuera del repo), consulta docs actuales. Termina
SIEMPRE en una parada: **hallazgos con cita + su lectura + recomendación con
alternativas**, y decides tú el siguiente paso — trivial (directo en sesión con un
check), `/plan`, `/investigate` si es un bug, o nada.

### `/plan <número-de-fase>` — el que alinea

El plan es para alinearse contigo, no para un ejecutor sin contexto.

1. **Explore primero** (invoca la skill o hereda sus hallazgos si ya corrió en la
   sesión). Veredicto "trivial" → no hay plan.
2. **Conversación**: las dudas reales que el explore destapó, de una en una; las
   decisiones de diseño como opciones con tradeoffs — decides tú.
3. **Documento de 1-3 páginas, prosa sin código**: objetivo, hallazgos, decisiones,
   contexto (ficheros con file:línea, docs con anchor, patrones reales), **contrato de
   aceptación** (criterios falsables + escenarios de test nombrados + comandos gate),
   out of scope, interfaces solo si hay contrato entre módulos, tareas con VALIDATE.
   **Sin tests como código** — esos los escribe un agente ciego en `/implement`.
4. **Self-review** (placeholders, contradicciones, ambigüedad) y te lo entrega:
   apruebas tú (`borrador` → `aprobado`).

### `/implement <n>` — el que construye, contigo mirando

Se niega a arrancar sobre un plan no aprobado.

- **Baseline limpio**: corre la suite acumulada antes de tocar nada; roja → para.
- **Paso 0 — RED por agente ciego**: un subagente que recibe SOLO el contrato +
  interfaces + convenciones + muestras de datos reales escribe los tests de
  aceptación. **Tú los apruebas** → van a `tests/acceptance/` → **un hook los congela**
  (editar uno exige que tú desbloquees con `touch .claude/plans/.unlock-tests`).
  Se corren: RED capturado — un test que pasa sin implementación está roto.
- Tareas en orden, incrementos pequeños, VALIDATE en verde antes de seguir, diffs a tu
  vista. Tests unitarios de andamiaje permitidos (`tests/unit/`, no son el examen).
- **Para y pregunta** ante decisiones que el plan no tomó. Rojo persistente →
  `/investigate`. Tareas independientes → te propone paralelizar, decides tú.
- Termina en "IMPLEMENTADO — pendiente de verificación" + la frase de siguiente paso:
  review con 1 revisor, panel, o saltar a verify. **No commitea: los commits son tuyos,
  al cierre de cada fase verificada.**

### `/review <n>` — el que critica (a demanda)

Lo invocas tú. Agente(s) frescos con **solo el plan y el diff** (`git add -A -N` para
que los ficheros nuevos aparezcan). Default 1 revisor; panel (+security, +architect) si
el diff toca entradas de usuario/auth/secretos, dependencia nueva o dominio de riesgo.
Cada hallazgo intenta refutarse antes de reportarse — sin repro no hay hallazgo.
Cualquier test de aceptación tocado = CRITICAL. No arregla nada y no aprueba nada.

### `/verify <n>` — el que corrige el examen

Corre los comandos gate del contrato y `tests/acceptance/` **entera**, no solo la fase
— por eso detecta que tocando la fase 4 rompiste la 2. Por criterio: PASS, FAIL,
MISSING o UNVERIFIABLE (las dos últimas no son aprobado). Sin opiniones: exit codes y
output crudo. **No puede tocar el código** — sus permisos solo alcanzan `.claude/plans/`.

- **Todo PASS** → el plan pasa a `verificado` → `archivado` (registro histórico); los
  tests se quedan en la suite como regresión perpetua; commiteas tú el cierre.
- **Algún FAIL** → decides tú: arreglar en sesión y re-verify · enmendar el criterio en
  abierto (con re-aprobación del test) · aceptarlo como deuda registrada (WAIVED).
  Nunca reintenta solo.

### `/plan-eng-review`

**Solo si la fase es grande.** Para fases pequeñas vas directo a `/implement`.

Revisa el plan, no la arquitectura — esa ya la validó `/system-design`. Su sección 1 es
una **comprobación de conformidad**: ¿inventa el plan un componente que el diseño no
describía? ¿mete una dependencia que ningún ADR cubre? ¿abre una frontera de
autenticación nueva? Si contradice un ADR, para y dice cuál.

Lo demás que aporta: te frena si el plan toca más de ocho ficheros o mete más de dos
clases nuevas, comprueba si el framework ya trae de serie lo que ibas a construir a mano,
dibuja el mapa de cobertura de tests marcando qué caminos no tienen ninguno, y levanta el
**mapa de errores** — por cada cosa que puede fallar: qué error es, si alguien lo captura,
qué hace, y qué ve el usuario. Una fila sin captura, sin test y con fallo silencioso es un
fallo crítico con nombre.

> Dos excepciones en las que **sí** hace la revisión de arquitectura completa: si no
> existe `SYSTEM-DESIGN.md`, o si el diseño se hizo con tamaño "herramienta de un proceso"
> —porque esa talla se salta la fase de validación. Plantarse cuando nadie más se levanta
> es como se abre un hueco de cobertura.

---

## Dónde vive cada cosa

Dos sitios, y la diferencia importa.

```
tests/acceptance/             ← EL PUNTO DE VERDAD (congelado por el hook)
  test_phase1_<nombre>.py       un archivo por fase, el escenario en el nombre del test
  test_phase2_<nombre>.py
```

Tests de verdad, versionados, ejecutables dentro de seis meses o en CI. Los escribe el
**agente ciego** del paso 0 de `/implement` (desde el contrato, sin ver implementación),
los apruebas tú, los congela el hook, y los ejecuta `/verify`. Lo demás es el registro
de qué se decidió y por qué:

```
.claude/plans/                ← EL REGISTRO
│
├── IDEA.md                   1º  /ceo-thinking
├── PRD.md                    2º  /prd               → lo leen /plan y /system-design
├── SYSTEM-DESIGN.md          3º  /system-design
│
├── decisiones/               los ADR, uno por decisión que condiciona el sistema
│   └── NNN-titulo.md         qué decidimos · qué descartamos · qué sacrificamos
├── alcance/                  /plan-ceo-review, opcional
│
└── <slug>/                   una carpeta por fase
    ├── plan.md               /plan → lo leen implement, verify, review; sus ## Notas
    │                         recogen desviaciones y enmiendas; al verificarse queda
    │                         archivado como registro histórico de la fase
    ├── test-plan.md          /plan-eng-review → lo lee /qa-only (solo fases gordas)
    ├── verify-report.md      /verify
    └── review-report.md      /review (cuando lo invocas)
```

Tres documentos sueltos arriba, en el orden en que los produces. Debajo, dos carpetas con
nombre que se entiende sin diccionario. Y cada fase con todo lo suyo dentro, en vez de
repartido por carpetas temáticas.

Si `/ceo-thinking` corre a nivel de feature en vez de producto, el fichero es
`IDEA-<rama>.md` — mismo sitio, sufijo con la rama.

Está dentro del repo y **versionado en git** — comprobado, no hay ninguna regla en el
`.gitignore` que excluya `.claude/`. Eso es lo que importa: que el diseño y los planes
viajen con el código y se puedan revisar en un PR.

---

## Fuera del camino principal

**`qa-only`** — abre un navegador de verdad (Playwright) y prueba la app como un usuario:
botones muertos, layouts rotos, errores de consola, flujos que se caen. Nota 0-100 y capturas
por cada bug. Nunca arregla nada y nunca lee el código fuente. Complementa a `/verify`: uno
corre la suite, el otro ve lo que la suite no puede ver.

**`learn`** — tu cuaderno. La invocas cuando algo te costó averiguar y no quieres volver a
averiguarlo. Escribe un archivo en `docs/aprendizajes/` del repo: qué pasaba, qué resulta que
es cierto, cómo lo comprobaste y qué haces distinto a partir de ahora. Escrito para que **tú**
lo releas, no para que lo consuma un agente. Busca antes de escribir: si ya hay una nota del
tema, la actualiza en vez de duplicarla.

> No confundir con la **memoria automática** de Claude Code, en
> `~/.claude/projects/<proyecto>/memory/`. Esa es para Claude, guarda cómo trabajar contigo y
> el contexto del proyecto, y se carga sola en cada sesión. `learn` es para ti y vive en el
> repo. No se solapan.

**`/plan-ceo-review`** — cuando dudas del alcance de algo grande. Cuatro modos: expandir,
expandir a la carta, mantener con rigor máximo, o recortar al mínimo. Once apartados de
revisión. Es cara: no la corras por defecto.

**`investigate`** — bug con causa no obvia. Ley de hierro: no hay arreglo sin causa raíz.
Si tres hipótesis fallan, para y replantea.

**`security-review`** — modo inline mientras tocas auth, pagos, secretos o APIs nuevas.
Modo auditoría cuando sospechas de algo o antes de un release.

**`health`** — nota de 0 a 10 con tendencia, envolviendo el linter, el type checker y los
tests del proyecto.

**`retro`** — qué has entregado esta semana, leyendo el git log.

**`context-save` / `context-restore`** — guardar y retomar sesión. Distinto de `/context`,
que lee el estado vivo del proyecto ahora mismo en vez de tu memoria de trabajo.

**`careful`** — avisa antes de comandos destructivos. Siempre activa.

**`skill-writer`** / **`find-skills`** — escribir skills nuevas / buscar e instalar existentes.

---

## Cosas que conviene saber

**El PRD no es sagrado.** `/system-design` lo va a contradecir, y eso es sano: se escribió
sin la información técnica que el diseño produce. Dos features que en realidad son una,
una fase tardía que resulta ser un cimiento, un orden que viola una dependencia de datos.
La skill te lo lista y tú decides.

**Los criterios vagos se propagan.** Los criterios de aceptación del §4 del PRD se
convierten en el contrato de `/plan`, que es lo que `/verify` ejecuta. Vago ahí es vago
en todo lo demás.

**Las decisiones caducan.** Cada ADR lleva una señal de caducidad: qué tendrías que
observar para reabrirla. Sin eso el registro de decisiones se convierte en un cementerio
que nadie relee.

**El bucle hereda el modelo de la sesión.** Ya no hay reparto Opus-planifica /
Sonnet-teclea: el plan es para alinearse contigo y la implementación corre contigo
mirando, así que ambos usan el modelo con el que estés trabajando.

**gstack ya no existe en esta máquina.** Lo que dependía de sus scripts o de su binario
`browse` fallaba en silencio. A `office-hours`, `plan-ceo-review` y `plan-eng-review` se les
quitó la dependencia (originales en `~/.claude/skills/.backup-pre-gstack-strip/`); `qa-only`
se reescribió sobre Playwright; `scrape` y `make-pdf` se retiraron a
`~/.claude/skills/.removed/`.

**Vigila el número de skills.** Pasado una docena por ámbito, la elección empieza a
fallar. No optimices antes de notar degradación real.
