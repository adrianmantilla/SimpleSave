"""Une SimpleSave con Maya: menú, panel acoplable, atajo, estantería, autoguardado y avisos."""

import os

from maya import cmds, mel

import simplesave
from simplesave import pack, qt
from simplesave.config import ARCHIVO_PROFESOR, DEFECTOS, Ajustes, escribir_json
from simplesave.gestor import ErrorGuardado, Gestor
from simplesave.i18n import t
from simplesave.qt import QtCore, QtWidgets, destruir, shiboken, sigue_vivo, ventana_maya

CONTROL = "SimpleSaveWorkspaceControl"
MENU = "SimpleSaveMenu"
CONJUNTO_ATAJOS = "SimpleSave_atajos"
NOMBRE_ATAJO = "SimpleSaveGuardarVersionNameCommand"
COMANDOS = {
    "SimpleSaveGuardarVersion": ("cmd_guardar", "guardar_version()"),
    "SimpleSavePanel": ("cmd_panel", "alternar()"),
    "SimpleSaveRecuperar": ("cmd_recuperar", "recuperar()"),
}
# Eventos de Maya que indican que el alumno ha hecho algo en la escena.
EVENTOS_CAMBIO = ("RecentCommandChanged", "Undo", "Redo", "DagObjectCreated", "NameChanged")
INTERVALO_MS = 5000

_estado = {"panel": None, "ajustes": None, "gestor": None, "servicios": None, "trabajos": [], "reloj": None,
           "pendiente": False}


# --- objetos compartidos -------------------------------------------------------------------

def carpeta_preferencias():
    return os.path.join(cmds.internalVar(userAppDir=True), "simplesave")


def ajustes():
    if _estado["ajustes"] is None:
        _estado["ajustes"] = Ajustes(carpeta_preferencias())
    return _estado["ajustes"]


def servicios():
    if _estado["servicios"] is None:
        from simplesave.maya_servicios import ServiciosMaya
        _estado["servicios"] = ServiciosMaya()
        _estado["servicios"].guardar_version_antes = guardar_version
    return _estado["servicios"]


def gestor():
    if _estado["gestor"] is None:
        _estado["gestor"] = Gestor(servicios(), ajustes())
        _estado["gestor"].cargar_proyecto()
    return _estado["gestor"]


def panel():
    p = _estado["panel"]
    return p if sigue_vivo(p) else None


def _refrescar(forzar=True):
    p = panel()
    if p is not None:
        p.cargar_ajustes()
        p.refrescar(forzar=forzar)


# --- panel acoplable -------------------------------------------------------------------------

def restaurar():
    """Maya lo llama al crear (o recuperar) el panel: mete el panel dentro."""
    from maya import OpenMayaUI as omui
    from simplesave.panel import PanelSimpleSave
    puntero = omui.MQtUtil.getCurrentParent()
    padre = shiboken.wrapInstance(int(puntero), QtWidgets.QWidget)
    p = panel()
    if p is None:
        p = PanelSimpleSave(gestor(), padre_dialogos=ventana_maya())
        _estado["panel"] = p
    padre.layout().addWidget(p)


def mostrar():
    if cmds.workspaceControl(CONTROL, exists=True):
        cmds.workspaceControl(CONTROL, edit=True, restore=True, visible=True)
        if panel() is None:
            cmds.deleteUI(CONTROL)
        else:
            _refrescar()
            return panel()
    cmds.workspaceControl(CONTROL, label="SimpleSave", retain=False, floating=True, initialWidth=420,
                          initialHeight=560, minimumWidth=300,
                          uiScript="import simplesave.interfaz_maya as m\nm.restaurar()",
                          closeCommand="import simplesave.interfaz_maya as m\nm.al_cerrar()")
    return panel()


def alternar():
    if cmds.workspaceControl(CONTROL, exists=True) and cmds.workspaceControl(CONTROL, query=True, visible=True):
        cmds.workspaceControl(CONTROL, edit=True, visible=False)
    else:
        mostrar()


def al_cerrar():
    _estado["panel"] = None


# --- acciones ----------------------------------------------------------------------------------

def guardar_version():
    """Guarda versión desde el atajo o el menú. Devuelve True si se guardó."""
    p = panel()
    if p is not None:
        return p.guardar_version()
    from simplesave.panel import PanelSimpleSave
    # Sin panel abierto: se usa uno invisible solo para los diálogos.
    temporal = PanelSimpleSave(gestor(), padre_dialogos=ventana_maya())
    try:
        return temporal.guardar_version()
    finally:
        temporal.reloj.stop()
        destruir(temporal)


def _con_panel(funcion):
    p = mostrar()
    if p is not None:
        return funcion(p)
    return None


def comparar():
    _con_panel(lambda p: p.comparar())


def entregar():
    _con_panel(lambda p: p.entregar())


def limpiar():
    _con_panel(lambda p: p.limpiar())


def recuperar():
    """Busca qué se puede recuperar: autoguardado de esta escena y copias de emergencia."""
    g = gestor()
    copia = g.recuperable()
    if copia:
        _ofrecer_recuperar(copia, g.escena())
        return
    rescates = g.rescates()
    if rescates:
        _ofrecer_rescates(rescates, siempre=True)
    else:
        QtWidgets.QMessageBox.information(ventana_maya(), "SimpleSave", t("nada_que_recuperar"))


def _ofrecer_recuperar(copia, ruta_escena):
    from simplesave.dialogos import DialogoRecuperar
    from simplesave import nombres
    g = gestor()
    h = g.historial(ruta_escena)
    dialogo = DialogoRecuperar(copia, h.ultima(), nombres.etiqueta(h.siguiente()), ventana_maya())
    qt.ejecutar(dialogo)
    if dialogo.eleccion == DialogoRecuperar.RECUPERAR:
        try:
            r = g.recuperar(copia, ruta_escena)
        except (ErrorGuardado, OSError) as error:
            QtWidgets.QMessageBox.warning(ventana_maya(), "SimpleSave", str(error))
            return
        if r is not None:
            servicios().aviso(t("recuperada", archivo=os.path.basename(r.ruta)))
    _refrescar()


def _ofrecer_rescates(rutas, siempre=False):
    from simplesave.dialogos import DialogoRescates
    g = gestor()
    dialogo = DialogoRescates(rutas, servicios(), ventana_maya())
    qt.ejecutar(dialogo)
    if not siempre or dialogo.elegida:
        g.olvidar_rescates(rutas)
    if dialogo.elegida:
        try:
            if g.abrir_rescate(dialogo.elegida):
                g.al_abrir_escena()
                servicios().aviso(t("rescate_abierto"))
                cmds.evalDeferred(guardar_version, lowestPriority=True)
        except Exception as error:
            QtWidgets.QMessageBox.warning(ventana_maya(), "SimpleSave", str(error))
    _refrescar()


def _comprobar_al_arrancar():
    """Al abrir Maya: ¿quedó algo sin guardar la última vez?"""
    g = gestor()
    ultima = ajustes()["ultima_escena"]
    copia = g.recuperable_de(ultima) if ultima else None
    if copia and not g.escena():
        _ofrecer_recuperar(copia, ultima)
        return
    rescates = g.rescates()
    if rescates:
        _ofrecer_rescates(rescates)


# --- escena y autoguardado ------------------------------------------------------------------------

def _al_abrir_escena():
    g = gestor()
    g.al_abrir_escena()
    _refrescar()
    copia = g.recuperable()
    if copia and not cmds.about(batch=True):
        # Se espera a que Maya termine de abrir del todo.
        cmds.evalDeferred(lambda: _ofrecer_recuperar(copia, g.escena()), lowestPriority=True)


def _al_guardar_escena():
    g = gestor()
    if g.autoguardando:
        return
    # Ctrl+S normal: cuenta como guardado para el autoguardado.
    g.planificador.reiniciar()
    if g.escena():
        ajustes()["ultima_escena"] = g.escena()
    _refrescar(forzar=False)


def _hubo_cambio():
    g = _estado["gestor"]
    if g is not None:
        g.planificador.hubo_cambio()


def _autoguardar():
    _estado["pendiente"] = False
    g = gestor()
    if not g.toca_autoguardar():
        return
    ruta = g.autoguardar()
    if ruta:
        print("SimpleSave | " + t("autoguardado_hecho", ruta=ruta))
    else:
        cmds.warning("SimpleSave: " + t("autoguardado_fallo"))
    _refrescar(forzar=False)


def _latido():
    g = _estado["gestor"]
    if g is None:
        return
    try:
        if not _estado["pendiente"] and g.toca_autoguardar():
            _estado["pendiente"] = True
            # Se hace cuando Maya está libre: nunca a mitad de un arrastre o un render.
            cmds.evalDeferred(_autoguardar, lowestPriority=True)
        if g.toca_aviso():
            servicios().aviso(t("aviso_version", minutos=g.minutos_sin_version(), atajo=texto_atajo()))
    except Exception as error:  # pragma: no cover - que un fallo no pare el reloj
        print("SimpleSave | {}".format(error))


# --- atajo, estantería, profesor ----------------------------------------------------------------

def _modificadores():
    if cmds.about(macOS=True):
        return {"altModifier": True, "commandModifier": True}
    return {"altModifier": True, "ctrlModifier": True}


def texto_atajo():
    return "⌘+Alt+S" if cmds.about(macOS=True) else "Ctrl+Alt+S"


def asignar_atajo(silencioso=False):
    """Asigna Ctrl+Alt+S (⌘+Alt+S en Mac) a «Guardar versión» si está libre."""
    mods = _modificadores()
    try:
        ocupado = cmds.hotkeyCheck(keyString="s", **mods)
    except Exception:
        ocupado = ""
    if ocupado and ocupado != NOMBRE_ATAJO and "SimpleSave" not in ocupado:
        if not silencioso:
            QtWidgets.QMessageBox.information(ventana_maya(), "SimpleSave",
                                              t("atajo_ocupado", atajo=texto_atajo(), orden=ocupado))
        return False
    try:
        actual = cmds.hotkeySet(query=True, current=True)
        if actual == "Maya_Default":
            # El conjunto de Maya no se puede tocar: se crea una copia.
            if not cmds.hotkeySet(CONJUNTO_ATAJOS, exists=True):
                cmds.hotkeySet(CONJUNTO_ATAJOS, source="Maya_Default", current=True)
            else:
                cmds.hotkeySet(CONJUNTO_ATAJOS, edit=True, current=True)
        cmds.nameCommand(NOMBRE_ATAJO, annotation=t("cmd_guardar"), command="SimpleSaveGuardarVersion",
                         sourceType="mel")
        cmds.hotkey(keyShortcut="s", name=NOMBRE_ATAJO, **mods)
        cmds.savePrefs(hotkeys=True)
    except Exception as error:
        if not silencioso:
            QtWidgets.QMessageBox.warning(ventana_maya(), "SimpleSave", str(error))
        return False
    if not silencioso:
        servicios().aviso(t("atajo_asignado", atajo=texto_atajo()))
    return True


def _icono():
    from simplesave.iconos import asegurar_icono
    return asegurar_icono(carpeta_preferencias())


def anadir_a_estanteria():
    try:
        estanterias = mel.eval("$tmp = $gShelfTopLevel")
        pestana = cmds.tabLayout(estanterias, query=True, selectTab=True)
        cmds.shelfButton(parent="{}|{}".format(estanterias, pestana), label="SimpleSave",
                         annotation=t("cmd_guardar"), image=_icono(), sourceType="python",
                         command="import simplesave.interfaz_maya as m\nm.guardar_version()",
                         doubleClickCommand="import simplesave.interfaz_maya as m\nm.mostrar()")
        servicios().aviso(t("estanteria_hecho", estanteria=pestana))
    except Exception as error:
        QtWidgets.QMessageBox.warning(ventana_maya(), "SimpleSave", str(error))


def crear_json_profesor():
    proyecto = servicios().proyecto()
    ruta = os.path.join(proyecto, ARCHIVO_PROFESOR)
    if not os.path.exists(ruta):
        ejemplo = {
            "plantilla": "{asignatura}_{apellido}_{escena}",
            "valores": {"asignatura": "MOD1"},
            "autoguardado": True,
            "minutos": DEFECTOS["minutos"],
            "copias": DEFECTOS["copias"],
            "aviso_minutos": DEFECTOS["aviso_minutos"],
            "formato": DEFECTOS["formato"],
            "carpeta_entregas": DEFECTOS["carpeta_entregas"],
        }
        escribir_json(ruta, ejemplo)
    gestor().cargar_proyecto()
    _refrescar()
    servicios().mostrar_en_carpeta(ruta)
    QtWidgets.QMessageBox.information(ventana_maya(), "SimpleSave", t("profesor_creado", ruta=ruta))


# --- menú y órdenes ---------------------------------------------------------------------------

def _crear_ordenes():
    for nombre, (clave, llamada) in COMANDOS.items():
        codigo = "import simplesave.interfaz_maya as m\nm.{}".format(llamada)
        if cmds.runTimeCommand(nombre, exists=True):
            cmds.runTimeCommand(nombre, edit=True, command=codigo, commandLanguage="python", annotation=t(clave))
        else:
            cmds.runTimeCommand(nombre, command=codigo, commandLanguage="python", annotation=t(clave),
                                category="Custom Scripts.SimpleSave")


def _crear_menu():
    pack.crear_menu(MENU, "SimpleSave")
    cmds.menuItem(label=t("menu_guardar", atajo=texto_atajo()), command=lambda *_: guardar_version(),
                  annotation=t("cmd_guardar"))
    cmds.menuItem(label=t("menu_panel"), command=lambda *_: mostrar())
    cmds.menuItem(label=t("menu_recuperar"), command=lambda *_: recuperar())
    cmds.menuItem(divider=True)
    cmds.menuItem(label=t("menu_comparar"), command=lambda *_: comparar())
    cmds.menuItem(label=t("menu_entregar"), command=lambda *_: entregar())
    cmds.menuItem(label=t("menu_limpiar"), command=lambda *_: limpiar())
    cmds.menuItem(divider=True)
    if not pack.en_pack():  # dentro de MantiTools el estante lo pone el pack
        cmds.menuItem(label=t("menu_estanteria"), command=lambda *_: anadir_a_estanteria())
    cmds.menuItem(label=t("menu_atajo", atajo=texto_atajo()), command=lambda *_: asignar_atajo())
    cmds.menuItem(label=t("menu_profesor"), command=lambda *_: crear_json_profesor())
    cmds.menuItem(divider=True)
    cmds.menuItem(label=t("menu_acerca", version=simplesave.__version__), enable=False)


def iniciar():
    _crear_ordenes()
    if cmds.about(batch=True):
        return
    _crear_menu()
    trabajos = [
        cmds.scriptJob(event=["SceneOpened", _al_abrir_escena]),
        cmds.scriptJob(event=["NewSceneOpened", _al_abrir_escena]),
        cmds.scriptJob(event=["SceneSaved", _al_guardar_escena]),
        cmds.scriptJob(event=["workspaceChanged", lambda: (gestor().cargar_proyecto(), _refrescar())]),
    ]
    for evento in EVENTOS_CAMBIO:
        try:
            trabajos.append(cmds.scriptJob(event=[evento, _hubo_cambio]))
        except Exception:
            pass
    _estado["trabajos"] = trabajos
    gestor()
    reloj = QtCore.QTimer(ventana_maya())
    reloj.setInterval(INTERVALO_MS)
    reloj.timeout.connect(_latido)
    reloj.start()
    _estado["reloj"] = reloj
    if not ajustes()["atajo_intentado"]:
        ajustes()["atajo_intentado"] = True
        asignar_atajo(silencioso=True)
    cmds.evalDeferred(_comprobar_al_arrancar, lowestPriority=True)


def detener():
    reloj = _estado.get("reloj")
    if reloj is not None and sigue_vivo(reloj):
        reloj.stop()
        destruir(reloj)
    _estado["reloj"] = None
    for trabajo in _estado["trabajos"]:
        if cmds.scriptJob(exists=trabajo):
            cmds.scriptJob(kill=trabajo, force=True)
    _estado["trabajos"] = []
    p = panel()
    if cmds.workspaceControl(CONTROL, exists=True):
        cmds.deleteUI(CONTROL)
    if p is not None:
        destruir(p)
    _estado["panel"] = None
    _estado["gestor"] = None
    pack.quitar_menu(MENU)
