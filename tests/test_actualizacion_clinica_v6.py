import os
import sys
import unittest
import tempfile
import time
import json
import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
import ai_engine
import generador_pdf
import mobile_mic_server
from desktop_app import BimoBridge

class TestActualizacionClinicaV6(unittest.TestCase):
    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()

        self.temp_dir = tempfile.mkdtemp(prefix="bimo_test_v6_")

        self.db_patcher = patch.object(database, "RUTA_DB", Path(self.temp_db_path))
        self.pacientes_patcher = patch.object(database, "RUTA_PACIENTES", Path(self.temp_dir))
        self.db_patcher.start()
        self.pacientes_patcher.start()
        database.init_db()

        with database.get_connection() as conn:
            conn.cursor().execute(
                "INSERT OR IGNORE INTO usuarios (id, nombre, email, password_hash) VALUES (1, 'Dr. Mateo', 'test@bimo.local', 'hash')"
            )
            conn.commit()

    def tearDown(self):
        self.db_patcher.stop()
        self.pacientes_patcher.stop()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ==========================================================
    # BLOQUE 1: Extracción de Intención del Expediente y Cédula
    # ==========================================================
    def test_extraer_accion_expediente_actualizar(self):
        """Verifica que frases de actualización devuelvan 'actualizar'."""
        frases = [
            "agrégale al expediente que presenta dolor en pieza 16",
            "actualiza la consulta de hoy con amoxicilina",
            "me olvidé de decir que tiene sarro subgingival",
            "ponle también que se le colocó resina en molar",
            "añade al historial que tiene caries interproximal"
        ]
        for f in frases:
            accion = ai_engine.extraer_accion_expediente(f)
            self.assertEqual(accion, "actualizar", f"Falló para frase: '{f}'")

    def test_extraer_accion_expediente_nuevo(self):
        """Verifica que frases de nuevo expediente devuelvan 'nuevo'."""
        frases = [
            "genérame un expediente aparte para Mateo",
            "crea un nuevo expediente para la paciente",
            "haz otra consulta por favor",
            "inicia nueva consulta dental"
        ]
        for f in frases:
            accion = ai_engine.extraer_accion_expediente(f)
            self.assertEqual(accion, "nuevo", f"Falló para frase: '{f}'")

    def test_extraer_accion_expediente_predeterminado(self):
        """Verifica que dictados estándar devuelvan 'predeterminado'."""
        frases = [
            "paciente acude por dolor en pieza 46, se observa caries profunda",
            "control postoperatorio favorable sin inflamación"
        ]
        for f in frases:
            accion = ai_engine.extraer_accion_expediente(f)
            self.assertEqual(accion, "predeterminado", f"Falló para frase: '{f}'")

    def test_extraer_digitos_cedula(self):
        """Verifica la extracción de 10 dígitos de cédula desde texto o palabras."""
        self.assertEqual(ai_engine.extraer_digitos_cedula("la cédula es 1723456789"), "1723456789")
        self.assertEqual(ai_engine.extraer_digitos_cedula("cédula 0912345678"), "0912345678")
        self.assertEqual(ai_engine.extraer_digitos_cedula("uno siete dos tres cuatro cinco seis siete ocho nueve"), "1723456789")
        self.assertIsNone(ai_engine.extraer_digitos_cedula("no recuerdo el número"))

    # ==========================================================
    # BLOQUE 2: Lógica de Fusión / Actualización Clínica en Mismo Día
    # ==========================================================
    def test_fusion_misma_consulta_del_dia(self):
        """
        Verifica que al dictar una actualización para un paciente que ya tiene consulta hoy:
        1. No se cree un nuevo ID de consulta.
        2. Se concatene el nuevo diagnóstico con '[Actualización]: '.
        3. Se fusionen las piezas del odontograma.
        4. Se sobrescriba la misma ruta de PDF.
        """
        # 1. Registrar paciente inicial
        pac_id = database.registrar_o_actualizar_paciente(
            nombre="Carlos Benítez",
            cedula="1711223344",
            telefono="0998877665",
            email="carlos@test.local"
        )

        pdf_dummy = os.path.join(self.temp_dir, "historia_carlos.pdf")
        with open(pdf_dummy, "w") as f:
            f.write("%PDF-1.4 dummy initial")

        # 2. Registrar consulta inicial de hoy
        cid_inicial = database.guardar_consulta_db(
            paciente_id=pac_id,
            json_clinico={
                "motivo_consulta": "Dolor agudo en molar inferior",
                "diagnostico": "Caries oclusal en pieza 46",
                "plan_tratamiento": "Apertura y curación provisional",
                "prescripcion": {"medicamentos": "Ibuprofeno 400mg c/8h"},
                "odontograma": [{"pieza_dental": "46", "procedimientos_o_hallazgos": ["caries"]}]
            },
            ruta_pdf=pdf_dummy
        )

        bridge = BimoBridge()
        bridge._window = MagicMock()

        resultado_dictado_actualizacion = {
            "tipo": "HISTORIA_CLINICA",
            "accion_expediente": "actualizar",
            "paciente": {
                "nombre": "Carlos Benítez",
                "cedula": "1711223344",
                "telefono": "0998877665",
                "email": "carlos@test.local"
            },
            "anamnesis": {"motivo_consulta": "Revisión adicional"},
            "diagnostico": {"descripcion": "Se detecta también fractura en esmalte"},
            "tratamiento": {"plan": "Pulido y aplicación de flúor"},
            "prescripcion": {"medicamentos": "Enjuague bucal clorexidina"},
            "odontograma": [{"pieza_dental": "47", "procedimientos_o_hallazgos": ["fractura"]}],
            "citas_programadas": [],
            "pagos": {}
        }

        with patch("desktop_app.procesar_comando_o_dictado", return_value=resultado_dictado_actualizacion), \
             patch("desktop_app.crear_historia_clinica", return_value=pdf_dummy) as mock_pdf, \
             patch("voice_assistant.hablar_asincrono"):

            resp = bridge.procesar_texto_clinico("agrégale al expediente que presenta fractura en pieza 47")

            self.assertEqual(resp.get("status"), "ok")
            self.assertEqual(resp.get("accion"), "actualizada")
            self.assertEqual(resp.get("consulta_id"), cid_inicial)

            # Verificar que no se creó otra consulta
            consultas = database.listar_consultas_paciente(pac_id)
            self.assertEqual(len(consultas), 1)

            # Verificar fusión de diagnóstico
            c_actual = consultas[0]
            self.assertIn("Caries oclusal en pieza 46", c_actual["diagnostico"])
            self.assertIn("[Actualización]:", c_actual["diagnostico"])
            self.assertIn("fractura en esmalte", c_actual["diagnostico"])

            # Verificar fusión de odontograma
            odonto_str = c_actual.get("json_clinico", "{}")
            odonto_data = json.loads(odonto_str)
            odonto_piezas = [p.get("pieza_dental") for p in odonto_data.get("odontograma", [])]
            self.assertIn("46", odonto_piezas)
            self.assertIn("47", odonto_piezas)

            # Verificar que se solicitó sobrescribir la ruta fija
            mock_pdf.assert_called_once()
            _, kwargs = mock_pdf.call_args
            self.assertEqual(kwargs.get("ruta_salida_fija"), pdf_dummy)

    def test_forzar_nuevo_expediente_crea_segunda_consulta(self):
        """Si accion_expediente == 'nuevo', debe crear un registro de consulta separado."""
        pac_id = database.registrar_o_actualizar_paciente(
            nombre="Lucía Gómez",
            cedula="1722334455"
        )
        cid_inicial = database.guardar_consulta_db(
            paciente_id=pac_id,
            json_clinico={
                "motivo_consulta": "Primera consulta",
                "diagnostico": "Gingivitis leve"
            },
            ruta_pdf=os.path.join(self.temp_dir, "lucia_1.pdf")
        )

        bridge = BimoBridge()
        bridge._window = MagicMock()

        resultado_dictado_nuevo = {
            "tipo": "HISTORIA_CLINICA",
            "accion_expediente": "nuevo",
            "paciente": {"nombre": "Lucía Gómez", "cedula": "1722334455"},
            "anamnesis": {"motivo_consulta": "Consulta independiente por ortodoncia"},
            "diagnostico": {"descripcion": "Maloclusión clase II"},
            "tratamiento": {"plan": "Estudio cefalométrico"},
            "prescripcion": {"medicamentos": ""},
            "odontograma": [],
            "citas_programadas": [],
            "pagos": {}
        }

        with patch("desktop_app.procesar_comando_o_dictado", return_value=resultado_dictado_nuevo), \
             patch("desktop_app.crear_historia_clinica", return_value=os.path.join(self.temp_dir, "lucia_v2.pdf")), \
             patch("voice_assistant.hablar_asincrono"):

            resp = bridge.procesar_texto_clinico("genérame un expediente aparte para Lucía Gómez")

            self.assertEqual(resp.get("status"), "ok")
            self.assertEqual(resp.get("accion"), "creada")
            self.assertNotEqual(resp.get("consulta_id"), cid_inicial)

            consultas = database.listar_consultas_paciente(pac_id)
            self.assertEqual(len(consultas), 2)

    # ==========================================================
    # BLOQUE 3: Desambiguación de Cédula por Voz
    # ==========================================================
    def test_desambiguacion_cedula_multiturno(self):
        """
        Verifica el flujo conversacional de desambiguación:
        1. Existen dos pacientes homónimos 'Juan Pérez' con cédulas distintas.
        2. Dictado de historia clínica menciona 'Juan Pérez' sin cédula.
        3. El sistema detecta homónimos, solicita cédula y activa auto-escucha.
        4. El usuario dicta la cédula en el siguiente turno.
        5. El sistema resuelve el paciente correcto y guarda la consulta.
        """
        # Registrar 2 homónimos
        p1_id = database.registrar_o_actualizar_paciente(nombre="Juan Pérez", cedula="0911111111", email="juan1@bimo.local")
        p2_id = database.registrar_o_actualizar_paciente(nombre="Juan Pérez", cedula="0922222222", email="juan2@bimo.local")

        bridge = BimoBridge()
        bridge._window = MagicMock()

        historia_sin_cedula = {
            "tipo": "HISTORIA_CLINICA",
            "accion_expediente": "predeterminado",
            "paciente": {"nombre": "Juan Pérez", "cedula": ""},
            "anamnesis": {"motivo_consulta": "Limpieza general"},
            "diagnostico": {"descripcion": "Placa bacteriana leve"},
            "tratamiento": {"plan": "Profilaxis"},
            "prescripcion": {"medicamentos": ""},
            "odontograma": [],
            "citas_programadas": [],
            "pagos": {}
        }

        with patch("desktop_app.procesar_comando_o_dictado", return_value=historia_sin_cedula), \
             patch("voice_assistant.hablar_asincrono") as mock_hablar, \
             patch.object(bridge, "_activar_auto_escucha_post_habla") as mock_auto_escucha, \
             patch("desktop_app.crear_historia_clinica", return_value=os.path.join(self.temp_dir, "juan2.pdf")):

            # Turno 1: Dictado con nombre ambiguo
            resp1 = bridge.procesar_texto_clinico("historia clínica para Juan Pérez acude por profilaxis")

            self.assertEqual(resp1.get("status"), "requiere_cedula")
            self.assertTrue(resp1.get("requiere_seguimiento"))
            self.assertTrue(bridge._esperando_respuesta_cedula)
            self.assertIsNotNone(bridge._historia_pendiente)
            mock_hablar.assert_called_once()
            self.assertIn("cédula", mock_hablar.call_args[0][0].lower())
            mock_auto_escucha.assert_called_once_with(12.0)

            # Turno 2: Respuesta con la cédula del segundo Juan Pérez
            resp2 = bridge.procesar_texto_clinico("cédula 0922222222")

            self.assertEqual(resp2.get("status"), "ok")
            self.assertEqual(resp2.get("paciente_id"), p2_id)
            self.assertFalse(bridge._esperando_respuesta_cedula)
            self.assertIsNone(bridge._historia_pendiente)

            consultas_p2 = database.listar_consultas_paciente(p2_id)
            self.assertEqual(len(consultas_p2), 1)
            self.assertIn("Placa bacteriana leve", consultas_p2[0]["diagnostico"])

    # ==========================================================
    # BLOQUE 4: Sincronización Móvil Transparente (mobile_mic_server.py)
    # ==========================================================
    def test_mobile_api_procesar_audio_o_texto(self):
        """Verifica que el endpoint /api/procesar_audio enrute texto al callback de procesamiento clínico."""
        from fastapi.testclient import TestClient
        client = TestClient(mobile_mic_server.app)

        token = mobile_mic_server.obtener_o_crear_movil_token()

        mock_cb_texto = MagicMock(return_value={"status": "ok", "tipo": "HISTORIA_CLINICA"})
        mobile_mic_server._CALLBACK_TEXTO = mock_cb_texto

        # 1. Petición no autorizada
        r_unauth = client.post("/api/procesar_audio", json={"texto": "paciente con dolor"})
        self.assertEqual(r_unauth.status_code, 401)

        # 2. Petición autorizada con JSON
        r_auth = client.post(
            "/api/procesar_audio",
            headers={"X-Bimo-Token": token},
            json={"texto": "agrégale que tiene caries en pieza 11"}
        )
        self.assertEqual(r_auth.status_code, 200)
        data = r_auth.json()
        self.assertTrue(data.get("ok"))
        mock_cb_texto.assert_called_once_with("agrégale que tiene caries en pieza 11")

if __name__ == "__main__":
    unittest.main()
