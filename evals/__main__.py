# -*- coding: utf-8 -*-
"""Punto de entrada:  python -m evals

Sale con codigo 1 si algun caso falla, para que sirva de compuerta en CI.

  python -m evals                          todo (32 casos)
  python -m evals --grupo aperturas        solo el barrido de botones (13 casos)
  python -m evals --caso precio_directo    un caso
  python -m evals --grupo base --apertura cta_precio
        los casos base pero entrando por el boton "Cuanto cuesta?"
"""
from __future__ import annotations

import argparse
import os
import sys

from agente.agente import MODELO
from agente.entorno import cargar_env

from . import aperturas as ap_mod
from .casos import GRUPOS, POR_ID, TODOS
from .corredor import correr
from .reporte import como_json, render


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evals", description="Banco de pruebas del agente.")
    p.add_argument("--caso", action="append", metavar="ID",
                   help="corre solo este caso (repetible)")
    p.add_argument("--grupo", choices=sorted(GRUPOS), default="todos",
                   help="base | aperturas | todos (por defecto todos)")
    p.add_argument("--apertura", metavar="ID",
                   help="reemplaza el primer turno por el texto de esa apertura")
    p.add_argument("--modelo", default=MODELO, help=f"por defecto {MODELO}")
    p.add_argument("--json", metavar="RUTA", help="ademas escribe el resultado en JSON")
    p.add_argument("--listar", action="store_true", help="lista casos y aperturas, y sale")
    args = p.parse_args(argv)
    cargar_env()

    # La consola de Windows no siempre es UTF-8 y los casos llevan emojis.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if not args.listar and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Falta ANTHROPIC_API_KEY.")
        print("Ponla en un archivo .env junto a este proyecto:")
        print("    ANTHROPIC_API_KEY=sk-ant-...")
        print("(.env está en .gitignore, no se sube a ningún lado)")
        return 1

    if args.listar:
        print("CASOS")
        for c in TODOS:
            print(f"  {c.id:<28} {len(c.turnos)} turno(s)  {c.descripcion}")
        print("\nAPERTURAS (--apertura ID)")
        for ap in ap_mod.APERTURAS:
            print(f"  {ap.id:<20} {ap.texto!r}  [{ap.fuente}]")
        return 0

    if args.caso:
        desconocidos = [c for c in args.caso if c not in POR_ID]
        if desconocidos:
            p.error(f"caso(s) desconocido(s): {', '.join(desconocidos)}")
        casos = [POR_ID[c] for c in args.caso]
    else:
        casos = GRUPOS[args.grupo]

    if args.apertura:
        if args.apertura not in ap_mod.POR_ID:
            p.error(f"apertura desconocida: {args.apertura}")
        ap = ap_mod.POR_ID[args.apertura]
        casos = [ap_mod.con_apertura(c, ap) for c in casos]

    resultados = correr(casos, modelo=args.modelo)
    print(render(resultados, args.modelo))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(como_json(resultados, args.modelo))
        print(f"\nJSON escrito en {args.json}")

    return 0 if all(r.paso for r in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
