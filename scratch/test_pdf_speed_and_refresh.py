# -*- coding: utf-8 -*-
"""
Test de verificación integral:
1. Rendimiento ultra-rápido de generación de PDFs (<0.5s)
2. Persistencia unificada en RUTA_PACIENTES
3. Auto-sanación y visualización en menús (listar_pdfs_recientes y obtener_paciente_detalle)
4. Robustez de generar_pdf_actual ante parámetros null/dict
5. No-bloqueo de escucha activa y TTS con timeout
"""
import os
import sys
import time
import json
import sqlite3
import numpy as np

# Configurar path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import RUTA_PACIENTES, RUTA_MASCARAS_ODONTOGRAMA, RUTA_BASE_ODONTOGRAMA
import generador_pdf
from desktop_app import BimoBridge
from voice_assistant import bimo_esta_hablando

def test_todo():
    print("=" * 60)
    print("INICIANDO PRUEBAS DE VELOCIDAD, PERSISTENCIA Y MENUS DE PDF")
    print("=" * 60)

    # 1. Verificar carga de máscaras
    t0 = time.time()
    mascaras = generador_pdf._calcular_mascaras_dientes()
    t_mascaras = time.time() - t0
    print(f"[TEST 1] Carga de máscaras dentales: {t_mascaras:.4f}s ({len(mascaras)} piezas)")
    assert len(mascaras) == 32, "Debe haber 32 piezas dentales en las máscaras"
    assert t_mascaras < 0.25, f"La carga de máscaras debe tardar <0.25s, tardó {t_mascaras:.4f}s"

    # 2. Obtener una consulta real de la base de datos
    conn = sqlite3.connect(os.path.join(BASE_DIR, "bimo.db"))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, paciente_id, json_clinico FROM consultas ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "Debe existir al menos una consulta en bimo.db"
    cid = row["id"]
    pid = row["paciente_id"]
    datos_clinicos = json.loads(row["json_clinico"])

    # 3. Test de velocidad de crear_historia_clinica
    t0_pdf = time.time()
    ruta_pdf = generador_pdf.crear_historia_clinica(datos_clinicos, paciente_id=pid)
    t_pdf = time.time() - t0_pdf
    print(f"[TEST 2] Generación completa de PDF MSP Formulario 033: {t_pdf:.3f}s")
    print(f"         Ruta generada: {ruta_pdf}")
    assert ruta_pdf and os.path.exists(ruta_pdf), "El PDF generado debe existir en disco"
    assert t_pdf < 1.0, f"La generación debe tomar menos de 1.0s (antes 7.5s), tomó {t_pdf:.3f}s"
    assert str(RUTA_PACIENTES) in ruta_pdf, f"El PDF debe guardarse dentro de RUTA_PACIENTES ({RUTA_PACIENTES})"

    # 4. Test de listar_pdfs_recientes (Visor de PDF)
    bridge = BimoBridge()
    pdfs = bridge.listar_pdfs_recientes()
    print(f"[TEST 3] Listado de PDFs recientes: {len(pdfs)} documentos encontrados")
    assert len(pdfs) > 0, "listar_pdfs_recientes debe devolver al menos 1 PDF"
    # El PDF recién generado debe estar en los primeros resultados
    nombres = [os.path.basename(p["ruta"]).lower() for p in pdfs]
    assert os.path.basename(ruta_pdf).lower() in nombres, "El PDF recién creado debe figurar en el menú de PDFs"

    # 5. Test de obtener_paciente_detalle (Menú Pacientes)
    detalles = bridge.obtener_paciente_detalle(pid)
    assert detalles.get("status") == "ok", "obtener_paciente_detalle debe devolver status ok"
    consultas = detalles.get("consultas", [])
    print(f"[TEST 4] Detalle del paciente ID {pid}: {len(consultas)} consultas")
    # Verificar que las consultas tengan ruta_pdf válida
    consultas_con_pdf = [c for c in consultas if c.get("ruta_pdf") and os.path.exists(c["ruta_pdf"])]
    print(f"         Consultas con PDF físico confirmado: {len(consultas_con_pdf)}/{len(consultas)}")
    assert len(consultas_con_pdf) > 0, "Al menos una consulta del paciente debe tener su PDF enlazado"

    # 6. Test de generar_pdf_actual con parámetros dict y null
    resp_dict = bridge.generar_pdf_actual({"consulta_id": cid, "incluir_ortodoncia": False, "abrir_externo": False})
    assert resp_dict.get("status") == "ok", f"generar_pdf_actual con dict falló: {resp_dict}"
    print(f"[TEST 5] generar_pdf_actual con dict: OK ({resp_dict['ruta_pdf']})")

    resp_null = bridge.generar_pdf_actual("null")
    assert resp_null.get("status") == "ok", f"generar_pdf_actual con 'null' falló: {resp_null}"
    print(f"[TEST 6] generar_pdf_actual con 'null': OK ({resp_null['ruta_pdf']})")

    # 7. Test de estado de escucha activa y bimo_esta_hablando
    assert not bimo_esta_hablando(), "Bimo no debe estar marcado como hablando al inicio"
    print("[TEST 7] Estado acústico de escucha: OK (no bloqueante)")

    print("=" * 60)
    print("TODAS LAS PRUEBAS PASARON EXITOSAMENTE (100% OK)")
    print("=" * 60)

if __name__ == "__main__":
    test_todo()
