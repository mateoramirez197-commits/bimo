# -*- coding: utf-8 -*-
"""
tests/test_registro_inicial.py
Primer uso del equipo: sin cuentas por defecto (admin@bimo.local / admin123) y
creación de la cuenta del doctor con su correo de Google, contraseña y PIN.
Usa una base de datos temporal: no toca bimo.db.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class TestRegistroInicial(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bimo_test_registro_")
        self.db = Path(self.tmp.name) / "bimo.db"
        self.p_db = patch("database.RUTA_DB", self.db)
        self.p_db.start()
        import database
        database.init_db()
        self.conf = {}
        self.p_cargar = patch("desktop_app.cargar_datos_clinica", side_effect=lambda: dict(self.conf))
        self.p_guardar = patch("desktop_app.guardar_datos_clinica", side_effect=lambda d: self.conf.update(d))
        self.p_cal = patch("calendar_sync.init_google_calendar")
        self.p_sesion = patch("desktop_app.set_sesion_activa")
        for p in (self.p_cargar, self.p_guardar, self.p_cal, self.p_sesion):
            p.start()
        from desktop_app import BimoBridge
        self.bridge = BimoBridge()

    def tearDown(self):
        patch.stopall()
        self.tmp.cleanup()

    def _datos(self, **kw):
        d = {"nombre": "Dra. Ana Pérez", "email": "Ana.Perez@Gmail.com", "password": "clave-segura", "pin": "4321"}
        d.update(kw)
        return d

    def test_01_no_se_crean_cuentas_por_defecto(self):
        from auth import inicializar_usuarios_default, autenticar_usuario
        inicializar_usuarios_default()
        self.assertFalse(self.bridge.estado_cuentas()["hay_cuentas"])
        self.assertIsNone(autenticar_usuario("admin@bimo.local", "admin123"))

    def test_02_crear_cuenta_y_entrar_con_correo(self):
        from auth import autenticar_usuario
        res = self.bridge.crear_cuenta_inicial(self._datos())
        self.assertEqual(res["status"], "ok", res)
        self.assertEqual(res["usuario"]["email"], "ana.perez@gmail.com")
        self.assertTrue(self.bridge.estado_cuentas()["hay_cuentas"])
        self.assertEqual(self.conf["email_google"], "ana.perez@gmail.com")
        self.assertEqual(self.conf["pin_rapido"], "4321")
        self.assertIsNotNone(autenticar_usuario("ana.perez@gmail.com", "clave-segura"))

    def test_03_no_permite_segunda_cuenta(self):
        self.assertEqual(self.bridge.crear_cuenta_inicial(self._datos())["status"], "ok")
        res = self.bridge.crear_cuenta_inicial(self._datos(email="intruso@gmail.com"))
        self.assertEqual(res["status"], "error")

    def test_04_validaciones(self):
        for malo in (dict(email="sin-arroba"), dict(password="corta"), dict(pin="12"), dict(pin="abcd"), dict(nombre="A")):
            res = self.bridge.crear_cuenta_inicial(self._datos(**malo))
            self.assertEqual(res["status"], "error", malo)
        self.assertFalse(self.bridge.estado_cuentas()["hay_cuentas"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
