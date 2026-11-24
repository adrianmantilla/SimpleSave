"""Limpiar versiones: apartar las antiguas a la carpeta ``archivo``. No depende de Maya.

Nunca borra nada. Se quedan siempre la primera, las ``conservar`` últimas, las
marcadas como importantes y la que está abierta.
"""

import os

from simplesave.archivos import mover_sin_pisar


def que_apartar(versiones, conservar, abierta=None):
    """Lista de versiones que se moverían."""
    if len(versiones) <= 1:
        return []
    ordenadas = sorted(versiones, key=lambda v: v.numero)
    quedan = {ordenadas[0].numero} | {v.numero for v in ordenadas[-max(1, int(conservar)):]}
    abierta = os.path.normcase(os.path.abspath(abierta)) if abierta else None
    apartar = []
    for v in ordenadas:
        if v.numero in quedan or v.importante:
            continue
        if abierta and os.path.normcase(os.path.abspath(v.ruta)) == abierta:
            continue
        apartar.append(v)
    return apartar


def apartar(versiones, carpeta_archivo):
    """Mueve las versiones a ``carpeta_archivo``. Devuelve las rutas nuevas."""
    return [mover_sin_pisar(v.ruta, carpeta_archivo) for v in versiones]


def devolver(version, carpeta):
    """Saca una versión del archivo y la vuelve a poner junto a las demás."""
    return mover_sin_pisar(version.ruta, carpeta)
