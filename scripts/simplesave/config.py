"""Ajustes del alumno y plantilla del profesor. No depende de Maya.

* Los ajustes del alumno se guardan en ``<preferencias de Maya>/simplesave/ajustes.json``.
* El profesor puede dejar un ``simplesave.json`` en la carpeta del proyecto de
  Maya. Lo que ponga ahí manda sobre los ajustes del alumno y aparece bloqueado
  en el panel. Ejemplo::

      {
        "plantilla": "{asignatura}_{apellido}_{escena}",
        "valores": {"asignatura": "MOD1"},
        "autoguardado": true,
        "minutos": 5,
        "copias": 5,
        "aviso_minutos": 30,
        "formato": "ma",
        "carpeta_entregas": "entregas"
      }
"""

import json
import os

ARCHIVO_PROFESOR = "simplesave.json"
_ARCHIVO = "ajustes.json"

DEFECTOS = {
    "plantilla": "{escena}",
    "valores": {},
    "autoguardado": True,
    "minutos": 5,
    "copias": 5,
    "pausa_reproduccion": True,
    "aviso": True,
    "aviso_minutos": 30,
    "formato": "ma",
    "copia_activada": False,
    "copia_carpeta": "",
    "carpeta_entregas": "entregas",
    "conservar_ultimas": 5,
    "miniaturas": True,
    # Internos (no se muestran en el panel)
    "recordados": {},
    "ultima_escena": "",
    "rescates_vistos": [],
    "atajo_intentado": False,
}
# Claves que el profesor puede fijar.
DEL_PROFESOR = ("plantilla", "valores", "autoguardado", "minutos", "copias", "pausa_reproduccion", "aviso",
                "aviso_minutos", "formato", "copia_activada", "copia_carpeta", "carpeta_entregas",
                "conservar_ultimas", "miniaturas")
LIMITES = {"minutos": (1, 120), "copias": (1, 50), "aviso_minutos": (5, 240), "conservar_ultimas": (1, 100)}


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def escribir_json(ruta, datos):
    """Escribe en un temporal y lo cambia por el bueno, para no dejar nunca un json a medias."""
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(temporal, ruta)


def _valido(clave, valor):
    defecto = DEFECTOS.get(clave)
    if defecto is None:
        return valor
    if isinstance(defecto, bool):
        return valor if isinstance(valor, bool) else defecto
    if isinstance(defecto, int):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return defecto
        bajo, alto = LIMITES.get(clave, (valor, valor))
        return int(min(max(valor, bajo), alto))
    if clave == "formato":
        return valor if valor in ("ma", "mb") else defecto
    if not isinstance(valor, type(defecto)):
        return defecto
    return valor


class Ajustes(object):
    """Ajustes del alumno más, encima, los del profesor del proyecto actual."""

    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.ruta = os.path.join(carpeta, _ARCHIVO)
        self.datos = _leer_json(self.ruta)
        self.profesor = {}
        self.ruta_profesor = ""

    # --- profesor ---------------------------------------------------------------
    def cargar_profesor(self, proyecto):
        """Lee ``simplesave.json`` de la carpeta del proyecto (o lo olvida si no hay)."""
        self.profesor, self.ruta_profesor = {}, ""
        if proyecto:
            ruta = os.path.join(proyecto, ARCHIVO_PROFESOR)
            if os.path.isfile(ruta):
                datos = _leer_json(ruta)
                self.profesor = {k: v for k, v in datos.items() if k in DEL_PROFESOR}
                self.ruta_profesor = ruta
        return bool(self.profesor)

    def bloqueado(self, clave):
        return clave in self.profesor

    # --- lectura y escritura --------------------------------------------------------
    def __getitem__(self, clave):
        if clave in self.profesor:
            return _valido(clave, self.profesor[clave])
        return _valido(clave, self.datos.get(clave, DEFECTOS.get(clave)))

    def __setitem__(self, clave, valor):
        self.datos[clave] = valor
        self.guardar()

    def get(self, clave, defecto=None):
        valor = self[clave]
        return defecto if valor is None else valor

    def guardar(self):
        try:
            escribir_json(self.ruta, self.datos)
        except OSError:
            pass

    # --- ayudas -----------------------------------------------------------------------
    def valores_fijos(self):
        """Valores de campos de la plantilla que pone el profesor (no se pueden cambiar)."""
        valores = self.profesor.get("valores")
        return dict(valores) if isinstance(valores, dict) else {}

    def recordar_valores(self, valores):
        """Guarda lo que escribió el alumno (apellido, asignatura...) para la próxima escena."""
        recordados = dict(self["recordados"])
        for campo, valor in valores.items():
            if campo != "escena" and valor:
                recordados[campo] = valor
        self["recordados"] = recordados

    def extension(self):
        return "." + self["formato"]
