"""Comparar dos versiones: objetos añadidos y borrados y caras. No depende de Maya.

Los objetos se apuntan en el historial al guardar cada versión. Para versiones
.ma antiguas sin esa información se leen del propio archivo.
"""

import re

_TRANSFORM = re.compile(r'^createNode\s+transform\s+(?:-s\s+)?-n\s+"([^"]+)"(?:\s+-p\s+"([^"]+)")?', re.MULTILINE)
_SISTEMA = {"persp", "top", "front", "side", "bottom", "back", "left"}


def objetos_de_ma(ruta, limite_mb=200):
    """Nombres de los transforms de un .ma (sin las cámaras por defecto). None si no se puede leer."""
    if not ruta.lower().endswith(".ma"):
        return None
    try:
        import os
        if os.path.getsize(ruta) > limite_mb * 1024 * 1024:
            return None
        with open(ruta, encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except OSError:
        return None
    lista = []
    for nombre, padre in _TRANSFORM.findall(texto):
        completo = "{}|{}".format(padre, nombre) if padre else nombre
        if nombre not in _SISTEMA:
            lista.append(completo)
    return lista


def objetos_de(version):
    if version.objetos is not None:
        return list(version.objetos)
    return objetos_de_ma(version.ruta)


def diferencias(a, b):
    """Qué cambió de la versión ``a`` a la ``b``."""
    oa, ob = objetos_de(a), objetos_de(b)
    resultado = {"a": a, "b": b, "conocido": oa is not None and ob is not None,
                 "anadidos": [], "borrados": [], "caras_a": a.caras, "caras_b": b.caras}
    if resultado["conocido"]:
        sa, sb = set(oa), set(ob)
        resultado["anadidos"] = sorted(sb - sa, key=str.lower)
        resultado["borrados"] = sorted(sa - sb, key=str.lower)
    return resultado
