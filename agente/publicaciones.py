# -*- coding: utf-8 -*-
"""Las publicaciones que los clientes comparten en el DM.

Cuando alguien comparte un post, Instagram entrega su `code`. Eso convierte
"¿que planta quiere?" en una busqueda en tabla, que no se equivoca -- siempre
que la tabla sepa que muestra ese post.

Lo que enseño mirar los datos
-----------------------------
La idea original era `code -> planta`. Contando las comparticiones reales
(35 en ~100 conversaciones) resulta que **casi ningun post muestra una planta
concreta**: son piezas promocionales. De los 5 posts que concentran el trafico,
solo uno identifica una especie.

    Dav71afA4OK   16x   "cuando hay plantas, hay vida"      generico
    DcUJy68g7pB    7x   post de delivery                    generico
    Dct1TnwASqn    7x   carrusel de resultados              generico
    DXK0wDVgP_3    3x   sin descripcion util                generico
    DbtXPDnAMin    2x   "cosecha tus propios mangos"        mango

Consecuencia de diseno: el valor de esta tabla NO es adivinar la planta, es
saber CUANDO NO SE PUEDE SABER. Un post generico compartido significa "me
interesa lo que hacen", no "quiero esta planta", y ahi lo correcto es preguntar
cual -- que es exactamente lo que hace el equipo.

Compartir un post generico y cotizar algo seria inventar dos veces: la planta y
el precio.

MANTENIMIENTO: los `code` salen de los DMs. Al publicar un post nuevo que
genere trafico, agregarlo aqui. Si no esta en la tabla, el agente igual
funciona: lee la descripcion que le llega en el propio mensaje.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Publicacion:
    code: str
    resumen: str            # que muestra, en una linea
    planta: str = ""        # especie concreta, o vacio si el post es generico
    veces_compartida: int = 0

    @property
    def es_generica(self) -> bool:
        """Si no identifica una planta, el agente tiene que preguntar cual."""
        return not self.planta


PUBLICACIONES: list[Publicacion] = [
    Publicacion(
        code="Dav71afA4OK",
        resumen="pieza promocional: plantas en distintos espacios",
        veces_compartida=16,
    ),
    Publicacion(
        code="DcUJy68g7pB",
        resumen="entrega a domicilio: el cliente elige y ellos la llevan",
        veces_compartida=7,
    ),
    Publicacion(
        code="Dct1TnwASqn",
        resumen="carrusel de espacios ya hechos para clientes",
        veces_compartida=7,
    ),
    Publicacion(
        code="DXK0wDVgP_3",
        resumen="publicacion sin descripcion util",
        veces_compartida=3,
    ),
    Publicacion(
        code="DbtXPDnAMin",
        resumen="arbol de mango con fruta, para el jardin",
        planta="mango",
        veces_compartida=2,
    ),
]

POR_CODE = {p.code: p for p in PUBLICACIONES}


def buscar(code: str) -> Publicacion | None:
    return POR_CODE.get((code or "").strip())


def contexto_para_prompt(code: str) -> str:
    """Lo que se le puede decir al modelo sobre un post que el cliente comparte.

    Se devuelve vacio si el post no esta en la tabla: entonces el modelo se
    apoya en la descripcion que ya viaja en el mensaje, que es mejor que una
    suposicion nuestra.
    """
    p = buscar(code)
    if p is None:
        return ""
    if p.es_generica:
        return (
            f"[la publicación {p.code} es {p.resumen}: NO muestra una planta concreta, "
            "así que no supongas cuál quiere — pregúntaselo]"
        )
    return (
        f"[la publicación {p.code} muestra {p.resumen}. La planta es: {p.planta}. "
        "Confírmalo con el cliente antes de cotizar]"
    )
