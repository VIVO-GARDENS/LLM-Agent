# -*- coding: utf-8 -*-
"""Precios OBSERVADOS en los DMs. No es una lista oficial y no hay que fingir que lo sea.

De donde sale
-------------
No existe lista de precios escrita. Lo que existe son 43 mensajes en los que el
equipo cotizo por DM entre agosto y septiembre de 2026. Este modulo es esa
evidencia, estructurada -- que es distinto de una politica de precios y hay que
tratarlo distinto: el agente da APROXIMADOS y el equipo confirma el exacto.

La estructura que se leyo de las conversaciones
----------------------------------------------
Hay DOS precios por planta, no uno:

    "planta sola"        el ejemplar y nada mas; tambien el precio si el
                         cliente la recoge en la tienda
    "listo en su casa"   incluye maceta, tierra, vitaminas (dicen "para 6
                         meses"), entrega e instalacion

Y el multiplicador es el TAMANO. Entre ellos lo miden en galones, pero con el
cliente lo hablan en "grande o pequena" y lo traducen a pies (1 pie / 3 pies).
El agente pregunta en los terminos del cliente, no en los del vivero: sin
tamano, cualquier cifra es inventada.

    "Son 250 y 450 la sola planta"                        (limon / naranjo)
    "El limon con la maceta tiene un costo de 1200 listo en su casa"
    "Asi de grande 1200 con su maceta tierra vitaminas listo en su casa"
    "Como el del video Cuesta 2200 listo en su casa"
    "Si la Recoje 80"
    "Desde 80 dolares hasta 250 dependiendo la especie"
    "15 galones"

⚠️ COMO USAR ESTO SIN HACER DANO
El mismo limon aparece a 250 (sola) y a 1200 (listo en su casa). Dar una cifra
sin decir cual de las dos modalidades es, es peor que no dar ninguna: el cliente
escucha 250 y le llega una cotizacion de 1200. Toda cifra va con su modalidad y
con la advertencia de que el equipo confirma.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Observacion:
    """Una cotizacion real, con su procedencia. `n` = cuantas veces se vio."""

    concepto: str
    modalidad: str      # "sola" | "listo_en_casa" | "recoge"
    monto: int
    n: int = 1
    nota: str = ""
    # ¿El concepto nombra una planta concreta, o es una talla generica?
    #
    # Esto no es cosmetico. Poner "planta mediana: $250" en el prompt le da al
    # modelo justo lo que necesita para contestar "¿cuanto cuesta?" con un rango
    # -- que es cotizar en abstracto, lo que la regla de arriba prohibe. Un
    # ensayo en seco lo confirmo: con la tabla generica delante, la respuesta
    # natural es "van desde 80 hasta 650".
    #
    # Solo los conceptos nombrados se le muestran como cotizables. Los genericos
    # quedan como orden de magnitud interno, para que no se desvie.
    nombrada: bool = False


# Ordenadas por confianza: cuantas veces se observo y que tan explicito fue el
# mensaje. Al conseguir la lista real del negocio, esto se reemplaza entero.
OBSERVACIONES: list[Observacion] = [
    # Nombradas: el equipo las cotizo para una planta concreta. Cotizables.
    Observacion("limón", "sola", 250, 2, "'son 250 y 450 la sola planta'", nombrada=True),
    Observacion("naranjo", "sola", 450, 3, "misma conversacion que el limon", nombrada=True),
    Observacion("frutal con maceta, entrega e instalación", "listo_en_casa", 1200, 4,
                "'con su maceta tierra vitaminas listo en su casa'", nombrada=True),
    # Genericas: salen de rangos sueltos, sin planta de por medio. Solo sirven
    # como orden de magnitud interno; el agente NO las usa para cotizar.
    Observacion("planta pequena o comun", "sola", 80, 3, "piso; tambien 'si la recoge 80'"),
    Observacion("planta mediana", "sola", 250, 4, "techo del rango 'desde 80 hasta 250'"),
    # ⚠️ NO ASCENDER A nombrada=True. El dueño del proyecto zanjo el 2026-09-18
    # que NO hay un 650 fijo: fue una cotizacion puntual de esa planta. Ademas
    # un DM del 2026-09-18 lo muestra como "cada planta instalada" (planta,
    # maceta, tierra, labor, vitaminas, delivery), o sea con OTRA modalidad que
    # la registrada aqui. Dos lecturas del mismo numero: no sirve de ancla.
    Observacion("planta grande", "sola", 650, 1,
                "cifra suelta, sin contexto de especie; lectura en disputa"),
    Observacion("ejemplar grande instalado", "listo_en_casa", 2200, 1,
                "dicho como 'como el del video': fuera de esa conversacion no significa nada"),
]

# Como se habla el tamano: con el cliente, en tallas; entre ellos, en galones.
TALLAS_CLIENTE = {"pequena": "1 pie", "grande": "3 pies"}
UNIDAD_INTERNA = "galones"

MODALIDADES = {
    "sola": "solo la planta (o si el cliente la recoge en la tienda)",
    "listo_en_casa": "con maceta, tierra, vitaminas, entrega e instalacion",
    "recoge": "el cliente la recoge en la tienda",
}


# El agente NUNCA repite la cifra exacta que le dijo el equipo. Si le dicen 120,
# dice "entre 110 y 140".
#
# Por que un rango y no el numero:
#   - Un numero exacto es una promesa. El equipo tendria que honrar 120 aunque
#     ese ejemplar sea mas grande, o desdecirse delante del cliente.
#   - El precio real varia por tamano, por ejemplar y por temporada. El 120 que
#     dijo el equipo era para UNA planta concreta, no para la especie.
#   - Un rango pone expectativa sin crear compromiso, que es exactamente lo que
#     un vendedor humano hace cuando todavia no vio la planta.
#
# El margen es asimetrico a proposito: tira mas hacia arriba que hacia abajo.
# Que el precio real quede por debajo de lo dicho es una sorpresa agradable;
# por encima, una discusion.
MARGEN_ABAJO = 0.10
MARGEN_ARRIBA = 0.20


def rango_para(monto: int) -> tuple[int, int]:
    """Convierte un precio aprendido en el rango que el agente puede decir.

    Redondea a decenas para que suene a estimacion y no a tarifa:
    "entre 110 y 140" se lee como aproximado; "entre 108 y 144" suena a que
    alguien calculo algo y por tanto a que es exacto.
    """
    # La granularidad crece con el monto: "entre 1080 y 1440" suena a que alguien
    # calculo algo, y por tanto a cifra firme. "entre 1100 y 1400" suena a lo que
    # es, una estimacion.
    paso = 10 if monto < 300 else 50 if monto < 1000 else 100

    def redondear(x: float) -> int:
        return max(paso, int(round(x / paso)) * paso)

    bajo = redondear(monto * (1 - MARGEN_ABAJO))
    alto = redondear(monto * (1 + MARGEN_ARRIBA))
    if alto <= bajo:
        alto = bajo + paso
    return bajo, alto


def rango_observado(modalidad: str) -> tuple[int, int] | None:
    montos = [o.monto for o in OBSERVACIONES if o.modalidad == modalidad]
    return (min(montos), max(montos)) if montos else None


# Cifras que el agente tiene permitido pronunciar: los extremos de los rangos,
# no los montos observados. El monto exacto es justo lo que no debe repetir.
MONTOS_AUTORIZADOS: set[int] = {
    extremo for o in OBSERVACIONES for extremo in rango_para(o.monto)
}
