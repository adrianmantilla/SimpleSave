"""Plugin de Maya para SimpleSave.

Aparece en el Plug-in Manager como «simplesave_plugin». Al cargarlo crea el menú
SimpleSave en la barra de Maya y las órdenes para el Editor de atajos; al
descargarlo lo quita todo. El instalador lo marca para que se cargue solo.
"""

import maya.api.OpenMaya as om
from maya import cmds


def maya_useNewAPI():
    pass


def initializePlugin(objeto):
    import simplesave
    plugin = om.MFnPlugin(objeto, "SimpleSave", simplesave.__version__, "Any")
    try:
        from simplesave import interfaz_maya
        cmds.evalDeferred(interfaz_maya.iniciar, lowestPriority=True)
    except Exception as error:
        cmds.warning("SimpleSave no se pudo cargar: {}".format(error))
    return plugin


def uninitializePlugin(objeto):
    try:
        from simplesave import interfaz_maya
        interfaz_maya.detener()
    except Exception:
        pass
