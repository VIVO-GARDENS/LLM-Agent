# Agente de citas para Vivo Gardens Miami

Agente conversacional que atiende los DMs de Instagram de un vivero real,
califica al interesado y deja un brief listo para cotizar. Con un banco de
evaluaciones que verifica **por código** que no invente precios, que no agende
sin tener los datos y que no prometa lo que el negocio no puede cumplir.

---

## El problema

Vivo Gardens es un vivero en Miami que vende por Instagram y cotiza a domicilio.
Su publicidad funciona: en agosto de 2026 generó **91 conversaciones**.

**Solo 2 fueron respondidas.**

A $2.48 por conversación, eso son unos **$600 al mes en conversaciones que nadie
atiende**. El problema no es que falten clientes: es que llegan y no hay quién
conteste.

Antes de escribir el agente leí **120 conversaciones reales** de la cuenta.
Lo que encontré:

| | |
|---|---|
| Empiezan con el texto fijo de un **botón** del anuncio, no escrito por una persona | **83%** |
| Entran preguntando el precio | **59%** |
| Solo el botón `¿Cuánto cuesta?` | **49%** |
| Terminan con el cliente esperando respuesta | **16%** |
| El negocio da cifras por DM (no es excepcional, es rutina) | **33%** |

Ese ejercicio cambió el proyecto. La especificación inicial decía "el agente
nunca da precios y siempre lleva a una visita a domicilio". Los datos decían que
la mitad del tráfico es **venta de producto** — "quiero esa planta" — y que el
equipo cotiza por DM todos los días. El agente que está en este repo atiende los
dos flujos porque los datos lo exigieron, no porque se me ocurriera.

---

## Lo que lo diferencia: las evaluaciones

Un chatbot lo arma cualquiera. Lo que cuesta es demostrar que **se comporta**.

`evals/` tiene **32 casos**: conversaciones con turnos de cliente fijos y
aserciones programáticas sobre lo que hizo el agente. Sin un modelo juzgando a
otro — un juez LLM es caro, no es reproducible, y para estas reglas es
innecesario porque son verificables con código.

```
python -m evals                      # 32 conversaciones contra la API
python -m evals --grupo aperturas    # solo los botones del anuncio
python -m evals.prueba_aserciones    # las aserciones a sí mismas, sin API
```

Algunas de las reglas que verifica:

| aserción | qué impide |
|---|---|
| `sin_cifras` | dar un precio de proyecto, que solo sale de la visita |
| `precio_con_modalidad` | decir "250" sin aclarar si es la planta sola o instalada — el mismo limón vale 250 y 1.200 |
| `pregunta_cual_planta` | cotizar en abstracto: el equipo siempre pregunta qué planta primero |
| `pedido_completo` | registrar una venta sin planta o sin tamaño, que obliga a rehacerle las preguntas al cliente |
| `solo_precios_autorizados` | inventar cifras: solo pasan los montos que el negocio realmente cotizó |
| `no_agenda_antes_del_turno(n)` | agendar sin tener zona, espacio y disponibilidad |
| `sugerencias_del_catalogo` | recomendar plantas que el vivero no vende |
| `no_niega_disponibilidad` | decir "no lo tenemos" cuando el catálogo publicado está incompleto |
| `horario_correcto` | inventar horarios y mandar gente un día que está cerrado |
| `no_inventa_en_brief` | rellenar el brief del equipo con datos que el cliente nunca dio |
| `una_pregunta_por_turno` | pedir los tres datos de golpe, que es como muere la conversación |

**Y las aserciones se prueban a sí mismas.** `evals/prueba_aserciones.py` corre
en frío, en menos de un segundo y sin gastar créditos: a cada aserción se le dan
textos que debe dejar pasar y textos que debe atrapar. Si el regex de
`sin_cifras` estuviera roto, el banco entero daría verde y nadie se enteraría.
Eso corre en CI en cada push.

El reporte de cada corrida imprime **tokens y costo proyectado al mes**, porque
si atender las conversaciones costara más que las conversaciones perdidas, el
proyecto no tendría sentido.

---

## Arquitectura

```
Instagram DM
   │  webhook → responde 200 en <2s   (el timeout de Instagram son 10s)
   ▼            dedup por mid
n8n (async, sin reloj)
   │
   ▼
AgenteVivoGardens ──► API de Anthropic (Sonnet 5)
   │
   ├─ end_turn ..................... texto → DM
   ├─ tool agendar_visita .......... visita: brief al equipo + confirmación
   ├─ tool registrar_pedido ........ venta: qué planta, qué tamaño, qué modalidad
   └─ tool anotar_precio_faltante .. lo que no supo → cola de aprobación
```

| módulo | qué hace |
|---|---|
| `agente/prompt.py` | system prompt y schema de las herramientas. Única fuente de verdad del comportamiento |
| `agente/agente.py` | el bucle: llama la API, ramifica por herramienta, devuelve una respuesta lista para actuar |
| `agente/conversacion.py` | estado por cliente y deduplicación por `mid` |
| `agente/catalogo.py` | las 43 plantas publicadas, para aterrizar al modelo |
| `agente/precios.py` | 43 cotizaciones reales extraídas del histórico de DMs |
| `agente/memoria_precios.py` | lo que el agente aprendió: ciclo de preguntar → aprobar → saber |
| `agente/publicaciones.py` | qué muestra cada post que la gente comparte — y cuándo **no se puede saber** |

### Decisiones que parecen detalles y no lo son

| decisión | por qué |
|---|---|
| **Tool use en vez de pedir JSON** | El agente conversa en texto natural y solo emite `tool_use` cuando ya reunió los datos. Quien orquesta bifurca por `stop_reason`. |
| **No desactivar el pensamiento extendido** | Con él desactivado el modelo a veces *escribe* la llamada a la herramienta como texto visible. Falla en silencio: el cliente ve un mensaje raro y la cita nunca se crea. Bajar `effort` sí; desactivar no. |
| **Buscar el bloque por `type == "tool_use"`** | Nunca por coincidencia de texto sobre el JSON: el escapado varía entre modelos y versiones. |
| **El estado vive fuera del agente** | `responder()` recibe el historial completo. Por eso las evals pueden inventarse cualquier historial sin base de datos. |
| **El system prompt se construye en cada llamada** | Lleva la fecha de hoy. Sin ella el modelo no puede convertir "el viernes" a una fecha ISO: se la inventa, y el brief le llega al equipo con un día que el cliente nunca dijo. |
| **Prompt caching sobre el bloque estable** | El prompt pesa ~1.900 tokens con catálogo y precios. Cacheado se paga una vez al día en vez de en cada mensaje. |
| **Identificar plantas sin entrenar nada** | Cuando el cliente comparte una publicación, el mensaje trae su código, su descripción y su imagen. Para la mitad del tráfico identificar es una búsqueda, no un problema de visión. |
| **El agente pregunta lo que no sabe** | Ante un precio que desconoce no estima: lo registra como pendiente y le dice al cliente que el equipo confirma. Cuando el dueño aprueba el precio, queda aprendido. |
| **Dos flujos, dos salidas** | La mitad del tráfico es venta de producto ("quiero esa planta") y la otra es proyecto ("arregla mi jardín"). Forzar los dos por la misma herramienta haría que el agente agende visitas que nadie pidió. |
| **Un post compartido no es una foto** | Una foto del patio significa "arregla esto"; un post compartido significa "quiero eso". Se anotan distinto o el modelo describe la foto promocional como si fuera el espacio del cliente. |

---

## Correrlo

```bash
pip install -r requirements.txt
cp .env.example .env          # y poner ANTHROPIC_API_KEY

python -m evals.prueba_aserciones   # gratis, sin API
python -m evals                     # 32 conversaciones reales
python ejecutar.py                  # conversar a mano
```

---

## Estado

Núcleo y evaluaciones completos. Pendiente: la integración con la API de
Mensajería de Instagram y el despliegue en n8n.

---

## Sobre los datos

Los números de este README son agregados. **No hay ningún dato de cliente en
este repositorio**: ni nombres, ni mensajes textuales, ni identificadores. Las
conversaciones de `evals/casos.py` son reconstrucciones de patrones observados,
con personas y direcciones inventadas. Las credenciales nunca se commitean
(`.env` está en `.gitignore` desde el primer commit).
