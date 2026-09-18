# -*- coding: utf-8 -*-
"""Los casos del banco de pruebas.

Cada caso es una conversacion con turnos de usuario FIJOS. No hay un modelo
simulando al cliente: si el usuario tambien fuera generado, dos corridas no
serian comparables y el banco dejaria de servir para detectar regresiones.

Los turnos salen del comportamiento real observado en la pauta de agosto 2026:
la mayoria pregunta el precio de entrada, casi nadie da los tres datos de una,
y un 4.8% escribe en ingles.

Hay dos grupos:
  CASOS            conversaciones completas, con el primer mensaje escrito a mano
  CASOS_APERTURA   un turno por cada boton configurado (ver `aperturas.py`)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import aperturas as ap_mod
from . import aserciones as a
import datetime as _dt

# Las fechas de los casos estaban escritas a mano ("viernes 12 de septiembre")
# y caducaron. El agente hacia lo correcto --avisar que el dia ya paso, porque
# el system prompt le da la fecha de hoy-- y el caso lo contaba como fallo.
# Relativas al dia de la corrida no se vuelven a podrir.
_DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _proximo(dia: int) -> str:
    """El proximo <dia> de la semana (0=lunes), siempre en el futuro."""
    hoy = _dt.date.today()
    d = hoy + _dt.timedelta(days=((dia - hoy.weekday()) % 7) or 7)
    return f"{_DIAS[dia]} {d.day} de {_MESES[d.month - 1]}"



# Una foto real de patio de cliente, publicada por el propio negocio en
# vivogardens.com/services (la mitad "BEFORE" de un antes/despues). Es publica,
# es de ellos, y es exactamente el tipo de imagen que llega por DM.
FOTO_PATIO = (
    "https://res.cloudinary.com/dxxvh5tlp/image/upload/v1785047657/"
    "WhatsApp_Image_2026-07-25_at_8.09.54_PM_xwcxpn.jpg"
)


@dataclass
class Caso:
    id: str
    descripcion: str
    # Cada turno es texto, o {"texto": ..., "imagenes": [url, ...]} cuando el
    # cliente manda fotos -- que en Instagram es tan comun como escribir.
    turnos: list
    aserciones: list[a.Asercion] = field(default_factory=list)
    # Cuando el agente agenda, la conversacion termino: los turnos que sigan
    # ya no aplican. Solo se apagaria para probar que hace despues de agendar.
    detener_al_agendar: bool = True


CASOS: list[Caso] = [
    Caso(
        id="precio_directo",
        descripcion="Pregunta el precio de entrada. Es el caso mas frecuente de la pauta.",
        turnos=["Hola, cuanto cuesta que me pongan plantas en el jardin?"],
        aserciones=[
            a.sin_errores(),
            a.sin_cifras(),
            a.ofrece_visita_gratis(),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="no_sabe_que_quiere",
        descripcion="Interes vago. Debe preguntar una cosa a la vez, no las tres juntas.",
        turnos=[
            "Hola! vi su pagina, me interesa",
            "Si, algo para la casa",
        ],
        aserciones=[
            a.sin_errores(),
            a.sin_cifras(),
            a.una_pregunta_por_turno(),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="tres_datos_de_golpe",
        descripcion="Da zona, espacio y disponibilidad en el primer mensaje: debe agendar ya.",
        turnos=[
            "Hola, soy Ana. Vivo en Coral Gables y quiero rediseniar el patio de mi casa. "
            f"Puedo el {_proximo(4)} por la maniana.",
        ],
        aserciones=[
            a.sin_errores(),
            a.agenda_en_turno(1),
            a.datos_cita_completos(),
            a.no_confirma_la_cita(),
            a.no_inventa_en_brief(),
            a.sin_cifras(),
        ],
    ),
    Caso(
        id="datos_de_a_poco",
        descripcion="Suelta los datos de a uno. No debe agendar hasta tener los tres.",
        turnos=[
            "Hola, quiero arreglar mi jardin",
            "Vivo en Doral",
            "Me llamo Carlos",
            f"El {_proximo(5)} en la tarde me viene bien",
        ],
        aserciones=[
            a.sin_errores(),
            a.no_agenda_antes_del_turno(4),
            a.agenda_al_final(),
            a.datos_cita_completos(),
            a.no_confirma_la_cita(),
            a.no_inventa_en_brief(),
            a.una_pregunta_por_turno(),
            a.sin_cifras(),
        ],
    ),
    Caso(
        id="pide_plantas_concretas",
        descripcion="Sabe que quiere y cuantas: eso tiene que llegar al brief del equipo.",
        turnos=[
            "Hola, quiero 3 palmas areca para la terraza de mi apartamento en Brickell. "
            f"Puedo el {_proximo(3)} en la tarde.",
        ],
        aserciones=[
            a.sin_errores(),
            a.agenda_en_turno(1),
            a.datos_cita_completos(),
            a.no_confirma_la_cita(),
            a.brief_registra("plantas_interes", r"areca"),
            a.brief_registra("cantidad", r"3|tres"),
            a.sin_cifras(),
        ],
    ),
    Caso(
        id="fuera_de_miami",
        descripcion="Esta fuera del area. No debe agendar ni inventar cobertura.",
        turnos=[
            "Hola, estoy en Orlando. Hacen jardines aca?",
            "Y si les pago el viaje?",
        ],
        aserciones=[
            a.sin_errores(),
            a.no_agenda_nunca(),
            a.no_inventa_cobertura("Orlando"),
            a.sin_cifras(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="reclamo",
        descripcion="Reclamo por un pedido. Fuera de alcance: derivar sin inventar.",
        turnos=[
            "Hice un pedido hace dos semanas y no me llega nada. Quiero una solucion.",
        ],
        aserciones=[
            a.sin_errores(),
            a.no_agenda_nunca(),
            a.deriva_al_equipo(),
            a.sin_cifras(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="ingles",
        descripcion="DM en ingles (4.8% de la pauta). Debe seguir siendo util.",
        turnos=[
            "Hi! Do you guys do garden design in Miami? How much would it be?",
        ],
        aserciones=[
            a.sin_errores(),
            a.sin_cifras(),
            a.responde_en("en"),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="emoji_solo",
        descripcion="Mensaje sin contenido util. No debe romperse ni alucinar una cita.",
        turnos=["🌿", "?"],
        aserciones=[
            a.sin_errores(),
            a.respuesta_no_vacia(),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),

    # ---- Casos sacados de conversaciones reales de @vivogardensmiami --------
    Caso(
        id="precio_de_una_planta",
        descripcion="Mensaje real: preguntan el precio de UNA planta. Hay rango y hay que darlo.",
        turnos=["¿Cuánto cuesta una planta?"],
        aserciones=[
            a.sin_errores(),
            a.da_rango_de_plantas(),       # inactiva mientras no haya lista de precios
            a.precio_con_modalidad(),
            a.cotiza_en_rango(),
            a.solo_precios_autorizados(),  # con RANGO_PLANTAS=None: cero cifras
            a.deriva_al_equipo(),          # no cotizar no puede ser dejarlo sin respuesta
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="insiste_precio_de_proyecto",
        descripcion="Presiona tres veces por el precio de un proyecto. La regla debe aguantar.",
        turnos=[
            "cuanto me sale ponerle grama artificial a todo el patio?",
            "dale, un aproximado nomas",
            "todos los viveros dan un rango, no me hagas perder el tiempo",
        ],
        aserciones=[
            a.sin_errores(),
            a.sin_cifras(),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="otro_estado",
        descripcion="Mensaje real desde South Carolina: fuera de cobertura y pidiendo asesoría.",
        turnos=[
            "Vivo en South Carolina que tipo de plantas puedo comprar el invierno aquí bajo los 40*",
        ],
        aserciones=[
            a.sin_errores(),
            a.no_agenda_nunca(),
            a.no_inventa_cobertura("South Carolina"),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="despedida_blanda",
        descripcion="Se despide sin agendar. Ahí se pierden más citas que en el precio.",
        turnos=[
            "Hola, estaba viendo sus plantas para el balcón",
            "Muchas gracias pronto me voy a comunicar con ustedes",
        ],
        aserciones=[
            a.sin_errores(),
            a.intenta_cerrar(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="no_es_cliente",
        descripcion="Agencia vendiendo servicios. No debe agendarle una visita de cotización.",
        turnos=[
            "Hola! Somos una agencia de marketing digital, manejamos redes de negocios "
            "como el suyo. ¿Con quién puedo hablar?",
        ],
        aserciones=[
            a.sin_errores(),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="planta_fuera_del_catalogo",
        descripcion="Pide una especie que no esta publicada. El vivero tiene mas de las que publica.",
        turnos=["Hola, tienen calatheas? busco una para la sala"],
        aserciones=[
            a.sin_errores(),
            a.no_niega_disponibilidad(),
            # Y que quede aprendido: si solo dice "el equipo confirma" y no
            # llama nada, el proximo cliente vuelve a empezar de cero.
            a.consulta_al_equipo("disponibilidad"),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="quiere_visitar_el_vivero",
        descripcion="Mensaje real: quiere ir A LA TIENDA, no que vayan a su casa.",
        turnos=["Quiero visitar el vivero"],
        aserciones=[
            a.sin_errores(),
            a.no_agenda_nunca(),          # agendar_visita es solo para domicilio
            a.horario_correcto(),
            a.contiene_alguno([r"11001", r"Biscayne"], "da_la_direccion"),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="post_compartido_precio",
        descripcion="LA conversación más común: comparte un post y pregunta el precio.",
        turnos=[
            {
                "texto": "¿Cuánto cuesta?",
                # Code y descripción reales del post que más tráfico genera.
                # La imagen no es la del CDN de Instagram (esas URLs van firmadas
                # y caducan): se usa una foto pública del propio negocio, estable.
                "post": {
                    "code": "Dct1TnwASqn",
                    "autor": "vivogardensmiami",
                    "caption": (
                        "🌿 Espacios que cobran vida con la planta perfecta. ✨ Estos son "
                        "algunos de los resultados que hemos creado para nuestros clientes. "
                        "En VivoGarden no solo eliges plantas: te asesoramos para encontrar "
                        "las ideales según tu espacio, estilo y ambiente."
                    ),
                    "imagen": (
                        "https://res.cloudinary.com/dxxvh5tlp/image/upload/v1785113242/"
                        "WhatsApp_Image_2026-07-26_at_7.44.23_PM_1_kghl5s.jpg"
                    ),
                },
            },
            "Un peace lily",
        ],
        aserciones=[
            a.sin_errores(),
            a.respuesta_no_vacia(),
            # El post es un carrusel de resultados, no una planta concreta:
            # lo correcto es preguntar cuál, no adivinar.
            a.pregunta_cual_planta(),
            # Ya con la planta elegida, el guion pide el tamaño antes del precio.
            a.pregunta_por_tamano(),
            a.precio_con_modalidad(),
            a.cotiza_en_rango(),
            a.solo_precios_autorizados(),
            a.no_agenda_nunca(),
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="venta_completa",
        descripcion="Flujo de producto de punta a punta: la venta tiene que llegarle al equipo.",
        turnos=[
            "¿Cuánto cuesta?",
            "Quiero un peace lily",
            "La grande, para la sala de mi casa en Kendall. Soy Rosa",
        ],
        aserciones=[
            a.sin_errores(),
            a.pregunta_cual_planta(),
            a.pregunta_por_tamano(),
            a.registra_pedido(),
            a.pedido_completo(),
            a.precio_con_modalidad(),
            a.cotiza_en_rango(),
            a.solo_precios_autorizados(),
            a.no_agenda_nunca(),      # es una venta, no una visita
            a.mensajes_cortos(),
        ],
    ),
    Caso(
        id="foto_del_patio",
        descripcion="Manda foto del patio, como 1 de cada 4 conversaciones reales.",
        turnos=[
            {"texto": "hola, quiero arreglar esto", "imagenes": [FOTO_PATIO]},
            "Estoy en Kendall, me sirve el sábado en la mañana. Soy Rosa.",
        ],
        aserciones=[
            a.sin_errores(),
            a.agenda_al_final(),
            a.datos_cita_completos(),
            a.no_confirma_la_cita(),
            a.describe_la_foto(r"c[ée]sped|grama|patio|jard[ií]n|piso|sol|planta|cerca|muro|tierra"),
            a.sugerencias_del_catalogo(),
            a.no_niega_disponibilidad(),
            a.sin_cifras(),
        ],
    ),
]


# --------------------------------------------------------------------------
# Barrido de aperturas
# --------------------------------------------------------------------------
# Un caso de un solo turno por cada boton configurado. Es barato (una llamada
# por apertura) y cubre el riesgo que los casos de arriba no ven: que cambiar
# el texto del boton en Ads Manager rompa el comportamiento sin tocar el codigo.

def _caso_de_apertura(ap: ap_mod.Apertura) -> Caso:
    # Invariantes que valen para CUALQUIER apertura: un boton no trae ninguno
    # de los tres datos, asi que agendar aqui seria inventarse la cita.
    aserciones = [
        a.sin_errores(),
        a.respuesta_no_vacia(),
        a.sin_cifras(),
        a.no_agenda_nunca(),
        a.mensajes_cortos(),
        a.una_pregunta_por_turno(),
    ]
    # Aserciones especificas del riesgo de cada boton, sacadas de como responde
    # el equipo en las conversaciones reales.
    if ap.id in ("cta_precio", "cta_precio_planta", "cta_precio_corto"):
        # El equipo NUNCA cotiza en abstracto: primero pregunta cual planta.
        aserciones.append(a.pregunta_cual_planta())
        aserciones.append(a.solo_precios_autorizados())
    if ap.id in ("cta_visitar_vivero", "organico_ubicacion"):
        aserciones.append(a.horario_correcto())
        aserciones.append(a.contiene_alguno([r"11001", r"Biscayne"], "da_la_direccion"))
    if ap.id == "cta_cita_domicilio":
        aserciones.append(a.horario_de_visitas_correcto())
    if ap.id in ("cta_elegir_plantas", "cta_que_tipos_plantas", "cta_que_plantas"):
        aserciones.append(a.no_niega_disponibilidad())
    if ap.id == "cta_ingles_generico":
        aserciones.append(a.responde_en("en"))

    return Caso(
        id=f"apertura:{ap.id}",
        descripcion=f"{ap.fuente} — {ap.riesgo}",
        turnos=[ap.texto],
        aserciones=aserciones,
    )


CASOS_APERTURA: list[Caso] = [_caso_de_apertura(ap) for ap in ap_mod.APERTURAS]

TODOS: list[Caso] = [*CASOS, *CASOS_APERTURA]
GRUPOS = {"base": CASOS, "aperturas": CASOS_APERTURA, "todos": TODOS}

POR_ID = {c.id: c for c in TODOS}
