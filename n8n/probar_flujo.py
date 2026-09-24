# -*- coding: utf-8 -*-
"""Prueba el workflow de punta a punta, sin Instagram y sin datos de Meta.

Dispara el webhook con un payload sintetico con la forma que manda Instagram y
comprueba la cadena entera: extraccion, deduplicacion, estado en Postgres y
llamada al servicio.

Lo que mas importa no es que funcione una vez, sino que el MISMO `mid` no
dispare una segunda respuesta: Instagram reenvia el evento si el webhook no
contesta 200 a tiempo, y sin dedup el cliente recibe lo mismo dos o tres veces.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WID = "EGBjHdEhMkFON9Ya"
N8N = "http://127.0.0.1:5678"
MID = "mid_prueba_%d" % int(time.time())
CLIENTE = "cliente_prueba_%d" % int(time.time())

import io, os
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = ""
for linea in io.open(os.path.join(RAIZ, ".env"), encoding="utf-8"):
    if linea.strip().startswith("N8N_API_KEY="):
        KEY = linea.split("=", 1)[1].strip()


def api(ruta, metodo="GET", cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo else None
    req = urllib.request.Request(
        N8N + ruta, data=datos, method=metodo,
        headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def psql(sql, base="agente"):
    return subprocess.run(
        ["docker", "exec", "n8n-postgres-1", "sh", "-c",
         'psql -U "$POSTGRES_USER" -d %s -tAc "%s"' % (base, sql)],
        capture_output=True, text=True).stdout.strip()


def payload(mid):
    """La forma que manda Instagram en el webhook de mensajes."""
    return {"object": "instagram", "entry": [{
        "id": "17841400000000000", "time": int(time.time() * 1000),
        "messaging": [{
            "sender": {"id": CLIENTE},
            "recipient": {"id": "17841400000000000"},
            "timestamp": int(time.time() * 1000),
            "message": {"mid": mid, "text": "Cuanto cuesta?"},
        }]}]}


def disparar(mid):
    req = urllib.request.Request(
        N8N + "/webhook/instagram", data=json.dumps(payload(mid)).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    inicio = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, round(time.time() - inicio, 2)
    except urllib.error.HTTPError as e:
        return e.code, round(time.time() - inicio, 2)
    except Exception as e:  # noqa: BLE001
        return str(e), round(time.time() - inicio, 2)


# ------------------------------------------------------------------ 1
print("1. activando el workflow")
cod, resp = api("/api/v1/workflows/%s/activate" % WID, "POST")
print("   POST activate -> http %s" % cod)
if cod not in (200, 201):
    print("  ", resp)
    raise SystemExit(1)

# ------------------------------------------------------------------ 2
print("\n2. estado ANTES de disparar")
print("   filas en mids          : %s" % psql("SELECT count(*) FROM mids"))
print("   filas en conversaciones: %s" % psql("SELECT count(*) FROM conversaciones"))

# ------------------------------------------------------------------ 3
print("\n3. primer envio (mid nuevo)")
cod, seg = disparar(MID)
print("   webhook -> http %s en %ss   %s" % (
    cod, seg, "el 200 sale rapido, antes de pensar" if isinstance(cod, int) and cod == 200 and seg < 3 else ""))

print("   esperando a que termine la rama asincrona...")
time.sleep(25)

# ------------------------------------------------------------------ 4
print("\n4. que hizo el workflow")
cod, ejec = api("/api/v1/executions?workflowId=%s&limit=5" % WID)
if cod == 200:
    for e in ejec.get("data", []):
        print("   ejecucion %s: status=%s  finalizada=%s" % (
            e.get("id"), e.get("status"), e.get("stoppedAt") is not None))
else:
    print("   no se pudieron leer las ejecuciones: %s" % ejec)

print("\n   estado DESPUES:")
print("   mid registrado         : %s" % psql("SELECT count(*) FROM mids WHERE mid = '%s'" % MID))
print("   conversacion guardada  : %s" % psql(
    "SELECT count(*) FROM conversaciones WHERE sender_id = '%s'" % CLIENTE))
turnos = psql("SELECT jsonb_array_length(mensajes) FROM conversaciones WHERE sender_id = '%s'" % CLIENTE)
print("   turnos en el historial : %s" % turnos)

# ------------------------------------------------------------------ 5
print("\n5. LO QUE MAS IMPORTA: el mismo mid otra vez")
cod2, seg2 = disparar(MID)
print("   webhook -> http %s en %ss" % (cod2, seg2))
time.sleep(20)
turnos2 = psql("SELECT jsonb_array_length(mensajes) FROM conversaciones WHERE sender_id = '%s'" % CLIENTE)
print("   turnos en el historial ahora: %s" % turnos2)
if turnos and turnos2 and turnos == turnos2:
    print("   CORRECTO: el duplicado no genero una segunda respuesta")
elif turnos2:
    print("   MAL: el historial crecio, el duplicado SI se proceso")
else:
    print("   no concluyente: revisar arriba")
