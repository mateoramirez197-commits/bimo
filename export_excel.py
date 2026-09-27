import os
import sqlite3
import datetime
from pathlib import Path
import pandas as pd
from config import RUTA_DB, BASE_DIR
from database import get_connection

def exportar_a_excel(ruta_salida=None) -> str:
    """
    Exporta toda la base de datos clínica a un archivo Excel (.xlsx) 
    estructurado profesionalmente en 4 pestañas:
    1. Directorio de Pacientes
    2. Historias Clínicas
    3. Agenda de Citas
    4. Resumen y Métricas
    """
    carpeta_export = BASE_DIR / "Reportes_Excel_CSV"
    carpeta_export.mkdir(parents=True, exist_ok=True)
    fecha_str = datetime.date.today().strftime("%d-%m-%Y")

    if not ruta_salida:
        ruta_salida = carpeta_export / f"BIMO_Registro_Clinico_Completo_{fecha_str}.xlsx"

    with get_connection() as conn:
        # 1. Datos de Pacientes
        df_pacientes = pd.read_sql_query("""
            SELECT 
                p.id AS "ID Paciente",
                p.nombre AS "Nombre Completo",
                COALESCE(p.documento, 'No especificado') AS "Cédula / Documento",
                p.edad AS "Edad",
                CASE WHEN p.edad < 18 THEN 'Pediátrico' ELSE 'Adulto' END AS "Categoría",
                p.sexo AS "Sexo",
                COALESCE(p.telefono, 'No especificado') AS "Teléfono",
                COALESCE(p.direccion, 'No especificado') AS "Dirección",
                COALESCE(p.ocupacion, 'No especificado') AS "Ocupación",
                COUNT(c.id) AS "Total Consultas",
                p.creado_en AS "Fecha de Registro"
            FROM pacientes p
            LEFT JOIN consultas c ON p.id = c.paciente_id
            GROUP BY p.id
            ORDER BY p.id ASC
        """, conn)

        # 2. Datos de Consultas / Historias Clínicas con Honorarios
        df_consultas = pd.read_sql_query("""
            SELECT 
                c.id AS "ID Consulta",
                c.paciente_id AS "ID Paciente",
                p.nombre AS "Paciente",
                c.fecha_hora AS "Fecha y Hora",
                c.motivo_consulta AS "Motivo de Consulta",
                c.enfermedad_actual AS "Enfermedad Actual",
                c.diagnostico AS "Diagnóstico Clínico",
                c.plan_tratamiento AS "Plan de Tratamiento",
                COALESCE(pg.costo_total, 0.0) AS "Costo Tratamiento ($)",
                COALESCE(pg.abono, 0.0) AS "Abono Pagado ($)",
                COALESCE(pg.saldo_pendiente, 0.0) AS "Saldo Restante ($)",
                COALESCE(pg.estado, 'Cancelado') AS "Estado Pago",
                COALESCE(c.ruta_pdf, 'Sin PDF') AS "Ruta Archivo PDF"
            FROM consultas c
            JOIN pacientes p ON c.paciente_id = p.id
            LEFT JOIN pagos pg ON c.id = pg.consulta_id
            ORDER BY c.fecha_hora DESC
        """, conn)

        # 3. Control Detallado de Pagos y Cuentas Claras
        df_pagos = pd.read_sql_query("""
            SELECT 
                pg.id AS "ID Pago",
                pg.fecha AS "Fecha Registro",
                p.nombre AS "Paciente",
                COALESCE(p.documento, 'No especificado') AS "Cédula / Documento",
                pg.costo_total AS "Costo Tratamiento ($)",
                pg.abono AS "Abono Recibido ($)",
                pg.saldo_pendiente AS "Saldo Restante ($)",
                pg.estado AS "Estado de Cuenta",
                pg.metodo_pago AS "Método de Pago",
                COALESCE(pg.notas, 'Sin observaciones') AS "Tratamiento / Concepto"
            FROM pagos pg
            JOIN pacientes p ON pg.paciente_id = p.id
            ORDER BY pg.id DESC
        """, conn)

        # 4. Datos de Agenda
        df_agenda = pd.read_sql_query("""
            SELECT 
                id AS "ID Cita",
                nombre_paciente AS "Paciente",
                COALESCE(telefono, 'No especificado') AS "Teléfono",
                fecha_hora_inicio AS "Fecha y Hora Inicio",
                COALESCE(fecha_hora_fin, 'No especificada') AS "Fecha y Hora Fin",
                COALESCE(descripcion, 'Consulta general') AS "Tratamiento / Motivo",
                estado AS "Estado",
                CASE WHEN google_event_id IS NOT NULL THEN 'Sí' ELSE 'No' END AS "Sincronizado Google",
                creado_en AS "Fecha Creación"
            FROM citas_agenda
            ORDER BY fecha_hora_inicio ASC
        """, conn)

        # 5. Métricas Clínicas y Financieras
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pacientes")
        total_p = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM pacientes WHERE edad < 18")
        pediatricos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM pacientes WHERE edad >= 18")
        adultos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM consultas")
        total_c = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM citas_agenda WHERE estado = 'programada'")
        citas_pend = cursor.fetchone()[0]

        # Métricas financieras
        cursor.execute("SELECT COALESCE(SUM(costo_total), 0.0), COALESCE(SUM(abono), 0.0), COALESCE(SUM(saldo_pendiente), 0.0) FROM pagos")
        sum_row = cursor.fetchone()
        tot_costo = sum_row[0] if sum_row else 0.0
        tot_abono = sum_row[1] if sum_row else 0.0
        tot_saldo = sum_row[2] if sum_row else 0.0

        cursor.execute("SELECT COUNT(*) FROM pagos WHERE estado = 'Saldo Pendiente' AND saldo_pendiente > 0")
        cuentas_pend = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM pagos WHERE estado = 'Cancelado' OR saldo_pendiente <= 0")
        cuentas_canc = cursor.fetchone()[0]

        df_metricas = pd.DataFrame([
            {"Indicador Clínico / Financiero": "Total Pacientes Registrados", "Valor": total_p},
            {"Indicador Clínico / Financiero": "Pacientes Adultos", "Valor": adultos},
            {"Indicador Clínico / Financiero": "Pacientes Pediátricos", "Valor": pediatricos},
            {"Indicador Clínico / Financiero": "Total Historias Clínicas Generadas", "Valor": total_c},
            {"Indicador Clínico / Financiero": "Citas Pendientes en Agenda", "Valor": citas_pend},
            {"Indicador Clínico / Financiero": "Total Facturado en Tratamientos ($)", "Valor": f"${tot_costo:,.2f}"},
            {"Indicador Clínico / Financiero": "Total Recaudado en Abonos ($)", "Valor": f"${tot_abono:,.2f}"},
            {"Indicador Clínico / Financiero": "Saldo Total Pendiente por Cobrar ($)", "Valor": f"${tot_saldo:,.2f}"},
            {"Indicador Clínico / Financiero": "Tratamientos con Saldo Pendiente", "Valor": cuentas_pend},
            {"Indicador Clínico / Financiero": "Tratamientos Totalmente Cancelados", "Valor": cuentas_canc},
            {"Indicador Clínico / Financiero": "Fecha de Generación del Reporte", "Valor": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")},
        ])

    # Guardar en archivo Excel con formato de 5 hojas profesionales
    with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:
        df_pacientes.to_excel(writer, sheet_name="Directorio Pacientes", index=False)
        df_consultas.to_excel(writer, sheet_name="Historias Clínicas", index=False)
        df_pagos.to_excel(writer, sheet_name="Control de Pagos y Saldos", index=False)
        df_agenda.to_excel(writer, sheet_name="Agenda de Citas", index=False)
        df_metricas.to_excel(writer, sheet_name="Métricas y Resumen", index=False)

    # Estilizar profesionalmente el libro de Excel (.xlsx) con openpyxl
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.load_workbook(ruta_salida)
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell_font = Font(name="Segoe UI", size=10)
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        for ws in wb.worksheets:
            ws.views.sheetView[0].showGridLines = True
            ws.row_dimensions[1].height = 28

            # Formatear encabezados de columna
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = thin_border

            # Formatear datos y auto-ajustar ancho de columnas
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                header_val = str(ws.cell(row=1, column=col[0].column).value or "")

                for cell in col:
                    if cell.row > 1:
                        cell.font = cell_font
                        cell.border = thin_border
                        if cell.row % 2 == 0:
                            cell.fill = zebra_fill
                        # Formatear montos en dólares
                        if ("($)" in header_val or "Valor" in header_val or "Costo" in header_val or "Abono" in header_val or "Saldo" in header_val) and isinstance(cell.value, (int, float)):
                            cell.number_format = '$#,##0.00'
                    val_str = str(cell.value or "")
                    max_len = max(max_len, len(val_str))

                ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

        wb.save(ruta_salida)
        print(f"[EXCEL] Libro estilizado con éxito con OpenPyXL: {ruta_salida}")
    except Exception as e_style:
        print(f"[EXCEL WARN] No se pudo aplicar estilos OpenPyXL: {e_style}")

    # Exportar simultáneamente CSVs estándar con separador ';' y codificación UTF-8-SIG para Excel en español (sin datos amontonados)
    ruta_csv_pacientes = carpeta_export / f"BIMO_Pacientes_Directorio_{fecha_str}.csv"
    ruta_csv_consultas = carpeta_export / f"BIMO_Historias_Clinicas_{fecha_str}.csv"
    ruta_csv_pagos = carpeta_export / f"BIMO_Control_Pagos_{fecha_str}.csv"
    ruta_csv_agenda = carpeta_export / f"BIMO_Agenda_Citas_{fecha_str}.csv"

    df_pacientes.to_csv(ruta_csv_pacientes, sep=';', index=False, encoding="utf-8-sig")
    df_consultas.to_csv(ruta_csv_consultas, sep=';', index=False, encoding="utf-8-sig")
    df_pagos.to_csv(ruta_csv_pagos, sep=';', index=False, encoding="utf-8-sig")
    df_agenda.to_csv(ruta_csv_agenda, sep=';', index=False, encoding="utf-8-sig")

    print(f"[EXCEL] Reportes XLSX y CSV generados con éxito en: {carpeta_export}")

    # Auto-abrir archivo Excel en Windows para visualización inmediata
    try:
        os.startfile(str(ruta_salida))
    except Exception:
        pass

    return str(carpeta_export)
