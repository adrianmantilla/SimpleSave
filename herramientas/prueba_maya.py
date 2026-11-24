"""Prueba de SimpleSave dentro de Maya, sin interfaz (herramienta de desarrollo).

Desde la terminal, con el mayapy de cada versión:

    /Applications/Autodesk/maya2027/Maya.app/Contents/bin/mayapy herramientas/prueba_maya.py
    "C:\\Program Files\\Autodesk\\Maya2027\\bin\\mayapy.exe" herramientas\\prueba_maya.py

No toca tus preferencias de Maya ni tus proyectos: trabaja en una carpeta
temporal. Comprueba que el plugin carga, guardar versión, que el autoguardado
no cambia el nombre de la escena ni borra el aviso de cambios, el autoguardado
de una escena sin nombre, restaurar, recuperar, comparar, .mb, entrega y limpiar.
El panel, la miniatura del visor, el atajo y la estantería necesitan la interfaz:
pruébalos abriendo Maya normalmente.
Termina con «RESULTADO: OK» o con la lista de fallos.
"""

import os
import shutil
import sys
import tempfile
import time
import traceback
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

fallos = []


def comprobar(condicion, texto):
    print(("  ok    " if condicion else "  FALLO ") + texto)
    if not condicion:
        fallos.append(texto)


def main():
    import maya.standalone
    maya.standalone.initialize(name="python")
    from maya import cmds

    print("Maya", cmds.about(version=True), "-", cmds.about(operatingSystem=True))
    cmds.loadPlugin(os.path.join(RAIZ, "plug-ins", "simplesave_plugin.py"))
    comprobar(cmds.pluginInfo("simplesave_plugin", query=True, loaded=True), "el plugin se carga")
    from simplesave import interfaz_maya
    interfaz_maya.iniciar()
    for nombre in interfaz_maya.COMANDOS:
        comprobar(cmds.runTimeCommand(nombre, exists=True), "existe la orden " + nombre)

    from simplesave import autoguardado
    from simplesave.archivos import verificar_escena
    from simplesave.config import Ajustes
    from simplesave.gestor import Gestor
    from simplesave.maya_servicios import ServiciosMaya

    temporal = tempfile.mkdtemp()
    try:
        proyecto = os.path.join(temporal, "Modelado_1")
        os.makedirs(os.path.join(proyecto, "scenes"))
        os.makedirs(os.path.join(proyecto, "sourceimages"))
        with open(os.path.join(proyecto, "workspace.mel"), "w") as f:
            f.write('workspace -fr "scene" "scenes";\nworkspace -fr "sourceImages" "sourceimages";\n')
        cmds.workspace(proyecto, openWorkspace=True)
        s = ServiciosMaya()
        comprobar(os.path.normcase(os.path.realpath(s.proyecto())) == os.path.normcase(os.path.realpath(proyecto)),
                  "proyecto activo")
        a = Ajustes(os.path.join(temporal, "prefs"))
        g = Gestor(s, a)

        # --- escena sin nombre: autoguardado por exportación ---
        cmds.file(new=True, force=True)
        cmds.polyCube(name="cubo")
        comprobar(s.modificada(), "crear un cubo marca cambios")
        copia = g.autoguardar()
        comprobar(bool(copia) and verificar_escena(copia), "autoguardado de escena sin nombre")
        comprobar(s.escena_actual() == "", "la escena sigue sin nombre tras el autoguardado")
        comprobar(s.modificada(), "sigue marcada con cambios")
        comprobar(copia in g.rescates(), "la copia sin nombre aparece para rescatar")

        # --- primera versión ---
        r = g.guardar_version("Bloqueo", {"escena": "Robot explorador"})
        esperado = os.path.join(proyecto, "scenes", "Robot_explorador", "Robot_explorador_v001.ma")
        comprobar(os.path.normcase(r.ruta) == os.path.normcase(esperado), "v001 en scenes/Robot_explorador")
        comprobar(os.path.normcase(os.path.realpath(s.escena_actual())) == os.path.normcase(os.path.realpath(esperado)),
                  "la escena abierta es v001")
        comprobar(not s.modificada(), "sin cambios tras guardar versión")
        comprobar(verificar_escena(r.ruta), "v001 es un .ma válido")
        v1 = g.historial().version(1)
        comprobar(v1 is not None and "cubo" in (v1.objetos or []), "objetos apuntados en el historial")
        comprobar(v1 is not None and v1.caras == 6, "caras apuntadas ({})".format(v1.caras if v1 else "?"))
        comprobar(not g.copias_sin_titulo(), "las copias de cuando no tenía nombre se limpian")

        # --- autoguardado de escena con nombre ---
        cmds.polySphere(name="cabeza")
        comprobar(s.modificada(), "crear una esfera marca cambios")
        copia = g.autoguardar()
        comprobar(bool(copia) and verificar_escena(copia), "copia automática escrita")
        comprobar(copia and "_auto_" in os.path.basename(copia) and ".simplesave" in copia,
                  "la copia va a .simplesave/…/autoguardado")
        comprobar(os.path.normcase(os.path.realpath(s.escena_actual())) == os.path.normcase(os.path.realpath(esperado)),
                  "el nombre de la escena no cambia al autoguardar")
        comprobar(s.modificada(), "Maya sigue avisando de cambios tras autoguardar")
        comprobar(len(g.historial().versiones()) == 1, "la copia no cuenta como versión")
        time.sleep(1.2)
        os.utime(copia, None)
        comprobar(g.recuperable() == copia, "la copia es recuperable (más nueva que v001)")

        # --- segunda versión, .mb ---
        a["formato"] = "mb"
        r2 = g.guardar_version("Cabeza")
        comprobar(r2.ruta.endswith("Robot_explorador_v002.mb") and verificar_escena(r2.ruta), "v002 en .mb")
        a["formato"] = "ma"
        comprobar(g.recuperable() is None, "tras guardar versión ya no hay nada que recuperar")

        # --- comparar ---
        d = g.comparar(1, 2)
        comprobar("cabeza" in d["anadidos"], "comparar: la esfera aparece como añadida")
        comprobar(d["caras_b"] > d["caras_a"], "comparar: más caras en v002")

        # --- restaurar v001 ---
        r3 = g.restaurar(1)
        comprobar(r3 is not None and r3.ruta.endswith("v003.ma"), "restaurar v001 crea v003")
        comprobar(cmds.objExists("cubo") and not cmds.objExists("cabeza"), "v003 tiene lo de v001")
        comprobar(os.path.normcase(os.path.realpath(s.escena_actual())) == os.path.normcase(os.path.realpath(r3.ruta)),
                  "v003 queda abierta")

        # --- recuperar una copia ---
        cmds.polyTorus(name="rueda")
        copia = g.autoguardar()
        time.sleep(1.2)
        os.utime(copia, None)
        cmds.file(modified=False)  # para no preguntar en modo sin interfaz
        r4 = g.recuperar(copia)
        comprobar(r4 is not None and r4.ruta.endswith("v004.ma"), "recuperar crea v004")
        comprobar(cmds.objExists("rueda"), "v004 tiene lo del autoguardado")

        # --- rotación ---
        a["copias"] = 2
        for _ in range(4):
            cmds.polyCube()
            g.autoguardar()
            time.sleep(1.05)
        h = g.historial()
        comprobar(len(autoguardado.copias(h.carpeta_autoguardado, h.base)) == 2, "se guardan solo 2 copias")

        # --- texturas y entrega ---
        textura = os.path.join(proyecto, "sourceimages", "madera.png")
        with open(textura, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
        nodo = cmds.shadingNode("file", asTexture=True)
        cmds.setAttr(nodo + ".fileTextureName", textura, type="string")
        comprobar(any(os.path.normcase(os.path.realpath(t)) == os.path.normcase(os.path.realpath(textura))
                      for t in s.texturas()), "encuentra la textura de un nodo file")
        g.guardar_version("con textura")
        e = g.entregar()
        with zipfile.ZipFile(e["zip"]) as z:
            contenido = z.namelist()
        comprobar(any(n.endswith("sourceimages/madera.png") for n in contenido), "la entrega lleva la textura")
        comprobar(os.path.isfile(e["escena"]), "copia de entrega")

        # --- limpiar ---
        a["conservar_ultimas"] = 1
        movidas = g.limpiar()
        comprobar(len(movidas) >= 1 and all(os.path.isfile(m) for m in movidas), "limpiar aparta versiones")
        comprobar(g.historial().siguiente() == 6, "tras limpiar la numeración sigue (v006)")
    except Exception:
        traceback.print_exc()
        fallos.append("excepción")
    finally:
        shutil.rmtree(temporal, ignore_errors=True)

    print()
    if fallos:
        print("RESULTADO: {} FALLOS".format(len(fallos)))
        for f in fallos:
            print("  - " + f)
    else:
        print("RESULTADO: OK")
    try:
        maya.standalone.uninitialize()
    except Exception:
        pass
    os._exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
