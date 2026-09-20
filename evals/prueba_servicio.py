# -*- coding: utf-8 -*-
"""Contrato del servicio HTTP, verificado en frio.

    python -m evals.prueba_servicio

Sin API y sin red: se inyecta un agente falso con `servicio.usar_agente()`. Lo
que se prueba no es el modelo, es el CONTRATO con n8n -- que es justo lo que se
rompe en silencio. El dia que alguien le agregue un campo a `Respuesta` o le
cambie el nombre a `mensajes`, n8n deja de persistir el historial y nadie se
entera hasta que un cliente recibe dos veces la misma respuesta.
"""
from __future__ import annotations

import os
import sys

os.environ["SERVICIO_TOKEN"] = "secreto-de-prueba"

import servicio
from agente.agente import Respuesta as RespuestaAgente

_fallos = 0


def _check(cond: bool, que: str) -> None:
    global _fallos
    print(f"  {'ok ' if cond else 'X  '} {que}")
    if not cond:
        _fallos += 1


class AgenteFalso:
    """Devuelve lo que se le diga y recuerda el historial que recibio."""

    def __init__(self, respuesta: RespuestaAgente) -> None:
        self.respuesta = respuesta
        self.visto: list | None = None

    def responder(self, historial, sender_id=""):
        # Instantanea, no referencia: el servicio sigue usando esa misma lista
        # despues de llamar (le agrega el turno del asistente). Guardando la
        # referencia se mediria el estado DESPUES de la mutacion, no lo que el
        # agente vio.
        self.visto = list(historial)
        self.sender_id = sender_id
        return self.respuesta


def _texto_de(bloques) -> str:
    if isinstance(bloques, str):
        return bloques
    return " ".join(b.get("text", "") for b in bloques if b.get("type") == "text")


def probar_turno_simple() -> None:
    print("turno de solo texto")
    falso = AgenteFalso(RespuestaAgente(texto="hola", stop_reason="end_turn",
                                        uso={"input_tokens": 1}))
    servicio.usar_agente(falso)
    r = servicio.responder(
        servicio.Peticion(sender_id="ana", texto="hola"), x_token="secreto-de-prueba")
    _check(r.texto == "hola", "devuelve el texto del agente")
    _check(len(r.mensajes) == 2, "devuelve el historial con el turno y la respuesta")
    _check(falso.sender_id == "ana", "el sender_id llega al agente (decide precio exacto o rango)")


def probar_post_compartido() -> None:
    print("post compartido")
    falso = AgenteFalso(RespuestaAgente(texto="ok", stop_reason="end_turn"))
    servicio.usar_agente(falso)
    servicio.responder(
        servicio.Peticion(sender_id="b", texto="¿Cuánto cuesta?",
                          post={"code": "ABC123", "caption": "Peace lily #miami",
                                "imagen": "http://x/y.jpg", "autor": "vivogardensmiami"}),
        x_token="secreto-de-prueba")
    bloques = falso.visto[0]["content"]
    texto = _texto_de(bloques)
    _check(any(b.get("type") == "image" for b in bloques), "la imagen del post viaja por URL")
    _check("ABC123" in texto, "el code llega al modelo: identificar es buscar, no adivinar")
    _check("compartió esta publicación" in texto, "se marca que es un post, no una foto suya")
    _check("#miami" not in texto, "los hashtags no gastan tokens")


def probar_fotos_propias() -> None:
    print("fotos del cliente")
    falso = AgenteFalso(RespuestaAgente(texto="ok", stop_reason="end_turn"))
    servicio.usar_agente(falso)
    servicio.responder(
        servicio.Peticion(sender_id="c", texto="arregla esto",
                          imagenes=["http://a/1.jpg", "http://a/2.jpg"]),
        x_token="secreto-de-prueba")
    texto = _texto_de(falso.visto[0]["content"])
    _check("2 foto" in texto, "se anota cuantas fotos mando")
    _check("compartió esta publicación" not in texto,
           "una foto propia NO se anota como post compartido")


def probar_ramas_de_herramienta() -> None:
    print("las tres salidas que n8n ramifica")
    for herramienta, campo, valor in (
        ("agendar_visita", "datos_cita", {"zona": "Brickell"}),
        ("registrar_pedido", "datos_pedido", {"planta": "peace lily"}),
        ("consultar_al_equipo", "consulta", {"tipo": "precio"}),
    ):
        falso = AgenteFalso(RespuestaAgente(
            texto="listo", herramienta=herramienta, stop_reason="tool_use",
            **{campo: valor}))
        servicio.usar_agente(falso)
        r = servicio.responder(servicio.Peticion(sender_id="d", texto="x"),
                               x_token="secreto-de-prueba")
        _check(r.herramienta == herramienta, f"{herramienta}: n8n puede ramificar")
        _check(getattr(r, campo) == valor, f"{herramienta}: el brief llega entero")


def probar_historial_ida_y_vuelta() -> None:
    print("sin estado: el historial va y vuelve")
    previo = [{"role": "user", "content": "hola"},
              {"role": "assistant", "content": "¡Hola! 🌿"}]
    falso = AgenteFalso(RespuestaAgente(texto="segunda", stop_reason="end_turn"))
    servicio.usar_agente(falso)
    r = servicio.responder(
        servicio.Peticion(sender_id="e", mensajes=previo, texto="otra cosa"),
        x_token="secreto-de-prueba")
    _check(len(falso.visto) == 3, "el agente ve el historial completo que mando n8n")
    _check(len(r.mensajes) == 4, "vuelve con el turno nuevo para que n8n lo persista")
    _check(previo == [{"role": "user", "content": "hola"},
                      {"role": "assistant", "content": "¡Hola! 🌿"}],
           "no muta el historial que recibio")


def probar_token() -> None:
    print("el endpoint no queda abierto")
    servicio.usar_agente(AgenteFalso(RespuestaAgente(texto="x")))
    try:
        servicio.responder(servicio.Peticion(sender_id="f", texto="x"), x_token="malo")
        _check(False, "un token invalido debe rechazarse")
    except Exception as e:
        _check(getattr(e, "status_code", None) == 401, "token invalido -> 401")


def main() -> int:
    for f in (probar_turno_simple, probar_post_compartido, probar_fotos_propias,
              probar_ramas_de_herramienta, probar_historial_ida_y_vuelta, probar_token):
        f()
    servicio.usar_agente(None)
    print()
    if _fallos:
        print(f"{_fallos} comprobacion(es) fallaron")
        return 1
    print("todas las comprobaciones pasaron")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
