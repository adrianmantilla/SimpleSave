"""Lo que SimpleSave necesita de Maya, en una clase aparte.

``maya_servicios.ServiciosMaya`` la implementa con ``cmds``; las pruebas usan
una versión falsa que escribe archivos de mentira. Así el resto del plugin se
puede probar sin Maya.
"""


class Servicios(object):
    en_maya = False

    def escena_actual(self):
        """Ruta de la escena abierta, o ``""`` si no tiene nombre."""
        return ""

    def proyecto(self):
        """Carpeta del proyecto de Maya activo."""
        return ""

    def nombre_proyecto(self):
        import os
        return os.path.basename(self.proyecto().rstrip("/\\")) or "proyecto"

    def modificada(self):
        """True si la escena tiene cambios sin guardar."""
        return False

    def guardar_como(self, ruta, formato):
        """Guarda la escena en ``ruta`` y la deja abierta con ese nombre."""
        raise NotImplementedError

    def guardar_copia(self, ruta, formato):
        """Guarda una copia en ``ruta`` sin cambiar el nombre de la escena ni su estado de cambios."""
        raise NotImplementedError

    def abrir(self, ruta, preguntar=True):
        """Abre ``ruta``. Si ``preguntar`` y hay cambios, pregunta antes. Devuelve False si se cancela."""
        raise NotImplementedError

    def confirmar_cerrar(self):
        """Si hay cambios, pregunta si guardarlos antes de abrir otra escena. False si se cancela."""
        return True

    def capturar_miniatura(self, ruta):
        """Guarda una imagen pequeña del visor activo. Devuelve True si pudo."""
        return False

    def objetos(self):
        """Nombres de los objetos de la escena (para comparar versiones)."""
        return []

    def caras(self):
        """Número total de caras de polígonos."""
        return 0

    def texturas(self):
        """Rutas de las imágenes que usa la escena (texturas, planos de imagen)."""
        return []

    def reproduciendo(self):
        return False

    def carpetas_rescate(self):
        """Carpetas donde Maya deja la copia de emergencia al colgarse."""
        return []

    def mostrar_en_carpeta(self, ruta):
        pass

    def aviso(self, texto):
        """Mensaje discreto en el visor."""
        pass
