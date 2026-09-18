# -*- coding: utf-8 -*-
"""Carga el .env sin dependencias.

Por que existe
--------------
El README dice "copia .env.example a .env y pon tu key", y sin esto esa
instruccion seria mentira: nada leia el archivo. Un proyecto que documenta un
paso que no funciona es peor que uno que no lo documenta.

Por que no python-dotenv
------------------------
Son 30 lineas y evita una dependencia en un proyecto cuyo unico requisito duro
es el SDK de Anthropic. Cuantas menos cosas haya que instalar para correr las
evaluaciones, mas probable es que alguien las corra.

Por que solo lo llaman los puntos de entrada
--------------------------------------------
Leer archivos y tocar `os.environ` al importar una libreria es un efecto
secundario invisible: rompe las pruebas y sorprende a quien la use desde otro
lado. Asi que `agente/` no lo hace nunca; lo hacen `ejecutar.py` y `evals`,
que son programas y no librerias.
"""
from __future__ import annotations

import os

RUTA_POR_DEFECTO = ".env"


def cargar_env(ruta: str = RUTA_POR_DEFECTO) -> int:
    """Mete en el entorno lo que haya en el .env. Devuelve cuantas cargo.

    Las variables que YA estan en el entorno mandan sobre el archivo: si
    alguien exporta la key a mano para una corrida puntual, esa gana.
    """
    if not os.path.exists(ruta):
        return 0

    cargadas = 0
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            clave = clave.strip()
            valor = valor.strip().strip('"').strip("'")
            if not clave or not valor:
                continue
            if clave in os.environ:      # el entorno explicito manda
                continue
            os.environ[clave] = valor
            cargadas += 1
    return cargadas
