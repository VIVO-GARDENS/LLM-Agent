# -*- coding: utf-8 -*-
"""Arregla el nodo `Leer historial` del workflow.

El bug: `SELECT mensajes FROM conversaciones WHERE sender_id = $1` no devuelve
filas para un cliente que escribe por primera vez -- que es el caso NORMAL de
toda conversacion nueva. En n8n un nodo sin items corta la rama, asi que
`Llamar al agente`, `Guardar historial` y `Que hizo?` no llegaban a ejecutarse
y aun asi la ejecucion figuraba como `success`. Una ejecucion verde que no
guarda nada es el peor fallo posible: no se nota.

La correccion usa COALESCE sobre una subconsulta, que siempre devuelve una fila
(con '[]' si el cliente es nuevo), mas alwaysOutputData como cinturon.

Se escribe desde un archivo y no con `python -c` a proposito: el shell se come
el `$1` del placeholder y lo convierte en otra cosa.
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


# El placeholder va como texto normal: aqui no hay shell que se lo coma.
QUERY = (
    "SELECT COALESCE("
    "(SELECT mensajes FROM conversaciones WHERE sender_id = $1), "
    "'[]'::jsonb) AS mensajes"
)

cod, wf = api("/api/v1/workflows/%s" % WID)
print("leido -> http %s" % cod)
if cod != 200:
    print("  ", wf)
    raise SystemExit(1)

for n in wf["nodes"]:
    if n["name"] == "Leer historial":
        n["parameters"]["query"] = QUERY
        n["alwaysOutputData"] = True

cod, _ = api("/api/v1/workflows/%s" % WID, "PUT", {
    "name": wf["name"], "nodes": wf["nodes"],
    "connections": wf["connections"], "settings": wf.get("settings", {})})
print("PUT workflow -> http %s" % cod)

cod, v = api("/api/v1/workflows/%s" % WID)
nodo = [n for n in v["nodes"] if n["name"] == "Leer historial"][0]
q = nodo["parameters"]["query"]
print("\nverificado en n8n:")
print("  query: %s" % q)
print("  alwaysOutputData: %s" % nodo.get("alwaysOutputData"))
print("  tiene el placeholder $1: %s" % ("$1" in q))
if "$1" not in q:
    print("  MAL: el placeholder se perdio otra vez")
    raise SystemExit(1)

# Guardar el workflow corregido junto al resto
ruta = os.path.join(RAIZ, "n8n", "workflow.json")
with io.open(ruta, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"name": v["name"], "nodes": v["nodes"],
               "connections": v["connections"], "settings": v.get("settings", {})},
              f, ensure_ascii=False, indent=2)
print("\n  n8n/workflow.json actualizado")
