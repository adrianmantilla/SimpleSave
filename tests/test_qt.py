"""Pruebas sin Maya del panel y los diálogos con Qt sin pantalla.

Necesitan PySide6 (``pip install PySide6-Essentials``); si no está, se saltan.
"""

import json
import os
import shutil
import tempfile
import unittest

from falsos import ServiciosFalsos

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
except ImportError:  # pragma: no cover
    QtWidgets = None

if QtWidgets is not None:
    from simplesave import iconos, qt
    from simplesave.config import Ajustes
    from simplesave.dialogos import DialogoComparar, DialogoNombre, DialogoRecuperar, DialogoRescates
    from simplesave.gestor import Gestor
    from simplesave.panel import FilaVersion, PanelSimpleSave

    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@unittest.skipIf(QtWidgets is None, "PySide6 no está instalado")
class Panel(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.proyecto = os.path.join(self.dir, "Modelado_1")
        os.makedirs(os.path.join(self.proyecto, "scenes"))
        self.s = ServiciosFalsos(self.proyecto)
        self.a = Ajustes(os.path.join(self.dir, "prefs"))
        self.g = Gestor(self.s, self.a)
        self.p = PanelSimpleSave(self.g)
        self._ejecutar = qt.ejecutar
        self.respuesta = None
        qt.ejecutar = self._falso_ejecutar

    def tearDown(self):
        qt.ejecutar = self._ejecutar
        self.p.reloj.stop()
        self.p.deleteLater()
        shutil.rmtree(self.dir)

    def _falso_ejecutar(self, dialogo):
        if isinstance(dialogo, DialogoNombre):
            dialogo.campos["escena"].setText(self.respuesta or "Robot explorador")
            return 1
        return 0

    def filas(self):
        return self.p.contenido.findChildren(FilaVersion)

    def guardar(self, nota=""):
        self.s.cambios = True
        self.p.nota.setText(nota)
        return self.p.guardar_version()

    def test_estado_inicial(self):
        self.assertIn("sin nombre", self.p.etiqueta_escena.text())
        self.assertIn("v001", self.p.boton_guardar.text())
        self.assertFalse(self.p.boton_comparar.isEnabled())
        self.assertIsNotNone(self.p.contenido.findChild(QtWidgets.QLabel, "vacio"))

    def test_guardar_primera_y_siguientes(self):
        self.assertTrue(self.guardar("Bloqueo"))
        self.assertEqual(self.p.etiqueta_escena.text(), "Robot_explorador_v001.ma")
        self.assertIn("v002", self.p.boton_guardar.text())
        self.assertEqual(self.p.nota.text(), "")
        self.assertIn("Guardada", self.p.mensaje.text())
        self.assertTrue(self.guardar("Cabeza"))
        filas = self.filas()
        self.assertEqual([f.version.numero for f in filas], [2, 1])  # la más nueva arriba
        self.assertEqual(filas[1].version.nota, "Bloqueo")
        self.assertTrue(self.p.boton_comparar.isEnabled())

    def test_cancelar_nombre(self):
        qt.ejecutar = lambda d: 0
        self.assertFalse(self.guardar())
        self.assertEqual(self.s.guardadas, [])

    def test_restaurar_desde_fila(self):
        self.guardar("uno")
        self.guardar("dos")
        fila_uno = [f for f in self.filas() if f.version.numero == 1][0]
        fila_uno.findChild(QtWidgets.QPushButton, "restaurar").click()
        self.assertTrue(self.s.ruta.endswith("v003.ma"))
        self.assertEqual(len(self.filas()), 3)
        self.assertIn("v001", self.p.mensaje.text())
        # la fila abierta no tiene «Restaurar»
        abierta = [f for f in self.filas() if f.version.numero == 3][0]
        self.assertIsNone(abierta.findChild(QtWidgets.QPushButton, "restaurar"))

    def test_estado_con_cambios_y_pie(self):
        self.guardar()
        self.s.cambios = False
        self.p.refrescar()
        self.assertIn("sin cambios", self.p.etiqueta_estado.text())
        self.assertIn("nada que guardar", self.p.etiqueta_auto.text())
        self.s.cambios = True
        self.p.refrescar()
        self.assertIn("Cambios sin guardar", self.p.etiqueta_estado.text())
        self.assertIn("próxima copia", self.p.etiqueta_auto.text())
        self.a["autoguardado"] = False
        self.p.refrescar()
        self.assertIn("desactivado", self.p.etiqueta_auto.text())

    def test_ajustes_y_profesor(self):
        self.p.controles["minutos"].setValue(12)
        self.assertEqual(self.a["minutos"], 12)
        with open(os.path.join(self.proyecto, "simplesave.json"), "w") as f:
            json.dump({"minutos": 3, "plantilla": "{apellido}_{escena}"}, f)
        self.g.cargar_proyecto()
        self.p.cargar_ajustes()
        self.assertEqual(self.p.controles["minutos"].value(), 3)
        self.assertFalse(self.p.controles["minutos"].isEnabled())
        self.assertTrue(self.p.controles["copias"].isEnabled())
        self.assertFalse(self.p.aviso_profesor.isHidden())
        self.p.controles["minutos"].setValue(20)  # bloqueado: no cambia nada
        self.assertEqual(self.a["minutos"], 3)

    def test_copia_seguridad_en_pie(self):
        self.a["copia_activada"] = True
        self.a["copia_carpeta"] = os.path.join(self.dir, "USB")
        self.p.refrescar()
        self.assertIn("No encuentro", self.p.etiqueta_copia.text())
        os.makedirs(self.a["copia_carpeta"])
        self.guardar()
        self.assertIn("Copia de seguridad", self.p.etiqueta_copia.text())

    def test_comparar_entregar_limpiar(self):
        self.guardar("uno")
        self.s.objetos_ = ["pCube1", "pTorus1"]
        self.guardar("dos")
        d = self.p.comparar()
        self.assertIsInstance(d, DialogoComparar)
        self.assertIn("1 objetos añadidos", d.resumen.text())
        d.close()
        r = self.p.entregar()
        self.assertTrue(os.path.isfile(r["zip"]))
        for i in range(6):
            self.guardar(str(i))
        self.a["conservar_ultimas"] = 2
        movidas = self.p.limpiar(confirmar=False)
        self.assertEqual(len(movidas), 5)
        self.assertEqual(len(self.filas()), 3)
        self.p.ver_archivadas.setChecked(True)
        self.assertEqual(len(self.filas()), 8)
        self.p.devolver(2)
        self.p.ver_archivadas.setChecked(False)
        self.assertEqual(len(self.filas()), 4)

    def test_nota_e_importante(self):
        self.guardar("uno")
        v = self.filas()[0].version
        self.p.marcar_importante(v, True)
        self.assertTrue(self.filas()[0].version.importante)


@unittest.skipIf(QtWidgets is None, "PySide6 no está instalado")
class Dialogos(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.s = ServiciosFalsos(self.dir)
        self.a = Ajustes(os.path.join(self.dir, "prefs"))
        self.g = Gestor(self.s, self.a)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_nombre_en_vivo(self):
        self.a["plantilla"] = "{asignatura}_{apellido}_{escena}"
        d = DialogoNombre(self.g)
        self.assertFalse(d.aceptar.isEnabled())
        d.campos["asignatura"].setText("MOD1")
        d.campos["apellido"].setText("García Núñez")
        d.campos["escena"].setText("Robot explorador (final)")
        self.assertEqual(d.vista.text(), "MOD1_Garcia_Nunez_Robot_explorador_final_v001.ma")
        self.assertIn("tildes", d.cambios.text())
        self.assertIn("símbolos", d.cambios.text())
        self.assertTrue(d.aceptar.isEnabled())
        self.assertIn("v001", d.aceptar.text())

    def test_valores_fijos_del_profesor(self):
        with open(os.path.join(self.dir, "simplesave.json"), "w") as f:
            json.dump({"plantilla": "{asignatura}_{escena}", "valores": {"asignatura": "MOD2"}}, f)
        self.g.cargar_proyecto()
        d = DialogoNombre(self.g)
        self.assertEqual(d.campos["asignatura"].text(), "MOD2")
        self.assertTrue(d.campos["asignatura"].isReadOnly())

    def test_recuperar_y_rescates(self):
        self.s.cambios = True
        self.g.guardar_version("", {"escena": "casa"})
        copia = self.g.autoguardar()
        d = DialogoRecuperar(copia, self.g.historial().ultima(), "v002")
        d.findChild(QtWidgets.QPushButton, "recuperar").click()
        self.assertEqual(d.eleccion, DialogoRecuperar.RECUPERAR)
        r = DialogoRescates([copia], self.s)
        r._abrir()
        self.assertEqual(r.elegida, copia)

    def test_icono(self):
        ruta = iconos.asegurar_icono(os.path.join(self.dir, "iconos"))
        self.assertTrue(os.path.isfile(ruta))


if __name__ == "__main__":
    unittest.main()
