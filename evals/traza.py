# -*- coding: utf-8 -*-
"""Estructuras que registran lo que hizo el agente durante un caso.

La traza es el unico insumo de las aserciones. Se separa del corredor para que
las aserciones se puedan probar en frio, sin API y sin gastar creditos
(ver `evals/prueba_aserciones.py`).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Resultado:
    """Veredicto de una asercion. `detalle` solo se llena cuando falla."""

    ok: bool
    detalle: str = ""


@dataclass
class Turno:
    """Un intercambio: lo que escribio el usuario y lo que hizo el agente."""

    numero: int                     # 1-indexado, como se cuenta en los casos
    usuario: str
    texto: str = ""                 # texto que se le enviaria al cliente
    agendo: bool = False
    datos_cita: dict | None = None
    datos_pedido: dict | None = None
    consulta: dict | None = None
    uso: dict = field(default_factory=dict)
    error: str | None = None        # excepcion de la API, si la hubo


@dataclass
class Traza:
    caso_id: str
    turnos: list[Turno] = field(default_factory=list)

    @property
    def textos(self) -> list[str]:
        return [t.texto for t in self.turnos]

    @property
    def texto_completo(self) -> str:
        return "\n".join(self.textos)

    @property
    def turno_agendo(self) -> int | None:
        """Numero del turno en que se emitio el tool_use, o None."""
        return next((t.numero for t in self.turnos if t.agendo), None)

    @property
    def datos_cita(self) -> dict | None:
        return next((t.datos_cita for t in self.turnos if t.agendo), None)

    @property
    def tokens_entrada(self) -> int:
        return sum(t.uso.get("input_tokens", 0) for t in self.turnos)

    @property
    def tokens_salida(self) -> int:
        return sum(t.uso.get("output_tokens", 0) for t in self.turnos)

    @property
    def tokens_cacheados(self) -> int:
        """Si esto sale 0 en una corrida completa, el cache no esta funcionando."""
        return sum(t.uso.get("cache_read_input_tokens", 0) for t in self.turnos)
