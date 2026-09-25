# -*- coding: utf-8 -*-
"""Anade la guarda de la ventana de 24 horas al workflow.

Meta solo permite responder dentro de las 24 h desde la ultima interaccion del
cliente. Fuera de esa ventana la API bloquea el envio, y forzarlo con la
etiqueta HUMAN_AGENT -- que existe y extiende a 7 dias -- es una violacion de
politica: esa etiqueta es SOLO para respuestas humanas y Meta la vigila.

Por eso el agente no usa etiquetas de ningun tipo, y por eso esta guarda va
ANTES de que el workflow tenga capacidad de enviar nada. Un mensaje fuera de
ventana no se responde: se deriva al equipo.

Va como nodo propio y no dentro del IF de deduplicacion a proposito. Si se
mezclan, una ejecucion detenida no dice si fue un duplicado o una ventana
vencida, y son dos problemas distintos.
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
WID = "EGBjHdEhMkFON9Ya"

KEY = ""
for linea in io.open(os.path.join(RAIZ, ".env"), encoding="utf-8"):
    if linea.strip().startswith("N8N_API_KEY="):
        KEY = linea.split("=", 1)[1].strip()


def api(ruta, metodo="GET", cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo else None
    req = urllib.request.Request(
        "http://127.0.0.1:5678" + ruta, data=datos, method=metodo,
        headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


# El Code node ahora calcula la edad del mensaje. Instagram manda `timestamp`
# en milisegundos dentro de cada entrada de `messaging`.
EXTRAER = """// El payload de Instagram anida distinto segun el tipo de mensaje.
// OJO: escrito SIN un payload real delante. Verificar contra uno de verdad.
const salida = [];
const ahora = Date.now();
for (const item of $input.all()) {
  const cuerpo = item.json.body ?? item.json;
  for (const entrada of cuerpo.entry ?? []) {
    for (const m of entrada.messaging ?? []) {
      const msg = m.message ?? {};
      const adjuntos = msg.attachments ?? [];
      // Sin timestamp se asume recien llegado: bloquear todo por un campo
      // ausente dejaria al bot mudo, y en un webhook real siempre viene.
      const ts = Number(m.timestamp ?? entrada.time ?? ahora);
      salida.push({ json: {
        sender_id: m.sender?.id ?? '',
        mid: msg.mid ?? '',
        texto: msg.text ?? '',
        imagenes: adjuntos.filter(a => a.type === 'image').map(a => a.payload?.url).filter(Boolean),
        timestamp: ts,
        edad_horas: Math.max(0, (ahora - ts) / 3600000),
      }});
    }
  }
}
return salida;"""

cod, wf = api("/api/v1/workflows/%s" % WID)
print("leido -> http %s" % cod)
if cod != 200:
    print("  ", wf)
    raise SystemExit(1)

if any(n["name"] == "Dentro de 24h?" for n in wf["nodes"]):
    print("  la guarda ya existia")
    raise SystemExit(0)

for n in wf["nodes"]:
    if n["name"] == "Extraer mensaje":
        n["parameters"]["jsCode"] = EXTRAER
        print("  Code node: ahora calcula edad_horas")

GUARDA = {
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "version": 2},
            "conditions": [{
                "leftValue": "={{ $('Extraer mensaje').item.json.edad_horas }}",
                "rightValue": 24,
                "operator": {"type": "number", "operation": "lt"},
            }],
            "combinator": "and",
        },
        "options": {},
    },
    "id": "Dentro de 24h?",
    "name": "Dentro de 24h?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.3,
    "position": [770, 0],
}
wf["nodes"].append(GUARDA)
print("  nodo 'Dentro de 24h?' anadido")

# Recableado: dedup -> guarda -> historial. Fuera de ventana -> el equipo.
wf["connections"]["Es nuevo?"] = {"main": [
    [{"node": "Dentro de 24h?", "type": "main", "index": 0}],
    [],
]}
wf["connections"]["Dentro de 24h?"] = {"main": [
    [{"node": "Leer historial", "type": "main", "index": 0}],
    [{"node": "Avisar al equipo", "type": "main", "index": 0}],
]}
print("  recableado: Es nuevo? -> Dentro de 24h? -> Leer historial")
print("               fuera de ventana -> Avisar al equipo")

cod, _ = api("/api/v1/workflows/%s" % WID, "PUT", {
    "name": wf["name"], "nodes": wf["nodes"],
    "connections": wf["connections"], "settings": wf.get("settings", {})})
print("\nPUT workflow -> http %s" % cod)

cod, v = api("/api/v1/workflows/%s" % WID)
print("verificacion -> http %s" % cod)
nombres = [n["name"] for n in v["nodes"]]
print("  nodos: %d" % len(nombres))
print("  la guarda esta: %s" % ("Dentro de 24h?" in nombres))
g = [n for n in v["nodes"] if n["name"] == "Dentro de 24h?"][0]
c = g["parameters"]["conditions"]["conditions"][0]
print("  condicion: %s %s %s" % (c["leftValue"], c["operator"]["operation"], c["rightValue"]))
code = [n for n in v["nodes"] if n["name"] == "Extraer mensaje"][0]
print("  el Code calcula edad_horas: %s" % ("edad_horas" in code["parameters"]["jsCode"]))
print("  salida falsa va a: %s" % [
    x["node"] for x in v["connections"]["Dentro de 24h?"]["main"][1]])

with io.open(os.path.join(RAIZ, "n8n", "workflow.json"), "w",
             encoding="utf-8", newline="\n") as f:
    json.dump({"name": v["name"], "nodes": v["nodes"],
               "connections": v["connections"], "settings": v.get("settings", {})},
              f, ensure_ascii=False, indent=2)
print("\n  n8n/workflow.json actualizado")
