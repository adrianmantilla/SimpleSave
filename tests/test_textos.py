"""Todos los textos que usa el código existen en es.json, y los json se leen bien."""

import json
import os
import re
import unittest

import falsos  # añade scripts al path

RAIZ = falsos.RAIZ
CODIGO = os.path.join(RAIZ, "scripts", "simplesave")


class Textos(unittest.TestCase):
    def test_claves(self):
        with open(os.path.join(CODIGO, "i18n", "es.json"), encoding="utf-8") as f:
            es = json.load(f)
        usadas = set()
        for nombre in os.listdir(CODIGO):
            if nombre.endswith(".py"):
                with open(os.path.join(CODIGO, nombre), encoding="utf-8") as f:
                    texto = f.read()
                usadas |= set(re.findall(r'\bt\("([a-z0-9_]+)"', texto))
                usadas |= set(re.findall(r'\("(cmd_[a-z_]+)",', texto))
        with open(os.path.join(RAIZ, "instalar.py"), encoding="utf-8") as f:
            usadas |= set(re.findall(r'\bt\("([a-z0-9_]+)"', f.read()))
        for prefijo in ("limpieza_tildes", "limpieza_espacios", "limpieza_simbolos"):
            usadas.add(prefijo)
        faltan = sorted(c for c in usadas if c not in es and not c.endswith("_"))
        self.assertEqual(faltan, [])

    def test_formato(self):
        from simplesave.i18n import t
        self.assertEqual(t("guardada", archivo="a_v001.ma"), "Guardada a_v001.ma")
        self.assertEqual(t("no_existe"), "no_existe")


if __name__ == "__main__":
    unittest.main()
