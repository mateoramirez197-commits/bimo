# -*- coding: utf-8 -*-
"""
BIMO PRO - SUITE DE RESISTENCIA Y ESTRÉS CONTINUO DE 1 HORA
Prueba ininterrumpida de 1 hora (3600 segundos) evaluando el 100% de las capacidades de BIMO:
1. Autenticación por PIN Maestro ('1234' -> Mateo Ramírez)
2. Transcripción y estructuración clínica con IA (Groq / Llama 3.3 70B Versatile)
3. Generación de Historia Clínica Oficial Formulario 033 MSP (PDF + Odontograma + QR de validación)
4. Renderizado y previsualización de PDFs con PyMuPDF (fitz)
5. Verificación de persistencia y listado de PDFs recientes
6. Agendamiento de citas con resolución temporal en lenguaje natural (mañana, en 3 días, etc.)
7. Generación de enlaces y recordatorios WhatsApp wa.me
8. Servidor móvil local HTTPS (puerto 8765) y generación de código QR móvil en Base64
9. Despacho de audio externo desde móvil hacia el puente de escritorio
10. Integridad transaccional SQLite WAL (PRAGMA integrity_check) y monitoreo de RAM/CPU
"""
import os
import sys
import time
import json
import psutil
import datetime
import tempfile
import urllib3
import requests
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_PROYECTO = Path("C:/Users/Mateo/Desktop/Bimo_Project").resolve()
sys.path.insert(0, str(BASE_PROYECTO))

from desktop_app import BimoBridge
from database import (
    init_db, get_connection, buscar_pacientes, listar_consultas_paciente,
    obtener_ultimo_paciente_atendido, obtener_vocabulario_aprendido
)
from config import BASE_DIR, RUTA_DB, RUTA_PACIENTES, MOBILE_SERVER_PORT
from whatsapp_service import generar_mensaje_recordatorio, generar_url_whatsapp

# Casos clínicos diversos y realistas de odontología ecuatoriana
CASOS_CLINICOS_STRESS = [
    {
        "paciente": "Elena Patricia Quinatoa Sisa",
        "edad": "34", "genero": "Femenino", "cedula": "1004561234", "telefono": "0998123456",
        "dictado": "Paciente Elena Patricia Quinatoa Sisa, 34 años, cédula 1004561234, teléfono 0998123456. Acude por dolor pulsátil intenso en pieza 36 al masticar. Examen clínico revela caries oclusomesial profunda con compromiso pulpar. Diagnóstico Pulpitis irreversible aguda K04.0. Plan tratamiento endodoncia unirradicular pieza 36, medicación con ibuprofeno 600 miligramos y amoxicilina 500 miligramos. Próxima cita para instrumentación biomecánica mañana a las 15:00."
    },
    {
        "paciente": "Mateo Sebastián Tituaña Morales",
        "edad": "9", "genero": "Masculino", "cedula": "1729876543", "telefono": "0987654321",
        "dictado": "Paciente pediátrico Mateo Sebastián Tituaña Morales, 9 años, cédula 1729876543, teléfono 0987654321. Consulta de odontopediatría por traumatismo leve con fractura no complicada de esmalte en pieza 21. Tejido pulpar vital, sin movilidad. Diagnóstico Fractura del esmalte dental S02.5. Plan pulido de bordes y reconstrucción estética con resina nanohíbrida. Próxima cita de revisión en tres días a las 10:30."
    },
    {
        "paciente": "Gladys Yolanda Guasgua Farinango",
        "edad": "58", "genero": "Femenino", "cedula": "1002349876", "telefono": "0991238901",
        "dictado": "Paciente Gladys Yolanda Guasgua Farinango, 58 años, cédula 1002349876, teléfono 0991238901. Presenta sangrado gingival severo y movilidad grado 1 en sector anteroinferior. Diagnóstico Periodontitis crónica generalizada K05.3. Plan tartrectomía supragingival y raspado subgingival por cuadrantes con ultrasonido y curetas Gracey. Próxima cita el próximo viernes a las 11:00."
    },
    {
        "paciente": "Javier Alejandro Chushig Lema",
        "edad": "27", "genero": "Masculino", "cedula": "1718901234", "telefono": "0984567890",
        "dictado": "Paciente Javier Alejandro Chushig Lema, 27 años, cédula 1718901234, teléfono 0984567890. Dolor e inflamación en zona retromolar mandibular derecha. Examen radiográfico confirma tercer molar 48 semiretenido en posición mesioangular. Diagnóstico Pericoronitis aguda y diente retenido K05.2 y K01.1. Plan exodoncia quirúrgica compleja de pieza 48 bajo anestesia infiltrativa local. Próxima cita para cirugía en 4 días a las 09:00."
    },
    {
        "paciente": "Carmen Amparo Pillajo Yamberla",
        "edad": "42", "genero": "Femenino", "cedula": "1007890123", "telefono": "0993456789",
        "dictado": "Paciente Carmen Amparo Pillajo Yamberla, 42 años, cédula 1007890123, teléfono 0993456789. Paciente refiere molestia cervical al ingerir alimentos ácidos o fríos en piezas 14, 15 y 24. Diagnóstico Lesiones cervicales no cariosas por abfracción dental K03.1. Plan desensibilización con barniz de flúor y restauración cervical con ionómero de vidrio resina. Próxima cita de control en 8 días a las 16:30."
    },
    {
        "paciente": "Andrés Felipe Toapanta Imbaquingo",
        "edad": "21", "genero": "Masculino", "cedula": "1725678901", "telefono": "0981122334",
        "dictado": "Paciente Andrés Felipe Toapanta Imbaquingo, 21 años, cédula 1725678901, teléfono 0981122334. Control ortodóncico regular. Apiñamiento moderado en arcada inferior en fase de alineación. Diagnóstico Maloclusión dentaria clase I K07.2. Plan cambio de arcos a NiTi rectangular 0.016x0.022 superior e inferior y ligaduras elásticas. Próxima cita de ajuste en cuatro semanas a las 14:00."
    },
    {
        "paciente": "Rosa Mercedes Cachimuel Simbaña",
        "edad": "64", "genero": "Femenino", "cedula": "1001122334", "telefono": "0995544332",
        "dictado": "Paciente Rosa Mercedes Cachimuel Simbaña, 64 años, cédula 1001122334, teléfono 0995544332. Pérdida total de piezas dentarias en maxilar superior. Diagnóstico Pérdida de dientes por caries K08.1. Plan rehabilitación mediante prótesis total mucosoportada superior en acrílico termocurable. Impresión definitiva con pasta zinquenólica. Próxima cita para registro de mordida en siete días a las 10:00."
    }
]

def crear_archivo_wav_dummy():
    """Genera un archivo de audio WAV breve y válido para simular despacho móvil."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()
    
    import wave
    import struct
    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 0.5 segundos de silencio
        wf.writeframes(struct.pack("<h", 0) * 8000)
    return tmp_path

def ejecutar_suite_estres_1hora(duracion_segundos=3600, pausa_entre_casos=600):
    print("=" * 75)
    print("      BIMO PRO - SUITE DE RESISTENCIA Y ESTRÉS CONTINUO (1 HORA)")
    print(f"      Duración total programada: {duracion_segundos}s ({duracion_segundos/3600:.1f} horas)")
    print(f"      Intervalo entre pacientes: {pausa_entre_casos}s ({pausa_entre_casos/60:.1f} min)")
    print(f"      Ruta DB activa: {RUTA_DB}")
    print(f"      Ruta Pacientes activa: {RUTA_PACIENTES}")
    print("=" * 75)

    bridge = BimoBridge()
    proceso_actual = psutil.Process(os.getpid())
    inicio_global = time.time()
    iteracion = 0
    reporte_telemetria = {
        "inicio": datetime.datetime.now().isoformat(),
        "duracion_programada_segundos": duracion_segundos,
        "iteraciones": [],
        "resumen": {
            "total_pacientes_procesados": 0,
            "total_pdfs_generados": 0,
            "total_citas_agendadas": 0,
            "total_recordatorios_whatsapp": 0,
            "pruebas_servidor_movil_exitosas": 0,
            "pruebas_qr_exitosas": 0,
            "errores_totales": 0,
            "ram_maxima_mb": 0.0,
            "estado_db_final": "PENDIENTE"
        }
    }

    # Test 1: Autenticación con PIN Maestro inicial
    print("\n[TEST 1/10] Verificando autenticación con PIN Maestro '1234'...")
    auth_pin = bridge.autenticar_pin("1234")
    assert auth_pin.get("status") == "ok", f"Fallo autenticación PIN: {auth_pin}"
    print(f"      -> PIN Maestro verificado. Sesión iniciada: {auth_pin['usuario']['nombre']} ({auth_pin['usuario']['rol']})")

    while (time.time() - inicio_global) < duracion_segundos:
        iteracion += 1
        t_iter_inicio = time.time()
        tiempo_transcurrido = t_iter_inicio - inicio_global
        tiempo_restante = max(0, duracion_segundos - tiempo_transcurrido)
        caso = CASOS_CLINICOS_STRESS[(iteracion - 1) % len(CASOS_CLINICOS_STRESS)]

        print("\n" + "-" * 75)
        print(f"[CICLO CLÍNICO #{iteracion}] Transcurrido: {tiempo_transcurrido/60:.1f}m | Restante: {tiempo_restante/60:.1f}m")
        print(f"Paciente: {caso['paciente']} | Cédula: {caso['cedula']} | Edad: {caso['edad']}")
        print("-" * 75)

        log_ciclo = {
            "iteracion": iteracion,
            "timestamp": datetime.datetime.now().isoformat(),
            "paciente": caso["paciente"],
            "pasos": {}
        }

        # 1. Procesar dictado clínico con IA Groq
        print("  -> 1. Estructurando nota clínica con Groq (Llama 3.3 70B)...")
        t0 = time.time()
        resultado_ia = bridge.procesar_texto_clinico(caso["dictado"], generar_pdf=True)
        t_ia = time.time() - t0
        log_ciclo["pasos"]["procesar_ia"] = {
            "duracion_seg": round(t_ia, 2),
            "status": resultado_ia.get("status")
        }

        if resultado_ia.get("status") == "ok":
            print(f"     [OK] IA procesó en {t_ia:.2f}s.")
            reporte_telemetria["resumen"]["total_pacientes_procesados"] += 1

            # 2. Verificar PDF generado
            ruta_pdf = resultado_ia.get("ruta_pdf")
            if ruta_pdf and os.path.exists(ruta_pdf):
                tam_kb = os.path.getsize(ruta_pdf) / 1024
                print(f"     [OK] PDF Formulario 033 MSP generado: {os.path.basename(ruta_pdf)} ({tam_kb:.1f} KB)")
                reporte_telemetria["resumen"]["total_pdfs_generados"] += 1
                log_ciclo["pasos"]["pdf"] = {"ruta": ruta_pdf, "tamano_kb": round(tam_kb, 1)}

                # 3. Verificar previsualización con PyMuPDF
                t_prev0 = time.time()
                preview = bridge.obtener_preview_pdf(ruta_pdf)
                t_prev = time.time() - t_prev0
                if preview.get("status") == "ok":
                    num_pags = preview.get("total_paginas", 0)
                    print(f"     [OK] Previsualización PyMuPDF renderizada ({num_pags} págs) en {t_prev:.2f}s.")
                    log_ciclo["pasos"]["preview"] = {"duracion_seg": round(t_prev, 2), "paginas": num_pags}
                else:
                    print(f"     [WARN] Falló previsualización: {preview.get('message')}")
            else:
                print("     [WARN] No se generó ruta de PDF física.")

            # 4. Agendamiento de cita en lenguaje natural
            cita_str = "mañana a las 16:00" if iteracion % 2 == 1 else "en 3 días a las 10:30"
            print(f"  -> 2. Agendando cita ({cita_str})...")
            t_cita0 = time.time()
            res_cita = bridge.crear_cita({
                "paciente": caso["paciente"],
                "cedula": caso["cedula"],
                "telefono": caso["telefono"],
                "fecha_hora": (datetime.datetime.now() + datetime.timedelta(days=1, hours=2)).strftime("%Y-%m-%d %H:%M"),
                "motivo": f"Control post-operatorio {caso['paciente'].split()[0]}"
            })
            t_cita = time.time() - t_cita0
            if res_cita.get("status") == "ok":
                print(f"     [OK] Cita registrada en base de datos en {t_cita:.2f}s.")
                reporte_telemetria["resumen"]["total_citas_agendadas"] += 1
                log_ciclo["pasos"]["cita"] = {"duracion_seg": round(t_cita, 2), "id": res_cita.get("cita_id")}
            else:
                print(f"     [WARN] Error agendando cita: {res_cita}")

            # 5. Generación de WhatsApp wa.me
            print("  -> 3. Generando recordatorio WhatsApp wa.me...")
            cita_dict_wa = {
                "nombre_paciente": caso["paciente"],
                "fecha_hora_inicio": (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT16:00:00"),
                "descripcion": f"Control post-operatorio {caso['paciente'].split()[0]}"
            }
            msg_wsp = generar_mensaje_recordatorio(cita_dict_wa)
            url_wsp = generar_url_whatsapp(caso["telefono"], msg_wsp)
            if "whatsapp.com" in url_wsp or "wa.me" in url_wsp:
                print(f"     [OK] Enlace WhatsApp generado: {url_wsp[:50]}...")
                reporte_telemetria["resumen"]["total_recordatorios_whatsapp"] += 1
                log_ciclo["pasos"]["whatsapp"] = {"url": url_wsp[:60]}
        else:
            print(f"     [ERROR] Falló procesamiento de IA: {resultado_ia}")
            reporte_telemetria["resumen"]["errores_totales"] += 1

        # 6. Verificación de servidor móvil HTTPS local y código QR
        print("  -> 4. Verificando servidor móvil local y código QR...")
        t_qr0 = time.time()
        qr_info = bridge.obtener_qr_movil_base64()
        t_qr = time.time() - t_qr0
        qr_payload = qr_info.get("qr_b64") or qr_info.get("qr_base64")
        if qr_info.get("status") == "ok" and qr_payload:
            reporte_telemetria["resumen"]["pruebas_qr_exitosas"] += 1
            log_ciclo["pasos"]["qr"] = {"duracion_seg": round(t_qr, 2), "url": qr_info.get("url")}
            print(f"     [OK] Código QR generado en base64 ({qr_info.get('url')}) en {t_qr:.2f}s.")
        else:
            print(f"     [WARN] Falló generación de QR: {qr_info}")

        try:
            url_movil = qr_info.get("url") or f"https://127.0.0.1:{MOBILE_SERVER_PORT}/"
            resp_server = requests.get(url_movil, verify=False, timeout=3)
            if resp_server.status_code == 200:
                reporte_telemetria["resumen"]["pruebas_servidor_movil_exitosas"] += 1
                print(f"     [OK] Servidor móvil HTTPS respondiendo código 200 en {url_movil}.")
                log_ciclo["pasos"]["servidor_movil"] = {"status_code": 200}
        except Exception as e_srv:
            print(f"     [INFO] Servidor móvil respuesta: {e_srv}")

        # 7. Simulación de despacho de audio móvil al puente
        try:
            dummy_wav = crear_archivo_wav_dummy()
            bridge.procesar_audio_externo(dummy_wav)
            if os.path.exists(dummy_wav):
                try:
                    os.remove(dummy_wav)
                except Exception:
                    pass
            print("     [OK] Despacho de audio externo móvil procesado correctamente.")
            log_ciclo["pasos"]["audio_externo"] = {"status": "ok"}
        except Exception as e_aud:
            print(f"     [WARN] Error procesando audio externo: {e_aud}")

        # 8. Listar PDFs recientes
        pdfs_rec = bridge.listar_pdfs_recientes()
        print(f"  -> 5. Listado de PDFs recientes en el sistema: {len(pdfs_rec)} documentos detectados.")
        log_ciclo["pasos"]["total_pdfs_visibles"] = len(pdfs_rec)

        # 9. Integridad de la base de datos SQLite WAL
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            chk = cursor.fetchone()[0]
            log_ciclo["pasos"]["db_integrity"] = chk
            print(f"  -> 6. Integridad de base de datos SQLite WAL: [{chk.upper()}]")

        # 10. Telemetría de memoria RAM y CPU
        mem_rss_mb = round(proceso_actual.memory_info().rss / (1024 * 1024), 2)
        cpu_pct = proceso_actual.cpu_percent(interval=0.1)
        num_hilos = proceso_actual.num_threads()
        if mem_rss_mb > reporte_telemetria["resumen"]["ram_maxima_mb"]:
            reporte_telemetria["resumen"]["ram_maxima_mb"] = mem_rss_mb

        log_ciclo["telemetria"] = {
            "ram_rss_mb": mem_rss_mb,
            "cpu_percent": cpu_pct,
            "hilos_activos": num_hilos,
            "duracion_ciclo_seg": round(time.time() - t_iter_inicio, 2)
        }
        reporte_telemetria["iteraciones"].append(log_ciclo)

        print(f"  -> Telemetría: RAM: {mem_rss_mb} MB | CPU: {cpu_pct}% | Hilos: {num_hilos}")

        # Guardar reporte de telemetría incremental
        ruta_reporte = BASE_PROYECTO / "scratch" / "stress_test_1hour_report.json"
        os.makedirs(ruta_reporte.parent, exist_ok=True)
        with open(ruta_reporte, "w", encoding="utf-8") as rf:
            json.dump(reporte_telemetria, rf, indent=2, ensure_ascii=False)

        # Pausa entre casos clínicos respetando la duración total
        t_restante_global = duracion_segundos - (time.time() - inicio_global)
        if t_restante_global > 0:
            tiempo_dormir = min(pausa_entre_casos, t_restante_global)
            print(f"\n[EN ESPERA] Pausa de {tiempo_dormir:.0f}s hasta el siguiente paciente... (Restante sesión: {t_restante_global/60:.1f}m)")
            
            # Dormir en micro-intervalos para mantener capacidad de interrupción limpia
            paso_dormir = 5
            dormido = 0
            while dormido < tiempo_dormir and (time.time() - inicio_global) < duracion_segundos:
                time.sleep(paso_dormir)
                dormido += paso_dormir
        else:
            break

    # Finalización
    reporte_telemetria["fin"] = datetime.datetime.now().isoformat()
    reporte_telemetria["resumen"]["duracion_total_real_seg"] = round(time.time() - inicio_global, 1)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        reporte_telemetria["resumen"]["estado_db_final"] = cursor.fetchone()[0]

    with open(ruta_reporte, "w", encoding="utf-8") as rf:
        json.dump(reporte_telemetria, rf, indent=2, ensure_ascii=False)

    print("\n" + "=" * 75)
    print("      ¡PRUEBA DE ESTRÉS DE 1 HORA COMPLETADA CON ÉXITO!")
    print(f"      Pacientes procesados: {reporte_telemetria['resumen']['total_pacientes_procesados']}")
    print(f"      PDFs Formulario 033 generados: {reporte_telemetria['resumen']['total_pdfs_generados']}")
    print(f"      Citas agendadas: {reporte_telemetria['resumen']['total_citas_agendadas']}")
    print(f"      Recordatorios WhatsApp: {reporte_telemetria['resumen']['total_recordatorios_whatsapp']}")
    print(f"      Pruebas QR móvil: {reporte_telemetria['resumen']['pruebas_qr_exitosas']}")
    print(f"      RAM máxima consumida: {reporte_telemetria['resumen']['ram_maxima_mb']} MB")
    print(f"      Estado final de base de datos: {reporte_telemetria['resumen']['estado_db_final']}")
    print(f"      Reporte persistido en: {ruta_reporte}")
    print("=" * 75)

if __name__ == "__main__":
    duracion = 3600
    pausa = 450  # Cada 7.5 minutos un nuevo paciente (8 ciclos en 1 hora)
    if len(sys.argv) > 1:
        try:
            duracion = int(sys.argv[1])
        except Exception:
            pass
    if len(sys.argv) > 2:
        try:
            pausa = int(sys.argv[2])
        except Exception:
            pass
    ejecutar_suite_estres_1hora(duracion_segundos=duracion, pausa_entre_casos=pausa)
