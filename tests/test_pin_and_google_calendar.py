# -*- coding: utf-8 -*-
"""
Prueba automatizada de verificación:
1. Cambio de PIN Maestro y validación estricta (no permitir PINs erróneos).
2. Vinculación de cuenta de Google Calendar y generación de URL con authuser.
"""
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(base_dir, ".."))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from config import cargar_datos_clinica, guardar_datos_clinica
from desktop_app import BimoBridge
from calendar_sync import generar_url_evento_google, init_google_calendar

print("=" * 65)
print(" VERIFICACIÓN DE CAMBIO DE PIN Y VINCULACIÓN GOOGLE CALENDAR")
print("=" * 65)

bridge = BimoBridge()

# 1. Probar PIN por defecto (1234)
print("\n[TEST 1] Verificando PIN por defecto (1234)...")
conf_original = cargar_datos_clinica()
res_def = bridge.autenticar_pin("1234")
assert res_def["status"] == "ok", f"PIN 1234 debió autenticar: {res_def}"
print("      -> PIN por defecto (1234) validado con éxito.")

# 2. Cambiar PIN a uno nuevo (ej. 8392)
print("\n[TEST 2] Cambiando PIN a '8392'...")
conf_nueva = dict(conf_original)
conf_nueva["pin_rapido"] = "8392"
conf_nueva["email_google"] = "mateo.dental@gmail.com"
guardar_datos_clinica(conf_nueva)

# Probar que el nuevo PIN '8392' autentica
res_nuevo = bridge.autenticar_pin("8392")
assert res_nuevo["status"] == "ok", f"El nuevo PIN 8392 debió autenticar: {res_nuevo}"
print("      -> Nuevo PIN '8392' autentica correctamente.")

# Probar que el PIN antiguo '1234' o uno incorrecto '0000' es RECHAZADO
print("\n[TEST 3] Verificando rechazo estricto de PINs incorrectos...")
res_antiguo = bridge.autenticar_pin("1234")
assert res_antiguo["status"] == "error", f"El PIN 1234 debió ser rechazado tras el cambio: {res_antiguo}"
print(f"      -> PIN antiguo (1234) rechazado correctamente: {res_antiguo.get('message')}")

res_falso = bridge.autenticar_pin("9999")
assert res_falso["status"] == "error", f"El PIN 9999 debió ser rechazado: {res_falso}"
print(f"      -> PIN aleatorio (9999) rechazado correctamente: {res_falso.get('message')}")

# Probar acceso maestro de emergencia
res_master = bridge.autenticar_pin("__master__")
assert res_master["status"] == "ok", f"Acceso maestro debió funcionar: {res_master}"
print("      -> Acceso Rápido Maestro verificado como respaldo del doctor.")

# 3. Verificando vinculación con Google Calendar
print("\n[TEST 4] Verificando Google Calendar con cuenta 'mateo.dental@gmail.com'...")
init_google_calendar()

url_evento = generar_url_evento_google(
    titulo="Consulta Paciente Prueba",
    fecha_inicio_str="2026-09-20 11:00:00",
    detalles="Prueba de sincronización con Google Calendar"
)
print(f"      -> URL generada: {url_evento}")
assert "authuser=mateo.dental%40gmail.com" in url_evento, "La URL de Google Calendar debe contener authuser con el correo configurado"
print("      -> ¡ÉXITO! La URL de Google Calendar incluye authuser apuntando directamente a la cuenta del doctor.")

# Restaurar configuración original
print("\n[CLEANUP] Restaurando configuración...")
guardar_datos_clinica(conf_original)
res_restaurado = bridge.autenticar_pin("1234")
assert res_restaurado["status"] == "ok"
print("      -> Configuración restaurada con éxito.")

print("\n" + "=" * 65)
print("  ¡TODAS LAS PRUEBAS DE PIN Y GOOGLE CALENDAR PASARON CON ÉXITO!")
print("=" * 65)
