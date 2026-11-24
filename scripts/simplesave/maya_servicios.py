"""Servicios de SimpleSave hechos con Maya (``cmds``)."""

import glob
import os
import subprocess
import sys
import tempfile

from maya import cmds, mel

from simplesave.i18n import t
from simplesave.servicios import Servicios

TIPOS = {"ma": "mayaAscii", "mb": "mayaBinary"}
TAMANO_MINIATURA = (320, 180)


def _tipo(formato, ruta):
    if ruta.lower().endswith(".mb"):
        return TIPOS["mb"]
    if ruta.lower().endswith(".ma"):
        return TIPOS["ma"]
    return TIPOS.get(formato, "mayaAscii")


def _recientes(ruta, tipo):
    try:
        mel.eval('addRecentFile("{}", "{}")'.format(ruta.replace("\\", "/"), tipo))
    except Exception:
        pass


class ServiciosMaya(Servicios):
    en_maya = True

    def __init__(self):
        # La interfaz lo rellena: guarda versión antes de abrir otra escena.
        self.guardar_version_antes = None

    # --- escena ------------------------------------------------------------------------
    def escena_actual(self):
        return cmds.file(query=True, sceneName=True) or ""

    def proyecto(self):
        return (cmds.workspace(query=True, rootDirectory=True) or "").rstrip("/\\")

    def modificada(self):
        return bool(cmds.file(query=True, modified=True))

    def guardar_como(self, ruta, formato):
        anterior = self.escena_actual()
        tipo = _tipo(formato, ruta)
        ruta = ruta.replace("\\", "/")
        cmds.file(rename=ruta)
        try:
            cmds.file(save=True, type=tipo)
        except Exception:
            # Si no pudo guardar, la escena vuelve a llamarse como antes.
            if anterior:
                cmds.file(rename=anterior)
            raise
        _recientes(ruta, tipo)

    def guardar_copia(self, ruta, formato):
        tipo = _tipo(formato, ruta)
        ruta = ruta.replace("\\", "/")
        actual = self.escena_actual()
        modificada = self.modificada()
        if not actual:
            # Sin nombre: se exporta todo, así la escena sigue «sin título».
            cmds.file(ruta, exportAll=True, type=tipo, preserveReferences=True, force=True)
            return
        cmds.file(rename=ruta)
        try:
            cmds.file(save=True, type=tipo)
        finally:
            cmds.file(rename=actual)
            # La copia no cuenta como guardar: Maya debe seguir avisando de cambios pendientes.
            cmds.file(modified=modificada)

    def confirmar_cerrar(self):
        if not self.modificada():
            return True
        guardar, descartar, cancelar = t("cerrar_guardar"), t("cerrar_descartar"), t("cerrar_cancelar")
        respuesta = cmds.confirmDialog(title="SimpleSave", message=t("cerrar_pregunta"),
                                       button=[guardar, descartar, cancelar], defaultButton=guardar,
                                       cancelButton=cancelar, dismissString=cancelar)
        if respuesta == cancelar:
            return False
        if respuesta == guardar:
            if self.guardar_version_antes is None:
                return False
            return bool(self.guardar_version_antes())
        return True

    def abrir(self, ruta, preguntar=True):
        if preguntar and not self.confirmar_cerrar():
            return False
        tipo = _tipo("", ruta)
        cmds.file(ruta.replace("\\", "/"), open=True, force=True, ignoreVersion=True, prompt=False)
        _recientes(ruta, tipo)
        return True

    # --- información para el historial -------------------------------------------------------
    def capturar_miniatura(self, ruta):
        if cmds.about(batch=True):
            return False
        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
            visibles = [p for p in (cmds.getPanel(visiblePanels=True) or [])
                        if cmds.getPanel(typeOf=p) == "modelPanel"]
            if not visibles:
                return False
            panel = visibles[0]
        formato_antes = cmds.getAttr("defaultRenderGlobals.imageFormat")
        try:
            cmds.setAttr("defaultRenderGlobals.imageFormat", 8)  # JPEG
            cuadro = cmds.currentTime(query=True)
            cmds.playblast(frame=[cuadro], format="image", compression="jpg", completeFilename=ruta,
                           widthHeight=TAMANO_MINIATURA, percent=100, quality=85, showOrnaments=False,
                           viewer=False, offScreen=True, forceOverwrite=True, editorPanelName=panel)
        except Exception:
            return False
        finally:
            cmds.setAttr("defaultRenderGlobals.imageFormat", formato_antes)
        if os.path.isfile(ruta):
            return True
        # Algunas versiones añaden el número de cuadro al nombre.
        raiz = os.path.splitext(ruta)[0]
        for candidata in glob.glob(raiz + "*.jp*g"):
            os.replace(candidata, ruta)
            return True
        return False

    def _camaras_inicio(self):
        transforms = set()
        for camara in cmds.ls(type="camera") or []:
            try:
                if cmds.camera(camara, query=True, startupCamera=True):
                    transforms.update(cmds.listRelatives(camara, parent=True) or [])
            except Exception:
                pass
        return transforms

    def objetos(self):
        inicio = self._camaras_inicio()
        lista = [o for o in (cmds.ls(type="transform") or []) if o not in inicio]
        return lista[:20000]

    def caras(self):
        mallas = cmds.ls(type="mesh", noIntermediate=True) or []
        if not mallas:
            return 0
        try:
            total = cmds.polyEvaluate(mallas, face=True)
        except Exception:
            return 0
        return total if isinstance(total, int) else 0

    def texturas(self):
        rutas = []
        for tipo, atributo in (("file", "fileTextureName"), ("aiImage", "filename"), ("imagePlane", "imageName")):
            try:
                nodos = cmds.ls(type=tipo) or []
            except Exception:
                continue
            for nodo in nodos:
                try:
                    valor = cmds.getAttr("{}.{}".format(nodo, atributo))
                except Exception:
                    continue
                if valor:
                    if not os.path.isabs(valor):
                        valor = cmds.workspace(expandName=valor)
                    rutas.append(os.path.normpath(valor))
        return list(dict.fromkeys(rutas))

    def reproduciendo(self):
        try:
            return bool(cmds.play(query=True, state=True))
        except Exception:
            return False

    def carpetas_rescate(self):
        carpetas = [tempfile.gettempdir()]
        for variable in ("TMPDIR", "TEMP", "TMP"):
            if os.environ.get(variable):
                carpetas.append(os.environ[variable])
        return list(dict.fromkeys(os.path.normpath(c) for c in carpetas))

    # --- utilidades ---------------------------------------------------------------------
    def mostrar_en_carpeta(self, ruta):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", ruta] if os.path.isfile(ruta) else ["open", ruta])
            elif sys.platform.startswith("win"):
                if os.path.isfile(ruta):
                    subprocess.Popen('explorer /select,"{}"'.format(os.path.normpath(ruta)))
                else:
                    os.startfile(os.path.normpath(ruta))
            else:
                subprocess.Popen(["xdg-open", ruta if os.path.isdir(ruta) else os.path.dirname(ruta)])
        except Exception as error:
            cmds.warning("SimpleSave: {}".format(error))

    def aviso(self, texto):
        if cmds.about(batch=True):
            print("SimpleSave | " + texto)
            return
        try:
            cmds.inViewMessage(assistMessage=texto, position="topCenter", fade=True, fadeStayTime=4500)
        except Exception:
            cmds.warning(texto)
