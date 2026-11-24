"""Pruebas sin Maya: nombres, historial, autoguardado, recuperación, entrega, limpieza."""

import json
import os
import shutil
import tempfile
import time
import unittest
import zipfile

from falsos import ServiciosFalsos

from simplesave import autoguardado, comparar, nombres
from simplesave.archivos import verificar_escena
from simplesave.config import Ajustes
from simplesave.gestor import ErrorGuardado, Gestor
from simplesave.historial import Historial


class Nombres(unittest.TestCase):
    def test_limpiar(self):
        self.assertEqual(nombres.limpiar("García Núñez")[0], "Garcia_Nunez")
        self.assertEqual(nombres.limpiar("Robot explorador (final)!")[0], "Robot_explorador_final")
        self.assertEqual(nombres.limpiar("  a  b  ")[0], "a_b")
        self.assertEqual(nombres.limpiar("con")[0], "con_")
        self.assertEqual(sorted(nombres.limpiar("Él (1)")[1]), ["espacios", "simbolos", "tildes"])
        self.assertEqual(nombres.limpiar("robot")[1], [])

    def test_plantilla(self):
        self.assertEqual(nombres.campos("{asignatura}_{apellido}_{escena}"), ["asignatura", "apellido", "escena"])
        self.assertEqual(nombres.campos("{apellido}"), ["apellido", "escena"])
        base, cambios, faltan = nombres.nombre_desde_campos(
            "{asignatura}_{apellido}_{escena}", {"asignatura": "MOD1", "apellido": "García", "escena": "mi robot"})
        self.assertEqual(base, "MOD1_Garcia_mi_robot")
        self.assertIn(("apellido", "tildes"), cambios)
        self.assertEqual(faltan, [])
        base, _, faltan = nombres.nombre_desde_campos("{apellido}_{escena}", {"escena": "robot"})
        self.assertEqual(base, "robot")
        self.assertEqual(faltan, ["apellido"])

    def test_separar_y_siguiente(self):
        self.assertEqual(nombres.separar("/x/robot_v004.ma"), ("robot", 4, ".ma"))
        self.assertEqual(nombres.separar("/x/robot_v2.ma"), ("robot_v2", None, ".ma"))
        self.assertEqual(nombres.separar("/x/robot_v1000.mb"), ("robot", 1000, ".mb"))
        self.assertEqual(nombres.separar("/x/robot.ma"), ("robot", None, ".ma"))
        self.assertEqual(nombres.archivo_version("robot", 7), "robot_v007.ma")
        d = tempfile.mkdtemp()
        try:
            for n in ("robot_v001.ma", "robot_v003.mb", "otro_v009.ma", "robot_v002.txt"):
                open(os.path.join(d, n), "w").close()
            self.assertEqual(nombres.siguiente(d, "robot"), 4)
            self.assertEqual(sorted(nombres.versiones_en(d, "robot")), [1, 3])
            self.assertEqual(nombres.siguiente(d, "nuevo"), 1)
        finally:
            shutil.rmtree(d)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.proyecto = os.path.join(self.dir, "Modelado_1")
        os.makedirs(os.path.join(self.proyecto, "scenes"))
        self.s = ServiciosFalsos(self.proyecto)
        self.a = Ajustes(os.path.join(self.dir, "prefs"))
        self.g = Gestor(self.s, self.a)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def primera(self, nota="Bloqueo"):
        self.s.cambios = True
        return self.g.guardar_version(nota, {"escena": "Robot explorador"})


class Versiones(Base):
    def test_primera_version_con_nombre(self):
        with self.assertRaises(ErrorGuardado):
            self.g.guardar_version("x")
        r = self.primera()
        esperado = os.path.join(self.proyecto, "scenes", "Robot_explorador", "Robot_explorador_v001.ma")
        self.assertEqual(r.ruta, esperado)
        self.assertEqual(r.numero, 1)
        self.assertTrue(verificar_escena(esperado))
        v = self.g.historial().versiones()[0]
        self.assertEqual(v.nota, "Bloqueo")
        self.assertEqual(v.objetos, ["pCube1", "pSphere1"])
        self.assertEqual(v.caras, 406)
        self.assertTrue(v.miniatura.endswith("v001.jpg"))

    def test_siguientes_y_nunca_pisa(self):
        self.primera()
        r2 = self.g.guardar_version("Cabeza")
        self.assertTrue(r2.ruta.endswith("Robot_explorador_v002.ma"))
        # alguien deja un v003 a mano: la siguiente salta a v004
        open(r2.ruta.replace("v002", "v003"), "w").write("//Maya ASCII")
        r = self.g.guardar_version("")
        self.assertTrue(r.ruta.endswith("v004.ma"))
        self.assertEqual([v.numero for v in self.g.historial().versiones()], [1, 2, 3, 4])

    def test_escena_con_nombre_sin_numero(self):
        ruta = os.path.join(self.proyecto, "scenes", "casa.ma")
        self.s._escribir(ruta, "ma")
        self.s.ruta = ruta
        r = self.g.guardar_version("primera")
        self.assertEqual(r.ruta, os.path.join(self.proyecto, "scenes", "casa_v001.ma"))

    def test_formato_mb(self):
        self.a["formato"] = "mb"
        r = self.primera()
        self.assertTrue(r.ruta.endswith(".mb"))
        self.assertTrue(verificar_escena(r.ruta))

    def test_fallo_al_guardar_no_deja_basura(self):
        self.primera()
        self.s.fallar_guardado = True
        with self.assertRaises(ErrorGuardado):
            self.g.guardar_version("x")
        self.assertEqual([v.numero for v in self.g.historial().versiones()], [1])

    def test_recuerda_campos(self):
        self.a["plantilla"] = "{apellido}_{escena}"
        self.s.cambios = True
        with self.assertRaises(ErrorGuardado):
            self.g.guardar_version("", {"escena": "robot"})
        r = self.g.guardar_version("", {"apellido": "Pérez", "escena": "robot"})
        self.assertTrue(r.ruta.endswith("Perez_robot_v001.ma"))
        self.assertEqual(self.g.valores_iniciales()["apellido"], "Pérez")

    def test_restaurar(self):
        self.primera()
        self.s.objetos_ = ["pCube1"]
        self.g.guardar_version("dos")
        r = self.g.restaurar(1)
        self.assertTrue(r.ruta.endswith("v003.ma"))
        self.assertEqual(self.s.ruta, r.ruta)
        v3 = self.g.historial().version(3)
        self.assertEqual(v3.origen, 1)
        self.assertIn("v001", v3.nota)
        self.assertTrue(v3.miniatura)
        self.assertEqual(len(self.g.historial().versiones()), 3)
        # si el alumno cancela al preguntarle por los cambios, no se crea nada
        self.s.cancelar = True
        self.assertIsNone(self.g.restaurar(2))
        self.assertEqual(len(self.g.historial().versiones()), 3)

    def test_nota_e_importante(self):
        self.primera()
        self.g.cambiar_nota(1, " otra nota ")
        self.g.marcar_importante(1)
        v = self.g.historial().version(1)
        self.assertEqual(v.nota, "otra nota")
        self.assertTrue(v.importante)


class Autoguardado(Base):
    def test_planificador(self):
        p = autoguardado.Planificador(ahora=0)
        self.assertFalse(p.toca(5, True, ahora=200))
        self.assertFalse(p.toca(5, True, ahora=301))  # sin señal de cambio aún
        p.hubo_cambio()
        self.assertTrue(p.toca(5, True, ahora=301))
        self.assertFalse(p.toca(5, False, ahora=301))  # escena sin cambios
        self.assertFalse(p.toca(5, True, reproduciendo=True, ahora=301))
        self.assertTrue(p.toca(5, True, reproduciendo=True, ahora=301, pausa_reproduccion=False))
        p.reiniciar(ahora=301)
        self.assertFalse(p.toca(5, True, ahora=700))
        self.assertTrue(p.toca(5, True, ahora=301 + 900))  # con cambios y 3 intervalos: guarda igual

    def test_autoguardar_rota_y_no_cambia_escena(self):
        self.primera()
        self.a["copias"] = 3
        rutas = []
        for i in range(5):
            ruta = self.g.autoguardar()
            self.assertIsNotNone(ruta)
            t = time.time() - 100 + i
            os.utime(ruta, (t, t))
            rutas.append(ruta)
        h = self.g.historial()
        quedan = autoguardado.copias(h.carpeta_autoguardado, h.base)
        self.assertEqual(len(quedan), 3)
        self.assertEqual(quedan[0], rutas[-1])
        self.assertTrue(self.s.ruta.endswith("v001.ma"))
        self.assertTrue(all("_auto_" in os.path.basename(r) for r in quedan))
        # las copias no cuentan como versiones
        self.assertEqual(len(h.versiones()), 1)

    def test_sin_titulo(self):
        ruta = self.g.autoguardar()
        self.assertIn(os.path.join("scenes", ".simplesave", "sin_titulo"), ruta)
        self.assertIn(ruta, self.g.rescates())
        self.g.olvidar_rescates([ruta])
        self.assertNotIn(ruta, self.g.rescates())

    def test_toca_autoguardar_respeta_ajustes(self):
        self.s.cambios = True
        self.g.planificador.reiniciar(ahora=0)
        self.g.planificador.hubo_cambio()
        self.assertTrue(self.g.toca_autoguardar(ahora=10000))
        self.a["autoguardado"] = False
        self.assertFalse(self.g.toca_autoguardar(ahora=10000))

    def test_recuperable(self):
        self.primera()
        h = self.g.historial()
        self.assertIsNone(self.g.recuperable())
        copia = self.g.autoguardar()
        futuro = time.time() + 60
        os.utime(copia, (futuro, futuro))
        self.assertEqual(self.g.recuperable(), copia)
        r = self.g.recuperar(copia)
        self.assertTrue(r.ruta.endswith("v002.ma"))
        self.assertIn("autoguardado", h.version(2).nota)
        self.assertEqual(self.s.ruta, r.ruta)

    def test_rescates_de_maya(self):
        tmp = os.path.join(self.dir, "tmp")
        os.makedirs(tmp)
        bueno = os.path.join(tmp, "alumno.20261124.1942.ma")
        viejo = os.path.join(tmp, "alumno.20261001.1000.ma")
        for r in (bueno, viejo, os.path.join(tmp, "otra_cosa.ma")):
            open(r, "w").write("//Maya ASCII")
        antiguo = time.time() - 30 * 86400
        os.utime(viejo, (antiguo, antiguo))
        self.s.rescate = [tmp, tmp]
        self.assertEqual(self.g.rescates(), [bueno])

    def test_rescate_abierto_pide_nombre(self):
        tmp = os.path.join(self.dir, "tmp")
        os.makedirs(tmp)
        rescate = os.path.join(tmp, "alumno.20261124.1942.ma")
        open(rescate, "w").write("//Maya ASCII")
        self.s.rescate = [tmp]
        self.assertTrue(self.g.abrir_rescate(rescate))
        self.assertTrue(self.g.sin_nombre())
        self.assertIsNone(self.g.historial())
        with self.assertRaises(ErrorGuardado):
            self.g.guardar_version("")
        r = self.g.guardar_version("rescatado", {"escena": "robot"})
        self.assertEqual(r.ruta, os.path.join(self.proyecto, "scenes", "robot", "robot_v001.ma"))
        # una copia automática abierta a mano tampoco cuenta como escena
        copia = self.g.autoguardar()
        self.s.ruta = copia
        self.assertTrue(self.g.sin_nombre())

    def test_aviso(self):
        self.a["aviso_minutos"] = 30
        self.s.cambios = True
        ahora = time.time()
        self.assertFalse(self.g.toca_aviso(ahora + 60))
        self.assertTrue(self.g.toca_aviso(ahora + 31 * 60))
        self.assertFalse(self.g.toca_aviso(ahora + 32 * 60))  # no repite enseguida


class Profesor(Base):
    def test_profesor_manda(self):
        with open(os.path.join(self.proyecto, "simplesave.json"), "w", encoding="utf-8") as f:
            json.dump({"plantilla": "{asignatura}_{apellido}_{escena}", "valores": {"asignatura": "MOD1"},
                       "minutos": 2, "copias": 999, "otra": 1}, f)
        self.a["minutos"] = 15
        self.g.cargar_proyecto()
        self.assertEqual(self.a["minutos"], 2)
        self.assertEqual(self.a["copias"], 50)  # limitado
        self.assertTrue(self.a.bloqueado("minutos"))
        self.assertFalse(self.a.bloqueado("formato"))
        self.assertEqual(self.g.valores_iniciales()["asignatura"], "MOD1")
        ruta, base, _, faltan = self.g.ruta_primera({"asignatura": "MOD1", "apellido": "Ruiz", "escena": "casa"})
        self.assertEqual(base, "MOD1_Ruiz_casa")
        self.assertEqual(faltan, [])

    def test_json_roto(self):
        with open(os.path.join(self.proyecto, "simplesave.json"), "w") as f:
            f.write("{ roto")
        self.g.cargar_proyecto()
        self.assertEqual(self.a["minutos"], 5)


class CopiaSeguridad(Base):
    def test_copia(self):
        usb = os.path.join(self.dir, "USB")
        os.makedirs(usb)
        self.a["copia_activada"] = True
        self.a["copia_carpeta"] = usb
        r = self.primera()
        self.assertEqual(r.avisos, [])
        self.assertTrue(os.path.isfile(os.path.join(usb, "Modelado_1", "Robot_explorador", "Robot_explorador_v001.ma")))
        shutil.rmtree(usb)  # quitan el USB
        r = self.g.guardar_version("dos")
        self.assertEqual(len(r.avisos), 1)
        self.assertTrue(os.path.isfile(r.ruta))


class V2(Base):
    def test_comparar(self):
        self.primera()
        self.s.objetos_ = ["pCube1", "pTorus1"]
        self.s.caras_ = 800
        self.g.guardar_version("dos")
        d = self.g.comparar(1, 2)
        self.assertEqual(d["anadidos"], ["pTorus1"])
        self.assertEqual(d["borrados"], ["pSphere1"])
        self.assertEqual((d["caras_a"], d["caras_b"]), (406, 800))

    def test_comparar_lee_ma_sin_historial(self):
        ruta = os.path.join(self.dir, "x_v001.ma")
        with open(ruta, "w") as f:
            f.write('//Maya ASCII\ncreateNode transform -s -n "persp";\ncreateNode transform -n "pCube1";\n'
                    'createNode transform -n "brazo" -p "pCube1";\n')
        self.assertEqual(comparar.objetos_de_ma(ruta), ["pCube1", "pCube1|brazo"])

    def test_limpiar(self):
        self.primera()
        for i in range(7):
            self.g.guardar_version(str(i))
        self.g.marcar_importante(3)
        self.a["conservar_ultimas"] = 2
        apartar = [v.numero for v in self.g.que_limpiar()]
        self.assertEqual(apartar, [2, 4, 5, 6])
        self.g.limpiar()
        h = self.g.historial()
        self.assertEqual([v.numero for v in h.versiones()], [1, 3, 7, 8])
        self.assertEqual(len(h.versiones(incluir_archivadas=True)), 8)
        self.assertEqual(h.siguiente(), 9)
        self.g.devolver(4)
        self.assertEqual([v.numero for v in h.versiones()], [1, 3, 4, 7, 8])

    def test_entrega(self):
        tex = os.path.join(self.proyecto, "sourceimages", "robot")
        os.makedirs(tex)
        for n in ("color.1001.png", "color.1002.png", "rugosidad.png"):
            open(os.path.join(tex, n), "wb").write(b"png")
        fuera = os.path.join(self.dir, "descargas", "hdri.exr")
        os.makedirs(os.path.dirname(fuera))
        open(fuera, "wb").write(b"exr")
        self.s.texturas_ = [os.path.join(tex, "color.<UDIM>.png"), os.path.join(tex, "rugosidad.png"), fuera,
                            os.path.join(tex, "no_existe.png")]
        self.primera()
        self.g.guardar_version("final")
        r = self.g.entregar()
        self.assertTrue(r["escena"].endswith(os.path.join("entregas", "Robot_explorador_entrega.ma")))
        with zipfile.ZipFile(r["zip"]) as z:
            nombres_zip = set(z.namelist())
        self.assertIn("Robot_explorador/scenes/Robot_explorador_v002.ma", nombres_zip)
        self.assertIn("Robot_explorador/workspace.mel", nombres_zip)
        self.assertIn("Robot_explorador/sourceimages/robot/color.1002.png", nombres_zip)
        self.assertIn("Robot_explorador/sourceimages/externas/hdri.exr", nombres_zip)
        self.assertEqual(r["texturas"], 4)
        self.assertEqual(r["externas"], [fuera])
        self.assertEqual(len(r["faltan"]), 1)


class HistorialSuelto(unittest.TestCase):
    def test_versiones_sin_json(self):
        d = tempfile.mkdtemp()
        try:
            for n in ("a_v001.ma", "a_v002.ma"):
                open(os.path.join(d, n), "w").write("//Maya ASCII")
            h = Historial(d, "a")
            self.assertEqual([v.numero for v in h.versiones()], [1, 2])
            self.assertTrue(h.versiones()[0].fecha)
            self.assertEqual(h.siguiente(), 3)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
