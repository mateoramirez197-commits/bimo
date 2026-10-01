import os
import sys
import unittest
import tempfile
import time
import datetime
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
import ai_engine
import voice_assistant
import audio_feedback
from desktop_app import BimoBridge

class TestConversacionalV5(unittest.TestCase):
    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()

        from pathlib import Path
        self.db_patcher = patch.object(database, "RUTA_DB", Path(self.temp_db_path))
        self.db_patcher.start()
        database.init_db()

        with database.get_connection() as conn:
            conn.cursor().execute(
                "INSERT OR IGNORE INTO usuarios (id, nombre, email, password_hash) VALUES (1, 'Dr. Mateo', 'test@bimo.local', 'hash')"
            )
            conn.commit()

    def tearDown(self):
        self.db_patcher.stop()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # ==========================================================
    # BLOQUE 1: Estabilización de la Voz TTS (audio_feedback / voice_assistant)
    # ==========================================================
    def test_detectar_voz_espanol_selecciona_voz_hispana(self):
        """Verifica que el selector de voz elija Helena/Sabina/Spanish y NUNCA David o Zira."""
        class MockVoice:
            def __init__(self, voice_id, name):
                self.id = voice_id
                self.name = name

        voices_sample = [
            MockVoice("HKEY_LOCAL_MACHINE\\...\\Tokens\\TTS_MS_EN-US_DAVID_11.0", "Microsoft David Desktop - English (United States)"),
            MockVoice("HKEY_LOCAL_MACHINE\\...\\Tokens\\TTS_MS_EN-US_ZIRA_11.0", "Microsoft Zira Desktop - English (United States)"),
            MockVoice("HKEY_LOCAL_MACHINE\\...\\Tokens\\TTS_MS_ES-ES_HELENA_11.0", "Microsoft Helena Desktop - Spanish (Spain)"),
        ]

        mock_engine = MagicMock()
        mock_engine.getProperty.return_value = voices_sample

        voz_id = voice_assistant.detectar_voz_espanol(mock_engine, forzar_recacheo=True)
        self.assertIsNotNone(voz_id)
        self.assertIn("HELENA", voz_id.upper())
        self.assertNotIn("DAVID", voz_id.upper())
        self.assertNotIn("ZIRA", voz_id.upper())

    def test_detectar_voz_espanol_ignora_voces_ingles(self):
        """Si solo hay voces en inglés, nunca selecciona David o Zira."""
        class MockVoice:
            def __init__(self, voice_id, name):
                self.id = voice_id
                self.name = name

        voices_english = [
            MockVoice("id_david", "Microsoft David Desktop - English (United States)"),
            MockVoice("id_zira", "Microsoft Zira Desktop - English (United States)"),
            MockVoice("id_george", "Microsoft George - English (United Kingdom)"),
        ]

        mock_engine = MagicMock()
        mock_engine.getProperty.return_value = voices_english

        voz_id = voice_assistant.detectar_voz_espanol(mock_engine, forzar_recacheo=True)
        self.assertIsNone(voz_id)

    def test_interfaces_hablar_expuestas_en_modulos(self):
        """Verifica que hablar y hablar_asincrono existan en audio_feedback y voice_assistant."""
        self.assertTrue(callable(getattr(audio_feedback, "hablar", None)))
        self.assertTrue(callable(getattr(audio_feedback, "hablar_asincrono", None)))
        self.assertTrue(callable(getattr(voice_assistant, "hablar", None)))
        self.assertTrue(callable(getattr(voice_assistant, "hablar_asincrono", None)))

    # ==========================================================
    # BLOQUE 2: Reparación de Extracción de Citas (ai_engine.py)
    # ==========================================================
    def test_limpiar_nombre_paciente_aisla_nombre_sin_destruir_tiempo(self):
        """Verifica que limpiar_nombre_paciente elimine proposiciones y tiempo del nombre sin afectar el texto."""
        nom1 = ai_engine.limpiar_nombre_paciente("genera una cita para Mateo mañana a las 3")
        self.assertEqual(nom1, "Mateo")

        nom2 = ai_engine.limpiar_nombre_paciente("agenda a Juan Ramírez para el viernes a las 11")
        self.assertEqual(nom2, "Juan Ramírez")

        nom3 = ai_engine.limpiar_nombre_paciente("separar cita con Sebastián Toapanta mañana")
        self.assertEqual(nom3, "Sebastián Toapanta")

    def test_resolver_fecha_relativa_espanol_mañana_a_las_3(self):
        """Verifica que 'mañana a las 3' asuma las 15:00 en contexto de consultorio."""
        base = datetime.datetime(2026, 10, 1, 9, 0, 0)
        res = ai_engine.resolver_fecha_relativa_espanol("mañana a las 3", base_dt=base)
        self.assertIsNotNone(res)
        self.assertEqual(res, "2026-10-02 15:00:00")

    def test_resolver_fecha_relativa_espanol_hoy_y_hora_sola(self):
        """Verifica resolución determinista para 'hoy a las 4' y 'a las 3'."""
        base = datetime.datetime(2026, 10, 1, 9, 0, 0)
        res_hoy = ai_engine.resolver_fecha_relativa_espanol("hoy a las 4", base_dt=base)
        self.assertEqual(res_hoy, "2026-10-01 16:00:00")

        res_hora = ai_engine.resolver_fecha_relativa_espanol("a las 3", base_dt=base)
        self.assertEqual(res_hora, "2026-10-01 15:00:00")

    def test_resolver_comando_agendar_cita_completo(self):
        """Verifica extracción directa de nombre, fecha y hora sin requerir seguimiento."""
        base = datetime.datetime(2026, 10, 1, 9, 0, 0)
        with patch("datetime.datetime") as mock_dt:
            mock_dt.now.return_value = base
            mock_dt.side_effect = lambda *args, **kw: datetime.datetime(*args, **kw)
            
            cmd = ai_engine.resolver_comando_agendar_cita("genera una cita para Mateo mañana a las 3")
            self.assertIsNotNone(cmd)
            self.assertEqual(cmd["tipo"], "COMANDO_CITA")
            self.assertEqual(cmd["nombre_paciente"], "Mateo")
            self.assertIn("15:00:00", cmd["fecha_hora"])
            self.assertFalse(cmd.get("requiere_seguimiento", False))
            self.assertFalse(cmd.get("requiere_fecha_hora", False))

    def test_resolver_comando_agendar_cita_incompleto_requiere_seguimiento(self):
        """Verifica que si no se dictó fecha u hora, devuelva requiere_seguimiento = True."""
        cmd = ai_engine.resolver_comando_agendar_cita("genera una cita para Mateo")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd["tipo"], "COMANDO_CITA")
        self.assertEqual(cmd["nombre_paciente"], "Mateo")
        self.assertIsNone(cmd.get("fecha_hora"))
        self.assertTrue(cmd.get("requiere_seguimiento", False))
        self.assertTrue(cmd.get("requiere_fecha_hora", False))

    # ==========================================================
    # BLOQUE 3: Flujo Multi-Turno y Auto-Escucha (desktop_app.py)
    # ==========================================================
    def test_flujo_multiturno_cita_esperando_respuesta_y_resolucion(self):
        """
        Verifica el ciclo completo multi-turno:
        1. Se dicta 'agenda cita para Mateo' -> falta fecha/hora.
        2. El sistema devuelve requiere_seguimiento = True y activa _esperando_respuesta.
        3. El usuario responde 'mañana a las 3' en el siguiente turno.
        4. El sistema ageda exitosamente la cita para Mateo mañana a las 15:00:00.
        """
        bridge = BimoBridge()
        bridge._window = MagicMock()
        bridge._wake_listener = MagicMock()

        with patch("desktop_app.preguntar_fecha_hora_cita") as mock_preguntar, \
             patch("desktop_app.agendar_cita") as mock_agendar, \
             patch("desktop_app.sonar_confirmacion_exito"), \
             patch("desktop_app.decir_confirmacion_cita"):

            mock_agendar.return_value = {"status": "ok", "cita_id": 999, "url_gcal": ""}

            # Turno 1: Orden sin fecha/hora
            resp1 = bridge.procesar_texto_clinico("agenda cita para Mateo")
            self.assertEqual(resp1.get("status"), "requiere_fecha_hora")
            self.assertTrue(resp1.get("requiere_seguimiento"))
            self.assertTrue(bridge._esperando_respuesta)
            self.assertIsNotNone(bridge._cita_pendiente)
            self.assertEqual(bridge._cita_pendiente["nombre_paciente"], "Mateo")
            mock_preguntar.assert_called_once_with("Mateo")

            # Turno 2: Respuesta directa del usuario a la pregunta ("mañana a las 3")
            resp2 = bridge.procesar_texto_clinico("mañana a las 3")
            self.assertEqual(resp2.get("status"), "ok")
            self.assertEqual(resp2.get("tipo"), "COMANDO_CITA")
            self.assertFalse(resp2.get("requiere_seguimiento", True))
            self.assertEqual(resp2.get("nombre_paciente"), "Mateo")
            self.assertIn("15:00:00", resp2.get("fecha_hora", ""))

            # Estado post-resolución
            self.assertFalse(bridge._esperando_respuesta)
            self.assertIsNone(bridge._cita_pendiente)
            mock_agendar.assert_called_once()

    def test_flujo_multiturno_descarta_cita_pendiente_si_entra_historia_clinica(self):
        """Verifica que si el doctor empieza a dictar una historia clínica, se descarte la cita pendiente."""
        bridge = BimoBridge()
        bridge._esperando_respuesta = True
        bridge._cita_pendiente = {
            "nombre_paciente": "Carlos",
            "telefono": "",
            "motivo": "Consulta",
            "timestamp": time.time(),
            "esperando": "fecha_hora"
        }

        with patch("desktop_app.procesar_comando_o_dictado") as mock_ia:
            mock_ia.return_value = {"tipo": "IGNORAR"}
            bridge.procesar_texto_clinico("paciente acude por dolor en pieza 46")
            self.assertFalse(bridge._esperando_respuesta)
            self.assertIsNone(bridge._cita_pendiente)

if __name__ == "__main__":
    unittest.main()
