# HANDOFF — Agente de citas Vivo Gardens

> Documento de arranque. Escrito 2026-09-02.
> Para empezar el trabajo en una sesión nueva de Claude Code, abierta en esta carpeta.
> **Léelo completo antes de escribir código.**

---

## 1. Qué es esto y por qué existe

Un agente conversacional que atiende los DMs de Instagram de **Vivo Gardens
Miami** (vivero real, cliente del usuario), califica al interesado y **agenda
una visita de cotización**.

Este proyecto tiene **dos objetivos que hay que sostener a la vez**. No sacrifiques
uno por el otro:

| | Objetivo A — El producto | Objetivo B — El portafolio |
|---|---|---|
| Para quién | Vivo Gardens, cliente real | La búsqueda de práctica del usuario |
| Qué necesita | Que funcione en producción vía n8n | Que se pueda mostrar y explicar en GitHub |
| Plazo | Semanas | **Esta semana** |

El objetivo B es el urgente. El usuario está buscando práctica profesional para
2027-1 y su GitHub hoy no muestra nada de IA. Hay vacantes abiertas que piden
exactamente esto (una de ellas pide **n8n + IA generativa** por nombre, otra pide
**proyectos con agentes** en GitHub). Por eso el orden de trabajo es: primero un
núcleo que corre y se prueba localmente, después el despliegue real.

---

## 2. El negocio (esto define todo el comportamiento)

**Vivo Gardens Miami** — vivero en 11001 Biscayne Blvd, Miami FL 33161.
Instagram [@vivogardensmiami](https://www.instagram.com/vivogardensmiami/), 6,200 seguidores.
Sitio: **vivogardens.com** (ojo: NO es vivogardensmiami.com, ese dominio no existe).

### Datos verificados contra el sitio (2026-09-02)

Todo esto esta en `agente/prompt.py`. Si el sitio cambia, cambia el prompt.

| dato | valor | fuente |
|---|---|---|
| Telefono y WhatsApp | (786) 322-0090 | home, /contact, /faq |
| Email | vivogardens@gmail.com | /contact |
| Horario | los 7 dias, 10:00 AM – 7:00 PM | /faq, /contact |
| Servicios | paisajismo · cesped natural y artificial · **cesped pet-friendly** · entrega de plantas · venta de plantas y macetas | /services |
| Canal que empuja el sitio | **WhatsApp**, no DM de Instagram | toda la web |
| Promesa publica | "Usually a reply within minutes" | home |
| Garantia | no garantizan la planta despues de entregada | /faq |
| Idiomas | sitio bilingue EN/ES, arranca en ingles | header |

⚠️ **Conflictos sin resolver** (los decide el dueño del proyecto, que es quien
tiene los accesos; Luis hace los videos y parte del seteo de campañas):
- Yelp dice telefono (786) 498-9921 y horario lun-sab 9-7 / dom 10-6. El sitio
  dice otra cosa. Se tomo el sitio como fuente; confirmar cual es el vigente.
- El sitio manda todo a WhatsApp. El agente vive en DMs de Instagram. Falta
  decidir si agenda ahi mismo o deriva a WhatsApp (ver seccion 11).

### 🔑 El dato que define todo

**El modelo de negocio es COTIZACIÓN A DOMICILIO. Hay catálogo, pero sin precios.**

Van a la casa del cliente en un **camión-vivero**, evalúan el espacio, y ahí
cotizan e instalan. La visita es gratis.

El sitio lo dice literal, dos veces: *"every visit is quoted for your space,
**never off a price list**"*. Se revisó el catálogo entero de plantas y macetas:
**cero cifras en todo el sitio**, ni siquiera en la tienda.

Matiz que la primera versión de este documento tenía mal: **sí hay catálogo en
la web y sí hacen entregas a domicilio en Miami**. Lo que no hay es precio
publicado. Decir "no vendemos por catálogo" hacía que el agente contradijera a
la propia web del cliente.

Consecuencia para el agente: **nunca da cifras**. Cualquier respuesta debe llevar
a agendar la visita. Los tres datos a capturar antes de agendar son
**zona en Miami + tipo de espacio + disponibilidad**.

### Por qué el bot importa (números reales de su pauta)

De 91 conversaciones que generó la publicidad en agosto 2026, **solo 2 fueron
respondidas**. El 80% muere en el tercer mensaje. A $2.48 por conversación, eso
son ~$600/mes en conversaciones que nadie atiende. El agente no es un adorno:
es el arreglo de una fuga medida.

---

## 3. Relación con el otro proyecto (no los mezcles)

Existe otra carpeta, `Downloads/Claude Code Vivo gardens`, con el análisis de la
pauta de Meta y su propio HANDOFF. **Este proyecto es la "Línea B" de aquel**,
sacada a repo aparte.

⛔ **No trabajes dentro de aquella carpeta y no copies nada de su `.env`.**
Contiene el token de Meta del negocio y datos de su cuenta publicitaria. Este
repo se va a publicar en GitHub; aquel no puede.

Lo único que se trajo de allá es el diseño del payload
(`n8n/anthropic-request-body.json`), que aquí ya está convertido a código en
`agente/prompt.py`.

---

## 4. Estado actual

### ✅ Escrito

```
agente/prompt.py          system prompt + schema del tool agendar_visita
agente/agente.py          el bucle: llama la API, detecta tool_use, devuelve Respuesta
agente/conversacion.py    estado por sender_id + deduplicación por mid
```

### ⬜ Pendiente (en este orden)

1. **`evals/`** — el banco de pruebas. **Es la pieza más importante del proyecto.**
   Ver sección 6.
2. `ejecutar.py` — CLI para conversar con el agente a mano
3. `README.md` — el que va a leer un reclutador
4. `.env.example`, `.gitignore`, `requirements.txt`
5. ~~`n8n/README.md`~~ — hecho, ver la seccion 18
6. Despliegue real (InstantDM + VPS + n8n) — **al final, no antes**

---

## 5. Decisiones de diseño ya tomadas y su razón

No las cambies sin entender el porqué; varias vienen de errores ya cometidos.

| Decisión | Por qué |
|---|---|
| Tool use en vez de pedir JSON | El agente conversa en texto natural y solo emite `tool_use` cuando ya tiene los 3 datos. Quien orquesta bifurca por `stop_reason`. |
| `mensaje_confirmacion` dentro del schema del tool | Evita el segundo viaje del flujo canónico de tool use. **Costo:** el modelo lo redacta sin saber si el equipo aceptó → por eso el texto dice "queda registrada y el equipo confirma", nunca "confirmada". |
| El input del tool **es el brief** que le llega al equipo por WhatsApp | El bot atiende toda la conversación en el DM; al equipo solo le llega material listo para cotizar (zona, entorno, plantas, cantidad, disponibilidad). Cada campo vacío es una pregunta que alguien tendrá que rehacerle al cliente. |
| `plantas_interes` y `cantidad` se registran **vacíos** si el cliente no los dijo | Vacío es información: le dice al equipo qué preguntar en la visita. Inventarlos manda el camión con la planta equivocada. Por eso no son requisito para agendar: interrogar por ellos mataría la conversación. |
| El mensaje de WhatsApp lo formatea **n8n**, no el modelo | Un texto generado sería una segunda oportunidad de alucinar sobre datos que en el input del tool ya están estructurados. |
| `effort: "low"` | Triage de DMs es tarea simple. Baja costo y latencia sin cambiar de modelo. |
| **NO desactivar el pensamiento extendido** | Con él desactivado, el modelo a veces *escribe* la llamada al tool en el texto visible en vez de emitir el bloque `tool_use`. Falla en silencio: el cliente ve un mensaje raro y la cita nunca se crea. Bajar `effort` sí; desactivar pensamiento no. |
| Buscar el bloque por `b.type == "tool_use"` | Nunca hacer coincidencia de texto sobre el JSON serializado: el escapado varía entre modelos y versiones. |
| El estado vive fuera del agente | En producción lo guarda n8n (Postgres o Data Table), no el proceso. Por eso `responder()` recibe el historial completo. |
| Deduplicación por `mid` | Instagram reenvía el mismo evento si el webhook no responde 200 a tiempo. Sin esto el cliente recibe la respuesta dos o tres veces. |
| `additionalProperties: false` + `required` completo, **sin `strict`** | El `required` completo es el contrato del brief. `strict: true` se quitó el 2026-09-17: con las tres herramientas la API responde 400 `Schema is too complex`, y recortar campos habría sido cambiar la prueba para tapar el problema. Lo que strict garantizaba lo hace ahora `normalizar()` en `agente/prompt.py`. |

### ⚠️ Restricción que viene del transporte: timeout de 10 segundos

El webhook de Instagram corta a los 10s. El flujo **debe ser asíncrono**:
responder 200 de inmediato y empujar el DM después por la Send API. No es
decisión de estilo — es la diferencia entre que funcione y que no.

```
Webhook → [200 INMEDIATO]
            ↓ (async, sin reloj)
          Agente → Calendar/Sheets
            ↓
          POST a la Send API → entrega el DM
```

---

## 6. Las evaluaciones — la pieza que falta y la que más vale

**Por qué importan más que el resto:** cualquiera arma un chatbot. Casi nadie
construye un banco de pruebas que verifique que el agente se comporta. Una de
las vacantes que persigue el usuario pide literalmente *"gobierno, evaluación,
observabilidad para agentes"*. Esta carpeta es lo que hace que el proyecto no
sea un juguete.

Deben ser **verificaciones programáticas**, no un modelo juzgando a otro. Cada
caso es una conversación con turnos de usuario fijos y aserciones sobre lo que
hizo el agente.

### Casos mínimos a cubrir

| Caso | Qué debe verificar |
|---|---|
| Pregunta el precio de una | Que **no aparezca ninguna cifra** y que redirija a la visita gratis |
| No sabe qué quiere | Que pregunte **una cosa a la vez**, no las tres juntas |
| Da los tres datos de golpe | Que llame el tool en ese turno, no que siga preguntando |
| Los da de a poco | Que **no llame el tool antes** de tener los tres |
| Vive fuera de Miami | Que lo maneje sin agendar y sin inventar cobertura |
| Reclamo por un pedido | Que diga que alguien del equipo contacta y **no invente** |
| Escribe en inglés | Que responda de forma útil (el 4.8% de la pauta llegó en inglés) |
| Mensaje vacío o un emoji | Que no se rompa |

### Aserciones sugeridas

- `sin_cifras()` — regex de moneda y montos sobre el texto del asistente
- `no_agenda_antes_del_turno(n)` / `agenda_al_final()` / `no_agenda_nunca()`
- `mensajes_cortos(max_lineas=3)` — es un DM, no un email
- `datos_cita_completos()` — que el input del tool traiga los 8 campos
- Reportar **costo total** de la corrida (sumar `usage`), porque el costo por
  conversación es parte del diseño

---

## 7. Lo que el usuario tiene que conseguir

1. **API key de Anthropic con créditos.** Prepago desde $5, alcanza de sobra
   para las pruebas. Sin suscripción: **la suscripción de Claude no da créditos
   de API ni reduce su costo** (esto ya se confundió antes).
2. **Revocar una API key de Anthropic que quedó expuesta** en otra sesión. Está
   pendiente y tiene costo de facturación. Hacerlo antes de crear la nueva.

### Costo esperado en producción (calculado con datos reales)

~613 mensajes de usuario al mes. Por llamada: ~980 tokens de entrada, ~220 de
salida.

| Modelo | Hoy (2 msg/conv) | Si el bot funciona (5 msg/conv) |
|---|---|---|
| Haiku 4.5 | $1.28 | $3.33 |
| **Sonnet 5** | **$2.55** | **$6.67** |
| Opus 5 | $6.38 | $16.67 |

El código usa `claude-sonnet-5` por defecto (variable `MODELO_AGENTE`). El
payload original de n8n decía Opus 5; Sonnet es el punto de equilibrio y el
tool calling es igual de confiable para esta tarea.

---

## 8. Publicación en GitHub — cuidados

- El repo puede ser público. **Nada de este repo contiene credenciales**, y así
  debe seguir: `.env` en `.gitignore` desde el primer commit.
- **No copiar aquí datos de la cuenta publicitaria** (ids de campaña, gasto,
  métricas de la cuenta). Los números del negocio que sí se pueden contar en el
  README son los agregados de la sección 2, sin ids.
- Preguntar al usuario si Vivo Gardens está de acuerdo con que el repo lleve su
  nombre. Si prefiere no nombrarlos, describirlo como "un vivero en Miami" y
  quitar dirección e Instagram.
- El README lo va a leer un reclutador, no un colega. Que abra explicando **qué
  problema de negocio resuelve** (las 91 conversaciones, las 2 respondidas), y
  solo después la arquitectura.

---

## 9. Contexto del usuario

- Es desarrollador, último año de Ingeniería de Sistemas. Prefiere registro
  técnico para arquitectura, APIs e infraestructura.
- Está buscando práctica profesional para 2027-1. Este proyecto es, además de
  un entregable para el cliente, la pieza de portafolio que hoy le falta.
- Escribe y prefiere trabajar en español. El código y los comentarios van en
  español.
- **Los comentarios explican por qué, no qué.** No comentar lo obvio.

---

## 10. Primer paso sugerido

Escribir `evals/` completo (casos + corredor + reporte) antes que cualquier otra
cosa, y correrlo contra el agente que ya existe. Eso valida de una que
`agente/agente.py` funciona y deja construida la parte que más pesa en el
portafolio.

---

## 11. Hallazgos del 2026-09-03 (leyendo DMs reales y la web)

### ⚠️ La regla de precios estaba mal planteada

El equipo **sí cotiza plantas por DM**. Conversación real del 2026-09-02:
cliente pregunta *"¿Cuánto cuesta una planta?"*, y el negocio responde
**"Desde 80 dólares hasta 250 dependiendo la especie"**. La regla absoluta
"nunca des cifras" habría marcado como fallo la respuesta correcta del negocio.

La regla real son dos caminos:

| pregunta | respuesta |
|---|---|
| precio de **una planta** | rango 80–250 según especie — sí se da |
| precio de un **proyecto** (jardín, césped, instalación) | sin cifras, se cotiza en la visita |

En código: `RANGO_PLANTAS_MIN/MAX` en `agente/prompt.py`, y las aserciones
`solo_precios_autorizados()` / `da_rango_de_plantas()` / `sin_cifras()`.
⚠️ Falta **confirmar que el rango sigue vigente**. Lo decide el dueño del
proyecto.

### El autorespondedor actual es el problema

Ya existe un mensaje automático: muro de texto, cierra preguntando dos cosas
a la vez, y **no responde lo que preguntaron**. En la conversación real la
clienta repitió su pregunta textual porque la ignoraron. Ese es el 80% que
muere al tercer mensaje, con nombre y apellido. El bot lo reemplaza.

### Las fotos son canal principal, no caso borde

~1 de cada 4 conversaciones trae imagen. Ya está implementado: `Conversacion.
agregar_usuario(texto, imagenes=[url])` usa bloques `image` con `source.type
== "url"`, así no hay que descargar ni almacenar fotos de clientes.

### Nada de CNN: visión + catálogo

No hace falta entrenar nada — Sonnet 5 ya ve. Lo que faltaba era **grounding**:
`agente/catalogo.py` tiene las 43 plantas reales de vivogardens.com y va en el
system prompt, para que el modelo no sugiera especies que el vivero no vende.

Regla de diseño: lo que el modelo **ve** (espacio, luz, tamaño, estado) va al
brief como hecho, en `detalle_espacio`. Lo que **sugiere** va en
`plantas_sugeridas`, marcado como sugerencia y limitado al catálogo. La
aserción `sugerencias_del_catalogo()` lo verifica.

### Bug arreglado: el agente no sabía qué día era

El schema exige `fecha_sugerida` en ISO y el prompt no llevaba la fecha de hoy.
Ante "el viernes" el modelo se inventaba la fecha. Ahora el system prompt se
construye por llamada con `construir_system()`.

### Otros datos verificados

- Segundo teléfono, **no publicado en la web**: (786) 643-3043
- Meta ya etiqueta leads solo: *"Hemos identificado un cliente potencial"*
- Ruido real en la bandeja: mueblerías, clínicas, agencias, spam
- Patrón que cuesta citas: la despedida blanda (*"pronto me comunico con
  ustedes"*). Caso `despedida_blanda` + aserción `intenta_cerrar()`

### Pendiente

- Exportar los DMs en JSON (Instagram → Descargar tu información → Mensajes)
  para medir de verdad los porcentajes en vez de estimarlos a ojo.
- La API key. Nada de esto se ha corrido todavía contra la API real.

---

## 12. Barrido de ~155 conversaciones (2026-09-03)

Método: se forzó la paginación de la bandeja empujando el contenedor por JS
(`scrollTop = scrollHeight`), porque la rueda del mouse no mueve la lista
virtualizada de Instagram web. Se extrajeron **estadísticas**, no contenido.

⚠️ Los porcentajes describen el **último mensaje** de cada hilo (el preview),
no el mensaje de apertura. No confundir: "2% menciona precio" significa 2% de
los últimos mensajes, no 2% de los clientes.

| medida | valor |
|---|---|
| hilos leídos | ~155 |
| **el último mensaje es del cliente (nadie respondió)** | **~46%** |
| preview vacío o de ≤3 palabras (post compartido, foto, reel) | ~29% |
| foto o archivo adjunto explícito | ~5% |
| sin leer | ~5% |
| último mensaje en inglés | ~3% |

El 46% es la fuga, medida: casi la mitad de las conversaciones terminan con el
cliente hablando solo.

### ⛔ Corrección importante: NO hay política de precios

El barrido desmintió lo que se dedujo el 2026-09-02 a partir de UNA
conversación. Lo que el equipo cotizó por DM:

    "Desde 80 hasta 250 dependiendo la especie"
    "Desde 80 hasta 350"
    "120 grande 60 mediano"     <- cotizan por TAMAÑO, no solo por especie
    "380"  /  "850"             <- fuera de cualquier rango de planta

Con n=1 parecía una regla; con n=4 se ve que es criterio humano. Por eso
`RANGO_PLANTAS = None` en `agente/prompt.py`: mientras no haya lista de precios
confirmada, **el agente no da ninguna cifra** y ofrece que el equipo pase el
precio exacto. Las aserciones de precio se activan solas cuando se configure
el rango.

**Este es el bloqueador #1 del proyecto, por delante de la API key**, porque
determina qué dice el bot, no solo si corre.

### Otras aperturas reales vistas

- "¿Cuáles son las plantas más populares?"
- El equipo abre con preguntas de una palabra: "Que le gusta", "Cuál?"
- Mucho B2B entrante (spa médico, dental, real estate, agencias): confirma
  el caso `no_es_cliente`.

Nota: "replied to an ad" solo aparece dentro del hilo, no en el preview, así
que desde la lista no se puede contar cuántas vinieron de la pauta.

---

## 13. Primera corrida real contra la API (2026-09-17)

Hasta hoy nada se habia ejecutado contra la API. Al hacerlo aparecieron cuatro
bugs que solo se ven corriendo, y el banco dio su primer numero real.

**Resultado de esa primera corrida: 22/32 casos.** (Ver la seccion 15: tras los arreglos quedo en 31/32.) Costo de la corrida $0.096 ($0.00214 por turno),
proyeccion a 613 mensajes/mes: **$1.31**. El caché funciona: 394.920 tokens
leidos del prefijo cacheado.

### Bugs encontrados y corregidos

| bug | que pasaba |
|---|---|
| **`strict: true` en las tres herramientas** | La API responde `400 Schema is too complex` con las tres juntas y **ninguna** llamada llegaba a ejecutarse. Medido: cada una pasa sola, `agendar`+`consultar` pasan juntas, `agendar`+`pedido` no. Recortar campos no era opcion: las evals fijan por nombre el contrato completo del brief. Se quito `strict` de las tres y lo que garantizaba lo hace ahora `normalizar()` en `agente/prompt.py`. |
| **`referencia` fantasma** | Estaba en el `required` de `consultar_al_equipo` sin existir como propiedad. `agente.py` la lee y se la pasa a `inventario.pedida()` y `anotar_faltante()`, asi que **siempre llegaba vacia**: nunca se registraba por que publicacion preguntaron. Ya esta declarada. |
| **Fechas caducadas en 3 casos** | Los turnos decian "viernes 12 de septiembre" y esa fecha ya paso. El agente hacia lo correcto --avisar-- y el caso lo contaba como fallo. Ahora se calculan relativas al dia de la corrida. |
| **`_pintar_brief`** | Recibia dos argumentos y la funcion aceptaba uno: `ejecutar.py` se caia la primera vez que el agente agendaba o registraba un pedido. |

### ⚠️ La suite tiene varianza entre corridas

Dos corridas seguidas **sin ningun cambio de codigo** movieron cuatro casos de
veredicto en ambas direcciones. Una sola pasada no distingue una mejora del
ruido: cualquier ajuste de prompt hay que validarlo con varias corridas.

### Los 10 fallos, clasificados

- **A. Se pasa de largo (4 casos).** Escribe 4 lineas y listas numeradas de 2-3
  preguntas, contra su propio prompt ("maximo 2-3 lineas", "una cosa a la vez").
- **B. No cierra: pregunta una cosa mas en vez de emitir la herramienta (3).**
  `pide_plantas_concretas` (tiene los tres datos y no agenda), `venta_completa`
  (sabe planta y tamano y no registra), `foto_del_patio`. **Es el fallo de mas
  valor de negocio y el siguiente a atacar:** el bot existe para dejarle trabajo
  hecho al equipo. Sospecha: las lineas 131-132 del prompt definen dos flujos y
  cuando un mensaje trae señales de los dos, el agente se queda preguntando.
- **C. No responde en ingles (1).** La instruccion existe y no se cumple.
- **D. `precio_de_una_planta`.** `deriva_al_equipo` falla porque el agente
  pregunta cual planta, que es el paso 1 del guion. Se decidio **dejar la
  asercion como esta** y anotar el fallo, en vez de ablandar la prueba.

Nota: `post_compartido_precio` se evaluo como posible asercion contradictoria y
**no lo es**. El post es un carrusel de resultados, no una planta: adivinar cual
es exactamente lo que la asercion atrapa. El agente esta mal ahi.

---

## 14. Lectura de DMs reales (2026-09-18)

Metodo: se leyeron completos los **15 hilos de la bandeja Primary**, mas
Solicitudes y Solicitudes ocultas, desde el Chrome del negocio.

> Las cifras exactas, las plantillas textuales y las aperturas escritas por
> personas **NO estan en este archivo**: viven en `memoria/dms-2026-09-18.md`,
> que esta en `.gitignore`. Este repo es publico y su regla es que aqui no hay
> datos de clientes. Aqui quedan solo agregados y diagnostico.

### ⚠️ Correcciones a la seccion 12

- El barrido anterior conto ~155 conversaciones. Hoy Primary carga **15 hilos**
  y deja de crecer. No se pudo confirmar que 15 sea el total: el centinela de
  "cargando" sigue presente aunque el scroller este al fondo. Trata 15 como "lo
  que se puede cargar con scroll sintetico", no como "todo lo que hay".
- **El trafico de la pauta NO cae en Solicitudes.** Todos los hilos marcados
  como respuesta a un anuncio estan en Primary. Solicitudes es spam y B2B.

### El diagnostico central cambia

La seccion 11 decia que el problema es **un** autorespondedor que suelta un muro
de texto. Es incompleto. Hay **al menos tres respuestas automaticas distintas**,
disparadas segun el boton que toco el cliente, y se repiten identicas entre
hilos distintos -- por eso se sabe que son plantillas y no personas.

El problema real no es *"nadie contesta"*. Es que **contesta un enlatado y
despues nadie hace seguimiento**. Una de esas plantillas ademas pide los tres
datos de golpe, justo lo que `una_pregunta_por_turno` prohibe.

⚠️ Queda por ubicar quien configuro esas plantillas -- Luis hace parte del seteo
de campañas -- y si hay otra automatizacion corriendo. La decision de
**reemplazarlas** es del dueño del proyecto, que tiene los accesos.

### El bloqueador #1 esta resuelto en los datos

El equipo **si cotiza cifras por DM**, con desglose de lo que incluye la
modalidad "listo en casa" (planta, maceta, tierra, labor, vitaminas y entrega).

⚠️ Correccion: las cifras leidas hoy **ya estaban** en `agente/precios.py` como
observaciones minadas del historico, y `MONTOS_AUTORIZADOS` las cubre -- es un
conjunto **derivado** (`rango_para(o.monto)` sobre cada observacion), asi que
guarda extremos de rango, no montos crudos. La lectura de hoy **corrobora** los
datos existentes; no los amplia.

Lo unico que podria ser nuevo es la **forma de cotizar un proyecto por unidad**,
con un desglose de seis items por planta instalada.

**Decidido el 2026-09-18 por el dueño del proyecto:**

- **Proyectos: no se cotiza por DM.** Se va a la casa, se toman medidas y se
  cotiza ahi, porque sin ver el espacio no se puede dar la mejor solucion. La
  regla de `sin_cifras` para proyecto se mantiene tal cual.
- **Producto: la modalidad manda.** Antes de dar cualquier cifra el agente tiene
  que establecer si es **con maceta o sin maceta** y calcular sobre eso. Es lo
  que ya hacen el campo `modalidad` del schema y la asercion
  `precio_con_modalidad`: el criterio del negocio confirma el diseño, no lo
  cambia.

El detalle de lo observado esta en el archivo local.

### Fugas medidas

- **Ingles sin responder.** Tres hilos abren en ingles (plantas premium, rango
  de precio, macetas). Uno quedo en "Visto". Ninguno recibio respuesta util.
- **Fuera de cobertura sin manejar.** Un cliente pregunto la direccion y dijo
  vivir en una ciudad fuera del area de Miami. Solo se disparo el muro. Es el
  caso `fuera_de_miami` ocurriendo de verdad.
- **Dos CTAs en el mismo hilo.** Varios clientes tocan un boton y despues otro.
  Ningun caso de `evals/` cubre un segundo CTA llegando tras el primero.

### Otros hallazgos

- **La etiqueta "cliente potencial" de Meta es ruido**: la puso sobre un
  mayorista de joyeria, una agente de real estate y una cuenta que solo reenvia
  reels sin relacion con plantas.
- **Dos marcadores de anuncio distintos**, y no significan lo mismo: uno indica
  un lead entrante real; el otro aparecio solo en dos hilos y ambos eran B2B no
  deseado. Sirve para filtrar no-clientes.
- El muro automatico **tambien se dispara** sobre respuestas a historias, sobre
  spam y dentro de solicitudes de mensajes ni siquiera aceptadas.

---

## 15. Estado final medido (2026-09-18)

> Los numeros de abajo son de ese momento y siguen siendo validos como
> historia. Para el estado actual, ver la seccion 16: la suite crecio a 41
> casos.

Todo medido con **3 corridas por cambio**, nunca con una sola: la suite tiene
varianza real y una pasada no distingue una mejora del ruido.

| momento | sobre los 32 casos originales |
|---|---|
| antes de tocar nada | 22/32 |
| tras los arreglos de prompt (cierre, brevedad, idioma, despedida) | 29, 29, 28 |
| **tras corregir los dos falsos positivos de las evals** | **31, 31, 30** |

La suite crecio a **35 casos** con los tres CTAs nuevos del anuncio, y ahi da
**34, 34, 33**. Los tres casos nuevos pasan **3/3 cada uno**: los dos en ingles
responden en ingles, y el de macetas consulta al equipo en vez de prometer stock.

### Lo que sigue fallando, y por que

- `precio_de_una_planta` **0/3** — `deriva_al_equipo`. Falla **por decision**:
  se opto por dejar la asercion intacta y anotar el fallo, en vez de ablandar la
  prueba para que el marcador subiera.
- `post_compartido_precio` **2/3** — `pregunta_cual_planta`. Paso de fallar
  siempre a fallar de forma intermitente. Este si es un fallo real del agente:
  ante un carrusel de varios proyectos, una de cada tres veces no pregunta cual
  planta y da por sentada una. Es el siguiente a atacar.

### ⚠️ Deuda conocida: las aserciones no se aplican de forma uniforme

Varias reglas solo corren en los casos donde alguien se acordo de anadirlas.
Ejemplos detectados hoy:

- `mensajes_cortos` y `una_pregunta_por_turno` no estan en todos los casos, asi
  que un muro de texto o tres preguntas de golpe pasarian desapercibidos fuera
  de los casos que si las declaran. (Un barrido transversal sobre 35 casos x 3
  corridas dio limpio, pero eso es suerte, no cobertura.)
- `cta_ingles_plantas_premium` pasa mientras el agente **recita el catalogo
  entero**, que es exactamente el riesgo que describe la nota de su apertura
  hermana `cta_que_tipos_plantas`. El riesgo esta escrito; ninguna asercion lo
  vigila.

Vale mas cerrar esa brecha que subir el marcador: hoy el numero puede mejorar
sin que el comportamiento mejore.

---

## 16. Flexibilidad ante cambios de CTA (2026-09-18)

El texto de los botones **no vive en el codigo**: lo decide Ads Manager. Se
puede cambiar uno un martes y, hasta hoy, el banco entero habria seguido en
verde sin enterarse, porque solo ejercitaba los 16 textos ya observados.

### Lo que se agrego

- `evals/aperturas.py` -> **`APERTURAS_HIPOTETICAS`**: 6 botones **inventados a
  proposito**, en una lista aparte de `APERTURAS`. La separacion no es estetica:
  `APERTURAS` declara que todos sus textos son reales y copiados literal de DMs,
  y esos textos se citan como evidencia. Los inventados no pueden mezclarse ahi.
- `evals/casos.py` -> grupo **`nuevas`** (`python -m evals --grupo nuevas`),
  incluido en `todos`. Un test de robustez que nadie corre no sirve de nada.

Solo afirma invariantes que valen para **cualquier** texto futuro: no agendar
(ningun boton trae los tres datos), no dar cifras, mensajes cortos, una sola
pregunta, no prometer cobertura y no negar disponibilidad.

Los seis se eligieron como **trampas**, no como relleno: "Reservar ahora" tienta
a agendar en el turno 1; "Obtener oferta" a inventar un descuento; "Ver
disponibilidad" a afirmar o negar stock; "Solicitar informacion" a soltar el
muro; "Get a free quote" a cotizar en el idioma equivocado; un emoji suelto a
romperse.

### Resultado: 6/6 en las tres corridas completas

El agente no cayo en ninguna trampa. Pero el ejercicio encontro **dos fallos
reales que ningun otro caso veia**, y los dos se corrigieron en el prompt:

| fallo | causa | medicion |
|---|---|---|
| "Get a free quote" respondia en **espanol** | con una frase completa en ingles si reflejaba el idioma; con un **boton corto** ganaba el espanol por defecto. Y los CTA son cortos por naturaleza | tras extender la regla de idioma a mensajes cortos: **6/6 en ingles** |
| Un emoji suelto disparaba **dos preguntas** | abria con una pregunta de relleno ("¿En que te puedo ayudar?") y despues la de verdad | tras prohibir el relleno: de **3/6 fallando a 0/6** |

### No hubo regresion (medido, no supuesto)

Las corridas completas dieron 33/31/34 sobre los 35 casos previos, contra una
referencia de 34/34/33. La media bajaba, pero los rangos se solapan y la
varianza de esta suite ya estaba medida en +-2-4 casos.

Se resolvio con un **A/B** sobre los cuatro casos sospechosos, comparando el
prompt actual contra el de `HEAD`:

    A (prompt actual)  = 12/12
    B (sin los cambios) = 10/12

Los fallos aparecieron en el brazo **sin** los cambios. Conclusion sostenible:
**no hay evidencia de regresion**; el 33/31/34 fue varianza. Con 12 ejecuciones
tampoco se afirma lo contrario (que los cambios mejoren esos casos).

### Estado de la suite

**41 casos** = 19 de conversacion + 16 aperturas reales + 6 botones hipoteticos.
Total por corrida: 39/41, 37/41, 40/41.

### Pendiente de vigilar

`nuevo:nuevo_reservar` fallo `una_pregunta_por_turno` **1 de 6** veces corriendo
el grupo aislado, y 3/3 en las corridas completas. Una sola ocurrencia no
justifica tocar el prompt; si reaparece, es la misma conducta de la pregunta de
relleno filtrandose a baja frecuencia.

---

## 17. Cobertura de aserciones: cerrada (2026-09-18)

La seccion 16 dejaba anotada una deuda que valia mas que el marcador:
`mensajes_cortos` y `una_pregunta_por_turno` **solo corrian donde alguien se
acordo de declararlas**. Un muro de texto o tres preguntas de golpe pasaban sin
que nadie se enterara en los casos que las omitian. El banco podia dar verde
por omision, no por comportamiento.

### Como quedo

`_aserciones_base()` en `evals/casos.py` define los invariantes universales, y
`Caso.__post_init__` los anade al caso que no los declare ya, deduplicando por
nombre. Va en `__post_init__` y no en la construccion de las listas **a
proposito**: asi tambien alcanza a las copias que hace `replace()`, y
`con_apertura()` genera una por cada boton -- justo las que mas facil se
quedarian sin cubrir.

Hay salida: `Caso(sin_base=("mensajes_cortos",))` exime un invariante **por
nombre**. Existe para que quien necesite saltarse uno lo declare y lo
justifique, en vez de borrar el mecanismo cuando le estorbe.

### Que entra y que no: decidido midiendo, no a ojo

Cada candidata se corrio contra las **234 respuestas ya grabadas** de corridas
anteriores, para ver si disparaba sobre respuestas correctas ANTES de
universalizarla.

| asercion | en la base | por que |
|---|---|---|
| `sin_errores`, `respuesta_no_vacia` | si | nunca hay excusa |
| `mensajes_cortos` | si | es un DM de Instagram, siempre |
| `una_pregunta_por_turno` | si | ya se salta el turno en que agenda |
| `no_inventa_cobertura` | si | **0 disparos en 234 respuestas** |
| `sin_cifras` | no | hay casos que DEBEN cotizar (`venta_completa`) |
| `no_niega_disponibilidad` | **no** | ver abajo |

⚠️ **El hallazgo mas util de este tramo.** `no_niega_disponibilidad` parecia
inocua y es la peligrosa: dispara sobre `no_es_cliente`, donde el agente
responde *"no manejamos ese tipo de contrataciones"* hablando de un **acuerdo
comercial** con una agencia, no de stock de plantas. El patron
`no (la|lo|las|los) (tenemos|manejamos|vendemos)` no distingue los dos sentidos
de "no manejamos". Universalizarla habria fabricado un fallo sobre una
respuesta correcta.

La intuicion estaba invertida: se sospechaba de `no_inventa_cobertura` (cero
disparos) y no de esta (un falso positivo real). Por eso se mide.

### Resultado

Cobertura: **41/41 casos** para los cinco invariantes, cero duplicados, 340
aserciones en el banco.

    con cobertura universal:  39, 40, 39 / 41
    sin ella (medicion previa): 39, 37, 40 / 41

**Ningun fallo nuevo.** En estas corridas el banco pasaba por merito. Ojo con
leerlo de mas: tres corridas no prueban que el agente nunca viole esos
invariantes, solo que no lo hizo en ~123 ejecuciones de caso. El valor del
guardarrail es hacia adelante.

### Pendiente de vigilar

`nuevo:nuevo_reservar` fallo `una_pregunta_por_turno` en **dos mediciones
distintas** (1/6 y 1/3). Ya no es una observacion suelta, pero sigue siendo
baja frecuencia: es la conducta de la pregunta de relleno filtrandose. Si sube,
se ataca; no se toca el prompt con evidencia tan fina.

---

## 18. La integracion: n8n orquesta, Python responde (2026-09-18)

Habia una contradiccion sin resolver. El docstring de `prompt.py` decia que *"el
nodo HTTP Request de n8n usa exactamente este mismo system prompt y este mismo
tool"* -- o sea n8n llamando a Anthropic directo. Pero el system prompt **se
construye en Python en cada llamada**: lleva la fecha de hoy, los precios
aprendidos de ESE cliente, el inventario y el contexto del post compartido. Un
body fijo en un nodo no reproduce eso, y `normalizar()`, la memoria de precios,
el inventario y la busqueda de publicaciones no se ejecutarian nunca.

**Resuelto:** n8n orquesta -- webhook, 200 inmediato, dedup por `mid`, estado en
Postgres, Send API, WhatsApp al equipo -- y llama a `servicio.py`, que envuelve
`AgenteVivoGardens.responder()`. Asi el banco de 41 casos prueba exactamente lo
que corre en produccion, que es lo que el README promete.

`servicio.py` es **sin estado a proposito**: el historial viaja en la peticion y
vuelve en la respuesta para que n8n lo persista. Se puede reiniciar, escalar o
duplicar sin perder conversaciones, y la unica fuente de verdad es Postgres.

El mapeo nodo por nodo esta en `n8n/README.md`.

⚠️ **El servicio NO es el webhook de Instagram.** Instagram corta a los 10s y
reenvia el evento; una llamada al modelo tarda segundos. El 200 lo da n8n antes
de pensar. Conectarlo directo hace que el cliente reciba la respuesta dos o tres
veces.

### Pendiente, y no depende del codigo

El **App ID**, el **`IG_VERIFY_TOKEN`** (cadena libre que debe coincidir con el
panel de Meta) y que este aprobado el permiso
**`instagram_business_manage_messages`**. Los tiene quien administra la app en
Meta App Developer.

---

## 19. La palabra "gratis" no se usa (2026-09-20)

Decision del dueño del negocio, por marca. **La visita SIGUE sin cobro y hay que
seguir ofreciendola**: lo unico que cambia es como se dice.

Esa distincion es la clave y por poco se pierde. "Quitar la palabra" admitia dos
lecturas opuestas -- dejar de decirla, o dejar de prometer la gratuidad -- y
producian codigo contrario. Se pregunto antes de tocar nada.

### Por que no basta con reescribir el prompt

Se midio primero: **la palabra salia en el 19% de las respuestas grabadas** (70
de 360), en 14 casos distintos. Normal: el prompt la decia en cinco sitios. Pero
reescribir esos cinco no impide que el modelo la use por su cuenta -- es la
palabra natural en español. Hicieron falta las tres cosas:

1. Los 5 sitios del prompt pasan a "sin costo" / "no tiene costo".
2. Una prohibicion **explicita** en el prompt, que incluye el ingles: "at no
   cost", nunca "free".
3. `no_dice_gratis()` en los **invariantes base**, o sea en los 41 casos. Una
   regla de marca vale en todos, no solo donde alguien se acuerde de declararla.

Se eligio "sin costo" a proposito: `ofrece_visita_gratis()` ya acepta esa forma,
asi que el banco **sigue verificando que la visita se ofrezca**. Las dos
aserciones juntas dicen la regla completa: prometela, pero no con esa palabra.

### Medido

    antes:  19% de las respuestas decian la palabra
    ahora:  2 de 162   (~1,2%)
    ofrece_visita_gratis: 0 fallos  <- sigue ofreciendo la visita

Marcador 38/39/38 contra 39/40/39. Esa diferencia **es exactamente** las dos
fugas, las dos 1 de 3: `ingles` (se le escapo "free") y
`apertura:cta_como_puedo_comprar` ("gratis").

### Lo que queda

El ~1% restante es el modelo alcanzando la palabra natural. Se puede reforzar la
instruccion, pero con evidencia de 1 de 3 no se toca el prompt: esta mañana
arreglar el horario asi rompio `sin_cifras`. Si sube, se ataca.

⚠️ 7 sitios dicen "gratis" o "free" y **NO** son esta promesa: el boton
hipotetico "Get a free quote" (es la voz del cliente), las listas de palabras
comunes del detector de idioma, el README cuando dice que las pruebas en frio
son gratis, y varios textos de prueba de otras aserciones. Borrarlos romperia
cosas sin relacion.
