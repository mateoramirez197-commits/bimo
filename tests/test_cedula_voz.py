import os
import sys
import json
import time
import unittest
import subprocess
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from desktop_app import BimoBridge


def ejecutar_js_en_node(codigo_js):
    """Ejecuta un fragmento JS usando Node.js cargando las funciones de web_ui/index.html."""
    html_path = os.path.join(PROJECT_ROOT, "web_ui", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Extraer las funciones del modal
    script_runner = f"""
    // Mock de objetos del navegador
    const window = {{}};
    const document = {{
        getElementById: function(id) {{
            return {{
                classList: {{
                    contains: function(c) {{ return false; }},
                    remove: function() {{}},
                    add: function() {{}}
                }},
                style: {{ display: 'block' }},
                value: '',
                dispatchEvent: function() {{}},
                click: function() {{}}
            }};
        }}
    }};
    function Event(type, opts) {{ this.type = type; this.opts = opts; }}
    function mostrarToast() {{}}

    // Inyectar HTML scripts
    {html_content[html_content.find("window.cedulaGuardandoPorVoz = false;"):html_content.find("// ==========================================\n    // VISOR DE PDF")]}

    const inyectarCedulaPorVoz = window.inyectarCedulaPorVoz;

    // Código de prueba a ejecutar
    {codigo_js}
    """
    res = subprocess.run(
        ["node", "-e", script_runner],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT
    )
    if res.returncode != 0:
        raise RuntimeError(f"Error ejecutando Node: {res.stderr}\nCódigo:\n{script_runner}")
    return res.stdout.strip()


class TestCedulaVozYModulo10(unittest.TestCase):
    """
    Suite de pruebas para el Bloque 3:
    Inyección de cédula por voz, parser de palabras numéricas a dígitos,
    algoritmo de validación módulo 10 ecuatoriano e integración con backend.
    """

    # 1. Dígitos directos
    def test_01_cedula_digitos_directos(self):
        js = """
        const c = cedulaDesdeTexto('1724891203');
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["cedula"], "1724891203")
        self.assertTrue(out["valida"])

    # 2. Dígitos hablados individuales
    def test_02_cedula_palabras_individuales(self):
        js = """
        const c = cedulaDesdeTexto('uno siete dos cuatro ocho nueve uno dos cero tres');
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["cedula"], "1724891203")
        self.assertTrue(out["valida"])

    # 3. Pares o decenas habladas
    def test_03_cedula_pares_y_decenas(self):
        js = """
        const c = cedulaDesdeTexto('diecisiete veinticuatro ochenta y nueve doce cero tres');
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["cedula"], "1724891203")
        self.assertTrue(out["valida"])

    # 4. Cédula Guayas (09) válida
    def test_04_cedula_guayas_valida(self):
        # 0924891203 -> 0*2 + 9*1 + 2*2 + 4*1 + (16-9) + 9*1 + 2*2 + 2*1 + 0*2 = 37 -> (10-7)%10 = 3
        js = """
        const c = cedulaDesdeTexto('cero nueve dos cuatro ocho nueve uno dos cero tres');
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["cedula"], "0924891203")
        self.assertTrue(out["valida"])

    # 5. Cédula Azuay (01) válida
    def test_05_cedula_azuay_valida(self):
        # 0102030400 -> 0 + 1 + 0 + 2 + 0 + 3 + 0 + 4 + 0 = 10 -> (10 - 0)%10 = 0
        js = """
        const c = cedulaDesdeTexto('cero uno cero dos cero tres cero cuatro cero cero');
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["cedula"], "0102030400")
        self.assertTrue(out["valida"])

    # 6. Con pausas, muletillas y palabras parásitas
    def test_06_cedula_con_muletillas_y_pausas(self):
        js = """
        const c = cedulaDesdeTexto('cédula del paciente por favor uno siete... dos cuatro... ocho nueve... uno dos cero tres gracias');
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["cedula"], "1724891203")
        self.assertTrue(out["valida"])

    # 7. Separada con espacios o guiones
    def test_07_cedula_con_espacios_y_guiones(self):
        js = """
        const c1 = cedulaDesdeTexto('17 24 89 12 03');
        const c2 = cedulaDesdeTexto('17-24-89-12-03');
        console.log(JSON.stringify({ c1: c1, c2: c2, v1: validarCedulaEcuatoriana(c1), v2: validarCedulaEcuatoriana(c2) }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["c1"], "1724891203")
        self.assertEqual(out["c2"], "1724891203")
        self.assertTrue(out["v1"])
        self.assertTrue(out["v2"])

    # 8. Cédula inválida por dígito verificador incorrecto
    def test_08_cedula_invalida_digito_verificador(self):
        js = """
        const c = '1724891209'; // Termina en 9 en vez de 3
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertFalse(out["valida"])

    # 9. Cédula inválida por provincia fuera de rango (ej. 35)
    def test_09_cedula_invalida_provincia_inexistente(self):
        js = """
        const v = validarCedulaEcuatoriana('3501234567');
        console.log(JSON.stringify({ valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertFalse(out["valida"])

    # 10. Cédula inválida por tercer dígito >= 6
    def test_10_cedula_invalida_tercer_digito(self):
        js = """
        const v = validarCedulaEcuatoriana('1781234567');
        console.log(JSON.stringify({ valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertFalse(out["valida"])

    # 11. Dictado corto (< 10 dígitos)
    def test_11_dictado_insuficiente(self):
        js = """
        const c = cedulaDesdeTexto('uno siete dos cuatro');
        console.log(JSON.stringify({ cedula: c, longitud: c.length }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["longitud"], 4)
        self.assertNotEqual(out["longitud"], 10)

    # 12. Extracción de cédula válida incrustada en texto largo
    def test_12_cedula_valida_incrustada(self):
        js = """
        const c = cedulaDesdeTexto('anota el teléfono 0987654321 y la cédula 1724891203');
        const v = validarCedulaEcuatoriana(c);
        console.log(JSON.stringify({ cedula: c, valida: v }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["cedula"], "1724891203")
        self.assertTrue(out["valida"])

    # 13. Cancelación por voz (omitir, cancelar, cerrar)
    def test_13_cancelacion_por_voz(self):
        js = """
        const r1 = inyectarCedulaPorVoz('cancelar');
        const r2 = inyectarCedulaPorVoz('omitir por ahora');
        const r3 = inyectarCedulaPorVoz('cerrar modal');
        const r4 = inyectarCedulaPorVoz('sin cédula');
        console.log(JSON.stringify({ r1: r1.accion, r2: r2.accion, r3: r3.accion, r4: r4.accion }));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["r1"], "cerrar")
        self.assertEqual(out["r2"], "cerrar")
        self.assertEqual(out["r3"], "cerrar")
        self.assertEqual(out["r4"], "cerrar")

    # 14. Inyección válida activa temporizador
    def test_14_inyeccion_valida_retorna_ok(self):
        js = """
        const r = inyectarCedulaPorVoz('uno siete dos cuatro ocho nueve uno dos cero tres');
        console.log(JSON.stringify(r));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["cedula"], "1724891203")
        self.assertTrue(out["valida"])

    # 15. Inyección con 10 dígitos pero módulo 10 inválido retorna warning
    def test_15_inyeccion_invalida_retorna_warning_sin_autosave(self):
        js = """
        const r = inyectarCedulaPorVoz('uno siete dos cuatro ocho nueve uno dos cero nueve'); // checksum inválido
        console.log(JSON.stringify(r));
        """
        out = json.loads(ejecutar_js_en_node(js))
        self.assertEqual(out["status"], "warning")
        self.assertEqual(out["cedula"], "1724891209")
        self.assertFalse(out["valida"])

    # 16. Integración Backend: modal_cedula_estado activa ventana en listener
    def test_16_backend_modal_cedula_estado(self):
        app = BimoBridge()
        app._wake_listener = MagicMock()

        # Abrir modal
        res_open = app.modal_cedula_estado(True)
        self.assertEqual(res_open["status"], "ok")
        self.assertTrue(app._modal_cedula_abierto)
        self.assertGreater(app._modal_cedula_hasta, time.time())
        app._wake_listener.activar_ventana_activa.assert_called_with(30.0)

        # Cerrar modal
        res_close = app.modal_cedula_estado(False)
        self.assertEqual(res_close["status"], "ok")
        self.assertFalse(app._modal_cedula_abierto)
        self.assertEqual(app._modal_cedula_hasta, 0.0)

    # 17. Integración Backend: interceptar dictado manual si el modal está abierto
    def test_17_backend_interceptor_dictado_manual_con_modal_abierto(self):
        app = BimoBridge()
        app._window = MagicMock()
        app._modal_cedula_abierto = True
        app._modal_cedula_hasta = time.time() + 60.0

        res = app.procesar_texto_clinico("uno siete dos cuatro ocho nueve uno dos cero tres")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["tipo"], "CEDULA_VOZ")
        app._window.evaluate_js.assert_called()


if __name__ == "__main__":
    unittest.main()
