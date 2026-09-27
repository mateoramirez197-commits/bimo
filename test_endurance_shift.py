# -*- coding: utf-8 -*-
"""
Suite de Prueba de Estrés y Resistencia - Simulación de Jornada Clínica de 5 a 6 Horas
Ejecuta de punta a punta el pipeline de BIMO (IA, Odontograma, SQLite WAL, PDF y Citas)
simulando una jornada completa con telemetría en tiempo real de RAM, CPU y consistencia.
"""
import os
import sys
import time
import json
import psutil
import datetime
from pathlib import Path

# Configurar codificación UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

base_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(base_dir))

from desktop_app import BimoBridge
from database import init_db, get_connection, obtener_ultimo_paciente_atendido
from config import get_groq_api_key, get_groq_model, get_whisper_model

# Silenciar apertura de pestañas de navegador durante la prueba de estrés
import webbrowser
webbrowser.open = lambda *args, **kwargs: True

CASOS_CLINICOS_JORNADA = [
    {
        "nombre": "Sisa Llumiquinga Guamán",
        "edad": "29",
        "genero": "Femenino",
        "cedula": "1003456781",
        "telefono": "0998112233",
        "dictado": "Paciente Sisa Llumiquinga Guamán, 29 años, cédula 1003456781, teléfono 0998112233. Consulta por dolor agudo en pieza 26 con sensibilidad al frío y calor. Al examen clínico se observa lesión cariosa profunda en pieza 26 sin afectación pulpar. Diagnóstico Caries de la dentina K02.1. Plan restauración con resina nanoparticulada bajo aislamiento absoluto y colocación de base cavitaria de ionómero de vidrio. Próxima cita de control en 8 días."
    },
    {
        "nombre": "Inti Toapanta Simbaña",
        "edad": "8",
        "genero": "Masculino",
        "cedula": "1724567890",
        "telefono": "0987223344",
        "dictado": "Paciente pediátrico Inti Toapanta Simbaña, 8 años, cédula 1724567890, teléfono 0987223344. Acude por fractura en ángulo incisal de pieza 11 tras caída en bicicleta. Pruebas de vitalidad positivas sin movilidad. Diagnóstico Fractura de diente en esmalte y dentina S02.5. Plan reconstrucción estética con resina y pulido de bordes. Cita de revisión en 15 días a las 10 de la mañana."
    },
    {
        "nombre": "María Carmen Pilataxi Quinatoa",
        "edad": "52",
        "genero": "Femenino",
        "cedula": "1002345678",
        "telefono": "0991334455",
        "dictado": "Paciente María Carmen Pilataxi Quinatoa, 52 años, cédula 1002345678, teléfono 0991334455. Refiere sangrado gingival espontáneo durante el cepillado y movilidad dental grado 1 en sector anteroinferior. Diagnóstico Periodontitis crónica generalizada K05.3. Plan detartraje supragingival y subgingival con ultrasonido en cuatro cuadrantes, profilaxis y enjuague de clorhexidina al 0.12%. Próxima cita en 21 días."
    },
    {
        "nombre": "José Antonio Chushig Tituaña",
        "edad": "34",
        "genero": "Masculino",
        "cedula": "1719876543",
        "telefono": "0984556677",
        "dictado": "Paciente José Antonio Chushig Tituaña, 34 años, cédula 1719876543, teléfono 0984556677. Control post-quirúrgico a los 7 días de exodoncia de pieza 38. Cicatrización favorable del alvéolo, sin infección. Diagnóstico Cuidados postoperatorios Z48.8. Plan retiro de puntos de sutura seda 3-0 y enjuagues antisépticos. Alta clínica del procedimiento."
    },
    {
        "nombre": "Rosa Elena Yugsi Guaminga",
        "edad": "41",
        "genero": "Femenino",
        "cedula": "1004567892",
        "telefono": "0995667788",
        "dictado": "Paciente Rosa Elena Yugsi Guaminga, 41 años, cédula 1004567892, teléfono 0995667788. Acude para inicio de diseño de sonrisa y carillas estéticas en sector anterosuperior. Sin caries activa. Diagnóstico Abrasión dental fisiológica K03.1. Plan toma de impresiones para modelos de estudio, registro oclusal y fotografías clínicas. Cita para prueba de mock-up el próximo viernes a las 15 horas."
    },
    {
        "nombre": "Carlos Alberto Quispe Yamberla",
        "edad": "46",
        "genero": "Masculino",
        "cedula": "1716543210",
        "telefono": "0992778899",
        "dictado": "Paciente Carlos Alberto Quispe Yamberla, 46 años, cédula 1716543210, teléfono 0992778899. Dolor pulsátil nocturno irradiado en pieza 16. Pruebas térmicas muy dolorosas. Diagnóstico Pulpitis irreversible sintomática K04.0 pieza 16. Plan apertura cameral de urgencia, extirpación pulpar, cura con hidróxido de calcio y sellado provisional. Se prescribe Ibuprofeno 600 miligramos cada 8 horas por 3 días. Cita en 5 días."
    },
    {
        "nombre": "Ana Lucía Cachimuel Farinango",
        "edad": "23",
        "genero": "Femenino",
        "cedula": "1005678901",
        "telefono": "0989889900",
        "dictado": "Paciente Ana Lucía Cachimuel Farinango, 23 años, cédula 1005678901, teléfono 0989889900. Control mensual de ortodoncia correctiva con aparatología fija metálica. Buena alineación de arcada superior, apiñamiento leve residual en pieza 33. Plan cambio de arcos a NiTi rectangular 0.016 por 0.022 y reposicionamiento de bracket. Cita para control en 4 semanas."
    },
    {
        "nombre": "Manuel Mesías Lema Imbaquingo",
        "edad": "61",
        "genero": "Masculino",
        "cedula": "1709876543",
        "telefono": "0997113355",
        "dictado": "Paciente Manuel Mesías Lema Imbaquingo, 61 años, cédula 1709876543, teléfono 0997113355. Desdentado parcial superior. Prueba de enfilado en cera de prótesis removible con base metálica. Verificación de dimensión vertical y línea media estética. Aprobado por el paciente. Plan envío al laboratorio para acrilizado final. Cita para instalación en 10 días a las 11 horas."
    }
]

def ejecutar_prueba_estres(total_pacientes=20):
    print("=" * 70)
    print(" 🏥 BIMO PRO - SUITE DE ESTRÉS Y RESISTENCIA: JORNADA CLÍNICA DE 6 HORAS")
    print("=" * 70)
    print(f"Simulación de {total_pacientes} consultas completas con IA, PDF y SQLite...")
    print(f"Modelo IA: {get_groq_model()} | Whisper: {get_whisper_model()}")
    print("-" * 70)

    # 1. Inicializar BD y Bridge
    init_db()
    bridge = BimoBridge()
    proceso_actual = psutil.Process(os.getpid())
    
    memoria_inicial_mb = proceso_actual.memory_info().rss / (1024 * 1024)
    tiempo_inicio = time.time()
    
    telemetria_ciclos = []
    pdfs_generados = []
    errores = []

    print(f"[INICIO] Memoria RSS Inicial: {memoria_inicial_mb:.2f} MB | Hilos activos: {proceso_actual.num_threads()}")

    for i in range(1, total_pacientes + 1):
        t_ciclo_inicio = time.time()
        caso = CASOS_CLINICOS_JORNADA[(i - 1) % len(CASOS_CLINICOS_JORNADA)]
        # Variamos levemente el nombre y cédula para simular pacientes únicos en la jornada
        sufijo = f" {i}" if i > len(CASOS_CLINICOS_JORNADA) else ""
        texto_dictado = caso["dictado"]
        if sufijo:
            texto_dictado = texto_dictado.replace(caso["nombre"], caso["nombre"] + sufijo)

        print(f"\n--- [PACIENTE {i}/{total_pacientes}] {caso['nombre']}{sufijo} ({caso['edad']} años) ---")

        try:
            # Procesar el dictado clínico de forma integral usando el bridge oficial de BIMO
            res = bridge.procesar_texto_clinico(texto_dictado, generar_pdf=True)
            
            assert res.get("status") == "ok", f"Error en procesar_texto_clinico: {res}"
            assert res.get("tipo") == "HISTORIA_CLINICA", f"Tipo inesperado: {res.get('tipo')}"
            
            p_nom = res.get("paciente", "")
            p_id = res.get("paciente_id")
            c_id = res.get("consulta_id")
            ruta_pdf = res.get("ruta_pdf")
            
            assert p_id and p_id > 0, f"Paciente ID inválido: {p_id}"
            assert c_id and c_id > 0, f"Consulta ID inválida: {c_id}"
            assert ruta_pdf and os.path.exists(ruta_pdf), f"PDF no generado: {ruta_pdf}"
            
            pdf_size_kb = os.path.getsize(ruta_pdf) / 1024
            assert pdf_size_kb > 10, f"PDF sospechosamente pequeño ({pdf_size_kb:.1f} KB)"
            pdfs_generados.append(ruta_pdf)

            # 1. Verificar comando relativo de voz: hora actual
            res_hora = bridge.procesar_texto_clinico("¿Bimo qué hora es?")
            assert res_hora.get("tipo") == "COMANDO_HORA", "Fallo en COMANDO_HORA"

            # 2. Verificar resolución de último paciente atendido
            ultimo_p = obtener_ultimo_paciente_atendido()
            assert ultimo_p and ultimo_p["id"] == p_id, f"Último paciente inconsistente: {ultimo_p} vs {p_id}"

            # 3. Comandos de voz de agendamiento y slot-filling
            f_cita_str = ""
            if i % 3 == 1 or i == total_pacientes:
                dia_offset = (i % 12) + 2
                hora_cita = f"{9 + (i % 8):02d}:00"
                res_cita = bridge.procesar_texto_clinico(f"Bimo genera una cita para el último paciente en {dia_offset} días a las {hora_cita}")
                assert res_cita.get("tipo") == "COMANDO_CITA", f"Fallo en agendar cita por voz: {res_cita}"
                cita_id = res_cita.get("cita_id")
                assert cita_id and cita_id > 0, f"ID de cita inválido: {res_cita}"
                f_cita_str = res_cita.get("fecha_hora", "")

                # Slot-filling conversacional (pedir cita sin fecha/hora)
                res_slot = bridge.procesar_texto_clinico(f"Bimo agenda una cita para {p_nom}")
                assert res_slot.get("status") == "requiere_fecha_hora", f"Fallo en slot-filling: {res_slot}"
                bridge._cita_pendiente = None

            # 4. Generación de Recordatorio WhatsApp Anti-ausentismo
            from whatsapp_service import generar_mensaje_recordatorio, generar_url_whatsapp, normalizar_numero_whatsapp
            from config import cargar_datos_clinica
            conf_cli = cargar_datos_clinica()
            num_wa = normalizar_numero_whatsapp(caso.get("telefono", "0998112233"))
            fecha_wa = f_cita_str or (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d 10:00")
            msg_wa = generar_mensaje_recordatorio({
                "nombre_paciente": p_nom,
                "fecha_hora_inicio": fecha_wa,
                "motivo": "Control odontológico y evolución clínica"
            }, conf_cli)
            url_wa = generar_url_whatsapp(num_wa, msg_wa)
            assert ("wa.me" in url_wa or "whatsapp.com" in url_wa) and len(msg_wa) > 30, f"Error en generación WhatsApp: {url_wa}"

            # 5. Verificación de Aprendizaje Dinámico de Apellidos
            ruta_apellidos = os.path.join(base_dir, "data", "apellidos_aprendidos.json")
            total_apellidos_aprendidos = 0
            if os.path.exists(ruta_apellidos):
                try:
                    with open(ruta_apellidos, "r", encoding="utf-8") as f_ap:
                        apellidos_cargados = json.load(f_ap)
                        total_apellidos_aprendidos = len(apellidos_cargados)
                except Exception:
                    pass

            # Telemetría
            t_ciclo_duracion = time.time() - t_ciclo_inicio
            mem_actual_mb = proceso_actual.memory_info().rss / (1024 * 1024)
            hilos_actuales = proceso_actual.num_threads()

            diag_ia = res.get("resultado", {}).get("diagnostico", "Diagnóstico clínico")

            telemetria_ciclos.append({
                "ciclo": i,
                "paciente": p_nom,
                "paciente_id": p_id,
                "consulta_id": c_id,
                "duracion_segundos": round(t_ciclo_duracion, 2),
                "memoria_rss_mb": round(mem_actual_mb, 2),
                "hilos_activos": hilos_actuales,
                "pdf_kb": round(pdf_size_kb, 1),
                "diagnostico": diag_ia[:45],
                "estado": "EXITOSO"
            })

            print(f"      [OK] Paciente #{p_id} | Consulta #{c_id} | PDF: {pdf_size_kb:.1f} KB | {t_ciclo_duracion:.2f}s | RAM: {mem_actual_mb:.1f} MB")
            sys.stdout.flush()
            time.sleep(2.0)

        except Exception as e:
            errores.append({"ciclo": i, "caso": caso["nombre"], "error": str(e)})
            print(f"      [ERROR] Fallo en ciclo {i}: {e}")

    # Verificación de Integridad de Base de Datos SQLite WAL
    print("\n" + "=" * 70)
    print(" [CONTROL DE CALIDAD] Verificando integridad de base de datos SQLite WAL...")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        row = cur.fetchone()
        db_integrity = row[0] if row else "unknown"
        print(f"      -> PRAGMA integrity_check: {db_integrity}")

        cur.execute("SELECT COUNT(*) FROM pacientes;")
        total_pacs_db = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM consultas;")
        total_cons_db = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM citas_agenda;")
        total_citas_db = cur.fetchone()[0]

    tiempo_total = time.time() - tiempo_inicio
    memoria_final_mb = proceso_actual.memory_info().rss / (1024 * 1024)
    delta_memoria = memoria_final_mb - memoria_inicial_mb

    reporte_final = {
        "fecha_ejecucion": datetime.datetime.now().isoformat(),
        "total_ciclos_planificados": total_pacientes,
        "total_ciclos_exitosos": len(telemetria_ciclos),
        "total_errores": len(errores),
        "tasa_exito_porcentaje": (len(telemetria_ciclos) / total_pacientes) * 100,
        "tiempo_total_segundos": round(tiempo_total, 2),
        "tiempo_promedio_por_paciente_segundos": round(tiempo_total / total_pacientes, 2),
        "memoria_inicial_mb": round(memoria_inicial_mb, 2),
        "memoria_final_mb": round(memoria_final_mb, 2),
        "delta_memoria_mb": round(delta_memoria, 2),
        "memoria_maxima_mb": round(max([c["memoria_rss_mb"] for c in telemetria_ciclos]), 2) if telemetria_ciclos else round(memoria_final_mb, 2),
        "hilos_finales": proceso_actual.num_threads(),
        "db_integrity": db_integrity,
        "registros_totales_db": {
            "pacientes_db": total_pacs_db,
            "consultas_db": total_cons_db,
            "citas_db": total_citas_db,
            "pdfs_generados_sesion": len(pdfs_generados)
        },
        "ciclos": telemetria_ciclos,
        "errores": errores
    }

    reporte_path = os.path.join(base_dir, "reporte_estres_jornada.json")
    with open(reporte_path, "w", encoding="utf-8") as f:
        json.dump(reporte_final, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("           RESUMEN FINAL DE RESISTENCIA Y ESTRÉS")
    print("=" * 70)
    print(f"  * Tasa de Éxito:               {reporte_final['tasa_exito_porcentaje']:.1f}% ({len(telemetria_ciclos)}/{total_pacientes})")
    print(f"  * Errores detectados:          {len(errores)}")
    print(f"  * Tiempo Total Simulado:       {tiempo_total:.1f} s ({reporte_final['tiempo_promedio_por_paciente_segundos']} s/paciente)")
    print(f"  * Memoria Inicial RAM:         {memoria_inicial_mb:.1f} MB")
    print(f"  * Memoria Final RAM:           {memoria_final_mb:.1f} MB (Delta: {delta_memoria:+.1f} MB)")
    print(f"  * Integridad SQLite WAL:       {db_integrity}")
    print(f"  * PDFs válidos generados:      {len(pdfs_generados)}")
    print(f"  * Reporte guardado en:         {reporte_path}")
    print("=" * 70)

    assert len(errores) == 0, f"La prueba tuvo {len(errores)} errores."
    assert db_integrity.lower() == "ok", f"Integridad de base de datos fallida: {db_integrity}"
    print("\n[RESULTADO]: BIMO PRO APROBÓ LA PRUEBA DE RESISTENCIA DE JORNADA CLÍNICA AL 100%.")

if __name__ == '__main__':
    total = 20
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        total = int(sys.argv[1])
    ejecutar_prueba_estres(total)
