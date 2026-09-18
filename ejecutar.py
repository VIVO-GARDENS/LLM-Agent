# -*- coding: utf-8 -*-
"""Conversar con el agente a mano, desde la terminal.

    python ejecutar.py                     conversación nueva
    python ejecutar.py --sender ana        retoma una guardada
    python ejecutar.py --modelo claude-haiku-4-5

Comandos dentro de la conversación:
    /foto <url>     manda una foto con el mensaje siguiente
    /post <url>     igual, pero simula que compartió una publicación nuestra
    /estado         historial, tokens y costo acumulado
    /pendientes     precios que el agente no supo y quedaron para el equipo
    /salir

Existe para lo que las evals no dan: probar una conversación que se te ocurre en
el momento. Cada turno imprime lo que gastó, porque el costo por conversación es
parte del diseño y no algo que se mira al final del mes.
"""
from __future__ import annotations

import argparse
import os
import sys

from agente.agente import MODELO, AgenteVivoGardens
from agente.entorno import cargar_env
from agente.conversacion import Memoria
from agente.memoria_precios import RUTA_POR_DEFECTO as RUTA_PRECIOS
from agente.memoria_precios import MemoriaPrecios
from evals.reporte import costo

RUTA_CONVERSACIONES = os.path.join("memoria", "conversaciones.json")


def _pintar_brief(datos: dict, titulo: str = "BRIEF PARA EL EQUIPO") -> None:
    print(f"\n  ┌─ {titulo} " + "─" * 40)
    for k, v in datos.items():
        if k == "mensaje_confirmacion":
            continue
        marca = "  " if str(v).strip() else " ·"   # · = vacío a propósito
        print(f"  │{marca} {k:<20} {v if str(v).strip() else '(no lo dijo)'}")
    print("  └" + "─" * 62)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ejecutar", description="Conversar con el agente.")
    p.add_argument("--sender", default="terminal", help="id de la conversación")
    p.add_argument("--modelo", default=MODELO)
    p.add_argument("--sin-guardar", action="store_true", help="no persiste nada a disco")
    args = p.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    cargar_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Falta ANTHROPIC_API_KEY. Copia .env.example a .env y rellénala,")
        print("o expórtala:  export ANTHROPIC_API_KEY=sk-ant-...")
        return 1

    ruta = None if args.sin_guardar else RUTA_CONVERSACIONES
    memoria_conv = Memoria(ruta=ruta)
    conv = memoria_conv.obtener(args.sender)
    memoria_precios = MemoriaPrecios(ruta=None if args.sin_guardar else RUTA_PRECIOS)
    agente = AgenteVivoGardens(modelo=args.modelo, memoria=memoria_precios)

    print(f"Vivo Gardens — {args.modelo} — conversación '{args.sender}'")
    print("Escribe /salir para terminar, /foto <url> para adjuntar una imagen.\n")
    if conv.mensajes:
        print(f"(retomando una conversación con {conv.turnos_usuario} turnos)\n")

    entrada_tot = salida_tot = 0
    imagenes: list[str] = []

    while True:
        try:
            texto = input("tú  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not texto:
            continue
        if texto == "/salir":
            break
        if texto == "/estado":
            print(f"  turnos del cliente: {conv.turnos_usuario}")
            print(f"  tokens: {entrada_tot} entrada / {salida_tot} salida")
            c = costo(args.modelo, entrada_tot, salida_tot)
            print(f"  costo: {'$%.5f' % c if c is not None else 'modelo sin tarifa en tabla'}\n")
            continue
        if texto == "/pendientes":
            pend = [f for f in memoria_precios.pendientes if not f.resuelto]
            print(f"  {len(pend)} precio(s) pendiente(s):")
            for f in pend:
                print(f"   · {f.concepto} [{f.modalidad}] — {f.contexto}")
            print()
            continue
        if texto.startswith(("/foto ", "/post ")):
            imagenes.append(texto.split(" ", 1)[1].strip())
            print(f"  (adjunta: {len(imagenes)} imagen(es); van con tu próximo mensaje)\n")
            continue

        conv.agregar_usuario(texto, imagenes or None)
        imagenes = []

        try:
            r = agente.responder(conv.mensajes)
        except Exception as e:                      # noqa: BLE001 — es un CLI
            print(f"  [error de API] {type(e).__name__}: {e}\n")
            conv.mensajes.pop()                     # no dejar el turno colgado
            continue

        conv.agregar_asistente(r.texto)
        entrada_tot += r.uso.get("input_tokens", 0)
        salida_tot += r.uso.get("output_tokens", 0)

        print(f"bot > {r.texto}")
        if r.agendo and r.datos_cita:
            _pintar_brief(r.datos_cita, "VISITA")
        elif r.datos_pedido:
            _pintar_brief(r.datos_pedido, "PEDIDO")
        elif r.consulta:
            print(f"  [consulta al equipo · {r.consulta.get('tipo')}] "
                  f"{r.consulta.get('concepto')} → anotado")

        cache = r.uso.get("cache_read_input_tokens", 0)
        print(f"  ({r.uso.get('input_tokens', 0)} in / {r.uso.get('output_tokens', 0)} out"
              f"{f', {cache} del caché' if cache else ''})\n")

        if not args.sin_guardar:
            memoria_conv.guardar()

        if r.agendo:
            print("  La conversación llegó a su objetivo: cita registrada.\n")

    if not args.sin_guardar:
        memoria_conv.guardar()
    c = costo(args.modelo, entrada_tot, salida_tot)
    print(f"\nTotal: {entrada_tot} in / {salida_tot} out"
          f"{f' — ${c:.5f}' if c is not None else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
