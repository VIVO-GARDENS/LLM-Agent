# -*- coding: utf-8 -*-
"""Pruebas de las aserciones y del corredor, SIN tocar la API.

Una asercion que no se prueba a si misma no vale nada: si `sin_cifras` tuviera
un regex roto, el banco entero daria verde y nadie se enteraria. Aqui se le dan
textos que deben pasar y textos que deben fallar.

Corre en frio, en menos de un segundo y sin gastar creditos:

    python -m evals.prueba_aserciones
"""
from __future__ import annotations

import sys

from . import aserciones as a
from .traza import Traza, Turno

_fallos: list[str] = []


def _check(condicion: bool, etiqueta: str) -> None:
    if condicion:
        print(f"  ok  {etiqueta}")
    else:
        print(f"  X   {etiqueta}")
        _fallos.append(etiqueta)


def _traza(*turnos: Turno, caso_id: str = "prueba") -> Traza:
    return Traza(caso_id=caso_id, turnos=list(turnos))


def _t(numero: int, texto: str, **kw) -> Turno:
    return Turno(numero=numero, usuario="(irrelevante)", texto=texto, **kw)


CITA_VALIDA = {
    "nombre_cliente": "Ana",
    "zona": "Coral Gables",
    "tipo_espacio": "patio",
    "detalle_espacio": "quiere rediseniar el patio trasero, le da sol toda la tarde",
    "plantas_interes": "",
    "cantidad": "",
    "plantas_sugeridas": "",
    "tamano": "",
    "fecha_sugerida": "2026-09-12",
    "franja_horaria": "manana",
    "intencion": "cotizacion",
    "mensaje_confirmacion": "Listo Ana, te vemos el viernes 12 por la maniana 🌿",
}


def probar_sin_cifras() -> None:
    print("sin_cifras")
    f = a.sin_cifras()
    debe_pasar = [
        "La visita es gratis, vamos a tu casa y ahi armamos la cotizacion.",
        "Estamos en 11001 Biscayne Blvd, Miami FL 33161.",
        "Te sirve el viernes 12 de septiembre a las 10 de la maniana?",
        "Tenemos 3 opciones de plantas para ese espacio.",
    ]
    debe_fallar = [
        "Depende, pero anda por los $250.",
        "Sale en 300 dolares aproximadamente.",
        "El precio es 400 mas instalacion.",
        "It costs about USD 500.",
        "Cuesta 200 la instalacion.",
        "Son mil dolares por el jardin completo.",
    ]
    for texto in debe_pasar:
        _check(f(_traza(_t(1, texto))).ok, f"pasa: {texto[:45]}")
    for texto in debe_fallar:
        _check(not f(_traza(_t(1, texto))).ok, f"detecta: {texto[:45]}")


def probar_momento_de_agendar() -> None:
    print("aserciones de agendamiento")
    temprano = _traza(_t(1, "ok", agendo=True, datos_cita=CITA_VALIDA), _t(2, "hola"))
    tarde = _traza(_t(1, "en que zona vives?"),
                   _t(2, "listo", agendo=True, datos_cita=CITA_VALIDA))
    nunca = _traza(_t(1, "en que zona vives?"))

    _check(not a.no_agenda_antes_del_turno(2)(temprano).ok, "detecta agendamiento prematuro")
    _check(a.no_agenda_antes_del_turno(2)(tarde).ok, "acepta agendar en el turno esperado")
    _check(a.no_agenda_antes_del_turno(2)(nunca).ok, "no exige que agende")
    _check(a.agenda_al_final()(tarde).ok, "agenda_al_final acepta el ultimo turno")
    _check(not a.agenda_al_final()(temprano).ok, "agenda_al_final rechaza turno intermedio")
    _check(a.no_agenda_nunca()(nunca).ok, "no_agenda_nunca acepta traza sin cita")
    _check(not a.no_agenda_nunca()(tarde).ok, "no_agenda_nunca rechaza traza con cita")
    _check(a.agenda_en_turno(2)(tarde).ok, "agenda_en_turno identifica el turno")


def probar_datos_cita() -> None:
    print("datos_cita_completos")
    f = a.datos_cita_completos()
    _check(f(_traza(_t(1, "ok", agendo=True, datos_cita=CITA_VALIDA))).ok, "acepta cita valida")

    sin_zona = dict(CITA_VALIDA, zona="")
    _check(not f(_traza(_t(1, "ok", agendo=True, datos_cita=sin_zona))).ok, "detecta campo vacio")

    enum_malo = dict(CITA_VALIDA, franja_horaria="noche")
    _check(not f(_traza(_t(1, "ok", agendo=True, datos_cita=enum_malo))).ok, "detecta enum invalido")

    fecha_mala = dict(CITA_VALIDA, fecha_sugerida="12 de septiembre")
    _check(not f(_traza(_t(1, "ok", agendo=True, datos_cita=fecha_mala))).ok, "detecta fecha no ISO")

    _check(not f(_traza(_t(1, "hola"))).ok, "detecta que nunca hubo tool_use")

    sin_brief = {k: v for k, v in CITA_VALIDA.items() if k != "plantas_interes"}
    _check(not f(_traza(_t(1, "ok", agendo=True, datos_cita=sin_brief))).ok,
           "detecta que falta un campo del brief")

    print()
    print("brief para el equipo")
    con_plantas = dict(CITA_VALIDA, plantas_interes="3 palmas areca", cantidad="3")
    r = a.brief_registra("plantas_interes", r"areca")
    _check(r(_traza(_t(1, "ok", agendo=True, datos_cita=con_plantas))).ok,
           "reconoce la planta registrada")
    _check(not r(_traza(_t(1, "ok", agendo=True, datos_cita=CITA_VALIDA))).ok,
           "detecta que el brief llego vacio")

    n = a.no_inventa_en_brief()
    _check(n(_traza(_t(1, "ok", agendo=True, datos_cita=CITA_VALIDA))).ok,
           "acepta brief vacio cuando el cliente no dijo nada")
    _check(not n(_traza(_t(1, "ok", agendo=True, datos_cita=con_plantas))).ok,
           "detecta planta inventada en el brief")


def probar_forma() -> None:
    print("forma del mensaje")
    largo = _traza(_t(1, "una\ndos\ntres\ncuatro"))
    corto = _traza(_t(1, "una\n\ndos"))
    _check(not a.mensajes_cortos(3)(largo).ok, "detecta mensaje de 4 lineas")
    _check(a.mensajes_cortos(3)(corto).ok, "ignora lineas en blanco")

    tres_juntas = _traza(_t(1, "En que zona vives? Que espacio es? Cuando puedes?"))
    una = _traza(_t(1, "Perfecto 🌿 En que zona de Miami vives?"))
    _check(not a.una_pregunta_por_turno()(tres_juntas).ok, "detecta tres preguntas juntas")
    _check(a.una_pregunta_por_turno()(una).ok, "acepta una sola pregunta")

    _check(not a.respuesta_no_vacia()(_traza(_t(1, "   "))).ok, "detecta respuesta vacia")
    _check(not a.sin_errores()(_traza(Turno(1, "hola", error="429"))).ok, "detecta error de API")


def probar_cobertura_y_derivacion() -> None:
    print("cobertura y derivacion")
    f = a.no_inventa_cobertura("Orlando")
    _check(f(_traza(_t(1, "Por ahora trabajamos en el area de Miami."))).ok,
           "acepta respuesta honesta")
    _check(not f(_traza(_t(1, "Si, atendemos Orlando sin problema."))).ok,
           "detecta cobertura inventada")
    _check(not f(_traza(_t(1, "Cubrimos toda la Florida."))).ok,
           "detecta 'toda la Florida'")

    d = a.deriva_al_equipo()
    _check(d(_traza(_t(1, "Un miembro del equipo te contacta hoy mismo."))).ok,
           "reconoce la derivacion")
    _check(not d(_traza(_t(1, "Que raro, deberia haber llegado ayer."))).ok,
           "detecta que no derivo")

    ng = a.no_dice_gratis()
    _check(not ng(_traza(_t(1, "La visita es gratis 🌿"))).ok, "atrapa la palabra prohibida")
    _check(not ng(_traza(_t(1, "The visit is free"))).ok, "tambien en ingles")
    _check(ng(_traza(_t(1, "La visita no tiene costo 🌿"))).ok, "deja pasar 'no tiene costo'")
    _check(ng(_traza(_t(1, "Vamos sin costo a tu casa"))).ok, "deja pasar 'sin costo'")
    g = a.ofrece_visita_gratis()
    _check(g(_traza(_t(1, "La visita es gratis 🌿"))).ok, "reconoce la visita gratis")
    _check(not g(_traza(_t(1, "Depende del espacio."))).ok, "detecta que no la ofrecio")


def probar_aperturas() -> None:
    """Las aperturas son configuracion externa: si el catalogo se desincroniza
    del anuncio, el banco prueba una conversacion que no ocurre."""
    print("aperturas")
    from . import aperturas as ap_mod
    from .casos import CASOS_APERTURA, POR_ID

    _check(len(CASOS_APERTURA) == len(ap_mod.APERTURAS),
           "hay un caso por cada apertura del catalogo")
    _check(all(len(c.turnos) == 1 for c in CASOS_APERTURA),
           "cada caso de apertura es de un solo turno")
    _check(all(a.no_agenda_nunca().nombre in [x.nombre for x in c.aserciones]
               for c in CASOS_APERTURA),
           "toda apertura exige que NO agende (un boton no trae los tres datos)")

    base = POR_ID["datos_de_a_poco"]
    variante = ap_mod.con_apertura(base, ap_mod.POR_ID["cta_precio"])
    _check(variante.turnos[0] == ap_mod.POR_ID["cta_precio"].texto,
           "con_apertura reemplaza el primer turno")
    _check(variante.turnos[1:] == base.turnos[1:], "con_apertura conserva el resto")
    _check(base.turnos[0] != ap_mod.POR_ID["cta_precio"].texto,
           "con_apertura no muta el caso original")
    _check(variante.id == "datos_de_a_poco@cta_precio", "la variante se identifica sola")

    h = a.horario_correcto()
    _check(h(_traza(_t(1, "Abrimos los 7 dias, de 10 AM a 7 PM 🌿"))).ok,
           "acepta el horario real")
    _check(h(_traza(_t(1, "We are open every day from 10 to 7."))).ok,
           "acepta el horario real en ingles")
    _check(not h(_traza(_t(1, "Atendemos de lunes a viernes de 9 a 6."))).ok,
           "detecta horario inventado")
    _check(not h(_traza(_t(1, "Abrimos a las 8 am."))).ok, "detecta hora de apertura falsa")
    _check(not h(_traza(_t(1, "Escribenos cuando quieras y coordinamos."))).ok,
           "detecta que esquivo la pregunta del horario")

    c = a.no_inventa_cobertura()
    _check(c(_traza(_t(1, "Trabajamos en el area de Miami. En que zona estas?"))).ok,
           "acepta cobertura honesta sin ciudad")
    _check(not c(_traza(_t(1, "Claro, vamos a cualquier parte."))).ok,
           "detecta promesa generica de cobertura")


def probar_catalogo_y_precios() -> None:
    print("catalogo y precios")
    sug = a.sugerencias_del_catalogo()
    buena = dict(CITA_VALIDA, plantas_sugeridas="Areca Palm, Snake Plant")
    mala = dict(CITA_VALIDA, plantas_sugeridas="Ficus lyrata y Calathea Orbifolia")
    _check(sug(_traza(_t(1, "ok", agendo=True, datos_cita=buena))).ok,
           "acepta sugerencias del catalogo")
    _check(not sug(_traza(_t(1, "ok", agendo=True, datos_cita=mala))).ok,
           "detecta planta fuera del catalogo")
    _check(sug(_traza(_t(1, "ok", agendo=True, datos_cita=CITA_VALIDA))).ok,
           "no sugerir nada es valido")

    aut = a.solo_precios_autorizados(80, 250)
    _check(aut(_traza(_t(1, "Las plantas van desde 80 hasta 250 dolares segun la especie."))).ok,
           "acepta el rango autorizado")
    _check(not aut(_traza(_t(1, "Te lo dejo en 400 dolares."))).ok,
           "detecta precio inventado")

    # Sin lista de precios confirmada (RANGO_PLANTAS=None) no se autoriza NADA.
    from agente.prompt import RANGO_PLANTAS
    cero = a.solo_precios_autorizados()
    if RANGO_PLANTAS is None:
        _check(not cero(_traza(_t(1, "Desde 80 hasta 350 dolares."))).ok,
               "sin lista confirmada, ninguna cifra pasa")
        _check(cero(_traza(_t(1, "Se cotiza segun el espacio; el equipo te pasa el exacto."))).ok,
               "sin lista confirmada, no cotizar es lo correcto")
    _check(aut(_traza(_t(1, "Abrimos todos los dias desde las 10 hasta las 7."))).ok,
           "no confunde un horario con un precio")

    if RANGO_PLANTAS is not None:
        rango = a.da_rango_de_plantas()
        _check(rango(_traza(_t(1, "Van desde 80 hasta 250 dolares."))).ok,
               "reconoce que dio el rango")
        _check(not rango(_traza(_t(1, "Depende de la especie, agendemos."))).ok,
               "detecta que esquivo la pregunta del precio")

    foto = a.describe_la_foto(r"patio|c[ée]sped|sol")
    detallada = dict(
        CITA_VALIDA,
        detalle_espacio="patio trasero de unos 30 metros con cesped seco y mucho sol de tarde",
    )
    pobre = dict(CITA_VALIDA, detalle_espacio="mando foto")
    _check(foto(_traza(_t(1, "ok", agendo=True, datos_cita=detallada))).ok,
           "acepta una descripcion real del espacio")
    _check(not foto(_traza(_t(1, "ok", agendo=True, datos_cita=pobre))).ok,
           "detecta que no describio la foto")

    disp = a.no_niega_disponibilidad()
    _check(disp(_traza(_t(1, "Dejame confirmarlo con el equipo y te digo 🌿"))).ok,
           "acepta 'lo confirmo con el equipo'")
    _check(not disp(_traza(_t(1, "No la tenemos, solo manejamos plantas de interior."))).ok,
           "detecta que nego disponibilidad")
    _check(not disp(_traza(_t(1, "Esa no esta en nuestro catalogo."))).ok,
           "detecta que trato el catalogo como inventario completo")

    cerrar = a.intenta_cerrar()
    _check(cerrar(_traza(_t(1, "Claro! Que dia te sirve para la visita?"))).ok,
           "reconoce el intento de cierre")
    _check(not cerrar(_traza(_t(1, "Perfecto, quedamos atentos."))).ok,
           "detecta que se dejo ir al cliente")


PEDIDO_VALIDO = {
    "nombre_cliente": "Rosa",
    "planta": "peace lily",
    "tamano": "grande",
    "cantidad": "1",
    "modalidad": "listo_en_casa",
    "zona": "Kendall",
    "post_referencia": "",
    "precio_dicho": "",
    "notas": "",
    "mensaje_confirmacion": "Listo Rosa, un peace lily grande. El equipo te confirma precio 🌿",
}


def probar_publicaciones_y_modalidad() -> None:
    print("publicaciones y modalidad del precio")
    from agente.publicaciones import buscar, contexto_para_prompt

    generico = buscar("Dav71afA4OK")
    concreto = buscar("DbtXPDnAMin")
    _check(generico is not None and generico.es_generica,
           "el post mas compartido no identifica planta")
    _check(concreto is not None and not concreto.es_generica,
           "el post de mango si identifica planta")
    _check("pregúntaselo" in contexto_para_prompt("Dav71afA4OK"),
           "ante un post generico le dice al modelo que pregunte")
    _check("mango" in contexto_para_prompt("DbtXPDnAMin"),
           "ante un post concreto le pasa la planta")
    _check(contexto_para_prompt("noExiste") == "",
           "un post desconocido no inventa contexto")

    m = a.precio_con_modalidad()
    _check(m(_traza(_t(1, "El limón sale 250 la planta sola 🌿"))).ok,
           "acepta cifra con modalidad")
    _check(m(_traza(_t(1, "Son 1200 listo en su casa, con maceta y tierra."))).ok,
           "acepta 'listo en su casa'")
    _check(not m(_traza(_t(1, "El limón cuesta 250."))).ok,
           "detecta cifra sin modalidad")
    _check(m(_traza(_t(1, "Depende del tamaño, ¿la quieres grande o pequeña?"))).ok,
           "sin cifras no exige modalidad")


def probar_ciclo_de_precio() -> None:
    """No sabe -> avisa al equipo con la imagen -> aprende -> cotiza en rango."""
    print("ciclo de aprendizaje del precio")
    from agente.memoria_precios import MemoriaPrecios
    from agente.precios import rango_para
    from datetime import date

    m = MemoriaPrecios(ruta=None)
    POST = "Dct1TnwASqn"

    _check(not m.por_referencia(POST), "al principio no sabe nada de esa imagen")
    f = m.anotar_faltante("peace lily grande", "listo_en_casa", "grande",
                          "compartió el post y preguntó el precio", referencia=POST)
    _check(f.referencia == POST, "el aviso al equipo lleva QUE mirar")

    p = m.proponer("peace lily grande", "listo_en_casa", 120, referencia=POST, fuente="equipo")
    _check(not m.por_referencia(POST), "una propuesta sin aprobar todavía no se usa")
    m.aprobar(p.clave)
    sabidos = m.por_referencia(POST)
    _check(len(sabidos) == 1, "tras aprobar, la imagen queda ligada a su precio")
    _check(sabidos[0].monto == 120, "guarda el monto exacto que dijo el equipo")
    _check(sabidos[0].rango == (110, 140), "pero lo que dice es el rango 110-140")
    _check(120 not in m.montos_autorizados, "la cifra exacta NO está autorizada a decirse")
    _check({110, 140} <= m.montos_autorizados, "los extremos del rango sí")

    _check(rango_para(1200) == (1100, 1400), "montos grandes se redondean a centenas")

    # Exacto solo donde un humano lo confirmo; en otra conversacion, rango.
    m2 = MemoriaPrecios(ruta=None)
    c = m2.confirmar("peace lily grande", "listo_en_casa", 120,
                     sender_id="ana", referencia=POST)
    _check(c.como_decirlo("ana") == "$120",
           "el equipo confirmó aquí: se dice exacto")
    _check(c.como_decirlo("luis") == "entre $110 y $140",
           "en otra conversación: rango, puede no ser la misma planta")
    _check(c.como_decirlo() == "entre $110 y $140", "sin conversación: rango")
    _check(120 in m2.montos_autorizados and 110 in m2.montos_autorizados,
           "quedan autorizados el exacto y los extremos")
    _check("$120" in m2.resumen_para_prompt("ana"), "el prompt de ana lleva el exacto")
    _check("$120" not in m2.resumen_para_prompt("luis"), "el de luis no")
    _check(rango_para(45)[0] < 45 < rango_para(45)[1], "el rango siempre envuelve al monto")

    from datetime import timedelta
    from agente.memoria_precios import VIGENCIA_DIAS
    viejo = m2.confirmar("areca", "sola", 200, sender_id="ana", referencia="Y")
    viejo.fecha = (date.today() - timedelta(days=VIGENCIA_DIAS + 2)).isoformat()
    _check(viejo.como_decirlo("ana").startswith("entre"),
           f"pasados {VIGENCIA_DIAS} días el exacto vuelve a ser rango")
    viejo.fecha = (date.today() - timedelta(days=VIGENCIA_DIAS - 1)).isoformat()
    _check(viejo.como_decirlo("ana") == "$200", "dentro del plazo sigue exacto")

    cita = a.no_confirma_la_cita()
    _check(cita(_traza(_t(1, "Listo, queda registrada y el equipo te confirma 🌿"))).ok,
           "acepta 'queda registrada, el equipo confirma'")
    _check(not cita(_traza(_t(1, "Perfecto, tu cita quedó confirmada para el sábado."))).ok,
           "detecta que dio la cita por confirmada")
    _check(not cita(_traza(_t(1, "Nos vemos el sábado 13 entonces!"))).ok,
           "detecta que prometió el día como hecho")

    r = a.cotiza_en_rango()
    _check(r(_traza(_t(1, "Ese va entre 110 y 140 dólares, solo la planta 🌿"))).ok,
           "acepta un rango")
    _check(not r(_traza(_t(1, "Ese cuesta 120 dólares."))).ok,
           "detecta la cifra sola")
    _check(r(_traza(_t(1, "Depende del tamaño, ¿grande o pequeña?"))).ok,
           "sin cifras no exige rango")


def probar_inventario_aprendido() -> None:
    """El vivero vende mas de lo publicado: una planta nueva tiene que aprenderse."""
    print("inventario aprendido")
    from agente.inventario import Inventario, NO_HAY, PREGUNTADO, SI_HAY

    inv = Inventario(ruta=None)
    _check(inv.buscar("calathea") is None, "al principio no conoce la calathea")

    p1 = inv.pedida("calathea orbifolia", referencia="Dct1TnwASqn")
    _check(p1.estado == PREGUNTADO, "queda como preguntada, no como inexistente")
    _check(p1.referencia == "Dct1TnwASqn", "guarda la imagen por la que preguntaron")
    _check("calathea" not in {n.lower() for n in inv.nombres_conocidos()},
           "preguntada no es lo mismo que confirmada: aún no se puede afirmar")

    inv.pedida("calathea orbifolia")
    _check(inv.pendientes()[0].veces_pedida == 2,
           "cuenta cuántas veces la piden: es demanda medida, no una duda del bot")

    inv.responder("calathea orbifolia", True, "llegan los jueves")
    _check(inv.buscar("calathea").estado == SI_HAY, "tras responder el equipo, ya lo sabe")
    _check(not inv.pendientes(), "y sale de la cola de pendientes")

    inv.responder("bonsai", False)
    _check(inv.buscar("bonsai").estado == NO_HAY, "también aprende lo que NO tienen")
    _check("bonsai" not in {n.lower() for n in inv.nombres_conocidos()},
           "lo descartado no se puede afirmar como disponible")

    resumen = inv.resumen_para_prompt()
    _check("calathea orbifolia" in resumen and "jueves" in resumen,
           "el prompt lleva lo confirmado con su nota")
    _check("bonsai" in resumen, "y lo descartado, para decirlo con tacto")
    _check(Inventario(ruta=None).resumen_para_prompt() == "",
           "un inventario vacío no añade ruido al prompt")

    c = a.consulta_al_equipo("disponibilidad")
    def tc(datos):
        return _traza(Turno(numero=1, usuario="u", texto="ok", consulta=datos))
    _check(c(tc({"tipo": "disponibilidad", "concepto": "calathea"})).ok,
           "reconoce la consulta de disponibilidad")
    _check(not c(tc({"tipo": "precio", "concepto": "calathea"})).ok,
           "detecta que consultó por el tipo equivocado")
    _check(not c(_traza(_t(1, "El equipo te confirma si la tenemos"))).ok,
           "decirlo sin llamar la herramienta no cuenta: el equipo no se entera")


def probar_pedido() -> None:
    print("pedido de producto")
    def tp(datos):
        return _traza(Turno(numero=1, usuario="u", texto="ok", datos_pedido=datos))

    f = a.pedido_completo()
    _check(f(tp(PEDIDO_VALIDO)).ok, "acepta un pedido bien armado")
    _check(not f(tp(dict(PEDIDO_VALIDO, tamano=""))).ok,
           "detecta pedido sin tamano (sin eso no se cotiza)")
    _check(not f(tp(dict(PEDIDO_VALIDO, planta=""))).ok, "detecta pedido sin planta")
    _check(f(tp(dict(PEDIDO_VALIDO, zona="", notas=""))).ok,
           "acepta campos opcionales vacios")
    _check(not f(tp(dict(PEDIDO_VALIDO, modalidad="regalo"))).ok,
           "detecta modalidad fuera del enum")
    _check(not f(_traza(_t(1, "hola"))).ok, "detecta que nunca hubo pedido")

    r = a.registra_pedido()
    _check(r(tp(PEDIDO_VALIDO)).ok, "reconoce que la venta se registro")
    _check(not r(_traza(_t(1, "claro, el peace lily grande es precioso"))).ok,
           "detecta que conversó la venta sin registrarla")


def probar_post_compartido() -> None:
    """Un post compartido no es una foto: significa 'quiero eso', no 'arregla esto'."""
    print("post compartido")
    from agente.conversacion import Conversacion, PostCompartido

    post = PostCompartido(
        code="Dct1TnwASqn", autor="vivogardensmiami",
        caption="Espacios que cobran vida con la planta perfecta. #VivoGarden #Miami",
        imagen="https://ejemplo/post.jpg",
    )
    c = Conversacion(sender_id="p")
    c.agregar_usuario("¿Cuánto cuesta?", post=post)
    bloques = c.mensajes[0]["content"]
    tipos = [b["type"] for b in bloques]
    texto = bloques[-1]["text"]

    _check(tipos == ["image", "text"], "arma bloque de imagen mas texto")
    _check(bloques[0]["source"]["type"] == "url", "la imagen viaja por URL")
    _check("Dct1TnwASqn" in texto, "el code del post llega al modelo")
    _check("compartió esta publicación" in texto, "se marca que es una publicacion, no una foto suya")
    _check("#VivoGarden" not in texto, "los hashtags no gastan tokens")
    _check(texto.endswith("¿Cuánto cuesta?"), "el texto del cliente va al final, sin mezclarse")

    # Una foto propia tiene que anotarse distinto: es su espacio, no un producto.
    c2 = Conversacion(sender_id="p2")
    c2.agregar_usuario("mira esto", imagenes=["https://ejemplo/patio.jpg"])
    t2 = c2.mensajes[0]["content"][-1]["text"]
    _check("su propio espacio" in t2, "una foto propia se anota distinto que un post")
    _check("publicación" not in t2, "no confunde foto propia con publicacion compartida")

    # Sin adjuntos el turno sigue siendo texto plano, como siempre.
    c3 = Conversacion(sender_id="p3")
    c3.agregar_usuario("hola")
    _check(c3.mensajes[0]["content"] == "hola", "sin adjuntos no cambia nada")

    tam = a.pregunta_por_tamano()
    _check(tam(_traza(_t(1, "Buenas, ¿la quiere grande o pequeña?"))).ok,
           "reconoce la pregunta de tamano")
    _check(not tam(_traza(_t(1, "Con gusto, ¿en qué zona vives?"))).ok,
           "detecta que no pregunto el tamano")


def probar_idioma() -> None:
    print("responde_en")
    ingles = _traza(_t(1, "Hi! We do garden design in Miami. The visit is free, "
                          "would you like to book one?"))
    espaniol = _traza(_t(1, "Hola! La visita es gratis, en que zona de Miami vives?"))
    _check(a.responde_en("en")(ingles).ok, "detecta ingles")
    _check(a.responde_en("es")(espaniol).ok, "detecta espaniol")
    _check(not a.responde_en("en")(espaniol).ok, "rechaza espaniol cuando pide ingles")


def probar_corredor_con_cliente_falso() -> None:
    """El corredor completo contra un cliente simulado: arma bien el historial,
    detecta el tool_use por tipo y corta el caso al agendar."""
    print("corredor (cliente simulado)")
    from .casos import Caso
    from .corredor import correr_caso
    from agente.agente import AgenteVivoGardens

    class _Bloque:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _Uso:
        input_tokens = 100
        output_tokens = 20

    class _Mensajes:
        def __init__(self):
            self.historiales = []

        def create(self, **kw):
            self.historiales.append(list(kw["messages"]))
            n = sum(1 for m in kw["messages"] if m["role"] == "user")
            if n < 2:
                return _Bloque(
                    content=[_Bloque(type="text", text="En que zona de Miami vives?")],
                    stop_reason="end_turn", usage=_Uso(),
                )
            return _Bloque(
                content=[_Bloque(type="tool_use", name="agendar_visita", input=CITA_VALIDA)],
                stop_reason="tool_use", usage=_Uso(),
            )

    class _Cliente:
        def __init__(self):
            self.messages = _Mensajes()

    cliente = _Cliente()
    caso = Caso(
        id="simulado",
        descripcion="prueba del corredor",
        turnos=["hola", "Coral Gables, el viernes 12 en la maniana", "sobra"],
        aserciones=[a.sin_errores(), a.agenda_en_turno(2), a.datos_cita_completos()],
    )
    r = correr_caso(caso, AgenteVivoGardens(cliente=cliente))

    _check(r.paso, "el caso simulado pasa sus aserciones")
    _check(len(r.traza.turnos) == 2, "corta al agendar y no consume el turno sobrante")
    _check(r.traza.turnos[1].texto == CITA_VALIDA["mensaje_confirmacion"],
           "usa mensaje_confirmacion como texto del turno")
    _check(r.traza.tokens_entrada == 200 and r.traza.tokens_salida == 40,
           "acumula el uso de tokens")
    # El historial de la segunda llamada debe traer el turno del asistente.
    segundo = cliente.messages.historiales[1]
    _check([m["role"] for m in segundo] == ["user", "assistant", "user"],
           "el historial alterna usuario/asistente")


def main() -> int:
    for prueba in (probar_sin_cifras, probar_momento_de_agendar, probar_datos_cita,
                   probar_forma, probar_cobertura_y_derivacion,
                   probar_catalogo_y_precios, probar_publicaciones_y_modalidad,
                   probar_ciclo_de_precio, probar_inventario_aprendido,
                   probar_pedido, probar_post_compartido,
                   probar_aperturas,
                   probar_idioma,
                   probar_corredor_con_cliente_falso):
        prueba()
        print()
    if _fallos:
        print(f"{len(_fallos)} comprobacion(es) fallaron:")
        for f in _fallos:
            print(f"  - {f}")
        return 1
    print("todas las comprobaciones pasaron")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
