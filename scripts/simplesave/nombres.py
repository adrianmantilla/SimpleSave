"""Nombres de archivo: limpieza, plantillas y números de versión. No depende de Maya.

Una versión se llama ``<base>_v<NNN>.<ext>``, por ejemplo ``robot_v004.ma``.
"""

import os
import re
import unicodedata

EXTENSIONES = (".ma", ".mb")
DIGITOS = 3
_VERSION = re.compile(r"^(?P<base>.+?)_v(?P<num>\d{%d,})$" % DIGITOS, re.IGNORECASE)
_CAMPO = re.compile(r"\{([a-z_][a-z0-9_]*)\}", re.IGNORECASE)
_PERMITIDOS = re.compile(r"[^A-Za-z0-9_-]")
# Nombres que Windows no deja usar como archivo.
_RESERVADOS = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}


def limpiar(texto):
    """Deja solo letras sin tilde, números, ``_`` y ``-``.

    Devuelve ``(limpio, cambios)`` donde ``cambios`` es una lista de claves de
    texto: ``tildes``, ``espacios``, ``simbolos``.
    """
    cambios = []
    texto = (texto or "").strip()
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    sin_tildes = sin_tildes.replace("ß", "ss").replace("æ", "ae").replace("Æ", "AE").replace("ø", "o").replace("Ø", "O")
    if sin_tildes != texto:
        cambios.append("tildes")
    texto = sin_tildes
    if re.search(r"\s", texto):
        cambios.append("espacios")
        texto = re.sub(r"\s+", "_", texto)
    sin_simbolos = _PERMITIDOS.sub("", texto)
    if sin_simbolos != texto:
        cambios.append("simbolos")
    texto = re.sub(r"_+", "_", sin_simbolos).strip("_-")
    if texto.lower() in _RESERVADOS:
        texto += "_"
    return texto, cambios


def campos(plantilla):
    """Campos de una plantilla en orden y sin repetir: ``{asignatura}_{escena}`` → ``["asignatura", "escena"]``."""
    vistos = []
    for nombre in _CAMPO.findall(plantilla or ""):
        nombre = nombre.lower()
        if nombre not in vistos:
            vistos.append(nombre)
    if "escena" not in vistos:
        vistos.append("escena")
    return vistos


def aplicar(plantilla, valores):
    """Rellena la plantilla con valores ya limpios. Quita separadores sobrantes de campos vacíos."""
    plantilla = plantilla or "{escena}"
    if "{escena}" not in plantilla.lower():
        plantilla += "_{escena}"

    def poner(m):
        return valores.get(m.group(1).lower(), "")
    texto = _CAMPO.sub(poner, plantilla)
    texto, _ = limpiar(texto)
    return texto


def nombre_desde_campos(plantilla, valores):
    """Limpia cada valor y rellena la plantilla.

    Devuelve ``(base, cambios, faltan)``: ``cambios`` es una lista de
    ``(campo, clave)`` y ``faltan`` los campos vacíos.
    """
    limpios, cambios, faltan = {}, [], []
    for campo in campos(plantilla):
        limpio, c = limpiar(valores.get(campo, ""))
        limpios[campo] = limpio
        cambios.extend((campo, clave) for clave in c)
        if not limpio:
            faltan.append(campo)
    return aplicar(plantilla, limpios), cambios, faltan


def separar(ruta):
    """``/x/robot_v004.ma`` → ``("robot", 4, ".ma")``. Sin número: ``("robot", None, ".ma")``."""
    nombre, ext = os.path.splitext(os.path.basename(ruta or ""))
    m = _VERSION.match(nombre)
    if m:
        return m.group("base"), int(m.group("num")), ext.lower()
    return nombre, None, ext.lower()


def archivo_version(base, numero, ext=".ma"):
    return "{}_v{}{}".format(base, str(int(numero)).zfill(DIGITOS), ext)


def etiqueta(numero):
    return "v" + str(int(numero)).zfill(DIGITOS)


def versiones_en(carpeta, base):
    """Diccionario ``{numero: ruta}`` de las versiones de ``base`` en ``carpeta`` (.ma y .mb)."""
    encontradas = {}
    try:
        nombres = os.listdir(carpeta)
    except OSError:
        return encontradas
    for nombre in nombres:
        b, n, ext = separar(nombre)
        if n is None or ext not in EXTENSIONES or b.lower() != base.lower():
            continue
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            # Si existen v004.ma y v004.mb, se queda la más reciente.
            if n not in encontradas or os.path.getmtime(ruta) > os.path.getmtime(encontradas[n]):
                encontradas[n] = ruta
    return encontradas


def siguiente(carpeta, base):
    """El siguiente número libre: uno más que el mayor que exista, en .ma o en .mb."""
    existentes = versiones_en(carpeta, base)
    return (max(existentes) + 1) if existentes else 1
