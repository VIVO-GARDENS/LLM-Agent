# -*- coding: utf-8 -*-
"""Servicio HTTP que envuelve al agente, para que n8n lo llame.

Reparto de responsabilidades (decidido el 2026-09-18)
-----------------------------------------------------
n8n orquesta y este servicio decide QUE responder. La division no es de gusto:
el system prompt se construye en Python **en cada llamada** -- lleva la fecha de
hoy, los precios aprendidos de ese cliente, el inventario y el contexto del post
que compartio. Un nodo HTTP Request de n8n con un body fijo no puede reproducir
eso, y si lo intentara, el banco de 41 casos dejaria de probar lo que corre en
produccion.

    n8n                                    este servicio
    ---------------------------------      --------------------------
    webhook de Instagram -> 200 en <2s
    deduplica por `mid`
    lee el historial de Postgres
    ------------------------------> POST /responder
                                           reconstruye la Conversacion
                                           llama al agente
                                           normaliza el input del tool
    <------------------------------ texto + brief + historial nuevo
    guarda el historial
    manda el DM por la Send API
    formatea el WhatsApp al equipo

⚠️ ESTE SERVICIO NO ES EL WEBHOOK DE INSTAGRAM. No lo conectes directo: una
llamada al modelo tarda segundos y el webhook de Instagram corta a los 10,
reenviando el evento. El 200 inmediato lo da n8n; aqui se responde con calma.

SIN ESTADO a proposito: el historial viaja en cada peticion y vuelve en la
respuesta. Asi el servicio se puede reiniciar, escalar o duplicar sin perder
conversaciones, y la unica fuente de verdad del historial es Postgres.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from agente.agente import MODELO, AgenteVivoGardens
from agente.conversacion import Conversacion, PostCompartido
from agente.entorno import cargar_env

cargar_env()

app = FastAPI(title="Agente Vivo Gardens", version="1.0")

# El agente se construye una vez y se reusa: MemoriaPrecios e Inventario leen
# de disco al instanciarse, y no hay razon para pagar eso en cada DM.
_agente: AgenteVivoGardens | None = None


def obtener_agente() -> AgenteVivoGardens:
    global _agente
    if _agente is None:
        _agente = AgenteVivoGardens(modelo=os.environ.get("MODELO_AGENTE", MODELO))
    return _agente


def usar_agente(a: AgenteVivoGardens | None) -> None:
    """Inyecta un agente. Existe para poder probar el endpoint sin gastar API."""
    global _agente
    _agente = a


class Post(BaseModel):
    code: str
    caption: str = ""
    imagen: str = ""
    autor: str = ""


class Peticion(BaseModel):
    sender_id: str
    # El historial tal como quedo en Postgres, con la forma de la API.
    mensajes: list[dict[str, Any]] = Field(default_factory=list)
    texto: str = ""
    imagenes: list[str] = Field(default_factory=list)
    post: Post | None = None


class Respuesta(BaseModel):
    texto: str
    agendo: bool
    herramienta: str | None
    datos_cita: dict | None
    datos_pedido: dict | None
    consulta: dict | None
    stop_reason: str | None
    uso: dict
    # Se devuelve para que n8n lo persista: el servicio no guarda nada.
    mensajes: list[dict[str, Any]]


def _verificar(token: str | None) -> None:
    """Secreto compartido con n8n. Sin esto el endpoint queda abierto."""
    esperado = os.environ.get("SERVICIO_TOKEN")
    if esperado and token != esperado:
        raise HTTPException(status_code=401, detail="token invalido")


@app.get("/salud")
def salud() -> dict:
    return {"ok": True, "modelo": os.environ.get("MODELO_AGENTE", MODELO)}


@app.post("/responder", response_model=Respuesta)
def responder(p: Peticion, x_token: str | None = Header(default=None)) -> Respuesta:
    _verificar(x_token)

    conv = Conversacion(sender_id=p.sender_id, mensajes=list(p.mensajes))
    conv.agregar_usuario(
        p.texto,
        p.imagenes or None,
        PostCompartido(**p.post.model_dump()) if p.post else None,
    )

    r = obtener_agente().responder(conv.mensajes, sender_id=p.sender_id)
    conv.agregar_asistente(r.texto)

    return Respuesta(
        texto=r.texto, agendo=r.agendo, herramienta=r.herramienta,
        datos_cita=r.datos_cita, datos_pedido=r.datos_pedido, consulta=r.consulta,
        stop_reason=r.stop_reason, uso=r.uso, mensajes=conv.mensajes,
    )
