# -*- coding: utf-8 -*-
"""El agente: mantiene la conversacion y decide cuando agendar.

Diseno
------
El agente NO responde en JSON. Conversa en texto natural y solo emite un
bloque `tool_use` cuando ya reunio los tres datos (zona, tipo de espacio,
disponibilidad). Quien orquesta bifurca por `stop_reason`, igual que hara el
nodo IF de n8n:

    stop_reason == "tool_use"  -> agendar y responder con mensaje_confirmacion
    stop_reason == "end_turn"  -> responder con el texto del modelo

Dos decisiones que parecen detalles y no lo son
-----------------------------------------------
1. `effort: "low"` en vez de cambiar de modelo. Triage de DMs es tarea simple;
   baja costo y latencia sin degradar el tool calling.
2. NO se desactiva el pensamiento extendido. Con el desactivado, el modelo a
   veces *escribe* la llamada a la herramienta en el texto visible en lugar de
   emitir el bloque `tool_use`, y eso falla en silencio: el usuario ve un
   mensaje raro y la cita nunca se crea.

El bloque `tool_use` se busca por tipo, nunca por coincidencia de texto sobre
el JSON serializado: el escapado varia entre modelos y versiones.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

import anthropic

from .inventario import Inventario
from .memoria_precios import MemoriaPrecios
from .prompt import HERRAMIENTAS, construir_system, normalizar

MODELO = os.environ.get("MODELO_AGENTE", "claude-sonnet-5")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "8000"))
ESFUERZO = os.environ.get("ESFUERZO", "low")


@dataclass
class Respuesta:
    """Lo que el orquestador necesita para actuar, sin volver a mirar la API."""

    texto: str                      # lo que se le envia al cliente por DM
    agendo: bool = False            # emitio tool_use de agendar_visita
    herramienta: str | None = None  # cual tool se uso, si se uso alguna
    datos_cita: dict | None = None  # input de agendar_visita
    datos_pedido: dict | None = None  # input de registrar_pedido
    consulta: dict | None = None    # input de consultar_al_equipo
    stop_reason: str | None = None
    uso: dict = field(default_factory=dict)


class AgenteVivoGardens:
    def __init__(self, cliente: anthropic.Anthropic | None = None,
                 modelo: str = MODELO,
                 al_agendar: Callable[[dict], Any] | None = None,
                 memoria: MemoriaPrecios | None = None,
                 inventario: Inventario | None = None):
        self.cliente = cliente or anthropic.Anthropic()
        self.modelo = modelo
        # Se inyecta para poder probar sin tocar Google Calendar.
        self.al_agendar = al_agendar
        # La memoria de precios entra por aqui para que las pruebas usen una
        # temporal en vez de ensuciar la del proyecto.
        self.memoria = memoria if memoria is not None else MemoriaPrecios()
        # Las plantas que el catalogo publicado no tiene. El vivero vende mas.
        self.inventario = inventario if inventario is not None else Inventario()

    def responder(self, historial: list[dict], sender_id: str = "") -> Respuesta:
        """Recibe el historial completo y devuelve el siguiente turno.

        `historial` son mensajes con la forma de la API: {"role", "content"}.
        `sender_id` identifica la conversacion: decide si un precio se dice
        exacto (el equipo lo confirmo aqui) o en rango (viene de la memoria).
        El estado vive fuera del agente a proposito: en produccion lo guarda
        n8n (Postgres o Data Table), no este proceso.
        """
        r = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=MAX_TOKENS,
            output_config={"effort": ESFUERZO},
            # Se construye por llamada: lleva la fecha de hoy, sin la cual el
            # modelo no puede convertir "el viernes" a la fecha ISO del schema.
            #
            # Va cacheado porque es lo que hace viable meter el catalogo entero
            # aqui en vez de montar recuperacion: el orden de render es
            # tools -> system -> messages, asi que este breakpoint cubre las dos
            # partes estables y solo cambia una vez al dia, cuando cambia la
            # fecha. Verificar con usage.cache_read_input_tokens: si sale 0 en
            # llamadas seguidas, algo esta invalidando el prefijo.
            system=[{
                "type": "text",
                "text": construir_system(memoria=self.memoria, sender_id=sender_id,
                                         inventario=self.inventario),
                "cache_control": {"type": "ephemeral"},
            }],
            tools=HERRAMIENTAS,
            messages=historial,
        )

        uso = {
            "input_tokens": getattr(r.usage, "input_tokens", 0),
            "output_tokens": getattr(r.usage, "output_tokens", 0),
            "cache_read_input_tokens": getattr(r.usage, "cache_read_input_tokens", 0),
            "cache_creation_input_tokens": getattr(r.usage, "cache_creation_input_tokens", 0),
        }

        # Se busca por tipo y se ramifica por NOMBRE. Hay mas de una herramienta,
        # y tomar la primera asumiendo cual es fue un bug real: el agente
        # respondia vacio cuando emitia la que no era.
        bloque_tool = next((b for b in r.content if b.type == "tool_use"), None)
        texto_libre = "".join(b.text for b in r.content if b.type == "text").strip()

        if bloque_tool is not None:
            # Sin `strict` la API ya no garantiza el objeto entero (ver prompt.py):
            # normalizar() repone los campos ausentes como vacios y sanea los enums.
            datos = normalizar(bloque_tool.name, bloque_tool.input)

            if bloque_tool.name == "agendar_visita":
                if self.al_agendar is not None:
                    self.al_agendar(datos)
                # El mensaje de confirmacion viaja dentro del schema del tool para
                # ahorrar el segundo viaje del flujo canonico. El precio de esa
                # decision: el modelo lo redacta sin saber si el calendario acepto,
                # asi que quien orqueste debe tener rama de error.
                return Respuesta(
                    texto=datos.get("mensaje_confirmacion", "") or texto_libre,
                    agendo=True,
                    herramienta=bloque_tool.name,
                    datos_cita=datos,
                    stop_reason=r.stop_reason,
                    uso=uso,
                )

            if bloque_tool.name == "registrar_pedido":
                # El flujo de producto: no hay cita que crear, hay una venta que
                # pasarle al equipo. Misma logica que agendar: el texto viaja
                # dentro del input para ahorrar el segundo viaje.
                return Respuesta(
                    texto=datos.get("mensaje_confirmacion", "") or texto_libre,
                    herramienta=bloque_tool.name,
                    datos_pedido=datos,
                    stop_reason=r.stop_reason,
                    uso=uso,
                )

            if bloque_tool.name == "consultar_al_equipo":
                # Lo que el agente no sabe queda anotado como trabajo para el
                # equipo, y se enruta segun QUE es lo que no sabe. Es la unica
                # forma de que el conocimiento crezca sin que el modelo invente
                # para tapar el hueco.
                tipo = datos.get("tipo", "otro")
                concepto = datos.get("concepto", "")
                referencia = datos.get("referencia", "")

                if tipo == "disponibilidad":
                    # Una planta que el catalogo publicado no tiene. Queda
                    # pendiente, y el contador de veces_pedida es demanda medida.
                    self.inventario.pedida(concepto, referencia=referencia)
                else:
                    self.memoria.anotar_faltante(
                        concepto=concepto,
                        modalidad=datos.get("modalidad", ""),
                        tamano=datos.get("tamano", ""),
                        contexto=f"[{tipo}] {datos.get('contexto', '')}",
                        referencia=referencia,
                        sender_id=sender_id,
                    )
                return Respuesta(
                    texto=datos.get("respuesta_al_cliente", "") or texto_libre,
                    herramienta=bloque_tool.name,
                    consulta=datos,
                    stop_reason=r.stop_reason,
                    uso=uso,
                )

        return Respuesta(texto=texto_libre, stop_reason=r.stop_reason, uso=uso)
