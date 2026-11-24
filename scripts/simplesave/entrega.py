"""Entrega: copia de la última versión con nombre de entrega y un .zip con escena y texturas.

No depende de Maya: las rutas de las texturas las da ``Servicios.texturas()``.

El .zip tiene forma de proyecto de Maya para que el profesor lo abra tal cual::

    robot_entrega.zip
        robot/
            workspace.mel
            scenes/robot_v007.ma
            sourceimages/...          (las texturas que estaban dentro del proyecto)
            sourceimages/externas/... (las que estaban fuera)
"""

import glob
import os
import re
import zipfile

from simplesave.archivos import copiar_seguro

_FICHAS = re.compile(r"<udim>|<uvtile>|<u>|<v>|<f>|<frame>|_MAPID_|<tile>|<aov>", re.IGNORECASE)
WORKSPACE_MINIMO = ('//Maya 2026 Project Definition\n\n'
                    'workspace -fr "scene" "scenes";\n'
                    'workspace -fr "sourceImages" "sourceimages";\n'
                    'workspace -fr "images" "images";\n')


def expandir(ruta):
    """Una textura con fichas (``<UDIM>``, ``<f>``...) se convierte en todos los archivos que encajan."""
    if not _FICHAS.search(ruta):
        return [ruta] if os.path.isfile(ruta) else []
    patron = _FICHAS.sub("*", glob.escape(ruta).replace("[*]", "*"))
    return sorted(p for p in glob.glob(patron) if os.path.isfile(p))


def _dentro(ruta, carpeta):
    try:
        rel = os.path.relpath(os.path.abspath(ruta), os.path.abspath(carpeta))
    except ValueError:  # otra unidad en Windows
        return None
    if rel.startswith(".."):
        return None
    return rel.replace("\\", "/")


def preparar(version, proyecto, carpeta_entregas, base, texturas):
    """Prepara la entrega. Devuelve un diccionario con lo hecho y lo que falta."""
    destino = os.path.join(proyecto, carpeta_entregas or "entregas")
    os.makedirs(destino, exist_ok=True)
    ext = os.path.splitext(version)[1]
    escena = copiar_seguro(version, os.path.join(destino, base + "_entrega" + ext))

    ruta_zip = os.path.join(destino, base + "_entrega.zip")
    temporal = ruta_zip + ".simplesave_tmp"
    externas, faltan, incluidas = [], [], set()
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(version, "{}/scenes/{}".format(base, os.path.basename(version)))
        workspace = os.path.join(proyecto, "workspace.mel")
        if os.path.isfile(workspace):
            z.write(workspace, base + "/workspace.mel")
        else:
            z.writestr(base + "/workspace.mel", WORKSPACE_MINIMO)
        for textura in texturas:
            archivos = expandir(textura)
            if not archivos:
                faltan.append(textura)
                continue
            for archivo in archivos:
                rel = _dentro(archivo, proyecto)
                if rel is None:
                    rel = "sourceimages/externas/" + os.path.basename(archivo)
                    externas.append(archivo)
                nombre = "{}/{}".format(base, rel)
                if nombre not in incluidas:
                    incluidas.add(nombre)
                    z.write(archivo, nombre)
    os.replace(temporal, ruta_zip)
    return {"escena": escena, "zip": ruta_zip, "texturas": len(incluidas), "externas": externas,
            "faltan": faltan}
