# -*- coding: utf-8 -*-
"""Estado de la conversacion y deduplicacion de mensajes.

En produccion esto lo hace n8n contra Postgres. Aqui vive en memoria y se
persiste a un JSON, para poder correr las pruebas sin base de datos y para que
la logica quede explicita y auditable.

La deduplicacion por `mid` no es opcional: Instagram reenvia el mismo evento
cuando el webhook no responde 200 a tiempo, y sin esto el cliente recibe la
misma respuesta dos o tres veces.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PostCompartido:
    """Una publicacion que el cliente comparte en el DM.

    Es la entrada mas frecuente del negocio: en 100 conversaciones leidas, la
    mayoria empieza compartiendo un post y preguntando el precio. Instagram
    entrega el `code` de la publicacion, su descripcion y su imagen, asi que
    identificar QUE planta quiere el cliente no es un problema de vision: es
    una busqueda por `code`. Ver `agente/publicaciones.py`.
    """

    code: str
    caption: str = ""
    imagen: str = ""        # url de la miniatura
    autor: str = ""         # normalmente vivogardensmiami

    def anotacion(self) -> str:
        """Lo que se le dice al modelo sobre esta imagen, entre corchetes."""
        from .publicaciones import contexto_para_prompt

        de_quien = f" de @{self.autor}" if self.autor else ""
        partes = [f"[el cliente compartió esta publicación{de_quien} · code {self.code}]"]
        if self.caption:
            # Los hashtags son ruido y ocupan tokens en cada llamada.
            limpio = self.caption.split("#")[0].strip()
            if limpio:
                partes.append(f'[descripción de la publicación: "{limpio[:400]}"]')
        # Si el post esta en la tabla, se le dice al modelo si identifica una
        # planta o no. Casi ninguno lo hace, y saberlo evita que suponga.
        extra = contexto_para_prompt(self.code)
        if extra:
            partes.append(extra)
        return "\n".join(partes)


@dataclass
class Conversacion:
    sender_id: str
    mensajes: list[dict] = field(default_factory=list)
    mids_vistos: set[str] = field(default_factory=set)
    cita: dict | None = None

    def ya_procesado(self, mid: str | None) -> bool:
        if mid is None:
            return False
        if mid in self.mids_vistos:
            return True
        self.mids_vistos.add(mid)
        return False

    def agregar_usuario(self, texto: str = "", imagenes: list[str] | None = None,
                        post: "PostCompartido | None" = None) -> None:
        """Un turno del cliente: texto, fotos suyas, o una publicacion compartida.

        Las tres cosas son distintas y el modelo tiene que poder distinguirlas:

            foto propia     "arregla ESTO"   -> es su espacio, hay que describirlo
            post compartido "quiero ESO"     -> es un producto nuestro, hay que
                                                identificarlo y cotizarlo

        Pasarle un post compartido como si fuera una foto cualquiera hace que
        describa el jardin de la foto promocional como si fuera el del cliente.
        Por eso el post va acompanado de una anotacion que dice que es, con su
        codigo y su descripcion: el cliente nos esta entregando el identificador
        exacto de lo que quiere, y desperdiciarlo seria adivinar sin necesidad.

        Las imagenes viajan por URL (`source.type == "url"`): la API las busca
        sola y asi no hay que descargar ni almacenar imagenes de clientes.
        """
        if not imagenes and post is None:
            self.mensajes.append({"role": "user", "content": texto})
            return

        bloques: list[dict] = []
        anotaciones: list[str] = []

        if post is not None:
            if post.imagen:
                bloques.append({"type": "image", "source": {"type": "url", "url": post.imagen}})
            anotaciones.append(post.anotacion())

        for u in imagenes or []:
            bloques.append({"type": "image", "source": {"type": "url", "url": u}})
        if imagenes:
            anotaciones.append(
                f"[el cliente envió {len(imagenes)} foto(s) de su propio espacio]"
            )

        # Un turno sin texto deja al modelo sin saber que se espera de el, y la
        # API necesita contenido textual acompanando. Las anotaciones van entre
        # corchetes para que se lean como metadato y no como voz del cliente.
        cuerpo = "\n".join(anotaciones)
        if texto:
            cuerpo = f"{cuerpo}\n{texto}" if cuerpo else texto
        bloques.append({"type": "text", "text": cuerpo})
        self.mensajes.append({"role": "user", "content": bloques})

    def agregar_asistente(self, texto: str) -> None:
        # Un turno vacio rompe la siguiente llamada: la API rechaza content "".
        if texto:
            self.mensajes.append({"role": "assistant", "content": texto})

    @property
    def turnos_usuario(self) -> int:
        return sum(1 for m in self.mensajes if m["role"] == "user")


class Memoria:
    """Coleccion de conversaciones, opcionalmente persistida en disco."""

    def __init__(self, ruta: str | None = None):
        self.ruta = ruta
        self._conv: dict[str, Conversacion] = {}
        if ruta and os.path.exists(ruta):
            self._cargar()

    def obtener(self, sender_id: str) -> Conversacion:
        if sender_id not in self._conv:
            self._conv[sender_id] = Conversacion(sender_id=sender_id)
        return self._conv[sender_id]

    def _cargar(self) -> None:
        with open(self.ruta, encoding="utf-8") as f:
            crudo = json.load(f)
        for sid, d in crudo.items():
            self._conv[sid] = Conversacion(
                sender_id=sid,
                mensajes=d.get("mensajes", []),
                mids_vistos=set(d.get("mids_vistos", [])),
                cita=d.get("cita"),
            )

    def guardar(self) -> None:
        if not self.ruta:
            return
        crudo = {
            sid: {
                "mensajes": c.mensajes,
                "mids_vistos": sorted(c.mids_vistos),
                "cita": c.cita,
            }
            for sid, c in self._conv.items()
        }
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=2)
