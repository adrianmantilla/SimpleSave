"""Icono de la estantería, dibujado con Qt la primera vez que hace falta."""

import os

from simplesave.qt import QtCore, QtGui

NOMBRE = "simplesave_32.png"


def dibujar(tamano=32):
    imagen = QtGui.QImage(tamano, tamano, QtGui.QImage.Format_ARGB32)
    imagen.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(imagen)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    escala = tamano / 32.0
    p.scale(escala, escala)
    # Disquete de líneas finas con una «v» de versión.
    p.setPen(QtGui.QPen(QtGui.QColor("#dddddd"), 1.6))
    p.setBrush(QtGui.QColor("#3c4650"))
    p.drawRoundedRect(QtCore.QRectF(4, 4, 24, 24), 3, 3)
    p.setBrush(QtGui.QColor("#dddddd"))
    p.drawRect(QtCore.QRectF(10, 4.8, 12, 6))
    p.setPen(QtGui.QPen(QtGui.QColor("#6aa6cc"), 2.4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
    camino = QtGui.QPainterPath()
    camino.moveTo(11, 15.5)
    camino.lineTo(16, 23.5)
    camino.lineTo(21, 15.5)
    p.drawPath(camino)
    p.end()
    return imagen


def asegurar_icono(carpeta):
    ruta = os.path.join(carpeta, NOMBRE)
    if not os.path.isfile(ruta):
        os.makedirs(carpeta, exist_ok=True)
        dibujar().save(ruta)
    return ruta.replace("\\", "/")
