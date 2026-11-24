"""Historial de versiones de una escena: notas, horas, miniaturas. No depende de Maya.

Todo lo que el alumno no necesita ver va en una carpeta oculta junto a las versiones::

    scenes/robot/
        robot_v001.ma
        robot_v002.ma
        .simplesave/robot/
            historial.json
            miniaturas/v001.jpg
            autoguardado/robot_auto_20261124_194200.ma
        archivo/                 (versiones apartadas con «Limpiar»)
"""

import datetime
import os

from simplesave import nombres
from simplesave.config import _leer_json, escribir_json

OCULTA = ".simplesave"
ARCHIVO = "archivo"


def ahora_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def fecha_de(iso):
    try:
        return datetime.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


class Version(object):
    __slots__ = ("numero", "ruta", "nota", "fecha", "bytes", "importante", "origen", "objetos", "caras",
                 "miniatura", "archivada")

    def __init__(self, numero, ruta, datos=None, miniatura="", archivada=False):
        datos = datos or {}
        self.numero = numero
        self.ruta = ruta
        self.nota = datos.get("nota", "") or ""
        self.fecha = datos.get("fecha") or ""
        if not self.fecha and os.path.isfile(ruta):
            self.fecha = datetime.datetime.fromtimestamp(os.path.getmtime(ruta)).replace(microsecond=0).isoformat()
        try:
            self.bytes = os.path.getsize(ruta)
        except OSError:
            self.bytes = int(datos.get("bytes") or 0)
        self.importante = bool(datos.get("importante"))
        self.origen = datos.get("origen")
        self.objetos = datos.get("objetos")
        self.caras = datos.get("caras")
        self.miniatura = miniatura if miniatura and os.path.isfile(miniatura) else ""
        self.archivada = archivada

    @property
    def etiqueta(self):
        return nombres.etiqueta(self.numero)

    @property
    def archivo(self):
        return os.path.basename(self.ruta)

    def __repr__(self):  # pragma: no cover
        return "<Version {} {}>".format(self.etiqueta, self.ruta)


class Historial(object):
    """Versiones de ``base`` dentro de ``carpeta``."""

    def __init__(self, carpeta, base):
        self.carpeta = carpeta
        self.base = base
        self.oculta = os.path.join(carpeta, OCULTA, base)
        self.ruta = os.path.join(self.oculta, "historial.json")
        self.recargar()

    def recargar(self):
        """Vuelve a leer el json (otra acción o el autoguardado pudo cambiarlo)."""
        self.datos = _leer_json(self.ruta)
        if not isinstance(self.datos.get("versiones"), dict):
            self.datos["versiones"] = {}

    # --- carpetas ------------------------------------------------------------------------
    @property
    def carpeta_miniaturas(self):
        return os.path.join(self.oculta, "miniaturas")

    @property
    def carpeta_autoguardado(self):
        return os.path.join(self.oculta, "autoguardado")

    @property
    def carpeta_archivo(self):
        return os.path.join(self.carpeta, ARCHIVO)

    def ruta_miniatura(self, numero):
        return os.path.join(self.carpeta_miniaturas, nombres.etiqueta(numero) + ".jpg")

    # --- lectura ------------------------------------------------------------------------
    def _datos(self, numero):
        return self.datos["versiones"].get(str(numero), {})

    def versiones(self, incluir_archivadas=False):
        """Versiones que existen en disco, de la más antigua a la más nueva."""
        self.recargar()
        lista = []
        for numero, ruta in nombres.versiones_en(self.carpeta, self.base).items():
            lista.append(Version(numero, ruta, self._datos(numero), self.ruta_miniatura(numero)))
        if incluir_archivadas:
            presentes = {v.numero for v in lista}
            for numero, ruta in nombres.versiones_en(self.carpeta_archivo, self.base).items():
                if numero not in presentes:
                    lista.append(Version(numero, ruta, self._datos(numero), self.ruta_miniatura(numero), True))
        lista.sort(key=lambda v: v.numero)
        return lista

    def version(self, numero):
        for v in self.versiones(incluir_archivadas=True):
            if v.numero == numero:
                return v
        return None

    def ultima(self):
        lista = self.versiones()
        return lista[-1] if lista else None

    def siguiente(self):
        numero = nombres.siguiente(self.carpeta, self.base)
        archivadas = nombres.versiones_en(self.carpeta_archivo, self.base)
        if archivadas:
            numero = max(numero, max(archivadas) + 1)
        return numero

    # --- escritura ----------------------------------------------------------------------
    def anotar(self, numero, **campos):
        self.recargar()
        entrada = dict(self._datos(numero))
        entrada.update({k: v for k, v in campos.items() if v is not None or k in ("origen",)})
        entrada.setdefault("fecha", ahora_iso())
        self.datos["versiones"][str(numero)] = entrada
        self.guardar()
        return entrada

    def guardar(self):
        try:
            escribir_json(self.ruta, self.datos)
        except OSError:
            pass
