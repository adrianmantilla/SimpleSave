"""Ventanas pequeñas: nombre la primera vez, recuperar, comparar, nota."""

import datetime
import os

from simplesave import nombres
from simplesave.archivos import tamano_legible
from simplesave import estilo
from simplesave.i18n import t
from simplesave.qt import QtCore, QtGui, QtWidgets

Qt = QtCore.Qt
MONO = "font-family: Menlo, Consolas, 'DejaVu Sans Mono', monospace;"
COLOR_OK = "#7fc79a"
COLOR_AVISO = "#e8b45a"
COLOR_MAL = "#e07b6a"
COLOR_TENUE = "#9a9a9a"


def boton_principal(texto):
    b = QtWidgets.QPushButton(texto)
    estilo.primario(b)
    b.setDefault(True)
    return b


def miniatura(ruta, ancho=96, alto=54):
    etiqueta = QtWidgets.QLabel()
    etiqueta.setFixedSize(ancho, alto)
    etiqueta.setAlignment(Qt.AlignCenter)
    etiqueta.setStyleSheet("background:#2b2e31;border-radius:2px;color:#666")
    poner_miniatura(etiqueta, ruta)
    return etiqueta


def poner_miniatura(etiqueta, ruta):
    imagen = QtGui.QPixmap(ruta) if ruta and os.path.isfile(ruta) else QtGui.QPixmap()
    if imagen.isNull():
        etiqueta.setPixmap(QtGui.QPixmap())
        etiqueta.setText("—")
    else:
        etiqueta.setText("")
        etiqueta.setPixmap(imagen.scaled(etiqueta.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))


# --- Nombre la primera vez --------------------------------------------------------------------

class DialogoNombre(QtWidgets.QDialog):
    """Pide las piezas de la plantilla y enseña cómo quedará el archivo."""

    def __init__(self, gestor, nota="", padre=None):
        super(DialogoNombre, self).__init__(padre)
        estilo.aplicar(self, "SimpleSaveNombre")
        self.gestor = gestor
        self.setWindowTitle(t("nombre_titulo"))
        self.setMinimumWidth(440)
        plantilla = gestor.plantilla()
        fijos = gestor.ajustes.valores_fijos()
        iniciales = gestor.valores_iniciales()
        lay = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(t("nombre_intro"))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QtWidgets.QFormLayout()
        self.campos = {}
        for campo in nombres.campos(plantilla):
            edit = QtWidgets.QLineEdit(iniciales.get(campo, ""))
            edit.setObjectName("campo_" + campo)
            edit.setPlaceholderText(t("campo_ayuda_" + campo) if t("campo_ayuda_" + campo) != "campo_ayuda_" + campo
                                    else "")
            if campo in fijos:
                edit.setText(str(fijos[campo]))
                edit.setReadOnly(True)
                edit.setToolTip(t("fijado_profesor"))
            edit.textChanged.connect(self._actualizar)
            etiqueta = t("campo_" + campo)
            if etiqueta == "campo_" + campo:
                etiqueta = campo.replace("_", " ").capitalize()
            form.addRow(etiqueta, edit)
            self.campos[campo] = edit
        lay.addLayout(form)
        self.nota = QtWidgets.QLineEdit(nota)
        self.nota.setPlaceholderText(t("nota_ayuda"))
        form.addRow(t("nota"), self.nota)
        self.vista = QtWidgets.QLabel()
        self.vista.setObjectName("vista")
        self.vista.setWordWrap(True)
        self.vista.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.vista.setStyleSheet("background:#2b2b2b;padding:8px 10px;border-radius:3px;font-size:13px;" + MONO)
        lay.addWidget(self.vista)
        self.cambios = QtWidgets.QLabel()
        self.cambios.setObjectName("cambios")
        self.cambios.setWordWrap(True)
        lay.addWidget(self.cambios)
        self.donde = QtWidgets.QLabel()
        self.donde.setWordWrap(True)
        self.donde.setStyleSheet("color:{}".format(COLOR_TENUE))
        lay.addWidget(self.donde)
        botones = QtWidgets.QHBoxLayout()
        botones.addStretch(1)
        cancelar = QtWidgets.QPushButton(t("cancelar"))
        cancelar.clicked.connect(self.reject)
        self.aceptar = boton_principal(t("guardar_v001"))
        self.aceptar.clicked.connect(self.accept)
        botones.addWidget(cancelar)
        botones.addWidget(self.aceptar)
        lay.addLayout(botones)
        self._actualizar()
        primero = next((e for e in self.campos.values() if not e.isReadOnly() and not e.text()), None)
        (primero or self.campos["escena"]).setFocus()

    def valores(self):
        return {campo: edit.text() for campo, edit in self.campos.items()}

    def _actualizar(self, *_):
        ruta, base, cambios, faltan = self.gestor.ruta_primera(self.valores())
        if base:
            archivo = os.path.basename(ruta)
            self.vista.setText(archivo)
        else:
            self.vista.setText("…")
        lineas = []
        for campo, clave in cambios:
            lineas.append('<span style="color:{}">{}</span>'.format(
                COLOR_AVISO, t("limpieza_" + clave, campo=t("campo_" + campo) if t("campo_" + campo) != "campo_" + campo
                               else campo)))
        if faltan:
            nombres_ = [t("campo_" + f) if t("campo_" + f) != "campo_" + f else f for f in faltan]
            lineas.append('<span style="color:{}">{}</span>'.format(COLOR_MAL, t("faltan", campos=", ".join(nombres_))))
        if not lineas:
            lineas.append('<span style="color:{}">{}</span>'.format(COLOR_OK, t("nombre_valido")))
        self.cambios.setText("<br>".join(lineas))
        if ruta:
            self.donde.setText(t("se_guarda_en", carpeta=os.path.dirname(ruta)))
            self.aceptar.setText(t("guardar_version_n", version=nombres.etiqueta(nombres.separar(ruta)[1])))
        else:
            self.donde.setText("")
        self.aceptar.setEnabled(bool(base) and not faltan)


# --- Recuperar ----------------------------------------------------------------------------------

def _hora_archivo(ruta):
    try:
        momento = datetime.datetime.fromtimestamp(os.path.getmtime(ruta))
    except OSError:
        return "?"
    if momento.date() == datetime.date.today():
        return t("hoy_a_las", hora=momento.strftime("%H:%M"))
    return momento.strftime("%d/%m/%Y %H:%M")


class DialogoRecuperar(QtWidgets.QDialog):
    """Hay una copia automática más nueva que la última versión de esta escena."""
    RECUPERAR, ABRIR, NADA = 1, 2, 0

    def __init__(self, copia, ultima, siguiente, padre=None):
        super(DialogoRecuperar, self).__init__(padre)
        estilo.aplicar(self, "SimpleSaveRecuperar")
        self.setWindowTitle(t("recuperar_titulo"))
        self.eleccion = self.NADA
        lay = QtWidgets.QVBoxLayout(self)
        texto = QtWidgets.QLabel(t("recuperar_texto", hora=_hora_archivo(copia),
                                   version=ultima.etiqueta if ultima else "—",
                                   hora_version=_hora_archivo(ultima.ruta) if ultima else "—"))
        texto.setWordWrap(True)
        lay.addWidget(texto)
        nota = QtWidgets.QLabel(t("recuperar_nota", nueva=siguiente, version=ultima.etiqueta if ultima else "—"))
        nota.setWordWrap(True)
        nota.setStyleSheet("color:{}".format(COLOR_TENUE))
        lay.addWidget(nota)
        botones = QtWidgets.QHBoxLayout()
        botones.addStretch(1)
        ahora_no = QtWidgets.QPushButton(t("ahora_no"))
        ahora_no.clicked.connect(self.reject)
        botones.addWidget(ahora_no)
        recuperar = boton_principal(t("recuperar_como", version=siguiente))
        recuperar.setObjectName("recuperar")
        recuperar.clicked.connect(lambda: self._elegir(self.RECUPERAR))
        botones.addWidget(recuperar)
        lay.addLayout(botones)
        self.setMinimumWidth(420)

    def _elegir(self, valor):
        self.eleccion = valor
        self.accept()


class DialogoRescates(QtWidgets.QDialog):
    """Copias de emergencia de Maya y de escenas sin nombre."""

    def __init__(self, rutas, servicios, padre=None):
        super(DialogoRescates, self).__init__(padre)
        estilo.aplicar(self, "SimpleSaveRescates")
        self.setWindowTitle(t("rescates_titulo"))
        self.servicios = servicios
        self.elegida = None
        lay = QtWidgets.QVBoxLayout(self)
        texto = QtWidgets.QLabel(t("rescates_texto"))
        texto.setWordWrap(True)
        lay.addWidget(texto)
        self.lista = QtWidgets.QListWidget()
        for ruta in rutas:
            item = QtWidgets.QListWidgetItem("{}   ·   {}   ·   {}".format(
                _hora_archivo(ruta), os.path.basename(ruta), tamano_legible(os.path.getsize(ruta))))
            item.setData(Qt.UserRole, ruta)
            item.setToolTip(ruta)
            self.lista.addItem(item)
        self.lista.setCurrentRow(0)
        self.lista.itemDoubleClicked.connect(lambda *_: self._abrir())
        lay.addWidget(self.lista)
        botones = QtWidgets.QHBoxLayout()
        carpeta = QtWidgets.QPushButton(t("mostrar_carpeta"))
        carpeta.clicked.connect(self._carpeta)
        botones.addWidget(carpeta)
        botones.addStretch(1)
        olvidar = QtWidgets.QPushButton(t("olvidar"))
        olvidar.setToolTip(t("olvidar_ayuda"))
        olvidar.clicked.connect(self.reject)
        botones.addWidget(olvidar)
        abrir = boton_principal(t("abrir"))
        abrir.clicked.connect(self._abrir)
        botones.addWidget(abrir)
        lay.addLayout(botones)
        self.resize(560, 300)

    def _actual(self):
        item = self.lista.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _carpeta(self):
        ruta = self._actual()
        if ruta:
            self.servicios.mostrar_en_carpeta(ruta)

    def _abrir(self):
        self.elegida = self._actual()
        if self.elegida:
            self.accept()


# --- Comparar ------------------------------------------------------------------------------------

class DialogoComparar(QtWidgets.QDialog):
    def __init__(self, gestor, a=None, b=None, padre=None):
        super(DialogoComparar, self).__init__(padre)
        estilo.aplicar(self, "SimpleSaveComparar")
        self.gestor = gestor
        self.setWindowTitle(t("comparar_titulo"))
        self.versiones = gestor.historial().versiones(incluir_archivadas=True)
        lay = QtWidgets.QVBoxLayout(self)
        fila = QtWidgets.QHBoxLayout()
        self.combo_a, self.combo_b = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for combo in (self.combo_a, self.combo_b):
            for v in self.versiones:
                combo.addItem("{} · {}".format(v.etiqueta, v.nota or v.archivo), v.numero)
        numeros = [v.numero for v in self.versiones]
        self.combo_a.setCurrentIndex(numeros.index(a) if a in numeros else max(0, len(numeros) - 2))
        self.combo_b.setCurrentIndex(numeros.index(b) if b in numeros else len(numeros) - 1)
        columnas = QtWidgets.QHBoxLayout()
        self.mini_a, self.mini_b = miniatura("", 240, 135), miniatura("", 240, 135)
        for combo, mini in ((self.combo_a, self.mini_a), (self.combo_b, self.mini_b)):
            col = QtWidgets.QVBoxLayout()
            col.addWidget(combo)
            col.addWidget(mini)
            columnas.addLayout(col)
        fila.addLayout(columnas)
        lay.addLayout(fila)
        self.resumen = QtWidgets.QLabel()
        self.resumen.setObjectName("resumen")
        self.resumen.setWordWrap(True)
        lay.addWidget(self.resumen)
        self.detalle = QtWidgets.QListWidget()
        lay.addWidget(self.detalle, 1)
        cerrar = QtWidgets.QPushButton(t("cerrar"))
        cerrar.clicked.connect(self.accept)
        pie = QtWidgets.QHBoxLayout()
        pie.addStretch(1)
        pie.addWidget(cerrar)
        lay.addLayout(pie)
        self.combo_a.currentIndexChanged.connect(self._actualizar)
        self.combo_b.currentIndexChanged.connect(self._actualizar)
        self.resize(560, 520)
        self._actualizar()

    def _actualizar(self, *_):
        if not self.versiones:
            return
        a, b = self.combo_a.currentData(), self.combo_b.currentData()
        d = self.gestor.comparar(a, b)
        poner_miniatura(self.mini_a, d["a"].miniatura)
        poner_miniatura(self.mini_b, d["b"].miniatura)
        self.detalle.clear()
        if not d["conocido"]:
            self.resumen.setText(t("comparar_sin_datos"))
            return
        partes = [t("comparar_resumen", anadidos=len(d["anadidos"]), borrados=len(d["borrados"]))]
        if d["caras_a"] is not None and d["caras_b"] is not None:
            partes.append(t("comparar_caras", a="{:,}".format(d["caras_a"]).replace(",", "."),
                            b="{:,}".format(d["caras_b"]).replace(",", "."),
                            dif="{:+,}".format(d["caras_b"] - d["caras_a"]).replace(",", ".")))
        self.resumen.setText(" · ".join(partes))
        for nombre in d["anadidos"]:
            item = QtWidgets.QListWidgetItem("+  " + nombre)
            item.setForeground(QtGui.QColor(COLOR_OK))
            self.detalle.addItem(item)
        for nombre in d["borrados"]:
            item = QtWidgets.QListWidgetItem("−  " + nombre)
            item.setForeground(QtGui.QColor(COLOR_MAL))
            self.detalle.addItem(item)
        if not d["anadidos"] and not d["borrados"]:
            self.detalle.addItem(t("comparar_iguales"))


def pedir_nota(padre, actual):
    texto, ok = QtWidgets.QInputDialog.getText(padre, t("editar_nota"), t("nota"), QtWidgets.QLineEdit.Normal, actual)
    return texto if ok else None
