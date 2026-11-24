"""Cuándo autoguardar, dónde y qué recuperar. No depende de Maya.

Las copias automáticas nunca van encima de las versiones: van a
``.simplesave/<base>/autoguardado/<base>_auto_AAAAMMDD_HHMMSS.ma`` y se guardan
solo las últimas N.
"""

import datetime
import os
import re
import time

from simplesave import nombres

SIN_TITULO = "sin_titulo"
_AUTO = re.compile(r"^(?P<base>.+)_auto_(?P<fecha>\d{8}_\d{6}[a-j]?)(?P<ext>\.m[ab])$", re.IGNORECASE)
# Copia de emergencia que Maya escribe al colgarse: <usuario>.<AAAAMMDD>.<HHMM>.ma
_RESCATE = re.compile(r"^.+\.\d{8}\.\d{4}\.m[ab]$", re.IGNORECASE)
# Si la escena sigue con cambios y no se ha autoguardado en tantas veces el
# intervalo, se guarda igualmente aunque no se hayan visto órdenes nuevas.
VECES_SIN_SENAL = 3


def es_copia(ruta):
    """True si ``ruta`` es una copia automática o de emergencia (no una escena del alumno)."""
    if not ruta:
        return False
    nombre = os.path.basename(ruta)
    partes = ruta.replace("\\", "/").split("/")
    return bool(_AUTO.match(nombre) or _RESCATE.match(nombre) or ".simplesave" in partes)


class Planificador(object):
    """Decide si toca autoguardar. ``ahora`` en segundos (``time.time()``)."""

    def __init__(self, ahora=None):
        self.ultimo = time.time() if ahora is None else ahora
        self.cambios = False

    def hubo_cambio(self):
        """Se llama cuando Maya registra una orden, un deshacer o un rehacer."""
        self.cambios = True

    def reiniciar(self, ahora=None):
        """Tras guardar versión, autoguardar o abrir otra escena."""
        self.ultimo = time.time() if ahora is None else ahora
        self.cambios = False

    def segundos_restantes(self, minutos, ahora=None):
        ahora = time.time() if ahora is None else ahora
        return max(0.0, self.ultimo + minutos * 60.0 - ahora)

    def toca(self, minutos, escena_modificada, reproduciendo=False, ahora=None, pausa_reproduccion=True):
        ahora = time.time() if ahora is None else ahora
        if not escena_modificada:
            return False
        if reproduciendo and pausa_reproduccion:
            return False
        transcurrido = ahora - self.ultimo
        if transcurrido < minutos * 60.0:
            return False
        return self.cambios or transcurrido >= minutos * 60.0 * VECES_SIN_SENAL


def nombre_copia(base, ext, cuando=None):
    cuando = cuando or datetime.datetime.now()
    return "{}_auto_{}{}".format(base, cuando.strftime("%Y%m%d_%H%M%S"), ext)


def copias(carpeta, base=None):
    """Copias automáticas de la carpeta, de la más nueva a la más antigua."""
    lista = []
    try:
        nombres_ = os.listdir(carpeta)
    except OSError:
        return lista
    for nombre in nombres_:
        m = _AUTO.match(nombre)
        if not m or (base is not None and m.group("base").lower() != base.lower()):
            continue
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            lista.append(ruta)
    lista.sort(key=lambda r: (os.path.getmtime(r), os.path.basename(r)), reverse=True)
    return lista


def rotar(carpeta, base, maximo):
    """Borra las copias más antiguas para que queden ``maximo``. Devuelve las borradas."""
    borradas = []
    for ruta in copias(carpeta, base)[max(1, int(maximo)):]:
        try:
            os.remove(ruta)
            borradas.append(ruta)
        except OSError:
            pass
    return borradas


def ruta_nueva(carpeta, base, ext, cuando=None):
    ruta = os.path.join(carpeta, nombre_copia(base, ext, cuando))
    # Dos copias en el mismo segundo: se añade una letra.
    if os.path.exists(ruta):
        raiz, ext_ = os.path.splitext(ruta)
        for letra in "abcdefghij":
            candidata = "{}{}{}".format(raiz, letra, ext_)
            if not os.path.exists(candidata):
                return candidata
    return ruta


def carpeta_sin_titulo(proyecto):
    """Dónde van las copias de una escena que aún no tiene nombre."""
    return os.path.join(proyecto, "scenes", ".simplesave", SIN_TITULO, "autoguardado")


def recuperable(historial):
    """La copia automática más reciente si es más nueva que la última versión guardada."""
    lista = copias(historial.carpeta_autoguardado, historial.base)
    if not lista:
        return None
    copia = lista[0]
    referencia = 0.0
    for ruta in nombres.versiones_en(historial.carpeta, historial.base).values():
        referencia = max(referencia, os.path.getmtime(ruta))
    return copia if os.path.getmtime(copia) > referencia + 1.0 else None


def rescates_de_maya(carpetas, dias=7, ahora=None):
    """Copias de emergencia que Maya dejó al cerrarse de golpe, de la más nueva a la más antigua."""
    ahora = time.time() if ahora is None else ahora
    encontrados = []
    vistos = set()
    for carpeta in carpetas:
        if not carpeta:
            continue
        try:
            nombres_ = os.listdir(carpeta)
        except OSError:
            continue
        for nombre in nombres_:
            if not _RESCATE.match(nombre):
                continue
            ruta = os.path.join(carpeta, nombre)
            clave = os.path.normcase(os.path.realpath(ruta))
            if clave in vistos or not os.path.isfile(ruta):
                continue
            if ahora - os.path.getmtime(ruta) > dias * 86400:
                continue
            vistos.add(clave)
            encontrados.append(ruta)
    encontrados.sort(key=os.path.getmtime, reverse=True)
    return encontrados
