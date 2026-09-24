# -*- coding: utf-8 -*-
"""Genera SERVICIO_TOKEN, reinicia el servicio y lo cablea en n8n.

Existe porque el token nunca se habia puesto: `_verificar()` en servicio.py
sale temprano cuando la variable esta vacia, asi que /responder aceptaba
cualquier llamada. Escucha solo en loopback, pero cualquier proceso de la
maquina podia gastar creditos de la API.

Verifica las DOS caras, que es donde se cuela el error: sin cabecera tiene que
dar 401, y con la cabecera correcta 200.
"""
from __future__ import annotations

import io
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(RAIZ, ".env")
ID_CRED = "zTDfnIsvTAdAtIV9"
N8N = "http://127.0.0.1:5678"
SRV = "http://127.0.0.1:8000"


def leer_env() -> dict:
    vals = {}
    with io.open(ENV, encoding="utf-8") as f:
        for linea in f:
            if "=" in linea and not linea.strip().startswith("#"):
                k, v = linea.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


# --------------------------------------------------------------------- 1
token = secrets.token_urlsafe(32)
texto = io.open(ENV, encoding="utf-8").read()
if "SERVICIO_TOKEN=" in texto:
    salida = []
    for linea in texto.splitlines():
        if linea.strip().startswith("SERVICIO_TOKEN="):
            salida.append("SERVICIO_TOKEN=" + token)
        else:
            salida.append(linea)
    texto = "\n".join(salida) + "\n"
else:
    texto = texto.rstrip() + "\n\n# Secreto compartido con n8n. Sin el, /responder queda abierto.\nSERVICIO_TOKEN=" + token + "\n"
io.open(ENV, "w", encoding="utf-8").write(texto)
print("1. .env: SERVICIO_TOKEN escrito (%d caracteres, no se imprime)" % len(token))

# --------------------------------------------------------------------- 2
print("2. reiniciando el servicio para que lo tome")
subprocess.run(["taskkill", "/F", "/FI", "WINDOWTITLE eq *uvicorn*"],
               capture_output=True, text=True)
salida = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-NetTCPConnection -LocalPort 8000 -State Listen | "
     "Select-Object -ExpandProperty OwningProcess"],
    capture_output=True, text=True).stdout.strip()
for pid in {p.strip() for p in salida.splitlines() if p.strip().isdigit()}:
    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)
    print("   proceso %s detenido" % pid)
time.sleep(2)

DETACHED = 0x00000008 | 0x00000200
subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "servicio:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=RAIZ, creationflags=DETACHED,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

arriba = False
for i in range(15):
    time.sleep(2)
    try:
        with urllib.request.urlopen(SRV + "/salud", timeout=4) as r:
            if r.status == 200:
                print("   servicio arriba (intento %d)" % (i + 1))
                arriba = True
                break
    except Exception:
        pass
if not arriba:
    print("   el servicio NO volvio a levantar")
    raise SystemExit(1)


# --------------------------------------------------------------------- 3
def probar(cabecera):
    cuerpo = json.dumps({"sender_id": "prueba", "texto": "hola"}).encode()
    cab = {"Content-Type": "application/json"}
    if cabecera:
        cab["X-Token"] = cabecera
    req = urllib.request.Request(SRV + "/responder", data=cuerpo, headers=cab, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:  # noqa: BLE001
        return str(e)


print("3. el endpoint ya exige la cabecera?")
sin = probar(None)
print("   sin cabecera      -> http %s   %s" % (sin, "correcto" if sin == 401 else "MAL: deberia ser 401"))
malo = probar("token-incorrecto")
print("   token incorrecto  -> http %s   %s" % (malo, "correcto" if malo == 401 else "MAL: deberia ser 401"))

# --------------------------------------------------------------------- 4
key = leer_env()["N8N_API_KEY"]


def api(ruta, metodo="GET", cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo else None
    req = urllib.request.Request(
        N8N + ruta, data=datos, method=metodo,
        headers={"X-N8N-API-KEY": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:  # noqa: BLE001
        return None, str(e)


print("4. actualizando la credencial de n8n con el mismo valor")
cuerpo = {"name": "Token servicio agente", "type": "httpHeaderAuth",
          "data": {"name": "X-Token", "value": token}}
cod, resp = api("/api/v1/credentials/%s" % ID_CRED, "PUT", cuerpo)
print("   PUT  -> http %s" % cod)
if cod not in (200, 201):
    cod, resp = api("/api/v1/credentials/%s" % ID_CRED, "PATCH", cuerpo)
    print("   PATCH -> http %s" % cod)
if cod not in (200, 201):
    print("   la API no permite actualizar; se recrea y se repunta el nodo")
    api("/api/v1/credentials/%s" % ID_CRED, "DELETE")
    cod, nueva = api("/api/v1/credentials", "POST", cuerpo)
    print("   POST -> http %s" % cod)
    if cod in (200, 201):
        nid = nueva["id"]
        print("   nueva credencial id=%s" % nid)
        cod, wf = api("/api/v1/workflows/EGBjHdEhMkFON9Ya")
        if cod == 200:
            for n in wf["nodes"]:
                c = n.get("credentials") or {}
                if "httpHeaderAuth" in c:
                    c["httpHeaderAuth"] = {"id": nid, "name": "Token servicio agente"}
            cod, _ = api("/api/v1/workflows/EGBjHdEhMkFON9Ya", "PUT",
                         {"name": wf["name"], "nodes": wf["nodes"],
                          "connections": wf["connections"],
                          "settings": wf.get("settings", {})})
            print("   workflow repuntado -> http %s" % cod)

# --------------------------------------------------------------------- 5
print("5. con la cabecera correcta sigue funcionando?")
ok = probar(token)
print("   con el token      -> http %s   %s" % (ok, "correcto" if ok == 200 else "MAL"))
print("\n   (esa ultima llamada gasta unos centavos de API: es una respuesta real)")
