# -*- coding: utf-8 -*-
"""
tests/test_limpieza_nombres.py
Pruebas exhaustivas para la función limpiar_nombre_paciente (Bloque U3).
Verifica:
  - Eliminación de prefijos de agendamiento y cortesía ('cita para', 'agenda a', 'dr.', etc.)
  - Eliminación de motivos clínicos ('con dolor', 'para revisión', 'por limpieza')
  - Eliminación de fechas y horas ('mañana a las 10', 'el 15 de marzo', 'a las 4')
  - Eliminación de edades ('de 30 años', 'de 8 años')
  - Preservación de apellidos compuestos ('de la Cruz', 'del Valle', 'San Martín', 'Montes de Oca')
  - Normalización de nombres andinos y correcciones fonéticas ('Llumiquinga', 'Toapanta', 'Caiza')
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_engine import limpiar_nombre_paciente

def run_tests():
    casos = [
        ("María José Pérez", "María José Pérez"),
        ("Sisa Llumiquinga", "Sisa Llumiquinga"),
        ("Pedro de la Cruz", "Pedro de la Cruz"),
        ("Ana con dolor el 15 de marzo a las 4", "Ana"),
        ("Cita para el doctor Mateo Ramírez para revisión", "Mateo Ramírez"),
        ("Agendar a Carlos Montes de Oca mañana a las 10", "Carlos Montes de Oca"),
        ("cita para la señora Estefanía Gómez de 30 años", "Estefanía Gómez"),
        ("el último paciente", "el último paciente"),
        ("la última paciente", "el último paciente"),
        ("sacar cita para Juan del Valle por molestia mañana a las 9am", "Juan del Valle"),
        ("revisar a don Pedro San Martín para control de brackets", "Pedro San Martín"),
        ("crear una nueva cita para Inti Guaminga para calza", "Inti Guaminga"),
        ("por favor agendar a Sebastián Toapanta el próximo lunes teléfono 0991234567", "Sebastián Toapanta"),
        ("cita para el niño Joaquín Caiza de 8 años con caries", "Joaquín Caiza"),
        ("agendar al paciente Sebastiano Yumikinga", "Sebastián Llumiquinga"),
        ("cita para la doctora Stefania Valdes para limpieza", "Estefanía Valdés"),
        ("separar cita para el señor Andrés Quispe para extracción", "Andrés Quispe"),
        ("dar cita a doña Lucía de los Reyes mañana", "Lucía de los Reyes"),
        ("haz una cita para Nicolás Sampedro a las cinco de la tarde", "Nicolás Sampedro"),
        ("cita para Diego de Jesús con dolor agudo", "Diego de Jesús")
    ]

    total = len(casos)
    pasados = 0
    fallados = 0

    print("=== INICIANDO PRUEBAS DE LIMPIEZA Y NORMALIZACION DE NOMBRES (U3) ===")
    for entrada, esperado in casos:
        resultado = limpiar_nombre_paciente(entrada)
        # Comparación insensible a mayúsculas en preposiciones si aplica
        if resultado == esperado or resultado.lower() == esperado.lower():
            print(f"[OK] '{entrada}' -> '{resultado}'")
            pasados += 1
        else:
            print(f"[FAIL] '{entrada}'\n  Esperado: '{esperado}'\n  Obtenido: '{resultado}'")
            fallados += 1

    print("\n==========================================")
    print(f"RESUMEN LIMPIEZA DE NOMBRES: {pasados}/{total} pasados (Fallados: {fallados})")
    print("==========================================")

    if fallados > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
