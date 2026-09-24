# -*- coding: utf-8 -*-
"""Crea el workflow de Instagram en n8n y lo vuelve a leer para verificarlo.

Se hace por la API y no a mano para que quede reproducible y verificado: el
workflow se lee de vuelta y se guarda en n8n/workflow.json tal como quedo.

El token del servicio NO se escribe en el workflow: va en una credencial de
n8n, cifrada con N8N_ENCRYPTION_KEY. El JSON acaba en un repo publico.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ID_PG = "ixoi4s4pPOhe0cnG"          # credencial creada antes
BASE = "http://127.0.0.1:5678"


def cargar_env() -> dict:
    vals = {}
    with io.open(os.path.join(RAIZ, ".env"), encoding="utf-8") as f:
        for linea in f:
            if "=" in linea and not linea.strip().startswith("#"):
                k, v = linea.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


VALS = cargar_env()
KEY = VALS["N8N_API_KEY"]


def api(ruta, metodo="GET", cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo else None
    req = urllib.request.Request(
        BASE + ruta, data=datos, method=metodo,
        headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:  # noqa: BLE001
        return None, str(e)


# --------------------------------------------------------------------------
# 1. Credencial con el token del servicio
# --------------------------------------------------------------------------
tok = VALS.get("SERVICIO_TOKEN", "")
cod, cred = api("/api/v1/credentials", "POST", {
    "name": "Token servicio agente",
    "type": "httpHeaderAuth",
    "data": {"name": "X-Token", "value": tok},
})
print("credencial de cabecera -> http %s" % cod)
if cod not in (200, 201):
    print("  ", cred)
    raise SystemExit(1)
ID_HDR = cred["id"]
print("  id=%s  (valor no impreso; %s)" % (ID_HDR, "con token" if tok else "SIN token"))

CRED_PG = {"postgres": {"id": ID_PG, "name": "Postgres agente"}}
CRED_HDR = {"httpHeaderAuth": {"id": ID_HDR, "name": "Token servicio agente"}}


def nodo(nombre, tipo, tv, pos, params, creds=None):
    n = {"parameters": params, "id": nombre, "name": nombre,
         "type": "n8n-nodes-base." + tipo, "typeVersion": tv, "position": pos}
    if creds:
        n["credentials"] = creds
    return n


EXTRAER = """// El payload de Instagram anida distinto segun el tipo de mensaje.
// OJO: escrito SIN un payload real delante. Verificar contra uno de verdad
// antes de confiar en el.
const salida = [];
for (const item of $input.all()) {
  const cuerpo = item.json.body ?? item.json;
  for (const entrada of cuerpo.entry ?? []) {
    for (const m of entrada.messaging ?? []) {
      const msg = m.message ?? {};
      const adjuntos = msg.attachments ?? [];
      salida.push({ json: {
        sender_id: m.sender?.id ?? '',
        mid: msg.mid ?? '',
        texto: msg.text ?? '',
        imagenes: adjuntos.filter(a => a.type === 'image').map(a => a.payload?.url).filter(Boolean),
      }});
    }
  }
}
return salida;"""


def cond(izq, der):
    return {"options": {"caseSensitive": True, "version": 2},
            "conditions": [{"leftValue": izq, "rightValue": der,
                            "operator": {"type": "string", "operation": "equals"}}],
            "combinator": "and"}


NODOS = [
    nodo("Webhook", "webhook", 2.1, [-220, 0],
         {"httpMethod": "POST", "path": "instagram", "responseMode": "responseNode"}),
    # El 200 sale ANTES de pensar: Instagram corta a los 10s y reenvia el evento.
    nodo("Responder 200", "respondToWebhook", 1.5, [0, 0],
         {"respondWith": "noData"}),
    nodo("Extraer mensaje", "code", 2, [220, 0],
         {"jsCode": EXTRAER}),
    # INSERT ... ON CONFLICT DO NOTHING RETURNING: si devuelve fila es nuevo.
    # Sin carrera, a diferencia de SELECT y luego INSERT.
    nodo("Marcar mid", "postgres", 2.7, [440, 0],
         {"operation": "executeQuery",
          "query": "INSERT INTO mids (mid) VALUES ($1) ON CONFLICT (mid) DO NOTHING RETURNING mid",
          "options": {"queryReplacement": "={{ $json.mid }}"}}, CRED_PG),
    nodo("Es nuevo?", "if", 2.3, [660, 0],
         {"conditions": {"options": {"caseSensitive": True, "version": 2},
                         "conditions": [{"leftValue": "={{ $json.mid }}", "rightValue": "",
                                         "operator": {"type": "string", "operation": "exists",
                                                      "singleValue": True}}],
                         "combinator": "and"},
          "options": {}}),
    nodo("Leer historial", "postgres", 2.7, [880, -60],
         {"operation": "executeQuery",
          "query": "SELECT mensajes FROM conversaciones WHERE sender_id = $1",
          "options": {"queryReplacement": "={{ $('Extraer mensaje').item.json.sender_id }}"}},
         CRED_PG),
    nodo("Llamar al agente", "httpRequest", 4.5, [1100, -60],
         {"method": "POST",
          "url": "http://host.docker.internal:8000/responder",
          "authentication": "genericCredentialType",
          "genericAuthType": "httpHeaderAuth",
          "sendBody": True,
          "specifyBody": "json",
          "jsonBody": "={{ JSON.stringify({ sender_id: $('Extraer mensaje').item.json.sender_id, mensajes: $json.mensajes ?? [], texto: $('Extraer mensaje').item.json.texto, imagenes: $('Extraer mensaje').item.json.imagenes }) }}",
          "options": {}}, CRED_HDR),
    nodo("Guardar historial", "postgres", 2.7, [1320, -60],
         {"operation": "executeQuery",
          "query": "INSERT INTO conversaciones (sender_id, mensajes, actualizado) VALUES ($1, $2::jsonb, now()) ON CONFLICT (sender_id) DO UPDATE SET mensajes = EXCLUDED.mensajes, actualizado = now()",
          "options": {"queryReplacement": "={{ $('Extraer mensaje').item.json.sender_id }},{{ JSON.stringify($json.mensajes) }}"}},
         CRED_PG),
    nodo("Que hizo?", "switch", 3.4, [1540, -60],
         {"rules": {"values": [
             {"conditions": cond("={{ $('Llamar al agente').item.json.herramienta }}", "agendar_visita"),
              "outputKey": "visita"},
             {"conditions": cond("={{ $('Llamar al agente').item.json.herramienta }}", "registrar_pedido"),
              "outputKey": "pedido"},
             {"conditions": cond("={{ $('Llamar al agente').item.json.herramienta }}", "consultar_al_equipo"),
              "outputKey": "consulta"}]},
          "options": {"fallbackOutput": "extra", "renameFallbackOutput": "solo conversa"}}),
    # Pendientes: necesitan los datos de Meta y la plantilla de WhatsApp.
    nodo("Avisar al equipo", "noOp", 1, [1760, -160], {}),
    nodo("Enviar DM", "noOp", 1, [1760, 40], {}),
]

CONEXIONES = {
    "Webhook": {"main": [[{"node": "Responder 200", "type": "main", "index": 0}]]},
    "Responder 200": {"main": [[{"node": "Extraer mensaje", "type": "main", "index": 0}]]},
    "Extraer mensaje": {"main": [[{"node": "Marcar mid", "type": "main", "index": 0}]]},
    "Marcar mid": {"main": [[{"node": "Es nuevo?", "type": "main", "index": 0}]]},
    # salida 2 vacia: si el mid ya se vio, el flujo termina ahi
    "Es nuevo?": {"main": [[{"node": "Leer historial", "type": "main", "index": 0}], []]},
    "Leer historial": {"main": [[{"node": "Llamar al agente", "type": "main", "index": 0}]]},
    "Llamar al agente": {"main": [[{"node": "Guardar historial", "type": "main", "index": 0}]]},
    "Guardar historial": {"main": [[{"node": "Que hizo?", "type": "main", "index": 0}]]},
    "Que hizo?": {"main": [
        [{"node": "Avisar al equipo", "type": "main", "index": 0}],
        [{"node": "Avisar al equipo", "type": "main", "index": 0}],
        [{"node": "Avisar al equipo", "type": "main", "index": 0}],
        [{"node": "Enviar DM", "type": "main", "index": 0}]]},
}

cod, wf = api("/api/v1/workflows", "POST", {
    "name": "Vivo Gardens - DMs de Instagram",
    "nodes": NODOS,
    "connections": CONEXIONES,
    "settings": {"executionOrder": "v1"},
})
print("\nPOST /api/v1/workflows -> http %s" % cod)
if cod not in (200, 201):
    print("  ", wf)
    raise SystemExit(1)
WID = wf["id"]
print("  creado: id=%s" % WID)

# --------------------------------------------------------------------------
# 2. Leerlo de vuelta: no se da por bueno lo que no se verifica
# --------------------------------------------------------------------------
cod, leido = api("/api/v1/workflows/%s" % WID)
print("\nlectura de vuelta -> http %s" % cod)
if cod != 200:
    print("  ", leido)
    raise SystemExit(1)

print("  nodos: %d" % len(leido["nodes"]))
for n in leido["nodes"]:
    creds = ", ".join((n.get("credentials") or {}).keys())
    print("    %-18s %-34s tv=%-5s %s" % (n["name"], n["type"], n["typeVersion"], creds))

ruta = os.path.join(RAIZ, "n8n", "workflow.json")
with io.open(ruta, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"name": leido["name"], "nodes": leido["nodes"],
               "connections": leido["connections"],
               "settings": leido.get("settings", {})},
              f, ensure_ascii=False, indent=2)
print("\n  guardado en n8n/workflow.json")
print("  id del workflow: %s" % WID)
