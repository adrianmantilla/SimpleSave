"""Panel de SimpleSave: pestañas Versiones y Ajustes."""

import os

from simplesave import nombres
from simplesave.archivos import tamano_legible
from simplesave.dialogos import (COLOR_AVISO, COLOR_MAL, COLOR_OK, COLOR_TENUE, MONO, DialogoComparar,
                                 DialogoNombre, boton_principal, miniatura, pedir_nota)
from simplesave.gestor import ErrorGuardado, hora_de
from simplesave.i18n import t
from simplesave import estilo, qt
from simplesave.qt import QtCore, QtWidgets

Qt = QtCore.Qt


def _punto(color):
    return '<span style="color:{};font-size:15px">●</span>'.format(color)


class FilaVersion(QtWidgets.QFrame):
    """Una versión en la lista: miniatura, archivo, nota, hora y botones."""

    def __init__(self, panel, version, abierta):
        super(FilaVersion, self).__init__()
        self.panel = panel
        self.version = version
        self.setObjectName("fila_" + version.etiqueta)
        fondo = "#46505a" if abierta else ("#383838" if version.archivada else "#3f3f3f")
        self.setStyleSheet("FilaVersion{{background:{};border-bottom:1px solid #353535}}".format(fondo))
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)
        lay.addWidget(miniatura(version.miniatura))
        info = QtWidgets.QVBoxLayout()
        info.setSpacing(1)
        archivo = QtWidgets.QLabel(("★ " if version.importante else "") + version.archivo)
        archivo.setStyleSheet("color:#f0f0f0;" + MONO)
        info.addWidget(archivo)
        nota = QtWidgets.QLabel(version.nota or t("sin_nota"))
        nota.setWordWrap(True)
        nota.setStyleSheet("color:#cfcfcf" if version.nota else "color:#888;font-style:italic")
        info.addWidget(nota)
        meta = [hora_de(version, t("ayer")), tamano_legible(version.bytes)]
        if abierta:
            meta.append(t("abierta"))
        if version.archivada:
            meta.append(t("archivada"))
        if version.origen:
            meta.append(t("viene_de", version=nombres.etiqueta(version.origen)))
        detalle = QtWidgets.QLabel(" · ".join(m for m in meta if m))
        detalle.setStyleSheet("color:{};font-size:11px".format(COLOR_TENUE))
        info.addWidget(detalle)
        lay.addLayout(info, 1)
        botones = QtWidgets.QVBoxLayout()
        botones.setSpacing(4)
        if version.archivada:
            b = QtWidgets.QPushButton(t("devolver"))
            b.setToolTip(t("devolver_ayuda"))
            b.clicked.connect(lambda: panel.devolver(version.numero))
            botones.addWidget(b)
        else:
            if not abierta:
                b = QtWidgets.QPushButton(t("restaurar"))
                b.setObjectName("restaurar")
                b.setToolTip(t("restaurar_ayuda", version=version.etiqueta))
                b.clicked.connect(lambda: panel.restaurar(version.numero))
                botones.addWidget(b)
            b = QtWidgets.QPushButton(t("abrir"))
            b.setObjectName("abrir")
            b.setEnabled(not abierta)
            b.clicked.connect(lambda: panel.abrir(version.ruta))
            botones.addWidget(b)
        botones.addStretch(1)
        lay.addLayout(botones)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def _menu(self, punto):
        v, p = self.version, self.panel
        menu = QtWidgets.QMenu(self)
        if not v.archivada:
            menu.addAction(t("abrir"), lambda: p.abrir(v.ruta))
            menu.addAction(t("restaurar_como_nueva"), lambda: p.restaurar(v.numero))
        menu.addAction(t("editar_nota"), lambda: p.editar_nota(v))
        accion = menu.addAction(t("importante"), lambda: p.marcar_importante(v, not v.importante))
        accion.setCheckable(True)
        accion.setChecked(v.importante)
        menu.addAction(t("comparar_con_abierta"), lambda: p.comparar(v.numero))
        menu.addSeparator()
        menu.addAction(t("mostrar_carpeta"), lambda: p.servicios.mostrar_en_carpeta(v.ruta))
        menu.addAction(t("copiar_ruta"), lambda: QtWidgets.QApplication.clipboard().setText(v.ruta))
        menu.popup(self.mapToGlobal(punto))


class PanelSimpleSave(QtWidgets.QWidget):
    def __init__(self, gestor, padre_dialogos=None, parent=None):
        super(PanelSimpleSave, self).__init__(parent)
        self.gestor = gestor
        self.servicios = gestor.s
        self.ajustes = gestor.ajustes
        self.padre_dialogos = padre_dialogos
        estilo.aplicar(self, "SimpleSavePanel")
        self._firma = None
        self._mensaje_hasta = 0
        self._latidos = 0
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.pestanas = QtWidgets.QTabWidget()
        lay.addWidget(self.pestanas)
        self.pestanas.addTab(self._pagina_versiones(), t("pestana_versiones"))
        self.pestanas.addTab(self._pagina_ajustes(), t("pestana_ajustes"))
        self.reloj = QtCore.QTimer(self)
        self.reloj.setInterval(1000)
        self.reloj.timeout.connect(self._latido)
        self.reloj.start()
        self.refrescar()

    def _padre(self):
        return self.padre_dialogos or self

    # --- pestaña Versiones ---------------------------------------------------------------
    def _pagina_versiones(self):
        pagina = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(pagina)
        lay.setSpacing(8)
        estado = QtWidgets.QFrame()
        estilo.rol(estado, "tarjeta")
        fila = QtWidgets.QHBoxLayout(estado)
        fila.setContentsMargins(10, 8, 10, 8)
        self.punto = QtWidgets.QLabel()
        fila.addWidget(self.punto)
        textos = QtWidgets.QVBoxLayout()
        textos.setSpacing(0)
        self.etiqueta_escena = QtWidgets.QLabel()
        self.etiqueta_escena.setObjectName("escena")
        self.etiqueta_escena.setStyleSheet("color:#f0f0f0;font-size:13px;background:transparent;" + MONO)
        self.etiqueta_escena.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.etiqueta_estado = QtWidgets.QLabel()
        self.etiqueta_estado.setObjectName("estado")
        self.etiqueta_estado.setStyleSheet("color:{};background:transparent".format(COLOR_TENUE))
        textos.addWidget(self.etiqueta_escena)
        textos.addWidget(self.etiqueta_estado)
        fila.addLayout(textos, 1)
        carpeta = QtWidgets.QToolButton()
        carpeta.setText("📁")
        carpeta.setToolTip(t("mostrar_carpeta"))
        carpeta.clicked.connect(self._mostrar_carpeta_escena)
        fila.addWidget(carpeta)
        lay.addWidget(estado)

        guardar = QtWidgets.QHBoxLayout()
        self.nota = QtWidgets.QLineEdit()
        self.nota.setObjectName("nota")
        self.nota.setPlaceholderText(t("nota_ayuda"))
        self.nota.setMaxLength(120)
        self.nota.returnPressed.connect(self.guardar_version)
        guardar.addWidget(self.nota, 1)
        self.boton_guardar = boton_principal(t("guardar_version"))
        self.boton_guardar.setObjectName("guardar")
        self.boton_guardar.clicked.connect(self.guardar_version)
        guardar.addWidget(self.boton_guardar)
        lay.addLayout(guardar)

        herramientas = QtWidgets.QHBoxLayout()
        self.boton_comparar = QtWidgets.QPushButton(t("comparar"))
        self.boton_comparar.clicked.connect(lambda: self.comparar())
        self.boton_entregar = QtWidgets.QPushButton(t("entregar"))
        self.boton_entregar.setToolTip(t("entregar_ayuda"))
        self.boton_entregar.clicked.connect(self.entregar)
        self.boton_limpiar = QtWidgets.QPushButton(t("limpiar"))
        self.boton_limpiar.setToolTip(t("limpiar_ayuda"))
        self.boton_limpiar.clicked.connect(self.limpiar)
        self.ver_archivadas = QtWidgets.QCheckBox(t("ver_archivadas"))
        self.ver_archivadas.toggled.connect(lambda *_: self.refrescar(forzar=True))
        for w in (self.boton_comparar, self.boton_entregar, self.boton_limpiar):
            herramientas.addWidget(w)
        herramientas.addStretch(1)
        herramientas.addWidget(self.ver_archivadas)
        lay.addLayout(herramientas)

        self.lista = QtWidgets.QScrollArea()
        self.lista.setWidgetResizable(True)
        self.lista.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.contenido = QtWidgets.QWidget()
        self.filas = QtWidgets.QVBoxLayout(self.contenido)
        self.filas.setContentsMargins(0, 0, 0, 0)
        self.filas.setSpacing(0)
        self.lista.setWidget(self.contenido)
        lay.addWidget(self.lista, 1)

        pie = QtWidgets.QHBoxLayout()
        caja = QtWidgets.QVBoxLayout()
        caja.setSpacing(3)
        self.etiqueta_auto = QtWidgets.QLabel()
        self.etiqueta_auto.setObjectName("auto")
        self.etiqueta_auto.setWordWrap(True)
        self.barra_auto = QtWidgets.QProgressBar()
        self.barra_auto.setTextVisible(False)
        self.barra_auto.setFixedHeight(4)
        self.barra_auto.setRange(0, 1000)
        self.barra_auto.setStyleSheet("QProgressBar{background:#2b2b2b;border:0;border-radius:2px}"
                                      "QProgressBar::chunk{background:" + COLOR_OK + ";border-radius:2px}")
        caja.addWidget(self.etiqueta_auto)
        caja.addWidget(self.barra_auto)
        self.etiqueta_copia = QtWidgets.QLabel()
        self.etiqueta_copia.setObjectName("copia")
        self.etiqueta_copia.setWordWrap(True)
        caja.addWidget(self.etiqueta_copia)
        self.mensaje = QtWidgets.QLabel()
        self.mensaje.setObjectName("mensaje")
        self.mensaje.setWordWrap(True)
        caja.addWidget(self.mensaje)
        pie.addLayout(caja, 1)
        lay.addLayout(pie)
        return pagina

    # --- pestaña Ajustes ------------------------------------------------------------------
    def _pagina_ajustes(self):
        pagina = QtWidgets.QWidget()
        exterior = QtWidgets.QVBoxLayout(pagina)
        self.aviso_profesor = QtWidgets.QLabel()
        self.aviso_profesor.setWordWrap(True)
        self.aviso_profesor.setStyleSheet("background:#4a4232;color:#f3dca8;padding:6px 8px;border-radius:3px")
        exterior.addWidget(self.aviso_profesor)
        form = estilo.formulario()
        exterior.addLayout(form)
        self.controles = {}

        def titulo(texto):
            form.addRow(estilo.etiqueta(texto, "seccion"))

        def casilla(clave, texto):
            c = QtWidgets.QCheckBox(texto)
            c.toggled.connect(lambda v: self._cambiar(clave, bool(v)))
            self.controles[clave] = c
            return c

        def numero(clave, minimo, maximo, sufijo):
            n = QtWidgets.QSpinBox()
            n.setRange(minimo, maximo)
            n.setSuffix(" " + sufijo)
            n.valueChanged.connect(lambda v: self._cambiar(clave, int(v)))
            self.controles[clave] = n
            return n

        titulo(t("ajustes_autoguardado"))
        form.addRow("", casilla("autoguardado", t("ajuste_autoguardado")))
        form.addRow(t("ajuste_cada"), numero("minutos", 1, 120, t("minutos")))
        form.addRow(t("ajuste_copias"), numero("copias", 1, 50, t("copias")))
        form.addRow("", casilla("pausa_reproduccion", t("ajuste_pausa")))
        titulo(t("ajustes_avisos"))
        aviso = QtWidgets.QHBoxLayout()
        aviso.addWidget(casilla("aviso", t("ajuste_aviso")))
        aviso.addWidget(numero("aviso_minutos", 5, 240, t("minutos")))
        aviso.addStretch(1)
        form.addRow("", aviso)
        titulo(t("ajustes_versiones"))
        self.plantilla = QtWidgets.QLineEdit()
        self.plantilla.setToolTip(t("plantilla_ayuda"))
        self.plantilla.editingFinished.connect(lambda: self._cambiar("plantilla", self.plantilla.text().strip()
                                                                     or "{escena}"))
        self.controles["plantilla"] = self.plantilla
        form.addRow(t("ajuste_plantilla"), self.plantilla)
        formato = QtWidgets.QComboBox()
        formato.addItem(t("formato_ma"), "ma")
        formato.addItem(t("formato_mb"), "mb")
        formato.currentIndexChanged.connect(lambda *_: self._cambiar("formato", formato.currentData()))
        self.controles["formato"] = formato
        form.addRow(t("ajuste_formato"), formato)
        form.addRow("", casilla("miniaturas", t("ajuste_miniaturas")))
        form.addRow(t("ajuste_conservar"), numero("conservar_ultimas", 1, 100, t("versiones")))
        titulo(t("ajustes_copia"))
        form.addRow("", casilla("copia_activada", t("ajuste_copia")))
        fila = QtWidgets.QHBoxLayout()
        self.copia_carpeta = QtWidgets.QLineEdit()
        self.copia_carpeta.setPlaceholderText(t("copia_ayuda"))
        self.copia_carpeta.editingFinished.connect(lambda: self._cambiar("copia_carpeta",
                                                                         self.copia_carpeta.text().strip()))
        self.controles["copia_carpeta"] = self.copia_carpeta
        elegir = QtWidgets.QPushButton(t("elegir"))
        elegir.clicked.connect(self._elegir_copia)
        self._boton_elegir = elegir
        fila.addWidget(self.copia_carpeta, 1)
        fila.addWidget(elegir)
        form.addRow(t("ajuste_copia_carpeta"), fila)
        titulo(t("ajustes_entrega"))
        self.entregas = QtWidgets.QLineEdit()
        self.entregas.editingFinished.connect(lambda: self._cambiar("carpeta_entregas",
                                                                    self.entregas.text().strip() or "entregas"))
        self.controles["carpeta_entregas"] = self.entregas
        form.addRow(t("ajuste_entregas"), self.entregas)
        exterior.addStretch(1)
        self._cargando = False
        self.cargar_ajustes()
        return pagina

    def cargar_ajustes(self):
        self._cargando = True
        try:
            for clave, control in self.controles.items():
                valor = self.ajustes[clave]
                if isinstance(control, QtWidgets.QCheckBox):
                    control.setChecked(bool(valor))
                elif isinstance(control, QtWidgets.QSpinBox):
                    control.setValue(int(valor))
                elif isinstance(control, QtWidgets.QComboBox):
                    control.setCurrentIndex(max(0, control.findData(valor)))
                else:
                    control.setText(str(valor or ""))
                bloqueado = self.ajustes.bloqueado(clave)
                control.setEnabled(not bloqueado)
                control.setToolTip(t("fijado_profesor") if bloqueado else control.toolTip())
            self._boton_elegir.setEnabled(not self.ajustes.bloqueado("copia_carpeta"))
            if self.ajustes.ruta_profesor:
                self.aviso_profesor.setText(t("aviso_profesor", ruta=self.ajustes.ruta_profesor))
                self.aviso_profesor.show()
            else:
                self.aviso_profesor.hide()
        finally:
            self._cargando = False

    def _cambiar(self, clave, valor):
        if self._cargando or self.ajustes.bloqueado(clave):
            return
        if self.ajustes[clave] != valor:
            self.ajustes[clave] = valor
            self.refrescar(forzar=True)

    def _elegir_copia(self):
        carpeta = QtWidgets.QFileDialog.getExistingDirectory(self, t("ajuste_copia_carpeta"),
                                                            self.copia_carpeta.text() or os.path.expanduser("~"))
        if carpeta:
            self.copia_carpeta.setText(carpeta)
            self._cambiar("copia_carpeta", carpeta)
            if not self.ajustes["copia_activada"]:
                self.controles["copia_activada"].setChecked(True)

    # --- estado ----------------------------------------------------------------------------
    def refrescar(self, forzar=False):
        escena = self.gestor.escena()
        modificada = self.servicios.modificada()
        if escena:
            self.etiqueta_escena.setText(os.path.basename(escena))
        else:
            self.etiqueta_escena.setText(t("sin_titulo"))
        if modificada:
            self.punto.setText(_punto(COLOR_AVISO))
            minutos = self.gestor.minutos_sin_version()
            self.etiqueta_estado.setText(t("estado_cambios") if minutos < 1 else
                                         t("estado_cambios_min", minutos=minutos))
        else:
            self.punto.setText(_punto(COLOR_OK))
            self.etiqueta_estado.setText(t("estado_guardado") if escena else t("estado_vacia"))
        if not self.gestor.sin_nombre():
            _, numero = self.gestor.destino_siguiente()
            self.boton_guardar.setText(t("guardar_version_n", version=nombres.etiqueta(numero)))
        else:
            self.boton_guardar.setText(t("guardar_version_primera"))
        h = self.gestor.historial()
        hay_versiones = bool(h and h.versiones())
        self.boton_comparar.setEnabled(bool(h and len(h.versiones(incluir_archivadas=True)) >= 2))
        self.boton_entregar.setEnabled(hay_versiones)
        self.boton_limpiar.setEnabled(hay_versiones)
        self._pintar_lista(forzar)
        self._pintar_pie()

    def _firma_actual(self):
        h = self.gestor.historial()
        if h is None:
            return ("",)
        partes = [self.gestor.escena(), self.ver_archivadas.isChecked(), os.path.getmtime(h.ruta)
                  if os.path.isfile(h.ruta) else 0]
        for v in h.versiones(incluir_archivadas=self.ver_archivadas.isChecked()):
            partes.append((v.numero, v.ruta, v.bytes, bool(v.miniatura)))
        return tuple(partes)

    def _pintar_lista(self, forzar=False):
        firma = self._firma_actual()
        if firma == self._firma and not forzar:
            return
        self._firma = firma
        while self.filas.count():
            item = self.filas.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        h = self.gestor.historial()
        versiones = h.versiones(incluir_archivadas=self.ver_archivadas.isChecked()) if h else []
        actual = os.path.normcase(os.path.abspath(self.gestor.escena())) if self.gestor.escena() else None
        for v in reversed(versiones):
            abierta = actual is not None and os.path.normcase(os.path.abspath(v.ruta)) == actual
            self.filas.addWidget(FilaVersion(self, v, abierta))
        if not versiones:
            vacio = QtWidgets.QLabel(t("lista_vacia") if self.gestor.escena() else t("lista_vacia_sin_titulo"))
            vacio.setObjectName("vacio")
            vacio.setWordWrap(True)
            vacio.setAlignment(Qt.AlignCenter)
            vacio.setStyleSheet("color:{};padding:24px".format(COLOR_TENUE))
            self.filas.addWidget(vacio)
        self.filas.addStretch(1)

    def _pintar_pie(self):
        a = self.ajustes
        if not a["autoguardado"]:
            self.etiqueta_auto.setText(_punto(COLOR_AVISO) + " " + t("auto_desactivado"))
            self.barra_auto.setValue(0)
        else:
            cabecera = t("auto_cada", minutos=a["minutos"])
            restante = self.gestor.segundos_para_autoguardado()
            if self.gestor.ultima_copia:
                hora = QtCore.QDateTime.fromSecsSinceEpoch(int(self.gestor.ultima_copia[1])).toString("HH:mm")
                ultima = t("auto_ultima", hora=hora)
            else:
                ultima = ""
            if self.servicios.modificada():
                detalle = t("auto_proxima", minutos=max(1, int(round(restante / 60.0))))
                total = a["minutos"] * 60.0
                self.barra_auto.setValue(int(1000 * (1 - restante / total)) if total else 0)
            else:
                detalle = t("auto_nada")
                self.barra_auto.setValue(0)
            self.etiqueta_auto.setText(_punto(COLOR_OK) + " <b>{}</b> · {} {}".format(cabecera, detalle, ultima))
        if a["copia_activada"]:
            estado = self.gestor.ultima_copia_seguridad
            carpeta = a["copia_carpeta"] or "?"
            if estado and not estado[0]:
                self.etiqueta_copia.setText(_punto(COLOR_MAL) + " " + estado[1])
            elif os.path.isdir(carpeta):
                self.etiqueta_copia.setText(_punto(COLOR_OK) + " " + t("copia_en", carpeta=carpeta))
            else:
                self.etiqueta_copia.setText(_punto(COLOR_AVISO) + " " + t("copia_no_esta", carpeta=carpeta))
            self.etiqueta_copia.show()
        else:
            self.etiqueta_copia.hide()

    def _latido(self):
        self._pintar_pie()
        if self._mensaje_hasta and QtCore.QDateTime.currentSecsSinceEpoch() > self._mensaje_hasta:
            self.mensaje.clear()
            self._mensaje_hasta = 0
        # El punto y el texto de estado también cambian solos (modelar marca cambios).
        self._latidos += 1
        if self._latidos % 3 == 0:
            self.refrescar()

    def avisar(self, texto, color=COLOR_OK, segundos=6):
        self.mensaje.setText('<span style="color:{}">{}</span>'.format(color, texto))
        self._mensaje_hasta = QtCore.QDateTime.currentSecsSinceEpoch() + segundos

    def _error(self, error):
        QtWidgets.QMessageBox.warning(self._padre(), "SimpleSave", str(error))

    def _mostrar_carpeta_escena(self):
        escena = self.gestor.escena()
        self.servicios.mostrar_en_carpeta(escena or os.path.join(self.servicios.proyecto(), "scenes"))

    # --- acciones --------------------------------------------------------------------------
    def guardar_version(self):
        """Devuelve True si se guardó."""
        nota = self.nota.text()
        valores = None
        if self.gestor.sin_nombre():
            dialogo = DialogoNombre(self.gestor, nota, self._padre())
            if not qt.ejecutar(dialogo):
                return False
            valores = dialogo.valores()
            nota = dialogo.nota.text()
        try:
            r = self.gestor.guardar_version(nota, valores)
        except ErrorGuardado as error:
            self._error(error)
            return False
        self.nota.clear()
        texto = t("guardada", archivo=os.path.basename(r.ruta))
        if r.avisos:
            self.avisar(texto + " · " + " ".join(r.avisos), COLOR_AVISO, 10)
        else:
            self.avisar(texto)
        self.servicios.aviso(texto)
        self.refrescar(forzar=True)
        return True

    def abrir(self, ruta):
        try:
            if self.servicios.abrir(ruta, preguntar=True):
                self.gestor.al_abrir_escena()
        except Exception as error:
            self._error(error)
        self.refrescar(forzar=True)

    def restaurar(self, numero):
        try:
            r = self.gestor.restaurar(numero)
        except (ErrorGuardado, OSError) as error:
            self._error(error)
            return
        if r is not None:
            self.avisar(t("restaurada", version=nombres.etiqueta(numero), nueva=nombres.etiqueta(r.numero)))
        self.refrescar(forzar=True)

    def devolver(self, numero):
        try:
            self.gestor.devolver(numero)
        except OSError as error:
            self._error(error)
        self.refrescar(forzar=True)

    def editar_nota(self, version):
        texto = pedir_nota(self._padre(), version.nota)
        if texto is not None:
            self.gestor.cambiar_nota(version.numero, texto)
            self.refrescar(forzar=True)

    def marcar_importante(self, version, valor):
        self.gestor.marcar_importante(version.numero, valor)
        self.refrescar(forzar=True)

    def comparar(self, numero=None):
        h = self.gestor.historial()
        if h is None or len(h.versiones(incluir_archivadas=True)) < 2:
            return None
        b = self.gestor.numero_actual() if numero is not None else None
        dialogo = DialogoComparar(self.gestor, numero, b, self._padre())
        dialogo.show()
        self._dialogo_comparar = dialogo
        return dialogo

    def entregar(self):
        try:
            r = self.gestor.entregar()
        except (ErrorGuardado, OSError) as error:
            self._error(error)
            return None
        partes = [t("entrega_hecha", escena=os.path.basename(r["escena"]), zip=os.path.basename(r["zip"]),
                    texturas=r["texturas"])]
        if r["externas"]:
            partes.append(t("entrega_externas", n=len(r["externas"])))
        if r["faltan"]:
            partes.append(t("entrega_faltan", lista="\n".join(r["faltan"][:10])))
        caja = QtWidgets.QMessageBox(self._padre())
        caja.setWindowTitle(t("entregar"))
        caja.setText("\n\n".join(partes))
        carpeta = caja.addButton(t("mostrar_carpeta"), QtWidgets.QMessageBox.ActionRole)
        caja.addButton(t("cerrar"), QtWidgets.QMessageBox.AcceptRole)
        qt.ejecutar(caja)
        if caja.clickedButton() is carpeta:
            self.servicios.mostrar_en_carpeta(r["zip"])
        self.refrescar(forzar=True)
        return r

    def limpiar(self, confirmar=True):
        lista = self.gestor.que_limpiar()
        if not lista:
            QtWidgets.QMessageBox.information(self._padre(), t("limpiar"),
                                              t("limpiar_nada", n=self.ajustes["conservar_ultimas"]))
            return []
        if confirmar:
            respuesta = QtWidgets.QMessageBox.question(
                self._padre(), t("limpiar"),
                t("limpiar_pregunta", n=len(lista), lista=", ".join(v.etiqueta for v in lista)))
            if respuesta != QtWidgets.QMessageBox.Yes:
                return []
        try:
            movidas = self.gestor.limpiar()
        except OSError as error:
            self._error(error)
            return []
        self.avisar(t("limpiadas", n=len(movidas)))
        self.refrescar(forzar=True)
        return movidas
