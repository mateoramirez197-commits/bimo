# -*- coding: utf-8 -*-
"""
tests/test_navegacion.py
Pruebas exhaustivas de navegación por voz (7 pestañas) y ruteo inteligente de pacientes (U2).
Cubre:
  1. Resolución por IA / Regex de las 7 pestañas + odontograma + ruteo de historias PDF (30+ casos).
  2. Ruteo inteligente: paciente único con PDF, único sin PDF, homónimos, inexistente.
  3. Comandos clínicos largos que no deben ser interpretados como navegación.
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Asegurar import de la raíz
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_engine import resolver_navegacion_ui
from desktop_app import BimoBridge

def run_tests():
    casos_navegacion = [
        # --- 1. Dictado ---
        ("abre dictado", "abrir_dictado", ""),
        ("ir a dictado", "abrir_dictado", ""),
        ("modo dictado", "abrir_dictado", ""),
        ("ve a dictar", "abrir_dictado", ""),
        ("pantalla de dictado", "abrir_dictado", ""),

        # --- 2. Agenda ---
        ("abre la agenda", "abrir_agenda", ""),
        ("ir a la agenda", "abrir_agenda", ""),
        ("ve a citas", "abrir_agenda", ""),
        ("ver calendario", "abrir_agenda", ""),
        ("Bimo por favor abre el calendario", "abrir_agenda", ""),
        ("bimo este llévame a la agenda", "abrir_agenda", ""),
        ("vete a la agenda", "abrir_agenda", ""),
        ("pon la agenda", "abrir_agenda", ""),

        # --- 3. Pacientes (listado) ---
        ("abre pacientes", "abrir_pacientes", ""),
        ("ir a pacientes", "abrir_pacientes", ""),
        ("ver pacientes", "abrir_pacientes", ""),
        ("directorio de pacientes", "abrir_pacientes", ""),
        ("lista de pacientes", "abrir_pacientes", ""),

        # --- 4. Búsqueda de pacientes ---
        ("busca al paciente Juan Pérez", "buscar_paciente", "Juan Pérez"),
        ("buscar a María Gómez", "buscar_paciente", "María Gómez"),
        ("busca expediente de Carlos Ruiz", "buscar_paciente", "Carlos Ruiz"),
        ("ver ficha de Ana López", "buscar_paciente", "Ana López"),

        # --- 5. Abrir PDF de paciente específico (ruteo inteligente) ---
        ("abrir historia de Juan Pérez", "abrir_pdf_paciente", "Juan Pérez"),
        ("ver historia clínica de María Gómez", "abrir_pdf_paciente", "María Gómez"),
        ("abrir pdf de Roberto Carlos", "abrir_pdf_paciente", "Roberto Carlos"),
        ("mostrar historia de Sandra Bullock", "abrir_pdf_paciente", "Sandra Bullock"),

        # --- 6. Mobile / Celular ---
        ("abrir mobile", "abrir_mobile", ""),
        ("conectar celular", "abrir_mobile", ""),
        ("conectar teléfono", "abrir_mobile", ""),
        ("ir a móvil", "abrir_mobile", ""),
        ("mostrar código qr", "abrir_mobile", ""),
        ("cámara móvil", "abrir_mobile", ""),

        # --- 7. Visor de PDF ---
        ("abre visor de pdf", "abrir_pdf", ""),
        ("ver pdfs", "abrir_pdf", ""),
        ("abrir pdf", "abrir_pdf", ""),
        ("historias clínicas", "abrir_pdf", ""),
        ("ver documentos", "abrir_pdf", ""),
        ("muéstrame historias", "abrir_pdf", ""),

        # --- 8. Widget flotante ---
        ("abrir widget", "abrir_widget", ""),
        ("modo flotante", "abrir_widget", ""),
        ("ventana flotante", "abrir_widget", ""),
        ("activar widget", "abrir_widget", ""),

        # --- 9. Configuración / Ajustes ---
        ("abrir configuración", "abrir_configuracion", ""),
        ("ir a ajustes", "abrir_configuracion", ""),
        ("cambiar temas", "abrir_configuracion", ""),
        ("ver opciones", "abrir_configuracion", ""),

        # --- 10. Odontograma ---
        ("muéstrame el odontograma", "abrir_odontograma", ""),
        ("abrir odontograma", "abrir_odontograma", ""),

        # --- 11. Dictados clínicos / no navegación (deben dar None) ---
        ("paciente presenta dolor agudo en pieza 18 con cavidad oclusal profunda", None, None),
        ("paciente Juan Pérez acude a consulta por fractura de resina en pieza 21", None, None),
        ("cita para mañana a las cuatro de la tarde para limpieza dental de Roberto", None, None),
        ("este es un dictado excesivamente largo de más de diez palabras que nunca debería ser considerado comando de navegación bajo ninguna circunstancia", None, None),
        ("abrir youtube y buscar videos de música clásica", None, None),
    ]

    total = 0
    pasados = 0
    fallados = 0

    print("=== INICIANDO PRUEBAS DE RESOLUCION DE NAVEGACION UI (AI ENGINE) ===")
    for texto, exp_accion, exp_param in casos_navegacion:
        total += 1
        res = resolver_navegacion_ui(texto)
        if exp_accion is None:
            if res is None:
                print(f"[OK] '{texto}' -> Correctamente ignorado (None)")
                pasados += 1
            else:
                print(f"[FAIL] '{texto}' -> Esperaba None pero obtuvo: {res}")
                fallados += 1
        else:
            if res and res.get("accion") == exp_accion and res.get("parametro") == exp_param:
                print(f"[OK] '{texto}' -> {res['accion']} ('{res['parametro']}')")
                pasados += 1
            else:
                print(f"[FAIL] '{texto}' -> Esperaba ({exp_accion}, '{exp_param}'), obtuvo: {res}")
                fallados += 1

    print(f"\nSubtotal Navegación UI: {pasados}/{total} pasados.")

    # --- Pruebas de Ruteo Inteligente (desktop_app.BimoBridge._resolver_ruteo_paciente) ---
    print("\n=== INICIANDO PRUEBAS DE RUTEO INTELIGENTE DE PACIENTES ===")
    bridge = BimoBridge()

    # Caso A: Paciente inexistente
    total += 1
    with patch("database.buscar_pacientes_por_nombre", return_value=[]):
        res_inexistente = bridge._resolver_ruteo_paciente("Zulma Desconocida", abrir_pdf=True)
        if res_inexistente["estado"] == "no_encontrado" and res_inexistente["accion_ui"] == "buscar_paciente":
            print(f"[OK] Ruteo Paciente Inexistente -> {res_inexistente['estado']}")
            pasados += 1
        else:
            print(f"[FAIL] Ruteo Paciente Inexistente falló: {res_inexistente}")
            fallados += 1

    # Caso B: Pacientes homónimos (2 o más)
    total += 1
    mock_homonimos = [
        {"id": 101, "nombre": "Carlos Gómez Padre"},
        {"id": 102, "nombre": "Carlos Gómez Hijo"}
    ]
    with patch("database.buscar_pacientes_por_nombre", return_value=mock_homonimos):
        res_homonimos = bridge._resolver_ruteo_paciente("Carlos Gómez", abrir_pdf=True)
        if res_homonimos["estado"] == "homonimos" and res_homonimos["total_coincidencias"] == 2:
            print(f"[OK] Ruteo Paciente Homónimos -> {res_homonimos['estado']} (coincidencias: {res_homonimos['total_coincidencias']})")
            pasados += 1
        else:
            print(f"[FAIL] Ruteo Paciente Homónimos falló: {res_homonimos}")
            fallados += 1

    # Caso C: Paciente único CON PDF existente
    total += 1
    mock_unico = [{"id": 201, "nombre": "Lucía Morales"}]
    pdf_ficticio = BASE_DIR / "scratch" / "test_paciente_dummy.pdf"
    pdf_ficticio.write_bytes(b"%PDF-1.4 mock")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"ruta_pdf": str(pdf_ficticio)}
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn

    try:
        with patch("database.buscar_pacientes_por_nombre", return_value=mock_unico):
            with patch("database.get_connection", return_value=mock_conn):
                res_con_pdf = bridge._resolver_ruteo_paciente("Lucía Morales", abrir_pdf=True)
                if res_con_pdf["estado"] == "pdf_encontrado" and res_con_pdf["accion_ui"] == "abrir_pdf_especifico":
                    print(f"[OK] Ruteo Paciente Único Con PDF -> {res_con_pdf['estado']} (ruta: {res_con_pdf['ruta_pdf']})")
                    pasados += 1
                else:
                    print(f"[FAIL] Ruteo Paciente Único Con PDF falló: {res_con_pdf}")
                    fallados += 1
    finally:
        if pdf_ficticio.exists():
            pdf_ficticio.unlink()

    # Caso D: Paciente único SIN PDF
    total += 1
    mock_cursor_vacio = MagicMock()
    mock_cursor_vacio.fetchone.return_value = None
    mock_conn_vacio = MagicMock()
    mock_conn_vacio.cursor.return_value = mock_cursor_vacio
    mock_conn_vacio.__enter__.return_value = mock_conn_vacio

    with patch("database.buscar_pacientes_por_nombre", return_value=mock_unico):
        with patch("database.get_connection", return_value=mock_conn_vacio):
            with patch("pathlib.Path.exists", return_value=False):
                res_sin_pdf = bridge._resolver_ruteo_paciente("Lucía Morales", abrir_pdf=True)
                if res_sin_pdf["estado"] == "sin_pdf" and res_sin_pdf["accion_ui"] == "buscar_paciente":
                    print(f"[OK] Ruteo Paciente Único Sin PDF -> {res_sin_pdf['estado']}")
                    pasados += 1
                else:
                    print(f"[FAIL] Ruteo Paciente Único Sin PDF falló: {res_sin_pdf}")
                    fallados += 1

    # Caso E: Búsqueda regular de paciente único (abrir_pdf=False)
    total += 1
    with patch("database.buscar_pacientes_por_nombre", return_value=mock_unico):
        res_busqueda = bridge._resolver_ruteo_paciente("Lucía Morales", abrir_pdf=False)
        if res_busqueda["estado"] == "paciente_unico" and res_busqueda["accion_ui"] == "buscar_paciente":
            print(f"[OK] Ruteo Búsqueda Regular Paciente -> {res_busqueda['estado']}")
            pasados += 1
        else:
            print(f"[FAIL] Ruteo Búsqueda Regular falló: {res_busqueda}")
            fallados += 1

    print("\n==========================================")
    print(f"RESUMEN FINAL: {pasados}/{total} pasados (Fallados: {fallados})")
    print("==========================================")

    if fallados > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
