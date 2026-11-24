"""Operaciones de archivo seguras. No depende de Maya."""

import os
import shutil


def verificar_escena(ruta):
    """True si ``ruta`` parece una escena de Maya completa y legible."""
    try:
        if os.path.getsize(ruta) < 16:
            return False
        with open(ruta, "rb") as f:
            cabecera = f.read(64)
    except OSError:
        return False
    if ruta.lower().endswith(".ma"):
        return cabecera.lstrip(b"\xef\xbb\xbf").startswith(b"//Maya")
    if ruta.lower().endswith(".mb"):
        return cabecera[:4] in (b"FOR4", b"FOR8")
    return True


def copiar_seguro(origen, destino):
    """Copia a un temporal junto al destino y lo renombra al terminar.

    Si el disco se llena a medias, el destino anterior (si había) no se toca.
    """
    carpeta = os.path.dirname(destino)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    temporal = destino + ".simplesave_tmp"
    try:
        shutil.copy2(origen, temporal)
        os.replace(temporal, destino)
    finally:
        if os.path.exists(temporal):
            try:
                os.remove(temporal)
            except OSError:
                pass
    return destino


def borrar(ruta):
    try:
        os.remove(ruta)
        return True
    except OSError:
        return False


def mover_sin_pisar(origen, carpeta):
    """Mueve ``origen`` a ``carpeta``; si ya hay uno con ese nombre, añade ``_2``, ``_3``..."""
    os.makedirs(carpeta, exist_ok=True)
    nombre = os.path.basename(origen)
    destino = os.path.join(carpeta, nombre)
    raiz, ext = os.path.splitext(nombre)
    n = 2
    while os.path.exists(destino):
        destino = os.path.join(carpeta, "{}_{}{}".format(raiz, n, ext))
        n += 1
    shutil.move(origen, destino)
    return destino


def tamano_legible(bytes_):
    valor = float(bytes_ or 0)
    for unidad in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidad == "GB":
            if unidad == "B":
                return "{} B".format(int(valor))
            return "{:.1f} {}".format(valor, unidad).replace(".", ",")
        valor /= 1024.0
