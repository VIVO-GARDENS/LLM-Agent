# -*- coding: utf-8 -*-
"""Prueba la guarda de 24 horas en las DOS direcciones.

Una guarda que bloquea todo se ve igual que una que funciona, hasta que el bot
se queda mudo. Por eso se prueban los dos casos:

  mensaje reciente (5 min)  -> debe RESPONDER y guardar el turno
  mensaje viejo   (48 h)    -> NO debe responder; se deriva al equipo

El criterio no es lo que diga la ejecucion, sino si el historial del cliente
crecio: eso es lo unico que demuestra que hubo o no respuesta.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N8N = "http://127.0.0.1:5678"

KEY = ""
for linea in io.open(os.path.join(RAIZ, ".env"), encoding="utf-8"):
    if linea.strip().startswith("N8N_API_KEY="):
        KEY = linea.split("=", 1)[1].strip()


def psql(sql):
    return subprocess.run(
        ["docker", "exec", "n8n-postgres-1", "sh", "-c",
         'psql -U "$POSTGRES_USER" -d agente -tAc "%s"' % sql],
        capture_output=True, text=True).stdout.strip()


def disparar(sender, mid, ts_ms):
    cuerpo = {"object": "instagram", "entry": [{
        "id": "17841400000000000", "time": ts_ms,
        "messaging": [{
            "sender": {"id": sender},
            "recipient": {"id": "17841400000000000"},
            "timestamp": ts_ms,
            "message": {"mid": mid, "text": "Cuanto cuesta?"},
        }]}]}
    req = urllib.request.Request(
        N8N + "/webhook/instagram", data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def turnos(sender):
    v = psql("SELECT COALESCE(jsonb_array_length(mensajes),0) FROM conversaciones "
             "WHERE sender_id = '%s'" % sender)
    return int(v) if v.strip().isdigit() else 0


ahora = int(time.time() * 1000)
sello = int(time.time())

# ------------------------------------------------------------------ caso 1
print("CASO 1: mensaje RECIENTE (5 minutos) -> debe responder")
s1 = "cliente_reciente_%d" % sello
cod = disparar(s1, "mid_reciente_%d" % sello, ahora - 5 * 60 * 1000)
print("  webhook -> http %s" % cod)
print("  esperando la rama asincrona...")
time.sleep(28)
t1 = turnos(s1)
print("  turnos guardados: %d   %s" % (
    t1, "CORRECTO: respondio" if t1 >= 2 else "MAL: no respondio"))

# ------------------------------------------------------------------ caso 2
print("\nCASO 2: mensaje VIEJO (48 horas) -> NO debe responder")
s2 = "cliente_viejo_%d" % sello
cod = disparar(s2, "mid_viejo_%d" % sello, ahora - 48 * 3600 * 1000)
print("  webhook -> http %s" % cod)
print("  esperando la rama asincrona...")
time.sleep(28)
t2 = turnos(s2)
print("  turnos guardados: %d   %s" % (
    t2, "CORRECTO: la guarda lo detuvo" if t2 == 0 else "MAL: respondio fuera de ventana"))

# ------------------------------------------------------------------ detalle
print("\nQue nodos ejecuto cada caso:")
req = urllib.request.Request(N8N + "/api/v1/executions?limit=2&includeData=true",
                             headers={"X-N8N-API-KEY": KEY})
try:
    with urllib.request.urlopen(req, timeout=25) as r:
        ejec = json.loads(r.read().decode())
    for e in ejec.get("data", []):
        rn = ((e.get("data") or {}).get("resultData") or {}).get("runData") or {}
        guarda = "Dentro de 24h?" in rn
        llamo = "Llamar al agente" in rn
        print("  ejecucion %s: status=%s | paso por la guarda=%s | llamo al agente=%s"
              % (e.get("id"), e.get("status"), guarda, llamo))
except Exception as e:  # noqa: BLE001
    print("  no se pudieron leer las ejecuciones: %s" % e)

print("\nVEREDICTO")
if t1 >= 2 and t2 == 0:
    print("  la guarda funciona en las dos direcciones")
elif t1 < 2:
    print("  PROBLEMA: bloquea tambien los mensajes validos, el bot quedaria mudo")
else:
    print("  PROBLEMA: deja pasar mensajes fuera de la ventana de 24h")
