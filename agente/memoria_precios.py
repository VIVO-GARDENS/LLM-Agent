# -*- coding: utf-8 -*-
"""Memoria de precios: lo que el agente sabe hoy y lo que aprendio ayer.

El problema que resuelve
------------------------
El catalogo de precios nunca va a estar completo. Entran especies nuevas, los
tamanos cambian, y nadie va a mantener una tabla a mano. Si el agente solo
puede cotizar lo que estaba escrito el dia que se programo, se queda mudo cada
vez que aparece algo nuevo -- que es justo el fallo que estamos arreglando.

El ciclo
--------
    1. El cliente pregunta por una planta cuyo precio no esta en la tabla.
    2. El agente NO inventa. Dice que el equipo le confirma el precio exacto,
       y llama `anotar_precio_faltante`. Eso deja una entrada en `pendientes`.
    3. El equipo responde el precio (por WhatsApp, o directamente en el DM).
    4. Ese precio entra como PROPUESTA, no como verdad.
    5. Alguien la aprueba y pasa a la tabla vigente.
    6. La proxima vez el agente ya lo sabe.

Por que las propuestas no entran solas
--------------------------------------
Los precios se dicen en contexto: "1200" puede ser el limon de 15 galones
listo en su casa, o el naranjo con maceta. Absorber cifras automaticamente
llenaria la tabla de numeros sin modalidad ni tamano, y el agente los repetiria
con confianza. Una cifra mal aprendida es peor que no saberla: la primera hace
que el cliente escuche un precio que nadie va a honrar.

El almacen es un JSON y no una base de datos a proposito: en produccion esto
vive en n8n (Postgres o Data Table), igual que el historial. Aqui se persiste a
disco para poder correr y auditar sin infraestructura.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date

from .precios import MODALIDADES, OBSERVACIONES

# Cuanto vale un precio confirmado por el equipo antes de volver a ser estimacion.
#
# Una semana. La razon no es tecnica: el vivero cambia de inventario, entran
# ejemplares distintos y las temporadas se mueven. Un precio de hace un mes
# repetido como exacto es una promesa que ya nadie recuerda haber hecho -- y el
# cliente que vuelve a un hilo viejo la leeria como vigente.
VIGENCIA_DIAS = 7

RUTA_POR_DEFECTO = os.path.join("memoria", "precios.json")


@dataclass
class Precio:
    concepto: str            # "limon", "areca de 15 galones", ...
    modalidad: str           # sola | listo_en_casa | recoge
    monto: int
    tamano: str = ""         # como se hablo con el cliente
    # El code del post o la URL de la foto por la que se pregunto. Es la clave
    # mas fiable que existe: la misma imagen es la misma planta, mientras que
    # "el arbolito ese" puede ser cualquier cosa.
    referencia: str = ""
    # Cuando se confirmo. Vencido el plazo el exacto vuelve a ser rango.
    fecha: str = ""
    # La conversacion para la que el equipo confirmo este precio.
    #
    # Es lo que decide si se dice exacto o en rango. Cuando el jefe mira la
    # planta y responde "120", ese 120 es autoridad PARA ESA CONSULTA: lo miro
    # un humano. En cualquier otra conversacion el mismo precio vuelve a ser una
    # estimacion, porque aunque la foto se parezca puede no ser la misma planta
    # -- otro ejemplar, otro tamano, otra temporada.
    sender_id: str = ""
    fuente: str = ""         # de donde salio: "dm_2026-09-02", "equipo", ...
    aprobado: bool = False
    visto: int = 1
    # Solo los conceptos que nombran una planta se le muestran al modelo como
    # cotizables. Los genericos ("planta mediana") le permitirian responder
    # "¿cuanto cuesta?" con un rango, que es justo lo que no debe hacer.
    cotizable: bool = False

    @property
    def clave(self) -> str:
        return f"{self.concepto.strip().lower()}|{self.modalidad}|{self.tamano.strip()}"

    @property
    def rango(self) -> tuple[int, int]:
        """El monto convertido a estimacion. Ver el porque en precios.py."""
        from .precios import rango_para
        return rango_para(self.monto)

    def vigente(self, hoy: date | None = None) -> bool:
        """¿Sigue dentro del plazo? Sin fecha se asume que no."""
        if not self.fecha:
            return False
        try:
            confirmado = date.fromisoformat(self.fecha)
        except ValueError:
            return False
        return ((hoy or date.today()) - confirmado).days <= VIGENCIA_DIAS

    def confirmado_para(self, sender_id: str, hoy: date | None = None) -> bool:
        """¿El equipo confirmo este precio para ESTA conversacion, y sigue vigente?"""
        return bool(sender_id) and self.sender_id == sender_id and self.vigente(hoy)

    def como_decirlo(self, sender_id: str = "") -> str:
        """Exacto si un humano lo confirmo aqui; rango si viene de la memoria."""
        if self.confirmado_para(sender_id):
            return f"${self.monto}"
        bajo, alto = self.rango
        return f"entre ${bajo} y ${alto}"


@dataclass
class Faltante:
    """Una pregunta que el agente no supo responder. Es trabajo para el equipo."""

    concepto: str
    modalidad: str = ""
    tamano: str = ""
    contexto: str = ""
    # Lo que el equipo tiene que MIRAR para poder responder: el post que
    # compartio el cliente o la foto que mando. Sin esto, el aviso de WhatsApp
    # dice "preguntan por un arbolito" y no se puede cotizar.
    referencia: str = ""
    sender_id: str = ""
    fecha: str = field(default_factory=lambda: date.today().isoformat())
    resuelto: bool = False


class MemoriaPrecios:
    def __init__(self, ruta: str | None = RUTA_POR_DEFECTO, sembrar: bool = True):
        self.ruta = ruta
        self.precios: dict[str, Precio] = {}
        self.pendientes: list[Faltante] = []
        if ruta and os.path.exists(ruta):
            self._cargar()
        elif sembrar:
            self._sembrar()

    # -- lectura ----------------------------------------------------------
    def _sembrar(self) -> None:
        """Arranca con las cotizaciones ya observadas en DMs reales."""
        for o in OBSERVACIONES:
            p = Precio(concepto=o.concepto, modalidad=o.modalidad, monto=o.monto,
                       fuente="dm_observado_2026-09", aprobado=True, visto=o.n,
                       cotizable=o.nombrada)
            self.precios[p.clave] = p

    def consultar(self, concepto: str, modalidad: str = "", tamano: str = "") -> list[Precio]:
        """Coincidencia laxa: el modelo escribe 'limon' y la tabla dice 'limon 15 gal'."""
        c = concepto.strip().lower()
        if not c:
            return []
        salida = []
        for p in self.precios.values():
            if not p.aprobado:
                continue
            if c not in p.concepto.lower() and p.concepto.lower() not in c:
                continue
            if modalidad and p.modalidad != modalidad:
                continue
            if tamano and p.tamano and p.tamano != tamano:
                continue
            salida.append(p)
        return sorted(salida, key=lambda p: p.monto)

    def sabe(self, concepto: str, modalidad: str = "") -> bool:
        return bool(self.consultar(concepto, modalidad))

    @property
    def montos_autorizados(self) -> set[int]:
        """Las cifras que el agente tiene permitido pronunciar.

        Son los extremos de los rangos, no los montos guardados: el precio
        exacto que dijo el equipo es justo lo que NO debe repetir.
        """
        salida: set[int] = set()
        for p in self.precios.values():
            if not p.aprobado:
                continue
            salida.update(p.rango)
            if p.sender_id and p.vigente():   # confirmado por un humano y fresco
                salida.add(p.monto)
        return salida

    # -- escritura --------------------------------------------------------
    def anotar_faltante(self, concepto: str, modalidad: str = "", tamano: str = "",
                        contexto: str = "", referencia: str = "",
                        sender_id: str = "") -> Faltante:
        """Registra que el agente no supo un precio. No es un error: es la senal."""
        existente = next(
            (f for f in self.pendientes
             if f.concepto.strip().lower() == concepto.strip().lower()
             and f.modalidad == modalidad and not f.resuelto),
            None,
        )
        if existente:
            return existente
        f = Faltante(concepto=concepto, modalidad=modalidad, tamano=tamano,
                     contexto=contexto, referencia=referencia, sender_id=sender_id)
        self.pendientes.append(f)
        self.guardar()
        return f

    def por_referencia(self, referencia: str) -> list[Precio]:
        """Lo que se sabe de ESA imagen o ESE post. La clave mas fiable."""
        ref = (referencia or "").strip()
        if not ref:
            return []
        return [p for p in self.precios.values() if p.aprobado and p.referencia == ref]

    def confirmar(self, concepto: str, modalidad: str, monto: int, sender_id: str,
                  tamano: str = "", referencia: str = "") -> Precio:
        """El equipo responde el precio de una consulta concreta.

        Entra APROBADO y atado a esa conversacion: ahi el agente puede decirlo
        exacto. Fuera de ella se lee como cualquier otro precio de la memoria,
        o sea en rango.
        """
        p = Precio(concepto=concepto, modalidad=modalidad, monto=monto, tamano=tamano,
                   fuente="equipo", aprobado=True, cotizable=True, referencia=referencia,
                   sender_id=sender_id, fecha=date.today().isoformat())
        self.precios[p.clave] = p
        for f in self.pendientes:
            if f.concepto.strip().lower() == concepto.strip().lower():
                f.resuelto = True
        self.guardar()
        return p

    def proponer(self, concepto: str, modalidad: str, monto: int,
                 tamano: str = "", fuente: str = "", referencia: str = "") -> Precio:
        """Un precio candidato. Entra SIN aprobar: ver el docstring del modulo."""
        p = Precio(concepto=concepto, modalidad=modalidad, monto=monto, tamano=tamano,
                   fuente=fuente, aprobado=False, cotizable=True, referencia=referencia)
        previo = self.precios.get(p.clave)
        if previo:
            previo.visto += 1
            if previo.monto != monto:
                previo.fuente += f" | discrepancia: tambien se vio {monto}"
            self.guardar()
            return previo
        self.precios[p.clave] = p
        self.guardar()
        return p

    def aprobar(self, clave: str) -> bool:
        p = self.precios.get(clave)
        if not p:
            return False
        p.aprobado = True
        for f in self.pendientes:
            if f.concepto.strip().lower() in p.concepto.lower():
                f.resuelto = True
        self.guardar()
        return True

    def sin_aprobar(self) -> list[Precio]:
        return [p for p in self.precios.values() if not p.aprobado]

    # -- persistencia -----------------------------------------------------
    def _cargar(self) -> None:
        with open(self.ruta, encoding="utf-8") as f:
            crudo = json.load(f)
        for d in crudo.get("precios", []):
            p = Precio(**d)
            self.precios[p.clave] = p
        self.pendientes = [Faltante(**d) for d in crudo.get("pendientes", [])]

    def guardar(self) -> None:
        if not self.ruta:
            return
        carpeta = os.path.dirname(self.ruta)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "precios": [asdict(p) for p in self.precios.values()],
                    "pendientes": [asdict(x) for x in self.pendientes],
                },
                f, ensure_ascii=False, indent=2,
            )

    # -- para el prompt ---------------------------------------------------
    def resumen_para_prompt(self, sender_id: str = "") -> str:
        aprobados = [p for p in self.precios.values() if p.aprobado]
        if not aprobados:
            return "Todavía no hay precios confirmados: no des ninguna cifra."
        cotizables = [p for p in aprobados if p.cotizable]
        lineas = [
            "El tamaño es lo que más mueve el precio, así que pregúntalo SIEMPRE antes de "
            "dar una cifra — y en los términos del cliente, no en los nuestros: "
            '"¿la quieres grande o pequeña?"',
            "Una cifra sin modalidad es engañosa: di siempre si es solo la planta o listo "
            "en su casa. El mismo limón vale 250 solo y 1200 instalado.",
        ]
        if cotizables:
            lineas.append(
                "Precios que conoces. Di EXACTAMENTE lo que aparece a la derecha, "
                "sin reformular la cifra:"
            )
            for p in sorted(cotizables, key=lambda p: p.monto):
                desc = MODALIDADES.get(p.modalidad, p.modalidad)
                ref = f" [publicación {p.referencia}]" if p.referencia else ""
                marca = " ← el equipo lo confirmó para esta conversación"                     if p.confirmado_para(sender_id) else ""
                lineas.append(
                    f"- {p.concepto}{ref} — {desc}: {p.como_decirlo(sender_id)}{marca}"
                )
            lineas.append(
                "Los que van como rango son de memoria: en su momento un humano los "
                "confirmó para OTRO cliente, y esta vez puede no ser la misma planta "
                "aunque la foto se parezca. Por eso van como estimación."
            )
        # El orden de magnitud va sin desglose por talla, y con la prohibicion
        # pegada: si se lista "planta mediana $250", el modelo responde
        # "¿cuanto cuesta?" con un rango, que es exactamente cotizar a ciegas.
        for clave in ("sola", "listo_en_casa"):
            # Los extremos de los rangos, no los montos crudos: si aquí fueran
            # los montos, el precio exacto que el equipo confirmó para UNA
            # conversación se filtraría al prompt de todas las demás.
            montos = sorted({
                extremo for p in aprobados if p.modalidad == clave for extremo in p.rango
            })
            if montos:
                lineas.append(
                    f"Orden de magnitud de {MODALIDADES[clave]}: entre ${montos[0]} y "
                    f"${montos[-1]}. Esto es para orientarte a ti, NO para responder "
                    '"¿cuánto cuesta?" con un rango: eso es cotizar a ciegas.'
                )
        lineas.append(
            "Si el cliente compartió una publicación o mandó una foto de la que ya "
            "conoces el precio, úsalo: la misma imagen es la misma planta."
        )
        lineas.append(
            "Si te preguntan por algo que NO está en esta lista: no inventes ni estimes. "
            "Di que el equipo le confirma el precio exacto y llama la herramienta "
            "anotar_precio_faltante. Todo precio que des es APROXIMADO y el equipo confirma."
        )
        return "\n".join(lineas)
