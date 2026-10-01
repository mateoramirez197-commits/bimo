import os
import sys
import unittest
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch

# Asegurar importación de módulos del proyecto
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import database
import desktop_app
from database import (
    buscar_paciente_por_similitud,
    registrar_o_actualizar_paciente,
    listar_consultas_paciente,
    get_connection
)

class TestMegaPromptV4(unittest.TestCase):
    def setUp(self):
        # Crear base de datos temporal para pruebas aisladas
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()

        from pathlib import Path
        # Parchear database.RUTA_DB para usar la DB de pruebas
        self.db_patcher = patch.object(database, "RUTA_DB", Path(self.temp_db_path))
        self.db_patcher.start()

        # Inicializar esquema
        database.init_db()
        with get_connection() as conn:
            conn.cursor().execute("INSERT OR IGNORE INTO usuarios (id, nombre, email, password_hash) VALUES (1, 'Dr. Mateo', 'test@bimo.local', 'hash')")
            conn.commit()

    def tearDown(self):
        self.db_patcher.stop()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    # ==========================================================
    # BLOQUE 1: Prevención de Duplicados mediante Similitud Difusa
    # ==========================================================
    def test_buscar_paciente_por_similitud_mayor_85(self):
        with get_connection() as conn:
            conn.cursor().execute("""
                INSERT INTO pacientes (nombre, edad, telefono)
                VALUES ('Mateo Ramírez', 32, '0999999999')
            """)
            conn.commit()

        # Variación con tilde / sin tilde
        match1 = buscar_paciente_por_similitud("Mateo Ramirez", umbral=0.85)
        self.assertIsNotNone(match1)
        self.assertEqual(match1["nombre"], "Mateo Ramírez")
        self.assertGreater(match1["_similitud"], 0.85)

        # Variación fonética / ortográfica (Ramires vs Ramírez)
        match2 = buscar_paciente_por_similitud("Mateo Ramires", umbral=0.85)
        self.assertIsNotNone(match2)
        self.assertEqual(match2["nombre"], "Mateo Ramírez")
        self.assertGreater(match2["_similitud"], 0.85)

    def test_buscar_paciente_por_similitud_diferente_retorna_none(self):
        with get_connection() as conn:
            conn.cursor().execute("""
                INSERT INTO pacientes (nombre, edad, telefono)
                VALUES ('Mateo Ramírez', 32, '0999999999')
            """)
            conn.commit()

        # Paciente completamente diferente
        match = buscar_paciente_por_similitud("Mateo Villacreses", umbral=0.85)
        self.assertIsNone(match)

    def test_registrar_o_actualizar_reutiliza_id_por_similitud(self):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO pacientes (nombre, edad, telefono) VALUES ('Carlos Ruiz', 40, '0987654321')")
            original_id = cur.lastrowid
            conn.commit()

        # Se registra variación "Carlos Ruis" sin cédula
        reused_id = registrar_o_actualizar_paciente({"nombre": "Carlos Ruis", "edad": 40, "telefono": "0987654321"})
        self.assertEqual(reused_id, original_id, "Debe reutilizar el ID existente si la similitud > 85%")

        # Verificar que no se creó un segundo paciente
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total FROM pacientes")
            total = cur.fetchone()["total"]
            self.assertEqual(total, 1, "No debe duplicar pacientes con variaciones ortográficas")

    def test_procesar_texto_clinico_reutiliza_paciente_por_similitud(self):
        app = desktop_app.BimoBridge()
        app._window = MagicMock()

        # Insertar paciente previo
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO pacientes (nombre, edad, telefono) VALUES ('Sofía Morales', 28, '0912345678')")
            pid_original = cur.lastrowid
            conn.commit()

        # Mock de IA devolviendo variación "Sofia Morales"
        dictado_texto = "paciente Sofia Morales presenta dolor agudo en molar pieza 18 con caries oclusal"
        mock_ia = {
            "tipo": "HISTORIA_CLINICA",
            "datos_filiacion": {"nombre": "Sofia Morales", "edad": 28},
            "nombre_paciente": "Sofia Morales",
            "diagnostico": "Caries oclusal en pieza 18",
            "plan_tratamiento": "Restauración con resina"
        }

        with patch("desktop_app.procesar_comando_o_dictado", return_value=mock_ia), \
             patch("desktop_app.crear_historia_clinica", return_value="dummy.pdf"):
            res = app.procesar_texto_clinico(dictado_texto)
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["paciente_id"], pid_original, "Debe reutilizar automáticamente el id existente")
            self.assertEqual(res["paciente"], "Sofía Morales", "Debe reutilizar el nombre existente")

    # ==========================================================
    # BLOQUE 2: Reactividad y Refresco Automático de la Interfaz
    # ==========================================================
    def test_reactividad_refresco_dom_inyecta_js_recarga(self):
        app = desktop_app.BimoBridge()
        mock_window = MagicMock()
        mock_window.evaluate_js = MagicMock()
        app._window = mock_window

        dictado_texto = "paciente Juan Pérez presenta dolor agudo en pieza 21 por caries profunda"
        mock_ia = {
            "tipo": "HISTORIA_CLINICA",
            "datos_filiacion": {"nombre": "Juan Pérez", "edad": 35},
            "nombre_paciente": "Juan Pérez",
            "diagnostico": "Caries pieza 21",
            "plan_tratamiento": "Obturación"
        }

        with patch("desktop_app.procesar_comando_o_dictado", return_value=mock_ia), \
             patch("desktop_app.crear_historia_clinica", return_value="dummy.pdf"):
            app.procesar_texto_clinico(dictado_texto)

            # Verificar que evaluate_js fue llamado con la orden de recarga en segundo plano y switchTab('pdf')
            llamadas_js = [call.args[0] for call in mock_window.evaluate_js.call_args_list if call.args]
            js_combinado = " ".join(llamadas_js)
            self.assertIn("cargarPacientes", js_combinado)
            self.assertIn("cargarCitas", js_combinado)
            self.assertIn("switchTab('pdf')", js_combinado)

    # ==========================================================
    # BLOQUE 3: Agrupación de Consultas en el Historial (DATETIME DESC)
    # ==========================================================
    def test_listar_consultas_orden_datetime_desc(self):
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO pacientes (nombre) VALUES ('Paciente Consultas')")
            pid = cur.lastrowid

            # Insertar consultas con fechas desordenadas
            cur.execute("INSERT INTO consultas (paciente_id, fecha_hora, diagnostico, json_clinico) VALUES (?, ?, ?, '{}')",
                        (pid, "2026-05-10 10:00:00", "Consulta Antigua Mayo"))
            cur.execute("INSERT INTO consultas (paciente_id, fecha_hora, diagnostico, json_clinico) VALUES (?, ?, ?, '{}')",
                        (pid, "2026-09-30 20:00:00", "Consulta Más Reciente"))
            cur.execute("INSERT INTO consultas (paciente_id, fecha_hora, diagnostico, json_clinico) VALUES (?, ?, ?, '{}')",
                        (pid, "2026-08-15 14:30:00", "Consulta Media Agosto"))
            conn.commit()

        consultas = listar_consultas_paciente(pid)
        self.assertEqual(len(consultas), 3, "Debe retornar todas las consultas del paciente")
        self.assertEqual(consultas[0]["diagnostico"], "Consulta Más Reciente", "La más reciente debe ir de primera")
        self.assertEqual(consultas[1]["diagnostico"], "Consulta Media Agosto")
        self.assertEqual(consultas[2]["diagnostico"], "Consulta Antigua Mayo")

    # ==========================================================
    # BLOQUE 4: Eliminación de Subtítulos y Toasts Minimalistas
    # ==========================================================
    def test_wake_command_no_envia_texto_crudo_a_toast(self):
        app = desktop_app.BimoBridge()
        mock_window = MagicMock()
        mock_window.evaluate_js = MagicMock()
        app._window = mock_window

        dictado_largo = "paciente Juan presenta dolor intenso en pieza 14 con fractura coronal extensa"

        # Simular llegada de comando desde el wake listener
        with patch.object(app, "_ejecutar_comando_detectado"):
            app._on_wake_command(dictado_largo)

            # Verificar que en ningún evaluate_js se envió dictado_largo a un toast
            llamadas = [call.args[0] for call in mock_window.evaluate_js.call_args_list if call.args]
            for js in llamadas:
                self.assertNotIn(dictado_largo, js, "No se debe enviar la transcripción cruda al toast como subtítulo")

            # Verificar que el toast enviado es estrictamente minimalista: 'Procesando dictado...'
            js_toast = " ".join(llamadas)
            self.assertIn("Procesando dictado...", js_toast)

    def test_wake_word_activacion_envia_toast_escuchando(self):
        app = desktop_app.BimoBridge()
        mock_window = MagicMock()
        mock_window.evaluate_js = MagicMock()
        app._window = mock_window

        app._on_wake_command("__BIMO_WAKE_LISTENING__")
        llamadas = [call.args[0] for call in mock_window.evaluate_js.call_args_list if call.args]
        js_toast = " ".join(llamadas)
        self.assertIn("Escuchando...", js_toast)
        self.assertNotIn("Te escucho,", js_toast)

if __name__ == "__main__":
    unittest.main()
