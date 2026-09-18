# -*- coding: utf-8 -*-
"""Aperturas: el primer mensaje que manda el boton, no el cliente.

Cuando alguien toca un boton del anuncio o del perfil, Instagram manda un texto
PREDEFINIDO como primer DM. El cliente no escribio nada.

⚠️ ESTOS TEXTOS SON REALES, NO INVENTADOS
La primera version de este archivo eran conjeturas mias, sacadas del FAQ del
sitio. Se reemplazaron leyendo ~30 conversaciones de @vivogardensmiami el
2026-09-04: cada `texto` de abajo esta copiado literal de un DM. Si el anuncio
cambia, esto se vuelve a leer -- no se adivina.

Dos consecuencias para el agente:

1. La apertura es configuracion del despliegue, no del codigo. Vive en Ads
   Manager y en los ajustes del perfil, y puede cambiar cualquier martes sin
   avisar. Si cambia y el agente se rompe, nadie se entera hasta ver la factura.

2. NINGUNA apertura trae los tres datos de una visita, y varias ni siquiera
   dicen que planta. De ahi el invariante que vale para todas: el agente jamas
   agenda en el primer turno, y jamas suelta una cifra -- ni siquiera cuando el
   boton es literalmente "¿Cuanto cuesta?", que es el mas usado de todos.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Apertura:
    id: str
    texto: str
    fuente: str        # de donde sale el texto
    riesgo: str = ""   # que puede salir mal con esta apertura en particular
    frecuencia: int = 0  # veces vistas en 100 hilos (0 = observada pero fuera del top)


# Frecuencias contadas sobre 100 hilos unicos el 2026-09-04, agrupando el primer
# mensaje del cliente por texto exacto: un CTA se repite identico, lo que escribe
# una persona es unico. Solo 17 de 100 primeros mensajes eran escritos a mano.
#
# 59 de 100 entran preguntando el precio. Si el agente solo hiciera bien una cosa,
# tendria que ser esa.
APERTURAS: list[Apertura] = [
    Apertura(
        id="cta_precio",
        texto="¿Cuánto cuesta?",
        fuente="CTA del anuncio",
        frecuencia=49,
        riesgo=(
            "LA MITAD DEL TRÁFICO entra por aquí. Pide precio sin decir de qué: "
            "cotizar es inventar, y callarse es lo que pasa hoy. El equipo responde "
            "'¿cuál planta le gusta?' y eso es lo correcto"
        ),
    ),
    Apertura(
        id="cta_precio_planta",
        texto="¿Cuánto cuesta una planta?",
        fuente="CTA del anuncio",
        frecuencia=7,
        riesgo="se vio repetido 2 y 3 veces sin que nadie respondiera",
    ),
    Apertura(
        id="cta_precio_corto",
        texto="¿Precio?",
        fuente="CTA del anuncio",
        frecuencia=3,
        riesgo="el mínimo contexto posible: una palabra y un signo",
    ),
    Apertura(
        id="cta_que_tipos_plantas",
        texto="¿Qué tipos de plantas tienen?",
        fuente="CTA del anuncio",
        frecuencia=5,
        riesgo="invita a recitar el catálogo entero en un DM, y a prometer stock",
    ),
    Apertura(
        id="cta_que_plantas",
        texto="¿Qué plantas tienen?",
        fuente="CTA del anuncio",
        frecuencia=4,
        riesgo="igual que el anterior; el inventario real es mayor que el publicado",
    ),
    Apertura(
        id="cta_ingles_generico",
        texto="Hi, please let us know how we can help you.",
        fuente="CTA en inglés (posible plantilla por defecto de Meta)",
        frecuencia=2,
        riesgo="debe responder EN INGLÉS y abrir la conversación sin contexto ninguno",
    ),
    Apertura(
        id="cta_visitar_vivero",
        texto="Quiero visitar el vivero",
        fuente="CTA del anuncio",
        frecuencia=8,
        riesgo="quiere ir a la TIENDA: no debe agendarle una visita a domicilio",
    ),
    Apertura(
        id="cta_cita_domicilio",
        texto="Agendar cita a domicilio",
        fuente="CTA del anuncio",
        riesgo="el horario de visitas NO es el de la tienda: lun-sáb de 11 a 5",
    ),
    Apertura(
        id="cta_redisenar",
        texto="Quiero rediseñar mi espacio",
        fuente="CTA del anuncio",
        riesgo="flujo de proyecto: aquí sí van los tres datos y la visita gratis",
    ),
    Apertura(
        id="cta_elegir_plantas",
        texto="Necesito ayuda para elegir plantas.",
        fuente="CTA del anuncio",
        riesgo="pide asesoría: no recomendar fuera del catálogo ni prometer stock",
    ),
    Apertura(
        id="cta_como_comprar",
        texto="¿Cómo realizo una compra?",
        fuente="CTA del anuncio",
        frecuencia=3,
        riesgo="flujo de producto puro: qué planta, qué tamaño, cómo se entrega",
    ),
    Apertura(
        id="cta_entrega",
        texto="¿Se puede entregar?",
        fuente="CTA del anuncio",
        riesgo="la respuesta es sí, pero no puede cerrar ahí: tiene que avanzar la venta",
    ),
    Apertura(
        id="organico_ubicacion",
        texto="Buenas noches donde están localizados, gracias",
        fuente="DM orgánico, sin botón",
        riesgo="dar dirección y horario de tienda sin inventarlos",
    ),
    # --- Vistos en la bandeja el 2026-09-18. Son textos de BOTON generados por
    # Meta (configuracion del anuncio), no mensajes escritos por una persona.
    # frecuencia=0: se observaron sobre 15 hilos, no sobre los 100 del conteo
    # del 2026-09-04, y no se mezclan dos muestras distintas.
    Apertura(
        id="cta_ingles_plantas_premium",
        texto="What types of premium plants do you offer?",
        fuente="CTA en ingles del anuncio",
        riesgo=(
            "Visto dos veces el mismo dia y ninguna vez tuvo respuesta util. "
            "Debe responder EN INGLES y no prometer stock: 'premium' invita a "
            "afirmar un catalogo que no se puede confirmar"
        ),
    ),
    Apertura(
        id="cta_ingles_macetas",
        texto="What types of pots do you offer?",
        fuente="CTA en ingles del anuncio",
        riesgo=(
            "Pregunta por MACETAS, no por plantas. El catalogo publicado no las "
            "lista con precio, asi que lo honesto es consultar al equipo"
        ),
    ),
    Apertura(
        id="cta_como_puedo_comprar",
        texto="¿Cómo puedo comprar?",
        fuente="CTA del anuncio",
        riesgo=(
            "Variante literal de cta_como_comprar ('¿Cómo realizo una compra?'): "
            "el anuncio manda las dos redacciones y conviene probar ambas"
        ),
    ),
]

POR_ID = {ap.id: ap for ap in APERTURAS}


def con_apertura(caso, apertura: Apertura):
    """Devuelve una copia del caso con el primer turno reemplazado por la apertura.

    Sirve para responder "este caso, pero entrando por tal boton" sin duplicar
    los casos en `casos.py`.
    """
    if not caso.turnos:
        return caso
    turnos = [apertura.texto, *caso.turnos[1:]]
    return replace(caso, id=f"{caso.id}@{apertura.id}", turnos=turnos)
