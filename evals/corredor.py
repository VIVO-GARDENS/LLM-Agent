# -*- coding: utf-8 -*-
"""Corredor: ejecuta cada caso contra el agente y evalua sus aserciones.

Reconstruye el historial igual que lo hara n8n en produccion: turno de usuario,
turno de asistente, y asi. Cuando el agente emite el tool_use, lo que se guarda
como turno del asistente es `mensaje_confirmacion` -- que es exactamente lo que
el cliente vera por DM, porque ese texto viaja dentro del input del tool.

Los errores de la API no abortan la corrida: se anotan en el turno y la asercion
`sin_errores` los reporta. Un caso que falla por rate limit tiene que verse
distinto de un caso que falla por comportamiento.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import anthropic

from agente.agente import MODELO, AgenteVivoGardens
from agente.conversacion import Conversacion, PostCompartido

from .casos import TODOS, Caso
from .traza import Traza, Turno


@dataclass
class ResultadoCaso:
    caso: Caso
    traza: Traza
    veredictos: list[tuple[str, bool, str]] = field(default_factory=list)
    segundos: float = 0.0

    @property
    def paso(self) -> bool:
        return all(ok for _, ok, _ in self.veredictos)


def _describir_error(e: Exception) -> str:
    """Mensaje corto y accionable. Distingue lo reintentable de lo que no."""
    if isinstance(e, anthropic.AuthenticationError):
        return "credenciales invalidas (revisa ANTHROPIC_API_KEY)"
    if isinstance(e, anthropic.RateLimitError):
        return "rate limit (429): reintentable, no es un fallo del agente"
    if isinstance(e, anthropic.BadRequestError):
        return f"peticion invalida (400): {e.message}"
    if isinstance(e, anthropic.APIStatusError):
        clase = "servidor" if e.status_code >= 500 else "API"
        return f"error de {clase} ({e.status_code}): {e.message}"
    if isinstance(e, anthropic.APIConnectionError):
        return "sin conexion con la API"
    return f"{type(e).__name__}: {e}"


def correr_caso(caso: Caso, agente: AgenteVivoGardens) -> ResultadoCaso:
    conv = Conversacion(sender_id=f"eval:{caso.id}")
    traza = Traza(caso_id=caso.id)
    inicio = time.perf_counter()

    for numero, mensaje in enumerate(caso.turnos, start=1):
        # Un turno puede traer fotos: en Instagram la imagen del patio llega
        # tanto como el texto, y a veces en vez del texto.
        post = None
        if isinstance(mensaje, dict):
            texto, imagenes = mensaje.get("texto", ""), mensaje.get("imagenes")
            if mensaje.get("post"):
                post = PostCompartido(**mensaje["post"])
        else:
            texto, imagenes = mensaje, None
        conv.agregar_usuario(texto, imagenes, post)
        etiqueta = texto + (f"  [+{len(imagenes)} foto]" if imagenes else "")
        etiqueta += f"  [+post {post.code}]" if post else ""
        turno = Turno(numero=numero, usuario=etiqueta)
        try:
            r = agente.responder(conv.mensajes, sender_id=conv.sender_id)
        except Exception as e:  # se anota y se corta el caso, no la corrida
            turno.error = _describir_error(e)
            traza.turnos.append(turno)
            break

        turno.texto = r.texto
        turno.agendo = r.agendo
        turno.datos_cita = r.datos_cita
        turno.datos_pedido = r.datos_pedido
        turno.consulta = r.consulta
        turno.uso = r.uso
        traza.turnos.append(turno)

        conv.agregar_asistente(r.texto)
        if r.agendo and caso.detener_al_agendar:
            break

    resultado = ResultadoCaso(caso=caso, traza=traza)
    resultado.segundos = time.perf_counter() - inicio
    for asercion in caso.aserciones:
        v = asercion(traza)
        nombre = getattr(asercion, "nombre", asercion.__name__)
        resultado.veredictos.append((nombre, v.ok, v.detalle))
    return resultado


def correr(casos: list[Caso] | None = None,
           modelo: str = MODELO,
           cliente: anthropic.Anthropic | None = None) -> list[ResultadoCaso]:
    agente = AgenteVivoGardens(cliente=cliente, modelo=modelo)
    return [correr_caso(c, agente) for c in (casos or TODOS)]
