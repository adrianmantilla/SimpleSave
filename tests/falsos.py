"""Servicios de mentira para probar SimpleSave sin Maya."""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

from simplesave.servicios import Servicios  # noqa: E402


class ServiciosFalsos(Servicios):
    en_maya = True

    def __init__(self, proyecto):
        self._proyecto = proyecto
        self.ruta = ""
        self.cambios = False
        self.objetos_ = ["pCube1", "pSphere1"]
        self.caras_ = 406
        self.texturas_ = []
        self.abiertas = []
        self.guardadas = []
        self.copias = []
        self.cancelar = False
        self.fallar_guardado = False
        self.reproduce = False
        self.rescate = []
        self.avisos = []

    def escena_actual(self):
        return self.ruta

    def proyecto(self):
        return self._proyecto

    def modificada(self):
        return self.cambios

    def _escribir(self, ruta, formato):
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "wb") as f:
            if formato == "mb":
                f.write(b"FOR4" + b"\0" * 60)
            else:
                f.write(("//Maya ASCII 2027 scene\n" + "".join(
                    'createNode transform -n "{}";\n'.format(o) for o in self.objetos_)).encode())

    def guardar_como(self, ruta, formato):
        if self.fallar_guardado:
            with open(ruta, "wb") as f:
                f.write(b"//Ma")
            raise IOError("disco lleno")
        self._escribir(ruta, formato)
        self.ruta = ruta
        self.cambios = False
        self.guardadas.append(ruta)

    def guardar_copia(self, ruta, formato):
        self._escribir(ruta, formato)
        self.copias.append(ruta)

    def abrir(self, ruta, preguntar=True):
        if preguntar and self.cancelar:
            return False
        self.ruta = ruta
        self.cambios = False
        self.abiertas.append(ruta)
        return True

    def confirmar_cerrar(self):
        return not self.cancelar

    def capturar_miniatura(self, ruta):
        with open(ruta, "wb") as f:
            f.write(b"\xff\xd8\xff")
        return True

    def objetos(self):
        return list(self.objetos_)

    def caras(self):
        return self.caras_

    def texturas(self):
        return list(self.texturas_)

    def reproduciendo(self):
        return self.reproduce

    def carpetas_rescate(self):
        return list(self.rescate)

    def aviso(self, texto):
        self.avisos.append(texto)
