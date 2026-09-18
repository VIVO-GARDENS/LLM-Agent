# -*- coding: utf-8 -*-
"""Reporte de una corrida: veredictos, tokens y costo.

El costo va en el reporte a proposito. El agente existe para rescatar ~$600/mes
de conversaciones que hoy nadie atiende; si atenderlas costara mas que eso, el
proyecto no tiene sentido. Que el numero se vea en cada corrida evita descubrir
el problema en la factura.
"""
from __future__ import annotations

import json

# USD por millon de tokens (tarifas de la API de Anthropic).
PRECIOS = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# ~613 mensajes de usuario al mes segun la pauta de agosto 2026.
MENSAJES_MES = 613


def costo(modelo: str, entrada: int, salida: int) -> float | None:
    if modelo not in PRECIOS:
        return None
    p_in, p_out = PRECIOS[modelo]
    return entrada / 1_000_000 * p_in + salida / 1_000_000 * p_out


def _linea(char: str = "-", n: int = 72) -> str:
    return char * n


def render(resultados, modelo: str) -> str:
    partes: list[str] = []
    partes.append(_linea("="))
    partes.append(f"EVALUACIONES — agente Vivo Gardens — modelo {modelo}")
    partes.append(_linea("="))

    for r in resultados:
        estado = "PASA " if r.paso else "FALLA"
        partes.append("")
        partes.append(f"[{estado}] {r.caso.id}  ({r.traza.tokens_entrada} in / "
                      f"{r.traza.tokens_salida} out, {r.segundos:.1f}s)")
        partes.append(f"         {r.caso.descripcion}")
        for nombre, ok, detalle in r.veredictos:
            marca = "  ok " if ok else "  X  "
            sufijo = f" — {detalle}" if detalle else ""
            partes.append(f"    {marca}{nombre}{sufijo}")
        if not r.paso:
            # Sin la transcripcion, un fallo no dice como arreglarlo.
            partes.append("    transcripcion:")
            for t in r.traza.turnos:
                partes.append(f"      usuario  > {t.usuario}")
                cuerpo = t.error or t.texto.replace("\n", " ")
                marca = "ERROR" if t.error else ("AGENDA" if t.agendo else "agente")
                partes.append(f"      {marca:<8} < {cuerpo}")

    entrada = sum(r.traza.tokens_entrada for r in resultados)
    salida = sum(r.traza.tokens_salida for r in resultados)
    pasaron = sum(1 for r in resultados if r.paso)
    c = costo(modelo, entrada, salida)

    partes.append("")
    partes.append(_linea("="))
    cacheados = sum(r.traza.tokens_cacheados for r in resultados)
    partes.append(f"{pasaron}/{len(resultados)} casos pasaron   |   "
                  f"{entrada} tokens de entrada, {salida} de salida")
    if cacheados:
        partes.append(f"cache: {cacheados} tokens leidos del prefijo cacheado")
    else:
        partes.append("cache: 0 tokens leidos — revisar que el prefijo no se este invalidando")
    if c is None:
        partes.append(f"costo: modelo {modelo!r} no esta en la tabla de precios")
    else:
        turnos = sum(len(r.traza.turnos) for r in resultados)
        por_turno = c / turnos if turnos else 0.0
        partes.append(f"costo de la corrida: ${c:.4f}   "
                      f"(${por_turno:.5f} por turno)")
        partes.append(f"proyeccion a {MENSAJES_MES} mensajes/mes: "
                      f"${por_turno * MENSAJES_MES:.2f}")
    partes.append(_linea("="))
    return "\n".join(partes)


def como_json(resultados, modelo: str) -> str:
    entrada = sum(r.traza.tokens_entrada for r in resultados)
    salida = sum(r.traza.tokens_salida for r in resultados)
    datos = {
        "modelo": modelo,
        "casos_totales": len(resultados),
        "casos_pasados": sum(1 for r in resultados if r.paso),
        "tokens_entrada": entrada,
        "tokens_salida": salida,
        "costo_usd": costo(modelo, entrada, salida),
        "casos": [
            {
                "id": r.caso.id,
                "descripcion": r.caso.descripcion,
                "paso": r.paso,
                "segundos": round(r.segundos, 2),
                "aserciones": [
                    {"nombre": n, "ok": ok, "detalle": d} for n, ok, d in r.veredictos
                ],
                "turnos": [
                    {
                        "numero": t.numero,
                        "usuario": t.usuario,
                        "agente": t.texto,
                        "agendo": t.agendo,
                        "datos_cita": t.datos_cita,
                        "error": t.error,
                        "uso": t.uso,
                    }
                    for t in r.traza.turnos
                ],
            }
            for r in resultados
        ],
    }
    return json.dumps(datos, ensure_ascii=False, indent=2)
