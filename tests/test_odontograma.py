import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai_engine import (
    extraer_piezas_mencionadas,
    inferir_hallazgo_pieza,
    parchear_odontograma_exhaustivo
)
from generador_pdf import extraer_fdi

class TestOdontogramaExhaustivo(unittest.TestCase):
    """
    Suite de pruebas unitarias para el Bloque 2:
    Exhaustividad del Odontograma, extracción determinista,
    tolerancia a formatos y fusión sin pérdidas.
    """

    # 1. "caries en premolar derecho, izquierdo y resinas en 31 y 32" -> 4
    def test_01_dictado_premolares_y_fdi(self):
        txt = "caries en premolar derecho, izquierdo y resinas en 31 y 32"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertGreaterEqual(len(piezas), 4)
        piezas_lower = [p.lower() for p in piezas]
        self.assertIn("premolar derecho", piezas_lower)
        self.assertIn("premolar izquierdo", piezas_lower)
        self.assertIn("31", piezas)
        self.assertIn("32", piezas)

    # 2. "caries en 16, 17 y 18, resina en 24" -> 4
    def test_02_dictado_tres_molares_y_un_premolar(self):
        txt = "caries en 16, 17 y 18, resina en 24"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 4)
        for p in ["16", "17", "18", "24"]:
            self.assertIn(p, piezas)

    # 3. "extracción de las piezas 36 y 46, sellantes del 14 al 16" -> 5
    def test_03_dictado_extracciones_y_rango(self):
        txt = "extracción de las piezas 36 y 46, sellantes del 14 al 16"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 5)
        for p in ["36", "46", "14", "15", "16"]:
            self.assertIn(p, piezas)

    # 4. "paciente de 25 años, cédula 1724891203, caries en 11, abono 50 dólares" -> 1
    def test_04_filtrado_edad_cedula_dinero(self):
        txt = "paciente de 25 años, cédula 1724891203, caries en 11, abono 50 dólares"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 1)
        self.assertIn("11", piezas)

    # 5. "resina en 31, resina en 31 y 32" -> 2
    def test_05_deduplicacion_y_fusion_hallazgos(self):
        txt = "resina en 31, resina en 31 y 32"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 2)
        self.assertIn("31", piezas)
        self.assertIn("32", piezas)

    # 6. JSON de Groq con solo 2 de 4 piezas -> 4 tras el parche
    def test_06_parche_groq_incompleto_recupera_todas(self):
        txt = "caries en premolar derecho, izquierdo y resinas en 31 y 32"
        json_groq_incompleto = [
            {"pieza_dental": "31", "procedimientos_o_hallazgos": ["resina"]},
            {"pieza_dental": "32", "procedimientos_o_hallazgos": ["resina"]}
        ]
        odonto_parcheado = parchear_odontograma_exhaustivo(json_groq_incompleto, txt)
        self.assertGreaterEqual(len(odonto_parcheado), 4)
        
        # Verificar que se incluyeron las 4
        piezas_en_parche = [p["pieza_dental"].lower() for p in odonto_parcheado]
        self.assertTrue(any("premolar derecho" in p for p in piezas_en_parche))
        self.assertTrue(any("premolar izquierdo" in p for p in piezas_en_parche))
        self.assertTrue(any("31" in p for p in piezas_en_parche))
        self.assertTrue(any("32" in p for p in piezas_en_parche))

    # 7. Compatibilidad de claves: pieza y hallazgo
    def test_07_compatibilidad_claves_pieza_y_hallazgo(self):
        txt = "control rutinario"
        entrada = [
            {"pieza": "14", "hallazgo": "caries oclusal"}
        ]
        res = parchear_odontograma_exhaustivo(entrada, txt)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["pieza_dental"], "14")
        self.assertEqual(res[0]["procedimientos_o_hallazgos"], ["caries oclusal"])

    # 8. Compatibilidad de claves: diente y procedimiento
    def test_08_compatibilidad_claves_diente_y_procedimiento(self):
        txt = "control rutinario"
        entrada = [
            {"diente": "46", "procedimiento": "endodoncia"}
        ]
        res = parchear_odontograma_exhaustivo(entrada, txt)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["pieza_dental"], "46")
        self.assertEqual(res[0]["procedimientos_o_hallazgos"], ["endodoncia"])

    # 9. Rango cuadrante 2 (21 al 25)
    def test_09_rango_cuadrante_superior_izquierdo(self):
        txt = "sellantes del 21 al 25"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 5)
        for p in ["21", "22", "23", "24", "25"]:
            self.assertIn(p, piezas)

    # 10. Rango cuadrante 4 (41 a 45)
    def test_10_rango_cuadrante_inferior_derecho(self):
        txt = "limpieza en piezas 41 a 45"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 5)
        for p in ["41", "42", "43", "44", "45"]:
            self.assertIn(p, piezas)

    # 11. Dientes temporales válidos (deciduos 51-85)
    def test_11_piezas_temporales_ninos(self):
        txt = "obturaciones en 54, 55 y 65"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 3)
        self.assertIn("54", piezas)
        self.assertIn("55", piezas)
        self.assertIn("65", piezas)

    # 12. Fusión de duplicados exactos sin perder hallazgos
    def test_12_fusion_duplicados_sin_perder_hallazgos(self):
        txt = "pieza 16 con caries y fractura"
        entrada = [
            {"pieza_dental": "16", "procedimientos_o_hallazgos": ["caries"]},
            {"pieza_dental": "16", "procedimientos_o_hallazgos": ["fractura"]}
        ]
        res = parchear_odontograma_exhaustivo(entrada, txt)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["pieza_dental"], "16")
        self.assertIn("caries", res[0]["procedimientos_o_hallazgos"])
        self.assertIn("fractura", res[0]["procedimientos_o_hallazgos"])

    # 13. Ignorar números de teléfono o fecha
    def test_13_no_confundir_telefono_o_fecha(self):
        txt = "llamar al 0998877665 fecha 2026-10-15 a las 15:00 por dolor en 47"
        piezas = extraer_piezas_mencionadas(txt)
        self.assertEqual(len(piezas), 1)
        self.assertIn("47", piezas)

    # 14. Inferencia de hallazgo específico desde el fragmento textual
    def test_14_inferencia_hallazgo_especifico(self):
        txt = "corona en 11, endodoncia en 21, caries en 36"
        h1 = inferir_hallazgo_pieza("11", txt)
        h2 = inferir_hallazgo_pieza("21", txt)
        h3 = inferir_hallazgo_pieza("36", txt)
        self.assertIn("Corona", h1)
        self.assertIn("Endodoncia", h2)
        self.assertIn("Caries", h3)

if __name__ == "__main__":
    unittest.main()
