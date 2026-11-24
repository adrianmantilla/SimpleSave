"""El cerebro de SimpleSave: guardar versión, autoguardar, restaurar, recuperar.

Habla con Maya solo a través de un objeto ``Servicios``, así que se prueba sin Maya.
"""

import datetime
import os
import time

from simplesave import autoguardado, comparar, entrega, limpieza, nombres
from simplesave.archivos import borrar, copiar_seguro, verificar_escena
from simplesave.historial import Historial, ahora_iso, fecha_de


class ErrorGuardado(Exception):
    """Algo salió mal al guardar; el texto ya es para el alumno."""


class Resultado(object):
    def __init__(self, ruta, numero=None, avisos=None):
        self.ruta = ruta
        self.numero = numero
        self.avisos = avisos or []


class Gestor(object):
    def __init__(self, servicios, ajustes, textos=None):
        self.s = servicios
        self.ajustes = ajustes
        if textos is None:
            from simplesave.i18n import t as textos
        self.t = textos
        self.planificador = autoguardado.Planificador()
        self.ultima_version_hora = time.time()
        self.ultimo_aviso = time.time()
        self.ultima_copia = None          # (ruta, hora) del último autoguardado
        self.ultima_copia_seguridad = None  # (ok, texto)
        self.autoguardando = False

    # --- la escena abierta ---------------------------------------------------------------
    def escena(self):
        return self.s.escena_actual() or ""

    def sin_nombre(self):
        """True si la escena no tiene nombre o es una copia automática o de emergencia abierta para rescatarla."""
        escena = self.escena()
        return not escena or autoguardado.es_copia(escena)

    def historial(self, ruta=None):
        """Historial de la escena abierta (o de ``ruta``), o None si no tiene nombre."""
        ruta = ruta if ruta is not None else self.escena()
        if not ruta or autoguardado.es_copia(ruta):
            return None
        base, _, _ = nombres.separar(ruta)
        return Historial(os.path.dirname(ruta), base)

    def numero_actual(self):
        _, numero, _ = nombres.separar(self.escena())
        return numero

    def cargar_proyecto(self):
        self.ajustes.cargar_profesor(self.s.proyecto())

    # --- nombre la primera vez ----------------------------------------------------------
    def plantilla(self):
        return self.ajustes["plantilla"] or "{escena}"

    def valores_iniciales(self):
        valores = dict(self.ajustes["recordados"])
        valores.update(self.ajustes.valores_fijos())
        return valores

    def ruta_primera(self, valores):
        """Dónde iría la primera versión de una escena sin nombre. Devuelve ``(ruta, base, cambios, faltan)``."""
        base, cambios, faltan = nombres.nombre_desde_campos(self.plantilla(), valores)
        proyecto = self.s.proyecto() or os.path.expanduser("~")
        carpeta = os.path.join(proyecto, "scenes", base) if base else ""
        ruta = ""
        if base:
            h = Historial(carpeta, base)
            ruta = os.path.join(carpeta, nombres.archivo_version(base, h.siguiente(), self.ajustes.extension()))
        return ruta, base, cambios, faltan

    # --- guardar versión -----------------------------------------------------------------
    def destino_siguiente(self):
        """Ruta y número de la próxima versión de la escena abierta (None si no tiene nombre)."""
        h = self.historial()
        if h is None:
            return None, None
        numero = h.siguiente()
        return os.path.join(h.carpeta, nombres.archivo_version(h.base, numero, self.ajustes.extension())), numero

    def guardar_version(self, nota="", valores=None):
        """Guarda la escena como versión nueva. ``valores`` hace falta si aún no tiene nombre."""
        if self.sin_nombre():
            if not valores:
                raise ErrorGuardado(self.t("error_sin_nombre"))
            ruta, base, _, faltan = self.ruta_primera(valores)
            if faltan or not base:
                raise ErrorGuardado(self.t("error_faltan", campos=", ".join(faltan)))
            self.ajustes.recordar_valores(valores)
            h = Historial(os.path.dirname(ruta), base)
            numero = nombres.separar(ruta)[1]
            sin_titulo = True
        else:
            ruta, numero = self.destino_siguiente()
            h = self.historial()
            sin_titulo = False
        while os.path.exists(ruta):  # por si otro programa lo creó entretanto: nunca se pisa
            numero += 1
            ruta = os.path.join(h.carpeta, nombres.archivo_version(h.base, numero, self.ajustes.extension()))
        return self._guardar(h, numero, ruta, nota, origen=None, sin_titulo=sin_titulo)

    def _guardar(self, h, numero, ruta, nota, origen=None, sin_titulo=False):
        avisos = []
        objetos = caras = None
        try:
            objetos = sorted(self.s.objetos())
            caras = int(self.s.caras())
        except Exception:
            pass
        if self.ajustes["miniaturas"]:
            try:
                os.makedirs(h.carpeta_miniaturas, exist_ok=True)
                self.s.capturar_miniatura(h.ruta_miniatura(numero))
            except Exception:
                pass
        os.makedirs(h.carpeta, exist_ok=True)
        try:
            self.s.guardar_como(ruta, self.ajustes["formato"])
        except Exception as error:
            if os.path.exists(ruta) and not verificar_escena(ruta):
                borrar(ruta)
            raise ErrorGuardado(self.t("error_guardar", error=error))
        if not verificar_escena(ruta):
            raise ErrorGuardado(self.t("error_verificar", ruta=ruta))
        h.anotar(numero, nota=nota.strip(), fecha=ahora_iso(), bytes=os.path.getsize(ruta), objetos=objetos,
                 caras=caras, origen=origen)
        self.planificador.reiniciar()
        self.ultima_version_hora = time.time()
        self.ultimo_aviso = time.time()
        self.ajustes["ultima_escena"] = ruta
        if sin_titulo:
            # Las copias automáticas de cuando no tenía nombre ya no hacen falta para recuperar.
            self._mover_copias_sin_titulo(h)
        aviso = self.copia_seguridad(ruta, h.base)
        if aviso:
            avisos.append(aviso)
        return Resultado(ruta, numero, avisos)

    def _mover_copias_sin_titulo(self, h):
        carpeta = autoguardado.carpeta_sin_titulo(self.s.proyecto() or "")
        for ruta in autoguardado.copias(carpeta, autoguardado.SIN_TITULO):
            borrar(ruta)

    # --- copia de seguridad -----------------------------------------------------------------
    def copia_seguridad(self, ruta, base):
        """Copia la versión a la segunda carpeta. Devuelve un aviso si no pudo, o None."""
        if not self.ajustes["copia_activada"]:
            self.ultima_copia_seguridad = None
            return None
        carpeta = (self.ajustes["copia_carpeta"] or "").strip()
        if not carpeta or not os.path.isdir(carpeta):
            texto = self.t("copia_no_esta", carpeta=carpeta or "?")
            self.ultima_copia_seguridad = (False, texto)
            return texto
        destino = os.path.join(carpeta, self.s.nombre_proyecto(), base, os.path.basename(ruta))
        try:
            copiar_seguro(ruta, destino)
        except OSError as error:
            texto = self.t("copia_fallo", error=error)
            self.ultima_copia_seguridad = (False, texto)
            return texto
        self.ultima_copia_seguridad = (True, destino)
        return None

    # --- autoguardado ---------------------------------------------------------------------
    def carpeta_y_base_copias(self):
        h = self.historial()
        if h is None:
            return autoguardado.carpeta_sin_titulo(self.s.proyecto() or os.path.expanduser("~")), autoguardado.SIN_TITULO
        return h.carpeta_autoguardado, h.base

    def segundos_para_autoguardado(self):
        return self.planificador.segundos_restantes(self.ajustes["minutos"])

    def toca_autoguardar(self, ahora=None):
        if not self.ajustes["autoguardado"] or self.autoguardando:
            return False
        try:
            reproduciendo = self.s.reproduciendo()
        except Exception:
            reproduciendo = False
        return self.planificador.toca(self.ajustes["minutos"], self.s.modificada(), reproduciendo, ahora,
                                      self.ajustes["pausa_reproduccion"])

    def autoguardar(self):
        """Guarda una copia automática. Devuelve la ruta o None si falló."""
        carpeta, base = self.carpeta_y_base_copias()
        os.makedirs(carpeta, exist_ok=True)
        ruta = autoguardado.ruta_nueva(carpeta, base, self.ajustes.extension())
        self.autoguardando = True
        try:
            self.s.guardar_copia(ruta, self.ajustes["formato"])
        except Exception:
            borrar(ruta)
            self.planificador.reiniciar()  # no reintentar en bucle; se probará en el próximo intervalo
            return None
        finally:
            self.autoguardando = False
        if not verificar_escena(ruta):
            borrar(ruta)
            self.planificador.reiniciar()
            return None
        autoguardado.rotar(carpeta, base, self.ajustes["copias"])
        self.planificador.reiniciar()
        self.ultima_copia = (ruta, time.time())
        return ruta

    def copias_automaticas(self):
        carpeta, base = self.carpeta_y_base_copias()
        return autoguardado.copias(carpeta, base)

    # --- aviso de «llevas mucho sin guardar versión» ------------------------------------------
    def toca_aviso(self, ahora=None):
        ahora = time.time() if ahora is None else ahora
        if not self.ajustes["aviso"] or not self.s.modificada():
            return False
        limite = self.ajustes["aviso_minutos"] * 60
        if ahora - self.ultima_version_hora >= limite and ahora - self.ultimo_aviso >= limite:
            self.ultimo_aviso = ahora
            return True
        return False

    def minutos_sin_version(self, ahora=None):
        ahora = time.time() if ahora is None else ahora
        return int((ahora - self.ultima_version_hora) // 60)

    def al_abrir_escena(self):
        """Se llama al abrir o crear escena: reinicia los contadores."""
        self.planificador.reiniciar()
        self.ultima_version_hora = time.time()
        self.ultimo_aviso = time.time()
        self.ultima_copia = None
        self.cargar_proyecto()
        if self.escena():
            self.ajustes["ultima_escena"] = self.escena()

    # --- restaurar y recuperar -------------------------------------------------------------
    def restaurar(self, numero):
        """Copia la versión ``numero`` como versión nueva y la abre. Nunca sustituye nada."""
        h = self.historial()
        vieja = h.version(numero) if h else None
        if vieja is None:
            raise ErrorGuardado(self.t("error_no_existe", version=nombres.etiqueta(numero)))
        return self._copiar_como_version(h, vieja.ruta, self.t("nota_restaurada", version=vieja.etiqueta),
                                         origen=vieja.numero, miniatura=vieja.miniatura,
                                         objetos=vieja.objetos, caras=vieja.caras)

    def _copiar_como_version(self, h, origen_ruta, nota, origen=None, miniatura="", objetos=None, caras=None,
                             abrir=True):
        # Primero se pregunta por los cambios: si el alumno guarda versión ahí, el número siguiente cambia.
        if abrir and not self.s.confirmar_cerrar():
            return None  # el alumno canceló
        ext = os.path.splitext(origen_ruta)[1].lower()
        numero = h.siguiente()
        ruta = os.path.join(h.carpeta, nombres.archivo_version(h.base, numero, ext))
        while os.path.exists(ruta):
            numero += 1
            ruta = os.path.join(h.carpeta, nombres.archivo_version(h.base, numero, ext))
        copiar_seguro(origen_ruta, ruta)
        if miniatura and os.path.isfile(miniatura):
            try:
                copiar_seguro(miniatura, h.ruta_miniatura(numero))
            except OSError:
                pass
        h.anotar(numero, nota=nota, fecha=ahora_iso(), bytes=os.path.getsize(ruta), origen=origen,
                 objetos=objetos, caras=caras)
        if abrir:
            self.s.abrir(ruta, preguntar=False)
            self.al_abrir_escena()
        aviso = self.copia_seguridad(ruta, h.base)
        return Resultado(ruta, numero, [aviso] if aviso else [])

    def recuperable(self):
        """Copia automática de la escena abierta más nueva que su última versión, o None."""
        h = self.historial()
        if h is None:
            return None
        return autoguardado.recuperable(h)

    def recuperable_de(self, ruta):
        h = self.historial(ruta) if ruta and os.path.isfile(ruta) else None
        return autoguardado.recuperable(h) if h is not None else None

    def recuperar(self, copia, ruta_escena=None):
        """Recupera una copia automática como versión nueva de su escena y la abre."""
        h = self.historial(ruta_escena) if ruta_escena else self.historial()
        hora = datetime.datetime.fromtimestamp(os.path.getmtime(copia)).strftime("%H:%M")
        return self._copiar_como_version(h, copia, self.t("nota_recuperada", hora=hora))

    def copias_sin_titulo(self):
        return autoguardado.copias(autoguardado.carpeta_sin_titulo(self.s.proyecto() or ""), autoguardado.SIN_TITULO)

    def rescates(self):
        """Copias de emergencia de Maya y copias de escenas sin nombre que aún no se han ofrecido."""
        vistos = set(self.ajustes["rescates_vistos"])
        lista = [r for r in autoguardado.rescates_de_maya(self.s.carpetas_rescate()) + self.copias_sin_titulo()
                 if r not in vistos]
        lista.sort(key=os.path.getmtime, reverse=True)
        return lista

    def olvidar_rescates(self, rutas):
        vistos = [r for r in self.ajustes["rescates_vistos"] if os.path.exists(r)]
        self.ajustes["rescates_vistos"] = (vistos + [r for r in rutas if r not in vistos])[-100:]

    def abrir_rescate(self, ruta):
        """Abre una copia de emergencia; el panel pedirá entonces el nombre para guardarla como versión."""
        return self.s.abrir(ruta, preguntar=True)

    # --- notas e importancia ---------------------------------------------------------------
    def cambiar_nota(self, numero, texto):
        h = self.historial()
        if h is not None:
            h.anotar(numero, nota=texto.strip())

    def marcar_importante(self, numero, valor=True):
        h = self.historial()
        if h is not None:
            h.anotar(numero, importante=bool(valor))

    # --- v2: entrega, comparar, limpiar ---------------------------------------------------------
    def entregar(self):
        h = self.historial()
        ultima = h.ultima() if h else None
        if ultima is None:
            raise ErrorGuardado(self.t("error_sin_versiones"))
        try:
            texturas = list(self.s.texturas())
        except Exception:
            texturas = []
        return entrega.preparar(ultima.ruta, self.s.proyecto() or h.carpeta, self.ajustes["carpeta_entregas"],
                                h.base, texturas)

    def comparar(self, a, b):
        h = self.historial()
        va, vb = h.version(a), h.version(b)
        if va is None or vb is None:
            raise ErrorGuardado(self.t("error_no_existe", version="?"))
        return comparar.diferencias(va, vb)

    def que_limpiar(self):
        h = self.historial()
        if h is None:
            return []
        return limpieza.que_apartar(h.versiones(), self.ajustes["conservar_ultimas"], self.escena())

    def limpiar(self):
        h = self.historial()
        lista = self.que_limpiar()
        return limpieza.apartar(lista, h.carpeta_archivo) if lista else []

    def devolver(self, numero):
        h = self.historial()
        v = h.version(numero)
        if v is None or not v.archivada:
            return None
        return limpieza.devolver(v, h.carpeta)


def hora_de(version, ayer="ayer"):
    fecha = fecha_de(version.fecha)
    if fecha is None:
        return ""
    hoy = datetime.date.today()
    if fecha.date() == hoy:
        return fecha.strftime("%H:%M")
    if fecha.date() == hoy - datetime.timedelta(days=1):
        return ayer + " " + fecha.strftime("%H:%M")
    return fecha.strftime("%d/%m/%Y %H:%M")
