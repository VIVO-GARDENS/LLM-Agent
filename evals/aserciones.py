# -*- coding: utf-8 -*-
"""Aserciones programaticas sobre la traza de una conversacion.

Deliberadamente NO se usa un modelo juzgando a otro. Un juez LLM es caro, no es
reproducible y, para las reglas que importan aqui ("nunca dar una cifra", "no
agendar sin los tres datos"), es innecesario: son verificables con codigo.

Cada asercion es una funcion `Traza -> Resultado` con un atributo `nombre` para
el reporte. Las que dependen de palabras clave lo dicen en su docstring, porque
son las unicas fragiles ante un cambio de redaccion del prompt.
"""
from __future__ import annotations

import re
from typing import Callable

from .traza import Resultado, Traza

Asercion = Callable[[Traza], Resultado]


def _nombrar(fn: Asercion, nombre: str) -> Asercion:
    fn.nombre = nombre  # type: ignore[attr-defined]
    return fn


# --------------------------------------------------------------------------
# Precios
# --------------------------------------------------------------------------

# Cada alternativa exige un marcador de dinero (simbolo, palabra de moneda o
# verbo de precio). Por eso la direccion del vivero -- "11001 Biscayne Blvd,
# Miami FL 33161" -- y las fechas no disparan falsos positivos.

# Extrae el MONTO, no solo detecta que hay uno. La alternativa por verbo no
# admite "las" antes del numero, para que "abrimos desde las 10" no se lea como
# un precio de 10 dolares.
_MONTO = re.compile(
    r"""
      (?:[$€]|\bUS\$|\bUSD\b)\s*(\d[\d.,]*)
    | (\d[\d.,]*)\s*(?:d[oó]lares?|dlls?\.?|usd|bucks)
    | \b(?:cuesta|cuestan|vale|valen|sale\s+en|precio\s+(?:es|de)|cobra(?:mos)?|
        desde|hasta|entre|alrededor\s+de|aproximadamente)\s+
        (?:los\s+|unos?\s+)?(\d[\d.,]*)
    """,
    re.IGNORECASE | re.VERBOSE,
)


# "son mil dolares" es un precio igual que "$1000". Solo se listan las cifras
# que aparecen escritas en palabras en un contexto de dinero; el orden importa
# porque la alternancia del regex toma la primera que calce.
_PALABRAS_MONTO = {
    "doscientos cincuenta": 250, "ochenta": 80, "cien": 100, "ciento": 100,
    "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
    "quinientos": 500, "mil": 1000,
}
_MONTO_PALABRA = re.compile(
    r"\b(" + "|".join(k.replace(" ", r"\s+") for k in _PALABRAS_MONTO) + r")\s+"
    r"(?:d[oó]lares?|usd)\b",
    re.IGNORECASE,
)


def _montos(texto: str) -> list[int]:
    salida = []
    for grupos in _MONTO.findall(texto):
        crudo = next((g for g in grupos if g), "")
        try:
            salida.append(int(crudo.replace(".", "").replace(",", "")))
        except ValueError:
            pass
    for palabra in _MONTO_PALABRA.findall(texto):
        clave = re.sub(r"\s+", " ", palabra.strip().lower())
        if clave in _PALABRAS_MONTO:
            salida.append(_PALABRAS_MONTO[clave])
    return salida


def sin_cifras() -> Asercion:
    """Ninguna cifra de dinero. Para PROYECTOS: jardin, cesped, instalacion.

    Ojo con el alcance: el negocio SI cotiza plantas sueltas por DM (se vio en
    conversaciones reales). Esta asercion es para las preguntas de proyecto,
    donde el precio depende del espacio y solo sale de la visita. Para preguntas
    de planta, usar `solo_precios_autorizados`.
    """

    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            montos = _montos(t.texto)
            if montos:
                return Resultado(False, f"turno {t.numero}: cifra de dinero ({montos[0]})")
        return Resultado(True)

    return _nombrar(_f, "sin_cifras")


def solo_precios_autorizados(*permitidos: int) -> Asercion:
    """Si aparece una cifra, tiene que ser una de las autorizadas.

    Lo que autoriza el rango es que el equipo ya lo da por DM, no una decision
    nuestra. Cualquier otro numero es inventado, y un precio inventado en un DM
    es una promesa que alguien va a tener que sostener o desdecir.
    """
    from agente.precios import MONTOS_AUTORIZADOS
    validos = set(permitidos) or set(MONTOS_AUTORIZADOS)

    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            for monto in _montos(t.texto):
                if monto not in validos:
                    return Resultado(
                        False,
                        f"turno {t.numero}: {monto} no está en el rango autorizado "
                        f"{sorted(validos)}",
                    )
        return Resultado(True)

    return _nombrar(_f, f"solo_precios_autorizados{tuple(sorted(validos))}")


# Una cifra sin modalidad es una cifra enganosa. En las conversaciones reales
# el MISMO limon vale 250 "la sola planta" y 1200 "listo en su casa": si el
# agente dice 250 a secas, el cliente escucha 250 y le llega una cotizacion de
# 1200. Perder la venta seria lo de menos; lo caro es que parezca un engano.
_MODALIDAD_DICHA = [
    r"sola|solo\s+la\s+planta|solamente\s+la\s+planta",
    r"listo\s+en\s+(?:su|tu)\s+casa|instalad|con\s+(?:la\s+)?maceta|con\s+entrega|puesta",
    r"si\s+la\s+recoge|recogi[ée]ndola|en\s+la\s+tienda|pasas?\s+por",
    r"just\s+the\s+plant|delivered|installed",
]


def no_confirma_la_cita() -> Asercion:
    """El agente PROPONE la cita; el jefe la confirma. Nunca al reves.

    El agente no ve la agenda del equipo ni sabe si ese sabado hay camion libre.
    Si le dice al cliente "listo, quedamos el sabado" y despues nadie aparece,
    el dano es mayor que el de no haber contestado. Lo correcto es "queda
    registrada y el equipo te confirma". Verificacion por palabra clave.
    """
    return no_contiene(
        [
            r"(?:ya\s+)?(?:qued[óo]|est[áa])\s+confirmad",
            r"(?:tu|su)\s+cita\s+(?:est[áa]|qued[óo])\s+(?:lista|confirmada|agendada)",
            r"te\s+esperamos\s+el\s+\w+\s+\d",     # "te esperamos el sábado 13"
            r"nos\s+vemos\s+el\s+\w+\s+\d",
            r"confirmed|you'?re\s+all\s+set|see\s+you\s+on\s+\w+\s+\d",
        ],
        "no_confirma_la_cita",
    )


def cotiza_en_rango() -> Asercion:
    """Si da un precio, lo da como rango. Nunca una cifra sola.

    El equipo dice "120" para UNA planta concreta que ya vio. Si el agente
    repite "120", eso es una promesa: cuando el ejemplar resulte distinto,
    alguien tiene que honrarla o desdecirse delante del cliente. Un rango pone
    expectativa sin comprometer a nadie, que es lo que hace un vendedor humano
    que todavia no vio la planta.
    """

    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            montos = _montos(t.texto)
            if not montos:
                continue
            if len(montos) < 2:
                return Resultado(
                    False,
                    f"turno {t.numero}: dijo {montos[0]} como cifra sola, sin rango",
                )
        return Resultado(True)

    return _nombrar(_f, "cotiza_en_rango")


def precio_con_modalidad() -> Asercion:
    """Toda cifra tiene que ir acompanada de que incluye.

    Verificacion por palabra clave sobre el turno donde aparece el monto: no
    basta con que la modalidad se mencione en cualquier parte de la
    conversacion, tiene que estar pegada al numero.
    """
    marcas = [re.compile(p, re.IGNORECASE) for p in _MODALIDAD_DICHA]

    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            montos = _montos(t.texto)
            if not montos:
                continue
            if not any(c.search(t.texto) for c in marcas):
                return Resultado(
                    False,
                    f"turno {t.numero}: dijo {montos[0]} sin decir si es la planta sola "
                    f"o listo en su casa",
                )
        return Resultado(True)

    return _nombrar(_f, "precio_con_modalidad")


def da_rango_de_plantas() -> Asercion:
    """Ante "cuanto cuesta una planta" hay que responder, no esquivar.

    La conversacion real que motiva esto: el autorespondedor no contesto y la
    clienta repitio la pregunta textual. Esquivar cuesta la conversacion.
    """
    from agente.prompt import RANGO_PLANTAS

    def _f(traza: Traza) -> Resultado:
        if RANGO_PLANTAS is None:
            # Sin lista de precios confirmada el agente no debe cotizar nada,
            # asi que exigirle un rango seria exigirle que invente.
            return Resultado(True)
        minimo, maximo = RANGO_PLANTAS
        montos = set()
        for t in traza.turnos:
            montos.update(_montos(t.texto))
        if minimo in montos and maximo in montos:
            return Resultado(True)
        return Resultado(
            False,
            f"no dio el rango {minimo}-{maximo}; montos vistos: {sorted(montos) or 'ninguno'}",
        )

    return _nombrar(_f, "da_rango_de_plantas")


def sugerencias_del_catalogo() -> Asercion:
    """Toda planta sugerida tiene que existir en el catalogo del vivero.

    Es el guardarraíl de la capa de vision: un modelo suelto nombra especies de
    toda la botanica, y sugerir algo que no se vende hace que el cliente llegue
    a la visita esperando lo que no hay.
    """
    from agente.catalogo import es_del_catalogo
    from agente.inventario import Inventario

    conocidas = {n.lower() for n in Inventario().nombres_conocidos()}

    def _conocida(nombre: str) -> bool:
        n = nombre.strip().lower()
        return es_del_catalogo(n) or any(n in c or c in n for c in conocidas)

    def _f(traza: Traza) -> Resultado:
        datos = traza.datos_cita
        if datos is None:
            return Resultado(False, "nunca se emitio el tool_use")
        crudo = str(datos.get("plantas_sugeridas", "")).strip()
        if not crudo:
            return Resultado(True)          # no sugerir es una respuesta valida
        for nombre in re.split(r"[,;/]| y ", crudo):
            nombre = nombre.strip()
            if nombre and not _conocida(nombre):
                return Resultado(False, f"{nombre!r} no está en el catálogo ni aprendida")
        return Resultado(True)

    return _nombrar(_f, "sugerencias_del_catalogo")


def consulta_al_equipo(tipo: str = "") -> Asercion:
    """Lo que el agente no puede saber tiene que salir por la herramienta.

    Si se limita a decirle al cliente "el equipo te confirma" y no llama nada,
    el equipo nunca se entera: la conversacion se ve bien atendida y el trabajo
    no existe. Es la diferencia entre parecer util y serlo.
    """

    def _f(traza: Traza) -> Resultado:
        consultas = [t.consulta for t in traza.turnos if t.consulta]
        if not consultas:
            return Resultado(False, "no llamó consultar_al_equipo: el equipo no se entera")
        if tipo and not any(c.get("tipo") == tipo for c in consultas):
            vistos = [c.get("tipo") for c in consultas]
            return Resultado(False, f"esperaba tipo={tipo!r}, se vio {vistos}")
        return Resultado(True)

    return _nombrar(_f, f"consulta_al_equipo({tipo})" if tipo else "consulta_al_equipo")


def no_niega_disponibilidad() -> Asercion:
    """Nunca decir "no lo tenemos". El catalogo publicado esta incompleto.

    El vivero vende mas especies de las que publica en la web. Si el agente
    trata la lista como el inventario completo, le va a decir a un cliente que
    no venden algo que si venden -- que pierde la venta y ademas queda mal.
    La respuesta correcta ante algo que no esta en la lista es "lo confirmo con
    el equipo". Verificacion por palabra clave.
    """
    return no_contiene(
        [
            r"no\s+(?:la|lo|las|los)\s+(?:tenemos|manejamos|vendemos|trabajamos)",
            r"no\s+(?:tenemos|vendemos|manejamos)\s+(?:esa|ese|esas|esos)",
            r"no\s+(?:contamos|disponemos)\s+con",
            r"(?:no\s+(?:está|esta)\s+en\s+(?:nuestro|el)\s+cat[áa]logo)",
            r"(?:we\s+)?don'?t\s+(?:carry|sell|have)\s+(?:that|those|it)",
        ],
        "no_niega_disponibilidad",
    )


def describe_la_foto(*pistas: str) -> Asercion:
    """El brief tiene que reflejar que el modelo miró la foto, no solo recibirla.

    Si `detalle_espacio` no dice nada del espacio, la foto no sirvió de nada y
    el equipo va a cotizar a ciegas igual.
    """
    compilados = [re.compile(p, re.IGNORECASE) for p in pistas]

    def _f(traza: Traza) -> Resultado:
        datos = traza.datos_cita
        if datos is None:
            return Resultado(False, "nunca se emitio el tool_use")
        detalle = str(datos.get("detalle_espacio", ""))
        if len(detalle.split()) < 8:
            return Resultado(False, f"detalle_espacio demasiado pobre: {detalle!r}")
        if compilados and not any(c.search(detalle) for c in compilados):
            return Resultado(False, f"detalle_espacio no describe el espacio: {detalle!r}")
        return Resultado(True)

    return _nombrar(_f, "describe_la_foto")


# --------------------------------------------------------------------------
# Momento de agendar
# --------------------------------------------------------------------------

def no_agenda_antes_del_turno(n: int) -> Asercion:
    """No debe emitir tool_use antes del turno n, donde recien completa los 3 datos."""

    def _f(traza: Traza) -> Resultado:
        turno = traza.turno_agendo
        if turno is not None and turno < n:
            return Resultado(False, f"agendo en el turno {turno}, sin tener los tres datos")
        return Resultado(True)

    return _nombrar(_f, f"no_agenda_antes_del_turno({n})")


def agenda_en_turno(n: int) -> Asercion:
    def _f(traza: Traza) -> Resultado:
        turno = traza.turno_agendo
        if turno != n:
            return Resultado(False, f"esperaba agendar en el turno {n}, agendo en {turno}")
        return Resultado(True)

    return _nombrar(_f, f"agenda_en_turno({n})")


def agenda_al_final() -> Asercion:
    def _f(traza: Traza) -> Resultado:
        if not traza.turnos:
            return Resultado(False, "traza vacia")
        ultimo = traza.turnos[-1].numero
        if traza.turno_agendo != ultimo:
            return Resultado(False, f"no agendo en el ultimo turno ({ultimo})")
        return Resultado(True)

    return _nombrar(_f, "agenda_al_final")


def no_agenda_nunca() -> Asercion:
    def _f(traza: Traza) -> Resultado:
        if traza.turno_agendo is not None:
            return Resultado(False, f"agendo en el turno {traza.turno_agendo} y no debia")
        return Resultado(True)

    return _nombrar(_f, "no_agenda_nunca")


# --------------------------------------------------------------------------
# Contenido de la cita
# --------------------------------------------------------------------------

_CAMPOS = (
    "nombre_cliente", "zona", "tipo_espacio", "detalle_espacio",
    "fecha_sugerida", "franja_horaria", "intencion", "mensaje_confirmacion",
)
# Se registran vacios cuando el cliente no los menciono. Vacio es informacion:
# le dice al equipo que eso hay que preguntarlo en la visita.
_CAMPOS_OPCIONALES = ("plantas_interes", "cantidad", "tamano")
_ENUMS = {
    "tipo_espacio": {"jardin", "patio", "terraza", "interiores", "oficina", "otro"},
    "franja_horaria": {"manana", "tarde"},
    "intencion": {"cotizacion", "venta_directa"},
}
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def datos_cita_completos() -> Asercion:
    """Los 8 campos presentes, no vacios, enums validos y fecha ISO.

    Ya no hay `strict` -- la API rechaza las tres herramientas juntas -- asi que
    esta asercion, junto con normalizar(), es la unica garantia del contrato
    que consume el calendario.
    """

    def _f(traza: Traza) -> Resultado:
        datos = traza.datos_cita
        if datos is None:
            return Resultado(False, "nunca se emitio el tool_use")
        faltan = [c for c in _CAMPOS if not str(datos.get(c, "")).strip()]
        if faltan:
            return Resultado(False, f"campos vacios o ausentes: {', '.join(faltan)}")
        for campo, validos in _ENUMS.items():
            if datos[campo] not in validos:
                return Resultado(False, f"{campo}={datos[campo]!r} fuera del enum")
        if not _ISO.match(str(datos["fecha_sugerida"])):
            return Resultado(
                False, f"fecha_sugerida={datos['fecha_sugerida']!r} no es YYYY-MM-DD"
            )
        ausentes = [c for c in _CAMPOS_OPCIONALES if c not in datos]
        if ausentes:
            return Resultado(False, f"faltan campos del brief: {', '.join(ausentes)}")
        return Resultado(True)

    return _nombrar(_f, "datos_cita_completos")


def pedido_completo() -> Asercion:
    """El brief de una VENTA. Sin planta y sin tamano no se puede cotizar nada.

    Los demas campos pueden ir vacios -- vacio es informacion: le dice al equipo
    que preguntar. Pero planta y tamano son el minimo por el que existe el
    registro: si faltan, alguien tiene que rehacerle al cliente justo las dos
    preguntas que el agente ya le hizo.
    """
    _OBLIGA = ("nombre_cliente", "planta", "tamano", "mensaje_confirmacion")
    _PRESENTES = ("cantidad", "modalidad", "zona", "post_referencia",
                  "precio_dicho", "notas")
    _MODALIDADES = {"sola", "listo_en_casa", "recoge", "sin_especificar"}

    def _f(traza: Traza) -> Resultado:
        datos = next((t.datos_pedido for t in traza.turnos if t.datos_pedido), None)
        if datos is None:
            return Resultado(False, "nunca se emitio registrar_pedido")
        faltan = [c for c in _OBLIGA if not str(datos.get(c, "")).strip()]
        if faltan:
            return Resultado(False, f"campos vacios que no pueden estarlo: {', '.join(faltan)}")
        ausentes = [c for c in _PRESENTES if c not in datos]
        if ausentes:
            return Resultado(False, f"faltan campos del brief: {', '.join(ausentes)}")
        if datos["modalidad"] not in _MODALIDADES:
            return Resultado(False, f"modalidad={datos['modalidad']!r} fuera del enum")
        return Resultado(True)

    return _nombrar(_f, "pedido_completo")


def registra_pedido() -> Asercion:
    """La conversacion de producto tiene que terminar en un pedido registrado."""

    def _f(traza: Traza) -> Resultado:
        if any(t.datos_pedido for t in traza.turnos):
            return Resultado(True)
        return Resultado(False, "conversó la venta pero no la registró para el equipo")

    return _nombrar(_f, "registra_pedido")


def brief_registra(campo: str, patron: str) -> Asercion:
    """Un dato que el cliente SI dijo tiene que llegar al brief del equipo.

    Es lo que separa "el bot conversa" de "el bot deja trabajo hecho": si el
    cliente nombro la planta y el brief llega vacio, alguien tiene que volver a
    preguntarselo y la automatizacion no ahorro nada.
    """
    c = re.compile(patron, re.IGNORECASE)

    def _f(traza: Traza) -> Resultado:
        datos = traza.datos_cita
        if datos is None:
            return Resultado(False, "nunca se emitio el tool_use")
        valor = str(datos.get(campo, ""))
        if not c.search(valor):
            return Resultado(False, f"{campo}={valor!r} no recoge lo que dijo el cliente")
        return Resultado(True)

    return _nombrar(_f, f"brief_registra({campo})")


def no_inventa_en_brief(*campos: str) -> Asercion:
    """Si el cliente no lo dijo, el campo va vacio. Inventar es peor que omitir.

    El equipo cotiza leyendo el brief. Una planta inventada en `plantas_interes`
    manda al camion con la planta equivocada.
    """
    esperados = campos or _CAMPOS_OPCIONALES

    def _f(traza: Traza) -> Resultado:
        datos = traza.datos_cita
        if datos is None:
            return Resultado(False, "nunca se emitio el tool_use")
        for campo in esperados:
            valor = str(datos.get(campo, "")).strip()
            if valor:
                return Resultado(False, f"{campo}={valor!r} pero el cliente nunca lo dijo")
        return Resultado(True)

    return _nombrar(_f, f"no_inventa_en_brief({', '.join(esperados)})")


# --------------------------------------------------------------------------
# Forma del mensaje
# --------------------------------------------------------------------------

def mensajes_cortos(max_lineas: int = 3) -> Asercion:
    """Es un DM de Instagram, no un email. Un muro de texto pierde al cliente."""

    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            lineas = [x for x in t.texto.splitlines() if x.strip()]
            if len(lineas) > max_lineas:
                return Resultado(
                    False, f"turno {t.numero}: {len(lineas)} lineas (max {max_lineas})"
                )
        return Resultado(True)

    return _nombrar(_f, f"mensajes_cortos({max_lineas})")


def una_pregunta_por_turno() -> Asercion:
    """Pedir los tres datos de golpe es el patron que mata la conversacion."""

    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            if t.agendo:            # la confirmacion puede cerrar preguntando
                continue
            n = t.texto.count("?")
            if n > 1:
                return Resultado(False, f"turno {t.numero}: {n} preguntas en un mismo mensaje")
        return Resultado(True)

    return _nombrar(_f, "una_pregunta_por_turno")


def respuesta_no_vacia() -> Asercion:
    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            if not t.texto.strip():
                return Resultado(False, f"turno {t.numero}: respuesta vacia")
        return Resultado(True)

    return _nombrar(_f, "respuesta_no_vacia")


def sin_errores() -> Asercion:
    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            if t.error:
                return Resultado(False, f"turno {t.numero}: {t.error}")
        return Resultado(True)

    return _nombrar(_f, "sin_errores")


# --------------------------------------------------------------------------
# Palabras clave
# --------------------------------------------------------------------------
# Estas son las unicas aserciones fragiles: dependen de como redacte el modelo.
# Si se cambia el system prompt hay que revisarlas.

def contiene_alguno(patrones: list[str], nombre: str) -> Asercion:
    """Alguno de los patrones aparece en la conversacion."""
    compilados = [re.compile(p, re.IGNORECASE) for p in patrones]

    def _f(traza: Traza) -> Resultado:
        texto = traza.texto_completo
        if any(c.search(texto) for c in compilados):
            return Resultado(True)
        return Resultado(False, f"ningun patron de {nombre} aparece en la conversacion")

    return _nombrar(_f, nombre)


def no_contiene(patrones: list[str], nombre: str) -> Asercion:
    """Ningun patron aparece en ningun turno."""
    compilados = [re.compile(p, re.IGNORECASE) for p in patrones]

    def _f(traza: Traza) -> Resultado:
        for t in traza.turnos:
            for c in compilados:
                m = c.search(t.texto)
                if m:
                    return Resultado(False, f"turno {t.numero}: {m.group(0)!r}")
        return Resultado(True)

    return _nombrar(_f, nombre)


def ofrece_visita_gratis() -> Asercion:
    return contiene_alguno(
        [r"gratis", r"sin costo", r"sin cargo", r"no tiene costo", r"free"],
        "ofrece_visita_gratis",
    )


def intenta_cerrar() -> Asercion:
    """Ante una despedida blanda, el bot debe intentar UNA vez cerrar la cita.

    "Muchas gracias, pronto me comunico con ustedes" es como se pierde una cita
    de verdad: el cliente se va cordialmente y nadie lo retiene. Verificacion
    por palabra clave.
    """
    return contiene_alguno(
        [r"agend", r"visita", r"qu[ée]\s+d[ií]a", r"te\s+sirve", r"coordin",
         r"separ(?:o|amos)", r"book", r"schedule"],
        "intenta_cerrar",
    )


def deriva_al_equipo() -> Asercion:
    return contiene_alguno(
        [r"equipo", r"alguien\s+(?:del|de\s+nuestro)", r"te\s+contact",
         r"lo\s+contact", r"se\s+comunica", r"team", r"reach\s+out"],
        "deriva_al_equipo",
    )


def no_inventa_cobertura(ciudad: str | None = None) -> Asercion:
    """No debe afirmar cobertura que el system prompt no respalda.

    Sin `ciudad` verifica solo las promesas genericas ("toda la Florida"), que
    es lo util cuando la conversacion todavia no menciono una zona.
    """
    patrones = [
        r"(?:s[ií]|claro|por supuesto)[,!\s]+(?:s[ií]\s+)?"
        r"(?:atendemos|vamos|llegamos|trabajamos|cubrimos)",
        r"toda\s+(?:la\s+)?florida",
        r"todo\s+el\s+estado",
        r"cualquier\s+(?:ciudad|parte)",
    ]
    if ciudad:
        c = re.escape(ciudad)
        patrones.insert(
            1, rf"(?:atendemos|vamos a|llegamos a|cubrimos|trabajamos en)\s+(?:hasta\s+)?{c}"
        )
    sufijo = f"({ciudad})" if ciudad else "()"
    return no_contiene(patrones, f"no_inventa_cobertura{sufijo}")


# Horario publicado por el negocio, verbatim de vivogardens.com/faq (visto el
# 2026-09-02): "We are open 7 days a week, Sunday through Saturday, from
# 10:00 AM to 7:00 PM". Si el sitio cambia, esto cambia.
_HORARIO_BIEN = [
    r"\b10\b[^.\n]{0,40}\b7\b",                       # "de 10 a 7", "10 AM to 7 PM"
    r"\b(?:7\s*d[ií]as|todos\s+los\s+d[ií]as|7\s*days|every\s*day)\b",
]
_HORARIO_MAL = [
    r"\b(?:8|9|11)\s*(?::\d{2})?\s*(?:am|a\.\s?m\.)",    # apertura inventada
    r"\b(?:4|5|6|8|9|10)\s*(?::\d{2})?\s*(?:pm|p\.\s?m\.)",  # cierre inventado
    r"lunes\s+a\s+(?:viernes|s[áa]bado)",
    r"monday\s+(?:to|through)\s+(?:friday|saturday)",
    r"cerrado\s+(?:los\s+)?domingo",
    r"closed\s+on\s+sunday",
]


def pregunta_por_tamano() -> Asercion:
    """Con la planta ya elegida, el siguiente paso del guion es el tamano.

    Del guion real del equipo: "Buenas la quiere grande o pequena" -> "1 pie" /
    "3 pies". Sin tamano no hay precio, porque el mismo limon vale 250 solo y
    1200 listo en su casa segun el ejemplar. Verificacion por palabra clave.
    """
    return contiene_alguno(
        [r"grande\s+o\s+peque", r"peque[ñn]a\s+o\s+grande", r"qu[ée]\s+tama[ñn]o",
         r"tama[ñn]o", r"\bpies?\b", r"cu[áa]n\s+grande", r"how\s+(?:big|tall)", r"\bsize\b"],
        "pregunta_por_tamano",
    )


def pregunta_cual_planta() -> Asercion:
    """Ante un precio sin objeto, primero se pregunta que planta. Nunca se cotiza.

    No es una preferencia de estilo: es literalmente lo que el equipo responde
    en cada conversacion ("Cual planta le gusta", "Que te gusto?", "Cual arbol
    le gusta"). Cotizar en abstracto es inventar, porque el precio depende de la
    especie y del tamano. Verificacion por palabra clave.
    """
    return contiene_alguno(
        [r"cu[áa]l\s+(?:planta|árbol|arbol|te|le)", r"qu[ée]\s+planta",
         r"qu[ée]\s+te\s+gust", r"cu[áa]l\s+te\s+gust", r"en\s+qu[ée]\s+est[áa]s\s+pensando",
         r"which\s+plant", r"what\s+kind\s+of\s+plant"],
        "pregunta_cual_planta",
    )


# El horario de VISITAS a domicilio no es el de la tienda. Visto textual en un
# DM real: "Que dia le gustaria que fueramos de lunes a sabado de 11 a 5".
# Confundirlos manda a alguien a esperar un camion un domingo.
_VISITA_BIEN = [r"lunes.{0,25}s[áa]bado", r"(?<![0-9])11(?![0-9]).{0,20}(?<![0-9])5(?![0-9])"]
_VISITA_MAL = [r"los?\s+7\s+d[íi]as", r"todos\s+los\s+d[íi]as", r"domingo"]


def horario_de_visitas_correcto() -> Asercion:
    """Si habla del horario de la visita, tiene que ser lun-sab de 11 a 5."""
    bien = [re.compile(p, re.IGNORECASE) for p in _VISITA_BIEN]
    mal = [re.compile(p, re.IGNORECASE) for p in _VISITA_MAL]

    def _f(traza: Traza) -> Resultado:
        texto = traza.texto_completo
        for c in mal:
            m = c.search(texto)
            if m:
                return Resultado(False, f"horario de visita incorrecto: {m.group(0)!r}")
        if not any(c.search(texto) for c in bien):
            return Resultado(False, "no dio el horario de visitas (lun-sáb de 11 a 5)")
        return Resultado(True)

    return _nombrar(_f, "horario_de_visitas_correcto")


def horario_correcto() -> Asercion:
    """Si da el horario, tiene que ser EL horario. Ni inventado ni omitido.

    El icebreaker "cual es su horario?" es la alucinacion mas facil de provocar
    y la mas cara: manda gente al vivero un dia u hora en que esta cerrado.
    """
    bien = [re.compile(p, re.IGNORECASE) for p in _HORARIO_BIEN]
    mal = [re.compile(p, re.IGNORECASE) for p in _HORARIO_MAL]

    def _f(traza: Traza) -> Resultado:
        texto = traza.texto_completo
        for c in mal:
            m = c.search(texto)
            if m:
                return Resultado(False, f"horario incorrecto: {m.group(0)!r}")
        if not any(c.search(texto) for c in bien):
            return Resultado(False, "no dio el horario real (7 dias, 10 AM a 7 PM)")
        return Resultado(True)

    return _nombrar(_f, "horario_correcto")


# --------------------------------------------------------------------------
# Idioma
# --------------------------------------------------------------------------

_STOP_ES = {"de", "que", "el", "la", "los", "las", "en", "para", "con", "tu", "su",
            "un", "una", "es", "y", "por", "mas", "como", "cuando", "donde",
            "gracias", "hola", "visita", "gratis", "jardin", "quieres", "te"}
_STOP_EN = {"the", "you", "your", "we", "do", "is", "are", "for", "with", "and",
            "to", "of", "would", "can", "free", "visit", "what", "how", "our",
            "let", "know", "thanks", "hi", "garden"}
_PALABRA = re.compile(r"[^\W\d_]+", re.UNICODE)


def _idioma(texto: str) -> str:
    palabras = [p.lower() for p in _PALABRA.findall(texto)]
    es = sum(1 for p in palabras if p in _STOP_ES)
    en = sum(1 for p in palabras if p in _STOP_EN)
    if es == en:
        return "indeterminado"
    return "es" if es > en else "en"


def responde_en(idioma: str) -> Asercion:
    """Idioma por conteo de palabras funcionales: deterministico y sin llamadas extra."""

    def _f(traza: Traza) -> Resultado:
        detectado = _idioma(traza.texto_completo)
        if detectado != idioma:
            return Resultado(False, f"respondio en {detectado!r}, se esperaba {idioma!r}")
        return Resultado(True)

    return _nombrar(_f, f"responde_en({idioma})")
