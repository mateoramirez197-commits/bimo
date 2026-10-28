# -*- coding: utf-8 -*-
"""
tests/test_mega_prompt_v3.py
Suite de verificación exhaustiva para los 4 Bloques del Mega Prompt V3:
  - BLOQUE 1: Acceso legítimo (PIN dinámico y correo de clinica.json) sin requerir BIMO_DEV_BACKDOOR=1.
  - BLOQUE 2: Escucha activa instantánea (feedback 0ms) y pausa inteligente (60 frames/3.84s).
  - BLOQUE 3: Guardrail clínico anti-PDFs fantasma (< 5 palabras o sin términos clínicos -> IGNORAR).
  - BLOQUE 4: Navegación determinista rápida con muletillas ("bimo este llévame a la agenda").
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

class TestMegaPromptV3(unittest.TestCase):

    # =========================================================================
    # BLOQUE 1: ACCESO LEGÍTIMO SIN BACKDOORS
    # =========================================================================
    @patch.dict(os.environ, {"BIMO_DEV_BACKDOOR": "0"}, clear=False)
    @patch("desktop_app.cargar_datos_clinica")
    @patch("desktop_app.get_connection")
    @patch("desktop_app.set_sesion_activa")
    def test_bloque1_autenticar_pin_legitimo_sin_backdoor(self, mock_set_sesion, mock_conn, mock_cargar_datos):
        from desktop_app import BimoBridge
        bridge = BimoBridge()

        # El doctor tiene configurado el PIN '9876' en clinica.json
        mock_cargar_datos.return_value = {
            "nombre_doctor": "Dra. Sofía Mendoza",
            "email_google": "dra.sofia@gmail.com",
            "pin_rapido": "9876"
        }
        # Simular base de datos sin usuarios aún
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

        # 1. Ingreso con PIN correcto -> Debe acceder con status 'ok' SIN requerir BIMO_DEV_BACKDOOR
        res = bridge.autenticar_pin("9876")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res["usuario"]["nombre"], "Dra. Sofía Mendoza")
        self.assertEqual(res["usuario"]["email"], "dra.sofia@gmail.com")

        # 2. Ingreso con PIN incorrecto -> Debe ser rechazado
        res_fail = bridge.autenticar_pin("1111")
        self.assertEqual(res_fail.get("status"), "error")
        self.assertIn("PIN incorrecto", res_fail.get("message", ""))

        # 3. Comodín "__master__" con BIMO_DEV_BACKDOOR=0 -> Debe ser rechazado
        res_master = bridge.autenticar_pin("__master__")
        self.assertEqual(res_master.get("status"), "error")

        # 4. PIN '1234' ya no es universal: si la clínica configuró otro PIN, debe ser rechazado
        res_1234 = bridge.autenticar_pin("1234")
        self.assertEqual(res_1234.get("status"), "error")

    @patch.dict(os.environ, {"BIMO_DEV_BACKDOOR": "1"}, clear=False)
    @patch("desktop_app.cargar_datos_clinica")
    @patch("desktop_app.get_connection")
    @patch("desktop_app.set_sesion_activa")
    def test_bloque1_backdoor_activado_permite_comodines(self, mock_set_sesion, mock_conn, mock_cargar_datos):
        from desktop_app import BimoBridge
        bridge = BimoBridge()

        mock_cargar_datos.return_value = {"pin_rapido": "9876", "nombre_doctor": "Dr. Test"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

        # Con BIMO_DEV_BACKDOOR=1, __master__ y 0000 son aceptados
        res = bridge.autenticar_pin("__master__")
        self.assertEqual(res.get("status"), "ok")

    @patch.dict(os.environ, {"BIMO_DEV_BACKDOOR": "0"}, clear=False)
    @patch("desktop_app.cargar_datos_clinica")
    @patch("desktop_app.autenticar_usuario")
    @patch("desktop_app.set_sesion_activa")
    def test_bloque1_autenticar_correo_clinica_sin_backdoor(self, mock_set_sesion, mock_autenticar_usr, mock_cargar_datos):
        from desktop_app import BimoBridge
        bridge = BimoBridge()

        # Doctor configurado en clinica.json
        mock_cargar_datos.return_value = {
            "nombre_doctor": "Dr. Camilo Torres",
            "email_google": "camilo.torres@gmail.com",
            "pin_rapido": "5544"
        }
        mock_autenticar_usr.return_value = None  # No en DB todavía

        # Login legítimo con correo y PIN de clinica.json sin flag backdoor
        res = bridge.autenticar("camilo.torres@gmail.com", "5544")
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res["usuario"]["nombre"], "Dr. Camilo Torres")

        # Contraseña errónea
        res_bad = bridge.autenticar("camilo.torres@gmail.com", "0000")
        self.assertEqual(res_bad.get("status"), "error")

    # =========================================================================
    # BLOQUE 2: ESCUCHA ACTIVA INSTANTÁNEA Y PAUSA INTELIGENTE
    # =========================================================================
    def test_bloque2_configuracion_pausa_inteligente(self):
        from wake_word_listener import BackgroundWakeListener
        listener = BackgroundWakeListener(callback_comando=lambda x: None)

        # En reposo (sin activación previa), silencio corto para detectar "Bimo" rápido
        self.assertFalse(listener.esta_en_ventana_activa())

        # Activar ventana activa post-detección
        listener.activar_ventana_activa(10.0)
        self.assertTrue(listener.esta_en_ventana_activa())

    @patch("audio_feedback.sonar_inicio_dictado")
    def test_bloque2_filtro_ruido_y_feedback_instantaneo(self, mock_sonar_ding):
        import numpy as np
        from wake_word_listener import BackgroundWakeListener
        comandos_recibidos = []
        listener = BackgroundWakeListener(callback_comando=lambda cmd: comandos_recibidos.append(cmd))
        listener.tiempo_ventana_activa = 0.0

        # Simular que Whisper detecta solo la palabra de activación 'Bimo'
        with patch("wake_word_listener.get_whisper_engine") as mock_engine:
            mock_seg = MagicMock()
            mock_seg.no_speech_prob = 0.05
            mock_seg.text = "Bimo"
            mock_engine.return_value.transcribe.return_value = ([mock_seg], None)

            # Audio sinusoidal de prueba (1 segundo)
            sr = 16000
            t = np.linspace(0, 1.0, sr, endpoint=False)
            audio_test = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)

            listener._analizar_audio(audio_test)

            # Debe disparar feedback sonoro instantáneo (ding)
            mock_sonar_ding.assert_called()
            # Debe activar la ventana inteligente
            self.assertTrue(listener.esta_en_ventana_activa())
            # Debe notificar __BIMO_WAKE_LISTENING__ a la UI sin emitir comando clínico nulo
            self.assertIn("__BIMO_WAKE_LISTENING__", comandos_recibidos)

    # =========================================================================
    # BLOQUE 3: GUARDRAIL CLÍNICO ANTI-PDFS FANTASMA
    # =========================================================================
    @patch("desktop_app.sonar_error")
    @patch("desktop_app.registrar_o_actualizar_paciente")
    @patch("desktop_app.crear_historia_clinica")
    @patch("desktop_app.procesar_comando_o_dictado")
    def test_bloque3_guardrail_clinico_rechaza_no_clinico(self, mock_ia, mock_crear_pdf, mock_reg_pac, mock_sonar_error):
        from desktop_app import BimoBridge
        bridge = BimoBridge()

        # Caso A: Frase corta no clínica (< 5 palabras)
        mock_ia.return_value = {"tipo": "HISTORIA_CLINICA", "nombre_paciente": "Desconocido"}
        res_corto = bridge.procesar_texto_clinico("hola bimo")
        self.assertEqual(res_corto.get("tipo"), "IGNORAR")
        self.assertIn("Dictado muy corto o irrelevante", res_corto.get("mensaje", ""))
        mock_sonar_error.assert_called()
        mock_reg_pac.assert_not_called()
        mock_crear_pdf.assert_not_called()

        # Caso B: Frase larga de charla sin términos clínicos
        res_charla = bridge.procesar_texto_clinico("hoy es un bonito día soleado para salir a pasear")
        self.assertEqual(res_charla.get("tipo"), "IGNORAR")
        self.assertIn("Dictado muy corto o irrelevante", res_charla.get("mensaje", ""))
        mock_reg_pac.assert_not_called()
        mock_crear_pdf.assert_not_called()

    @patch("desktop_app.sonar_confirmacion_exito")
    @patch("desktop_app.registrar_o_actualizar_paciente")
    @patch("desktop_app.crear_historia_clinica")
    @patch("desktop_app.guardar_consulta_db")
    @patch("desktop_app.obtener_siguiente_num_expediente_paciente")
    @patch("desktop_app.obtener_consulta_del_dia")
    @patch("desktop_app.procesar_comando_o_dictado")
    def test_bloque3_guardrail_clinico_permite_dictado_valido(self, mock_ia, mock_hoy, mock_num, mock_guardar, mock_crear_pdf, mock_reg_pac, mock_sonar_ok):
        from desktop_app import BimoBridge
        bridge = BimoBridge()

        mock_ia.return_value = {
            "tipo": "HISTORIA_CLINICA",
            "datos_filiacion": {"nombre": "Ana Lucía Gómez", "cedula": "1722334455"},
            "diagnostico": "Caries profunda en pieza 46"
        }
        mock_hoy.return_value = None
        mock_num.return_value = 1
        mock_reg_pac.return_value = 42
        mock_guardar.return_value = 101
        mock_crear_pdf.return_value = "/path/test.pdf"

        # Dictado clínico completo (> 5 palabras y con 'paciente', 'dolor', 'pieza', 'caries')
        dictado_valido = "paciente Ana Lucía Gómez acude con dolor agudo por caries en pieza 46"
        res = bridge.procesar_texto_clinico(dictado_valido)
        self.assertEqual(res.get("tipo"), "HISTORIA_CLINICA")
        mock_reg_pac.assert_called()
        mock_crear_pdf.assert_called()

    # =========================================================================
    # BLOQUE 4: ROBUSTEZ EN NAVEGACIÓN RÁPIDA CON MULETILLAS
    # =========================================================================
    def test_bloque4_navegacion_rapida_con_muletillas(self):
        from ai_engine import resolver_navegacion_ui

        casos = [
            ("bimo este llévame a la agenda", "abrir_agenda"),
            ("vete a la agenda", "abrir_agenda"),
            ("pon la agenda", "abrir_agenda"),
            ("bimo porfa abre pacientes", "abrir_pacientes"),
            ("muéstrame historias", "abrir_pdf"),
            ("bimo a ver abre el visor de pdf", "abrir_pdf"),
            ("bimo eh pon dictado", "abrir_dictado"),
            ("bimo llévame a ajustes", "abrir_configuracion"),
        ]

        for frase, accion_esperada in casos:
            res = resolver_navegacion_ui(frase)
            self.assertIsNotNone(res, f"Falló al resolver: '{frase}'")
            self.assertEqual(res.get("accion"), accion_esperada, f"Acción incorrecta para '{frase}': {res.get('accion')}")

if __name__ == "__main__":
    unittest.main()
