# -*- coding: utf-8 -*-
"""
Prueba de Verificación Exhaustiva:
1. Estructura de carpetas por paciente (Adultos vs Pediátricos).
2. Prevención de sobrescritura entre pacientes homónimos (Sufijo ID único).
3. Generación acumulativa de consultas en diferentes días (Exp1, Exp2, Exp3...).
4. Coexistencia de múltiples PDFs históricos sin sobrescribirse.
"""
import os
import sys
import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(base_dir, ".."))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from database import (
    registrar_o_actualizar_paciente,
    guardar_consulta_db,
    obtener_siguiente_num_expediente_paciente,
    obtener_consulta_por_id,
    obtener_paciente_por_id,
    get_connection
)
from generador_pdf import crear_historia_clinica, BASE_DIR

print("=" * 65)
print("  VERIFICACIÓN DE CARPETAS Y CONTROL ANTI-SOBRESCRITURA DE PDFs")
print("=" * 65)

# --- CASO 1: Paciente Adulto (Consulta Día 1) ---
print("\n[TEST 1] Registrando Paciente Adulto #1...")
filiacion_adulto = {
    "nombre": "Esteban Morales Test",
    "documento": "1799988811",
    "edad": 35,
    "sexo": "M",
    "telefono": "0991112233",
    "direccion": "Quito Norte",
    "ocupacion": "Arquitecto"
}
pac_id_1 = registrar_o_actualizar_paciente(filiacion_adulto)
print(f"      -> Paciente registrado con ID: {pac_id_1}")

# Consulta Día 1 (fecha simulada: 10 de Septiembre 2026)
fecha_dia_1 = datetime.datetime(2026, 9, 10, 10, 30)
num_exp_1 = obtener_siguiente_num_expediente_paciente(pac_id_1)
assert num_exp_1 == 1, f"Expected Exp 1, got {num_exp_1}"

clinico_dia_1 = {
    "datos_filiacion": filiacion_adulto,
    "motivo_consulta": "Dolor en pieza 36",
    "enfermedad_actual": "Sensibilidad al frío desde hace 3 días",
    "diagnostico": "Caries de la dentina K021",
    "plan_tratamiento": "Restauración con resina compuesta",
    "odontograma": [{"pieza_dental": "36", "procedimientos_o_hallazgos": ["Caries oclusal profunda"]}],
    "num_expediente": num_exp_1,
    "fecha_consulta": fecha_dia_1.strftime("%Y-%m-%d %H:%M:%S")
}

ruta_pdf_1 = crear_historia_clinica(clinico_dia_1, paciente_id=pac_id_1, num_expediente=num_exp_1)
assert ruta_pdf_1 and os.path.exists(ruta_pdf_1), "PDF 1 no fue generado"
guardar_consulta_db(paciente_id=pac_id_1, json_clinico=clinico_dia_1, ruta_pdf=ruta_pdf_1)

print(f"      -> PDF Día 1 generado: {os.path.basename(ruta_pdf_1)}")
print(f"      -> Carpeta contenedora: {os.path.dirname(ruta_pdf_1)}")
assert "Pacientes_Adultos" in ruta_pdf_1, "Debe categorizarse en Pacientes_Adultos"
assert f"ID{pac_id_1}" in ruta_pdf_1, f"La carpeta debe tener sufijo ID{pac_id_1}"


# --- CASO 2: Mismo Paciente Adulto, Consulta Día 2 (fecha simulada: 18 de Septiembre 2026) ---
print("\n[TEST 2] Registrando Consulta en OTRO DÍA para el mismo paciente...")
fecha_dia_2 = datetime.datetime(2026, 9, 18, 16, 0)
num_exp_2 = obtener_siguiente_num_expediente_paciente(pac_id_1)
assert num_exp_2 == 2, f"Expected Exp 2, got {num_exp_2}"

clinico_dia_2 = {
    "datos_filiacion": filiacion_adulto,
    "motivo_consulta": "Control y profilaxis dental",
    "enfermedad_actual": "Asintomático. Evolución favorable post-resina.",
    "diagnostico": "Examen de rutina Z012",
    "plan_tratamiento": "Profilaxis y aplicación de flúor",
    "odontograma": [{"pieza_dental": "36", "procedimientos_o_hallazgos": ["Resina en buen estado"]}],
    "num_expediente": num_exp_2,
    "fecha_consulta": fecha_dia_2.strftime("%Y-%m-%d %H:%M:%S")
}

ruta_pdf_2 = crear_historia_clinica(clinico_dia_2, paciente_id=pac_id_1, num_expediente=num_exp_2)
assert ruta_pdf_2 and os.path.exists(ruta_pdf_2), "PDF 2 no fue generado"
guardar_consulta_db(paciente_id=pac_id_1, json_clinico=clinico_dia_2, ruta_pdf=ruta_pdf_2)

print(f"      -> PDF Día 2 generado: {os.path.basename(ruta_pdf_2)}")
assert ruta_pdf_1 != ruta_pdf_2, "Los nombres de PDF no deben ser idénticos"
assert os.path.exists(ruta_pdf_1), "¡CRÍTICO! El PDF del Día 1 fue sobrescrito"
assert os.path.exists(ruta_pdf_2), "¡CRÍTICO! El PDF del Día 2 no existe"
print("      -> ¡ÉXITO! Ambos PDFs coexisten en la misma carpeta sin sobrescribirse.")


# --- CASO 3: Paciente Pediátrico (< 18 años) ---
print("\n[TEST 3] Registrando Paciente Pediátrico...")
filiacion_pediatrico = {
    "nombre": "Sofia Morales Test",
    "documento": "1788877700",
    "edad": 8,
    "sexo": "F",
    "telefono": "0994445566",
    "direccion": "Cumbayá"
}
pac_id_ped = registrar_o_actualizar_paciente(filiacion_pediatrico)
num_exp_ped = obtener_siguiente_num_expediente_paciente(pac_id_ped)

clinico_ped = {
    "datos_filiacion": filiacion_pediatrico,
    "motivo_consulta": "Revisión dental y sellantes",
    "diagnostico": "Z012 Examen rutinario",
    "plan_tratamiento": "Sellantes en molares temporales",
    "odontograma": [{"pieza_dental": "55", "procedimientos_o_hallazgos": ["Sano para sellante"]}],
    "num_expediente": num_exp_ped
}
ruta_pdf_ped = crear_historia_clinica(clinico_ped, paciente_id=pac_id_ped, num_expediente=num_exp_ped)
print(f"      -> PDF Pediátrico generado: {os.path.basename(ruta_pdf_ped)}")
print(f"      -> Carpeta: {os.path.dirname(ruta_pdf_ped)}")
assert "Pacientes_Pediatricos" in ruta_pdf_ped, "Debe categorizarse en Pacientes_Pediatricos"


# --- CASO 4: Homónimo (Mismo nombre, diferente cédula/persona) ---
print("\n[TEST 4] Registrando Paciente Homónimo (Mismo nombre pero cédula distinta)...")
filiacion_homonimo = {
    "nombre": "Esteban Morales Test",
    "documento": "1799988899",  # Cédula distinta
    "edad": 35,
    "sexo": "M",
    "telefono": "0987654321"
}
pac_id_hom = registrar_o_actualizar_paciente(filiacion_homonimo)
assert pac_id_hom != pac_id_1, f"Debe crearse un nuevo ID para distinta cédula ({pac_id_hom} vs {pac_id_1})"

num_exp_hom = obtener_siguiente_num_expediente_paciente(pac_id_hom)
clinico_hom = {
    "datos_filiacion": filiacion_homonimo,
    "motivo_consulta": "Limpieza general",
    "diagnostico": "Z012",
    "plan_tratamiento": "Profilaxis",
    "num_expediente": num_exp_hom
}
ruta_pdf_hom = crear_historia_clinica(clinico_hom, paciente_id=pac_id_hom, num_expediente=num_exp_hom)
print(f"      -> Carpeta Homónimo: {os.path.dirname(ruta_pdf_hom)}")
print(f"      -> Carpeta Paciente 1: {os.path.dirname(ruta_pdf_1)}")
assert os.path.dirname(ruta_pdf_hom) != os.path.dirname(ruta_pdf_1), "Las carpetas de homónimos deben ser distintas"
assert os.path.exists(ruta_pdf_1), "PDF de Paciente 1 debe seguir existiendo"
assert os.path.exists(ruta_pdf_hom), "PDF de Homónimo debe existir"

# Listado final de archivos en la carpeta de Paciente 1
carpeta_p1 = os.path.dirname(ruta_pdf_1)
archivos_p1 = [f for f in os.listdir(carpeta_p1) if f.endswith(".pdf")]
print(f"\n[LISTADO FINAL] PDFs en carpeta de Esteban Morales (ID {pac_id_1}):")
for f in archivos_p1:
    print(f"   [PDF] {f}")

assert len(archivos_p1) >= 2, f"Deben existir al menos 2 PDFs en la carpeta, encontrados: {len(archivos_p1)}"

print("\n" + "=" * 65)
print("  ¡TODAS LAS PRUEBAS DE ESTRUCTURA Y NO SOBRESCRITURA PASARON (4/4)!")
print("=" * 65)
