# -*- coding: utf-8 -*-
"""El catalogo real de Vivo Gardens: la capa que aterriza al modelo.

Dos preguntas distintas, dos mundos distintos
---------------------------------------------
    "¿Que planta es esta?"  -> mundo ABIERTO. La responde el modelo de vision
                               solo, sin catalogo. Identificar es libre.
    "¿La tienen?"           -> mundo CERRADO. La responde este archivo. Afirmar
                               disponibilidad no es libre.

No entrenamos ningun clasificador. Sonnet 5 ya identifica plantas ornamentales
comunes; el cuello de botella nunca fue el modelo sino saber que hay en stock.

Distincion que sostiene el diseno
---------------------------------
Lo que el modelo VE (el espacio, la luz, el tamano, el estado) va al brief como
hecho, en detalle_espacio. Lo que el modelo RECOMIENDA como disponible va en
plantas_sugeridas y sale de aqui. Identificar especies por foto se equivoca
seguido, y una especie equivocada prometida como disponible manda el camion con
la planta que no era.

⚠️ ESTA LISTA ESTA INCOMPLETA A PROPOSITO Y HAY QUE SABERLO
El vivero tiene mas especies de las que publica en la web. Por eso el catalogo
NO se usa como jaula ("no esta aqui, no existe") sino como el conjunto sobre el
que se puede AFIRMAR disponibilidad. Identificar es de mundo abierto; prometer
que lo tenemos es de mundo cerrado. Decirle a un cliente que no vendemos algo
que si vendemos pierde la venta y queda mal.

Fuente: vivogardens.com/plants, 43 plantas leidas el 2026-09-03.
PENDIENTE: pedirle a Luis el inventario real (Excel, o fotos de las etiquetas
de los estantes). Hasta ~300 plantas caben en el prompt sin cambiar nada mas.
"""
from __future__ import annotations

from dataclasses import dataclass

# nombre | interior / exterior / ambos | "facil" si esta marcada como apta para principiantes
_CRUDO = """
Orange Tree                            | exterior
Bougainvillea                          | exterior
Banana Plant                           | exterior
Areca Palm                             | ambos    | facil
Sago Palm                              | ambos    | facil
Color Cactus Garden                    | ambos    | facil
Philodendron Xanadu                    | ambos    | facil
Column Cactus                          | ambos    | facil
Variegated Ficus Topiary               | ambos
Spiral Cactus                          | exterior | facil
Podocarpus Ball Topiary                | exterior | facil
Pencil Cactus                          | exterior | facil
Beaked Yucca                           | exterior | facil
Agave                                  | exterior | facil
Japanese Sedge                         | exterior | facil
Snake Plant                            | interior | facil
Satin Pothos                           | interior | facil
Neon Pothos                            | interior | facil
Marble Queen Pothos                    | interior | facil
White Bird of Paradise                 | interior | facil
Braided Money Tree                     | interior | facil
Dracaena Janet Craig                   | interior | facil
Dracaena Marginata                     | interior | facil
Braided Dracaena Marginata             | interior | facil
Dracaena Fragrans                      | interior | facil
Dracaena Fragrans 'Dorado'             | interior | facil
Dracaena Reflexa 'Anita'               | interior | facil
Corn Plant                             | interior | facil
Rubber Plant                           | interior | facil
Heartleaf Philodendron                 | interior | facil
Philodendron Red Emerald               | interior | facil
Philodendron Green Congo               | interior | facil
Philodendron 'Prince of Orange'        | interior | facil
Epipremnum Pinnatum 'Albo Variegata'   | interior | facil
Aglaonema Red                          | interior | facil
ZZ Plant                               | interior | facil
Phalaenopsis Orchid                    | interior | facil
Ponytail Palm                          | interior | facil
Monstera                               | interior
Fiddle Leaf Fig                        | interior
Peace Lily                             | interior
Ficus Audrey                           | interior
Bird of Paradise                       | interior
"""


@dataclass(frozen=True)
class Planta:
    nombre: str
    ubicacion: str   # interior | exterior | ambos
    facil: bool


def _parsear() -> list[Planta]:
    plantas = []
    for linea in _CRUDO.strip().splitlines():
        partes = [p.strip() for p in linea.split("|")]
        plantas.append(Planta(
            nombre=partes[0],
            ubicacion=partes[1],
            facil=len(partes) > 2 and partes[2] == "facil",
        ))
    return plantas


CATALOGO: list[Planta] = _parsear()
NOMBRES: set[str] = {p.nombre for p in CATALOGO}


def interiores() -> list[Planta]:
    return [p for p in CATALOGO if p.ubicacion in ("interior", "ambos")]


def exteriores() -> list[Planta]:
    return [p for p in CATALOGO if p.ubicacion in ("exterior", "ambos")]


def resumen_para_prompt() -> str:
    """El catalogo comprimido para meterlo en el system prompt.

    Pesa ~200 tokens por llamada. Se paga en cada mensaje, y vale la pena: sin
    esto el modelo sugiere plantas que el vivero no tiene, y el cliente llega a
    la visita esperando algo que no existe.
    """
    def fila(p: Planta) -> str:
        return f"{p.nombre}{' (fácil)' if p.facil else ''}"

    return (
        "INTERIOR: " + ", ".join(fila(p) for p in interiores()) + "\n"
        "EXTERIOR: " + ", ".join(fila(p) for p in exteriores())
    )


def es_del_catalogo(nombre: str) -> bool:
    """Comparacion laxa: el modelo puede escribir 'areca' o 'palma areca'."""
    n = nombre.strip().lower()
    if not n:
        return False
    return any(n in c.lower() or c.lower() in n for c in NOMBRES)
