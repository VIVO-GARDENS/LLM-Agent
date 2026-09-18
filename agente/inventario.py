# -*- coding: utf-8 -*-
"""Inventario aprendido: las plantas que el catalogo publicado no tiene.

El problema
-----------
`catalogo.py` son las 43 plantas de la web. El vivero vende mas. Un cliente
puede llegar preguntando por una calathea, una monstera variegada o un mango
injertado, y ninguna esta en la lista.

Hoy el agente hace lo correcto en el momento: no niega, dice que el equipo
confirma. Pero eso se olvida. Si el equipo responde "si, tenemos calatheas", el
proximo cliente que pregunte se encuentra al agente igual de ignorante -- y a
alguien le toca contestar la misma pregunta otra vez. Eso es justo la fuga que
el agente vino a tapar, reproducida por el agente.

Tres estados, y el tercero es el que importa
--------------------------------------------
    si_hay        el equipo confirmo que la tienen -> el agente ya puede decirlo
    no_hay        el equipo confirmo que no -> puede decirlo, con tacto
    preguntado    alguien pregunto y nadie ha respondido -> trabajo pendiente

Lo valioso no es la lista de confirmadas: es la de `preguntado`. Es demanda
medida. Si quince clientes preguntan por calatheas en un mes, eso no es una
duda del bot, es una recomendacion de compra para el vivero.

Por que se separa del catalogo publicado
----------------------------------------
El catalogo es un hecho verificable (esta en la web). Esto es conocimiento
acumulado, con procedencia y fecha. Mezclarlos haria imposible saber de donde
salio cada afirmacion -- y el agente afirma disponibilidad, que es lo que mas
caro cuesta equivocar.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date

RUTA_POR_DEFECTO = os.path.join("memoria", "inventario.json")

SI_HAY = "si_hay"
NO_HAY = "no_hay"
PREGUNTADO = "preguntado"


@dataclass
class PlantaAprendida:
    nombre: str
    estado: str = PREGUNTADO
    # El post o la foto por la que se pregunto, cuando hubo imagen.
    referencia: str = ""
    # Cuantas veces la han pedido. Es la senal de demanda.
    veces_pedida: int = 1
    nota: str = ""
    fecha: str = field(default_factory=lambda: date.today().isoformat())

    @property
    def clave(self) -> str:
        return self.nombre.strip().lower()


class Inventario:
    def __init__(self, ruta: str | None = RUTA_POR_DEFECTO):
        self.ruta = ruta
        self.plantas: dict[str, PlantaAprendida] = {}
        if ruta and os.path.exists(ruta):
            self._cargar()

    # -- lectura ----------------------------------------------------------
    def buscar(self, nombre: str) -> PlantaAprendida | None:
        """Coincidencia laxa: el cliente escribe 'calatea' y la tabla 'calathea'."""
        n = (nombre or "").strip().lower()
        if not n:
            return None
        if n in self.plantas:
            return self.plantas[n]
        for clave, p in self.plantas.items():
            if n in clave or clave in n:
                return p
        return None

    def confirmadas(self) -> list[PlantaAprendida]:
        return [p for p in self.plantas.values() if p.estado == SI_HAY]

    def descartadas(self) -> list[PlantaAprendida]:
        return [p for p in self.plantas.values() if p.estado == NO_HAY]

    def pendientes(self) -> list[PlantaAprendida]:
        """Lo que nadie ha respondido, de mas pedida a menos. Es demanda medida."""
        return sorted(
            (p for p in self.plantas.values() if p.estado == PREGUNTADO),
            key=lambda p: -p.veces_pedida,
        )

    # -- escritura --------------------------------------------------------
    def pedida(self, nombre: str, referencia: str = "") -> PlantaAprendida:
        """Un cliente la pidio. Si ya se conocia, solo sube el contador."""
        p = self.buscar(nombre)
        if p is not None:
            p.veces_pedida += 1
            if referencia and not p.referencia:
                p.referencia = referencia
            self.guardar()
            return p
        p = PlantaAprendida(nombre=nombre.strip(), referencia=referencia)
        self.plantas[p.clave] = p
        self.guardar()
        return p

    def responder(self, nombre: str, hay: bool, nota: str = "") -> PlantaAprendida:
        """El equipo contesta. A partir de aqui el agente ya lo sabe."""
        p = self.buscar(nombre) or self.pedida(nombre)
        p.estado = SI_HAY if hay else NO_HAY
        p.nota = nota
        p.fecha = date.today().isoformat()
        self.guardar()
        return p

    # -- persistencia -----------------------------------------------------
    def _cargar(self) -> None:
        with open(self.ruta, encoding="utf-8") as f:
            for d in json.load(f).get("plantas", []):
                p = PlantaAprendida(**d)
                self.plantas[p.clave] = p

    def guardar(self) -> None:
        if not self.ruta:
            return
        carpeta = os.path.dirname(self.ruta)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump({"plantas": [asdict(p) for p in self.plantas.values()]},
                      f, ensure_ascii=False, indent=2)

    # -- para el prompt ---------------------------------------------------
    def nombres_conocidos(self) -> set[str]:
        """Confirmadas. Se suman al catalogo para lo que el agente puede afirmar."""
        return {p.nombre for p in self.confirmadas()}

    def resumen_para_prompt(self) -> str:
        si = self.confirmadas()
        no = self.descartadas()
        if not si and not no:
            return ""
        lineas = ["ADEMÁS del catálogo, el equipo ya confirmó estas:"]
        if si:
            lineas.append(
                "- SÍ tenemos (puedes afirmarlo): "
                + ", ".join(f"{p.nombre}{f' — {p.nota}' if p.nota else ''}" for p in si)
            )
        if no:
            lineas.append(
                "- NO tenemos (dilo con tacto y ofrece alternativas del catálogo): "
                + ", ".join(p.nombre for p in no)
            )
        return "\n".join(lineas)
