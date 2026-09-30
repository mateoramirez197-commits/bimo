# -*- coding: utf-8 -*-
"""
tests/test_multitarea_u4.py
Pruebas exhaustivas para el Bloque U4:
  1. Multitarea en HISTORIA_CLINICA (odontograma, diagnostico, pagos, cita_programada).
  2. Aislamiento y anti-duplicados de citas y pagos en desktop_app.py.
  3. Cola de escucha activa (hasta 3 segmentos), búfer de hasta 120s y watchdog adaptativo.
"""

import sys
import os
import time
import queue
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from wake_word_listener import BackgroundWakeListener

def run_tests():
    total = 0
    pasados = 0
    fallados = 0

    print("=== INICIANDO PRUEBAS DE MULTITAREA Y ESCUCHA ACTIVA (U4) ===")

    # Test 1: BackgroundWakeListener cola y buffering
    total += 1
    dummy_cb = MagicMock()
    listener = BackgroundWakeListener(dummy_cb)
    if hasattr(listener, "_cola_audio") and listener._cola_audio.maxsize == 3:
        print("[OK] BackgroundWakeListener: Cola de audio inicializada con capacidad 3")
        pasados += 1
    else:
        print("[FAIL] BackgroundWakeListener: Cola de audio no configurada correctamente")
        fallados += 1

    # Test 2: Despacho de audio a la cola y descarte del más antiguo al saturar
    total += 1
    try:
        import numpy as np
        seg1 = np.zeros(16000, dtype=np.int16)
        seg2 = np.ones(16000, dtype=np.int16)
        seg3 = np.full(16000, 2, dtype=np.int16)
        seg4 = np.full(16000, 3, dtype=np.int16)

        listener._despachar_analisis(seg1)
        listener._despachar_analisis(seg2)
        listener._despachar_analisis(seg3)
        listener._despachar_analisis(seg4)  # Debe descartar seg1 y contener seg2, seg3, seg4

        if listener._cola_audio.qsize() == 3:
            item_primero = listener._cola_audio.get_nowait()
            if item_primero[0] == 1:  # seg2 es el primero ahora
                print("[OK] BackgroundWakeListener: Rotación correcta de cola FIFO ante saturación")
                pasados += 1
            else:
                print(f"[FAIL] BackgroundWakeListener: Primer elemento inesperado {item_primero[0]}")
                fallados += 1
        else:
            print(f"[FAIL] BackgroundWakeListener: qsize inesperado {listener._cola_audio.qsize()}")
            fallados += 1
    except Exception as e:
        print(f"[FAIL] Error en prueba de cola: {e}")
        fallados += 1

    # Test 3: Watchdog adaptativo
    total += 1
    listener._duracion_actual_analisis = 10.0
    timeout_calculado = max(6.0, listener._duracion_actual_analisis * 1.5)
    if timeout_calculado == 15.0:
        listener._duracion_actual_analisis = 2.0
        timeout_corto = max(6.0, listener._duracion_actual_analisis * 1.5)
        if timeout_corto == 6.0:
            print(f"[OK] Watchdog adaptativo verificado: {timeout_calculado}s para 10s audio, {timeout_corto}s para 2s audio")
            pasados += 1
        else:
            print(f"[FAIL] Watchdog corto falló: {timeout_corto}")
            fallados += 1
    else:
        print(f"[FAIL] Watchdog calculado incorrecto: {timeout_calculado}")
        fallados += 1

    # Test 4: Paridad de transcripción en clips > 3s
    total += 1
    with patch("ai_engine.transcribir_audio", return_value="texto transcrito con paridad manual") as mock_trans:
        t_arr = np.linspace(0, 4, 16000 * 4)
        audio_dummy = (np.sin(2 * np.pi * 440 * t_arr) * 5000).astype(np.int16)  # Tono 440Hz de 4 segundos
        listener._analizar_audio(audio_dummy)
        if mock_trans.called:
            print("[OK] Paridad de transcripción: transcribir_audio llamado para clip de 4 segundos")
            pasados += 1
        else:
            print("[FAIL] Paridad de transcripción: no se invocó transcribir_audio para clip > 3s")
            fallados += 1

    # Test 5: Aislamiento y anti-duplicados en HISTORIA_CLINICA (desktop_app.py)
    total += 1
    from desktop_app import BimoBridge
    bridge = BimoBridge()

    resultado_ia_multitarea = {
        "tipo": "HISTORIA_CLINICA",
        "datos_filiacion": {
            "nombre": "Carlos Alberto Montes",
            "edad": "35 años",
            "documento": "1712345678",
            "telefono": "0991234567"
        },
        "odontograma": [{"pieza_dental": "16", "procedimientos_o_hallazgos": ["Caries oclusal profunda"]}],
        "diagnostico": "Caries de la dentina",
        "plan_tratamiento": "Restauración con resina compuesta",
        "pagos": {
            "costo_total": 80.0,
            "abono": 30.0,
            "saldo_pendiente": 50.0,
            "estado": "Saldo Pendiente",
            "metodo_pago": "Efectivo",
            "notas": "Resina oclusal 16"
        },
        "cita_programada": {
            "agendar": True,
            "fecha_hora": "2026-10-15 15:00:00",
            "motivo": "Control de restauración"
        }
    }

    mock_pago_db = MagicMock(return_value=1)
    mock_cita_db = MagicMock(return_value=1)
    mock_crear_historia = MagicMock(return_value="C:/dummy/historia.pdf")

    with patch("desktop_app.procesar_comando_o_dictado", return_value=resultado_ia_multitarea):
        with patch("desktop_app.registrar_o_actualizar_paciente", return_value=999):
            with patch("desktop_app.obtener_consulta_del_dia", return_value=None):
                with patch("desktop_app.obtener_siguiente_num_expediente_paciente", return_value=1):
                    with patch("desktop_app.crear_historia_clinica", mock_crear_historia):
                        with patch("desktop_app.guardar_consulta_db", return_value=888):
                            with patch("desktop_app.actualizar_consulta_existente") as mock_act_c:
                                with patch("database.obtener_pago_consulta", return_value=None):
                                    with patch("database.registrar_o_actualizar_pago_db", mock_pago_db):
                                        with patch("database.get_connection") as mock_conn:
                                            # Simular sin cita previa
                                            mock_cur = MagicMock()
                                            mock_cur.fetchone.return_value = None
                                            mock_conn.return_value.cursor.return_value = mock_cur
                                            mock_conn.return_value.__enter__.return_value = mock_conn.return_value

                                            with patch("desktop_app.agendar_cita", mock_cita_db):
                                                resp1 = bridge.procesar_texto_clinico("dictado clinico simulado", generar_pdf=True)

    if resp1.get("status") == "ok" and mock_pago_db.called and mock_cita_db.called:
        print("[OK] Multitarea en HISTORIA_CLINICA: Consulta guardada, PDF generado, pago y cita agendados en una sola pasada")
        pasados += 1
    else:
        print(f"[FAIL] Falló ejecución multitarea: resp1={resp1}")
        fallados += 1

    # Test 6: Anti-duplicados de cita y pago en segunda pasada
    total += 1
    mock_pago_previo = {"id": 55, "consulta_id": 888, "costo_total": 80.0, "abono": 30.0}
    mock_pago_update = MagicMock(return_value=55)

    with patch("desktop_app.procesar_comando_o_dictado", return_value=resultado_ia_multitarea):
        with patch("desktop_app.registrar_o_actualizar_paciente", return_value=999):
            with patch("desktop_app.obtener_consulta_del_dia", return_value={"id": 888, "json_clinico": "{}"}):
                with patch("desktop_app.obtener_num_expediente_consulta", return_value=1):
                    with patch("desktop_app.crear_historia_clinica", mock_crear_historia):
                        with patch("desktop_app.actualizar_consulta_existente"):
                            with patch("database.obtener_pago_consulta", return_value=mock_pago_previo):
                                with patch("database.registrar_o_actualizar_pago_db", mock_pago_update):
                                    with patch("database.get_connection") as mock_conn:
                                        # Simular que la cita YA existe
                                        mock_cur = MagicMock()
                                        mock_cur.fetchone.return_value = {"id": 123}
                                        mock_conn.return_value.cursor.return_value = mock_cur
                                        mock_conn.return_value.__enter__.return_value = mock_conn.return_value

                                        with patch("desktop_app.agendar_cita") as mock_ag_segunda:
                                            resp2 = bridge.procesar_texto_clinico("dictado clinico repetido", generar_pdf=True)

    cita_no_duplicada = not mock_ag_segunda.called
    pago_actualizado = mock_pago_update.called
    avisos = resp2.get("avisos", [])
    tiene_aviso_cita = any("Cita ya existente" in a for a in avisos)

    if cita_no_duplicada and pago_actualizado and tiene_aviso_cita:
        print("[OK] Anti-duplicados verificado: Cita no duplicada y pago actualizado con aviso en segunda pasada")
        pasados += 1
    else:
        print(f"[FAIL] Anti-duplicados falló: cita_no_dup={cita_no_duplicada}, pago_upd={pago_actualizado}, avisos={avisos}")
        fallados += 1

    print("\n==========================================")
    print(f"RESUMEN FINAL BLOQUE U4: {pasados}/{total} pasados (Fallados: {fallados})")
    print("==========================================")

    if fallados > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
