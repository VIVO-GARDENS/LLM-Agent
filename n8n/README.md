# Cómo se mapea el núcleo a los nodos de n8n

**Arquitectura decidida el 2026-09-18: n8n orquesta, Python responde.**

n8n hace lo que hace bien —recibir el webhook, responder 200 al instante,
deduplicar, guardar estado, llamar a la Send API— y delega en `servicio.py`
la única pregunta que requiere el núcleo: *qué* contestarle al cliente.

No es una decisión de gusto. El system prompt **se construye en Python en cada
llamada**: lleva la fecha de hoy, los precios aprendidos de ese cliente, el
inventario y el contexto del post que compartió. Un nodo HTTP Request con un
body fijo no puede reproducir eso, y si lo intentara, el banco de 41 casos
dejaría de probar lo que corre en producción.

---

## ⚠️ La restricción que manda sobre todo el diseño

**El webhook de Instagram corta a los 10 segundos** y reenvía el evento si no
recibe un 200. Una llamada al modelo tarda segundos. Por eso el flujo es
asíncrono y el 200 se devuelve **antes** de pensar:

```
Webhook  -->  Respond to Webhook (200)   <- inmediato, menos de 2s
                    |
                    v  (rama asíncrona, sin reloj)
              dedup -> estado -> servicio -> Send API -> aviso al equipo
```

Si alguien "simplifica" esto conectando el servicio directo al webhook, el
cliente recibirá la misma respuesta dos o tres veces.

---

## Los nodos, en orden

| # | Nodo | Qué hace | Por qué |
|---|---|---|---|
| 1 | **Webhook** | Recibe el evento de Instagram | La verificación inicial responde el `hub.challenge` con `IG_VERIFY_TOKEN` |
| 2 | **Respond to Webhook** | Devuelve 200 vacío | Antes de cualquier cosa lenta. Ver arriba |
| 3 | **Code** — extraer | Saca `sender_id`, `mid`, texto, adjuntos y post compartido | El payload de Instagram anida distinto según el tipo |
| 4 | **Postgres** — ¿visto? | Busca el `mid` en la tabla de vistos | Instagram reenvía. Sin esto se contesta duplicado |
| 5 | **IF** | Si ya se vio, terminar | |
| 6 | **Postgres** — historial | Lee `mensajes` de la conversación | El estado vive aquí, no en el servicio |
| 7 | **HTTP Request** | `POST /responder` con header `X-Token` | El único nodo que habla con el núcleo |
| 8 | **Postgres** — guardar | Guarda el `mensajes` devuelto y marca el `mid` | El servicio no persiste nada |
| 9 | **Switch** | Ramifica por `herramienta` | Ver abajo |
| 10 | **HTTP Request** — Send API | Manda `texto` al cliente por DM | |

### El Switch del nodo 9

| `herramienta` | Qué hizo el agente | Qué hace n8n además del DM |
|---|---|---|
| vacío | Solo conversó | Nada |
| `agendar_visita` | Reunió zona, espacio y disponibilidad | Formatea `datos_cita` y lo manda al equipo por WhatsApp |
| `registrar_pedido` | Sabe qué planta y qué tamaño | Formatea `datos_pedido` para el equipo |
| `consultar_al_equipo` | No supo algo y lo anotó | Avisa al equipo con `consulta` para que lo responda |

**El mensaje de WhatsApp lo formatea n8n, no el modelo.** Los campos ya vienen
estructurados y verificados en el input del tool; pedirle al modelo que redacte
ese texto sería darle una segunda oportunidad de alucinar sobre datos que ya
están resueltos.

---

## Contrato del servicio

`POST /responder`, con el header `X-Token`. Recibe `sender_id`, `mensajes` (el
historial tal como quedó en Postgres), `texto`, `imagenes` y `post`.

Devuelve `texto`, `agendo`, `herramienta`, `datos_cita`, `datos_pedido`,
`consulta`, `stop_reason`, `uso` y **`mensajes`** — el historial actualizado,
que el nodo 8 persiste. El servicio es **sin estado**: se puede reiniciar,
escalar o duplicar sin perder conversaciones.

`GET /salud` devuelve el modelo activo.

---

## Correrlo

```bash
pip install -r requirements.txt
uvicorn servicio:app --host 0.0.0.0 --port 8000
```

---

## Lo que falta, y no depende del código

Tres datos que tiene quien administra la app en Meta App Developer:

- el **App ID** de la app de Meta
- el **`IG_VERIFY_TOKEN`**, cadena libre que debe coincidir con la del panel
- que esté aprobado el permiso **`instagram_business_manage_messages`**
