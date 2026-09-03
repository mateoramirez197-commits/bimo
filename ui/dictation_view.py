import os
import json
import threading
import time
import webbrowser
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import customtkinter as ctk

from ai_engine import transcribir_audio, procesar_comando_o_dictado
from generador_pdf import crear_historia_clinica
from database import registrar_o_actualizar_paciente, guardar_consulta_db, buscar_pacientes_por_nombre, buscar_paciente_por_cedula
from calendar_sync import agendar_cita
from voice_assistant import (
    decir_confirmacion_cita, 
    preguntar_desambiguacion_homonimos_detallada, 
    preguntar_paciente_cita,
    preguntar_cedula_paciente,
    decir_escuchando,
    hablar_asincrono
)
from auth import get_sesion_activa
from config import (
    obtener_tema_activo_dict, cargar_datos_clinica,
    COLOR_BG_DARK, COLOR_CARD_DARK, COLOR_AZUL_ACERO, COLOR_AZUL_PASTEL,
    COLOR_FUCSIA, COLOR_AQUA, COLOR_AMARILLO, COLOR_BORDER,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED
)
from ui.calendar_widget import CalendarWidget
from wake_word_listener import BackgroundWakeListener
from ui.pdf_preview_modal import VentanaVistaPreviaPDF
from ui.correction_modal import VentanaCorreccionExpediente

class DictationView(ctk.CTkFrame):
    def __init__(self, master):
        self.theme = obtener_tema_activo_dict()
        super().__init__(master, fg_color=self.theme["bg_dark"], corner_radius=self.theme["corner_radius"])
        
        self.grabando = False
        self.datos_audio = []
        self.frecuencia = 44100
        self.ultima_ruta_pdf = None

        # Paciente activo en consulta (memoria contextual clínica)
        self.paciente_activo = None

        self._build_ui()

        # Iniciar escucha activa continua automática ultra-sensible (Sin interruptores)
        self.wake_listener = BackgroundWakeListener(callback_comando=self._on_wake_command)
        self.wake_listener.iniciar()
        self._iniciar_loop_pulso()

    def _build_ui(self):
        t = self.theme

        # Header Superior Pulido con Esquinas Redondeadas Soft 3D
        top_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=74, corner_radius=22, border_width=1, border_color=t["border"])
        top_bar.pack(fill="x", padx=20, pady=(16, 16))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(top_bar, text="🎙️ Dictado Clínico & Asistente Inteligente", font=("Segoe UI", 17, "bold"), text_color=t["text_primary"]).pack(side="left", padx=20)
        
        # Etiqueta de paciente en consulta actual
        self.lbl_paciente_activo = ctk.CTkLabel(
            top_bar, text="👤 Sin paciente en consulta", font=("Segoe UI", 11, "bold"),
            text_color=t["text_muted"]
        )
        self.lbl_paciente_activo.pack(side="left", padx=10)

        self.badge_estado = ctk.CTkLabel(
            top_bar, text="● Escucha Activa Lista (Di 'Bimo')", font=("Segoe UI", 11, "bold"),
            text_color=t["aqua"], fg_color=t["card_hover"], corner_radius=16, padx=14, pady=5
        )
        self.badge_estado.pack(side="right", padx=(6, 18))

        self.escucha_activa_habilitada = True
        self.btn_toggle_escucha = ctk.CTkButton(
            top_bar, text="🎙️ Escucha Activa: ON", width=165, height=38, font=("Segoe UI", 11, "bold"),
            fg_color="#059669", hover_color="#047857", corner_radius=19, command=self._toggle_escucha_activa
        )
        self.btn_toggle_escucha.pack(side="right", padx=(6, 6))

        # Contenedor central dividido en dos paneles Soft 3D
        main_grid = ctk.CTkFrame(self, fg_color="transparent")
        main_grid.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ----------------------------------------------------
        # Panel Izquierdo: Controles, Botón y Widget de Agenda
        # ----------------------------------------------------
        col_left = ctk.CTkFrame(main_grid, fg_color=t["card_dark"], corner_radius=26, width=400, border_width=1, border_color=t["border"])
        col_left.pack(side="left", fill="y", padx=(0, 14))
        col_left.pack_propagate(False)

        ctk.CTkLabel(col_left, text="CONTROL DE CAPTURA", font=("Segoe UI", 11, "bold"), text_color=t["text_muted"]).pack(pady=(18, 10), padx=20, anchor="w")

        # Botón masivo tipo PÍLDORA con hover neón de alto contraste
        self.btn_grabar = ctk.CTkButton(
            col_left, text="🎤 Iniciar Dictado Manual", font=("Segoe UI", 13, "bold"),
            height=52, fg_color=t["azul_acero"], hover_color=t.get("aqua", "#00F5D4"), text_color="#ffffff",
            corner_radius=26, command=self._toggle_grabacion
        )
        self.btn_grabar.pack(fill="x", padx=20, pady=(0, 10))

        self.btn_abrir_pdf = ctk.CTkButton(
            col_left, text="📄 Abrir Último PDF", font=("Segoe UI", 12, "bold"),
            height=42, fg_color="#334155", hover_color=t.get("card_hover", "#475569"),
            corner_radius=21, state="disabled", command=self._abrir_pdf_actual
        )
        self.btn_abrir_pdf.pack(fill="x", padx=20, pady=(0, 12))

        # Visualizador de Telemetría Acústica e Ingeniería Médica
        hud_box = ctk.CTkFrame(col_left, fg_color=t["bg_dark"], corner_radius=18, border_width=1, border_color=t["border"])
        hud_box.pack(fill="x", padx=20, pady=(0, 12))

        hud_header = ctk.CTkFrame(hud_box, fg_color="transparent")
        hud_header.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(hud_header, text="📡 TELEMETRÍA DSP & VOZ", font=("Segoe UI", 9, "bold"), text_color=t["aqua"]).pack(side="left")
        self.lbl_dsp_hz = ctk.CTkLabel(hud_header, text="44.1 kHz • 16-Bit VAD", font=("Segoe UI", 9), text_color=t["text_muted"])
        self.lbl_dsp_hz.pack(side="right")

        import tkinter as tk
        self.canvas_audio = tk.Canvas(hud_box, height=28, bg=t["bg_dark"], highlightthickness=0, bd=0)
        self.canvas_audio.pack(fill="x", padx=10, pady=(2, 8))
        self._audio_bars = []
        for i in range(16):
            bx = 10 + i * 20
            bar = self.canvas_audio.create_rectangle(bx, 24, bx + 12, 26, fill=t["azul_acero"], outline="")
            self._audio_bars.append(bar)

        # Widget de Calendario y Agenda Diaria estilo Google Calendar
        self.widget_agenda = CalendarWidget(col_left)
        self.widget_agenda.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # ----------------------------------------------------
        # Panel Derecho: Salida Médica Elegante en Tarjetas Visuales (Cards)
        # ----------------------------------------------------
        col_right = ctk.CTkFrame(main_grid, fg_color=t["card_dark"], corner_radius=26, border_width=1, border_color=t["border"])
        col_right.pack(side="right", fill="both", expand=True)

        header_r = ctk.CTkFrame(col_right, fg_color="transparent")
        header_r.pack(fill="x", padx=20, pady=(18, 8))

        ctk.CTkLabel(header_r, text="EXPEDIENTE CLÍNICO DIGITALIZADO", font=("Segoe UI", 12, "bold"), text_color=t["text_muted"]).pack(side="left")

        # Barra animada de progreso
        self.progress_frame = ctk.CTkFrame(col_right, fg_color="transparent")
        self.lbl_progress = ctk.CTkLabel(self.progress_frame, text="⏳ BIMO está estructurando la consulta médica y generando el odontograma...", font=("Segoe UI", 12, "bold"), text_color=t["aqua"])
        self.lbl_progress.pack(pady=(4, 4))
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, mode="indeterminate", height=6, fg_color=t["bg_dark"], progress_color=t["aqua"])
        self.progress_bar.pack(fill="x", padx=10)

        # Contenedor Desplazable de Tarjetas Clínicas Visuales (Cards)
        self.cards_scroll = ctk.CTkScrollableFrame(col_right, fg_color="transparent")
        self.cards_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 14))

        # Caja de salida oculta de respaldo para compatibilidad interna
        self.caja_salida = ctk.CTkTextbox(col_right, font=("Segoe UI", 11))

        # Render inicial de tarjeta de bienvenida
        self._mostrar_tarjeta_bienvenida()

    def _mostrar_tarjeta_bienvenida(self):
        t = self.theme
        for w in self.cards_scroll.winfo_children():
            w.destroy()

        card_hero = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=20, border_width=1, border_color=t["border"])
        card_hero.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(card_hero, text="🎙️ ESCUCHA ACTIVA BIMO LISTA", font=("Segoe UI", 14, "bold"), text_color=t["aqua"]).pack(anchor="w", padx=20, pady=(18, 6))
        ctk.CTkLabel(
            card_hero,
            text="Habla naturalmente sin presionar botones. BIMO identificará automáticamente tus órdenes:\n"
                 "• \"Bimo, una cita para Mateo Ramírez para el martes a las 3 de la tarde\"\n"
                 "• \"Bimo, cancela la cita de Gandhi López\"\n"
                 "• Dictado libre de historias clínicas completas y odontograma.",
            font=("Segoe UI", 11, "bold"), text_color=t["text_muted"], justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 18))

        card_status = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=20, border_width=1, border_color=t["border"])
        card_status.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(card_status, text="⚡ ESTADO DEL SISTEMA", font=("Segoe UI", 12, "bold"), text_color=t["azul_acero"]).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(card_status, text="● Motor Whisper Neuronal: Activo\n● Micrófono Remoto HTTPS: En línea\n● Base de Datos y Deduplicación: Operativa", font=("Segoe UI", 11), text_color=t["text_primary"], justify="left").pack(anchor="w", padx=20, pady=(0, 16))

    def _on_wake_command(self, texto_comando):
        # GUARDA ESTRICTA: Si el doctor está grabando manualmente o procesando una historia, descartar 100%
        if self.grabando or getattr(self, "_en_dictado_manual", False) or not self.escucha_activa_habilitada:
            print(f"[VOICE LISTENER] Comando descartado por estar en dictado manual: \"{texto_comando}\"")
            return
        self.after(0, lambda: self._ejecutar_comando_detectado(texto_comando))

    def _ejecutar_comando_detectado(self, texto_comando):
        t = self.theme
        self.badge_estado.configure(text="● Voz Detectada", text_color=t["azul_pastel"], fg_color=t["card_hover"])
        
        # Actualizar tarjeta de estado con la voz detectada
        self._mostrar_tarjeta_voz_detectada(texto_comando)

        # Si el usuario solo llamó a Bimo sin orden adicional:
        limpio = texto_comando.lower().replace("bimo", "").replace("vimo", "").replace("bymo", "").replace("hola", "").strip(" ,.?!")
        if not limpio or len(limpio) < 3:
            datos_clinica = cargar_datos_clinica()
            nom_doc = datos_clinica.get("nombre_doctor", "Mateo")
            decir_escuchando(nom_doc)
            return

        threading.Thread(target=self._analizar_intencion_ia, args=(texto_comando,), kwargs={"es_dictado_manual": False}, daemon=True).start()

    def _mostrar_tarjeta_voz_detectada(self, texto_comando):
        t = self.theme
        for w in self.cards_scroll.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=18, border_width=1.5, border_color=t["aqua"])
        card.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(card, text="🔊 VOZ DETECTADA POR BIMO", font=("Segoe UI", 13, "bold"), text_color=t["aqua"]).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(card, text=f"\"{texto_comando}\"", font=("Segoe UI", 12, "bold"), text_color=t["text_primary"], justify="left").pack(anchor="w", padx=18, pady=(0, 16))

    def _mostrar_tarjeta_aviso_dictado_manual(self):
        t = self.theme
        for w in self.cards_scroll.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=18, border_width=1.5, border_color=t["azul_acero"])
        card.pack(fill="x", padx=8, pady=8)

        ctk.CTkLabel(card, text="📋 HISTORIA CLÍNICA & ODONTOGRAMA (MODO MANUAL)", font=("Segoe UI", 13, "bold"), text_color=t["aqua"]).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            card,
            text="Para máxima fidelidad clínica, la generación de historias clínicas y PDFs se activa mediante dictado manual.\n"
                 "Presiona el botón a continuación para hablar sin límites de tiempo:",
            font=("Segoe UI", 11), text_color=t["text_primary"], justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 12))

        btn_iniciar = ctk.CTkButton(
            card, text="🎤 Iniciar Dictado Manual de Historia Clínica", height=42,
            font=("Segoe UI", 12, "bold"), fg_color=t["azul_acero"], hover_color=t["azul_pastel"],
            corner_radius=t["corner_btn"], command=self._toggle_grabacion
        )
        btn_iniciar.pack(fill="x", padx=18, pady=(0, 16))

    def _toggle_escucha_activa(self):
        from audio_feedback import sonar_inicio_dictado, sonar_fin_dictado
        t = self.theme
        if self.escucha_activa_habilitada:
            self.wake_listener.detener()
            self.escucha_activa_habilitada = False
            self.btn_toggle_escucha.configure(text="🔇 Escucha Activa: OFF", fg_color="#475569")
            self.badge_estado.configure(text="● Escucha Pausada", text_color=t["text_muted"])
            sonar_fin_dictado()
        else:
            self.wake_listener.iniciar()
            self.escucha_activa_habilitada = True
            self.btn_toggle_escucha.configure(text="🎙️ Escucha Activa: ON", fg_color="#059669")
            self.badge_estado.configure(text="● Escucha Activa Lista (Di 'Bimo')", text_color=t["aqua"])
            sonar_inicio_dictado()

    def _toggle_grabacion(self):
        from audio_feedback import sonar_inicio_dictado, sonar_fin_dictado
        t = self.theme
        if not self.grabando:
            # EXCLUSIÓN MUTUA ESTRICTA: Pausar escucha activa para no cortar ni interferir en el dictado manual
            self._en_dictado_manual = True
            self.wake_listener.pausar()
            if self.escucha_activa_habilitada:
                self.wake_listener.detener()

            sonar_inicio_dictado()
            self.grabando = True
            self.btn_grabar.configure(text="🛑 Detener Dictado", fg_color=t["fucsia"], hover_color="#dc2626")
            self.badge_estado.configure(text="● Grabando Audio...", text_color="#ffffff", fg_color=t["fucsia"])
            self.datos_audio = []
            self.caja_salida.delete("0.0", "end")
            self.caja_salida.insert("0.0", "🔴 Grabando dictado clínico... Habla con claridad.\n")
            threading.Thread(target=self._grabar_audio_loop, daemon=True).start()
        else:
            sonar_fin_dictado()
            self.grabando = False
            self.btn_grabar.configure(text="⏳ Procesando...", fg_color="#475569", state="disabled")
            self.badge_estado.configure(text="● Analizando Whisper...", text_color=t["amarillo"], fg_color=t["card_hover"])

    def _grabar_audio_loop(self):
        with sd.InputStream(samplerate=self.frecuencia, channels=1, dtype='int16', callback=self._audio_callback):
            while self.grabando:
                sd.sleep(100)
        self._procesar_audio_archivo("temp_dictado.wav")

    def _audio_callback(self, indata, frames, time, status):
        if self.grabando:
            self.datos_audio.extend(indata.copy())
            vol = float(np.abs(indata).mean())
            self.after(0, lambda v=vol: self._actualizar_hud_audio(v))

    def _iniciar_loop_pulso(self):
        self._pulso_fase = 0
        self._animar_pulso_loop()

    def _animar_pulso_loop(self):
        if not self.winfo_exists():
            return
        t = self.theme
        self._pulso_fase = (self._pulso_fase + 1) % 24

        if hasattr(self, "badge_estado") and self.badge_estado.winfo_exists():
            if self.grabando:
                fucsia_glows = ["#FF006E", "#E11D48", "#BE123C", "#9F1239", "#BE123C", "#E11D48"]
                idx = (self._pulso_fase // 4) % len(fucsia_glows)
                self.badge_estado.configure(fg_color=fucsia_glows[idx])
            elif self.escucha_activa_habilitada:
                aqua_glows = ["#00F5D4", "#70D6FF", "#38BDF8", "#0284C7", "#38BDF8", "#70D6FF"]
                idx = (self._pulso_fase // 4) % len(aqua_glows)
                self.badge_estado.configure(text_color=aqua_glows[idx])

        self.after(120, self._animar_pulso_loop)

    def _actualizar_hud_audio(self, vol):
        try:
            t = self.theme
            h_target = min(23, max(2, int(vol * 1.8)))
            if not hasattr(self, "_bar_heights"):
                self._bar_heights = [2] * len(self._audio_bars)

            for i, bar in enumerate(self._audio_bars):
                dist = abs(i - 7.5) / 7.5
                factor = max(0.18, 1.0 - dist * 0.65)
                target = max(2, int(h_target * factor))
                if target > self._bar_heights[i]:
                    self._bar_heights[i] = int(self._bar_heights[i] * 0.35 + target * 0.65)
                else:
                    self._bar_heights[i] = max(2, int(self._bar_heights[i] * 0.80 + target * 0.20))

                h = self._bar_heights[i]
                col = t["aqua"] if h > 11 else t["azul_acero"]
                bx = 10 + i * 20
                self.canvas_audio.coords(bar, bx, 26 - h, bx + 12, 26)
                self.canvas_audio.itemconfig(bar, fill=col)
        except Exception:
            pass

    def procesar_audio_externo(self, ruta_archivo):
        self.after(0, lambda: self._inicio_procesamiento_externo(ruta_archivo))

    def _inicio_procesamiento_externo(self, ruta_archivo):
        t = self.theme
        self.badge_estado.configure(text="● Audio Móvil Recibido", text_color=t["azul_pastel"], fg_color=t["card_hover"])
        self.caja_salida.delete("0.0", "end")
        self.caja_salida.insert("0.0", "📱 Audio recibido desde smartphone. Procesando...\n")
        threading.Thread(target=self._procesar_audio_archivo, args=(ruta_archivo,), daemon=True).start()

    def _procesar_audio_archivo(self, ruta_archivo):
        t = self.theme
        try:
            self._mostrar_animacion_espera(True)

            if ruta_archivo == "temp_dictado.wav":
                audio_np = np.array(self.datos_audio)
                write(ruta_archivo, self.frecuencia, audio_np)

            self._actualizar_status("Transcribiendo con Faster-Whisper...", t["amarillo"], t["card_hover"])
            texto_crudo = transcribir_audio(ruta_archivo)

            self.after(0, lambda: self.caja_salida.insert("end", f"📝 Transcripción de Audio:\n\"{texto_crudo}\"\n\n"))
            self._analizar_intencion_ia(texto_crudo, es_dictado_manual=True)

        except Exception as e:
            err_msg = str(e)
            print(f"[ERROR EN PROCESO DE DICTADO]: {err_msg}")
            self._actualizar_status("❌ Error en Proceso", t["fucsia"], "#450a0a")
            self.after(0, lambda msg=err_msg: self.caja_salida.insert("end", f"\n[ERROR]: {msg}\n"))
        finally:
            self._mostrar_animacion_espera(False)
            self.after(0, lambda: self.btn_grabar.configure(text="🎤 Iniciar Dictado Manual", fg_color=t["azul_acero"], state="normal"))
            if os.path.exists("temp_dictado.wav"):
                try:
                    os.remove("temp_dictado.wav")
                except Exception:
                    pass

            self._en_dictado_manual = False
            # Reactivar la escucha activa solo al concluir completamente el dictado manual
            if self.escucha_activa_habilitada:
                self.after(600, lambda: [self.wake_listener.reanudar(), self.wake_listener.iniciar()])

    def _analizar_intencion_ia(self, texto_crudo, es_dictado_manual=False):
        t = self.theme
        self._actualizar_status("BIMO estructurando con IA...", t["azul_pastel"], t["card_hover"])
        resultado_ia = procesar_comando_o_dictado(texto_crudo)

        tipo = resultado_ia.get("tipo", "HISTORIA_CLINICA")

        # ----------------------------------------------------
        # CASO 1: COMANDO DE CITA O REPROGRAMACIÓN POR VOZ
        # ----------------------------------------------------
        reprogramar_kw = (
            "corrige la cita", "corregir la cita", "cambia la cita", "cambiar la cita",
            "reprograma la cita", "reprogramar la cita", "reprograma", "reprogramar",
            "mueve la cita", "mover la cita", "no puede ese día", "no puede para ese día",
            "no puede el", "para el", "entonces", "mejor para el", "pásale para", "pásala para"
        )
        es_reprogramacion = (tipo == "REPROGRAMAR_CITA") or any(k in texto_crudo.lower() for k in [
            "corrige la cita", "corregir la cita", "cambia la cita", "cambiar la cita",
            "reprograma", "mueve la cita", "no puede ese día", "no puede para ese día"
        ])

        if tipo in ("COMANDO_CITA", "REPROGRAMAR_CITA") or es_reprogramacion:
            paciente_nom = resultado_ia.get("nombre_paciente", "").strip() or "No especificado"
            fecha_hora = resultado_ia.get("fecha_hora", "")
            motivo = resultado_ia.get("motivo", "Consulta reprogramada" if es_reprogramacion else "Consulta general")

            # 1. SI NO SE MENCIONÓ NOMBRE EN EL COMANDO:
            if not paciente_nom or paciente_nom.lower() in ["no especificado", "paciente", "alguien", "desconocido", "none"]:
                if self.paciente_activo:
                    pac_id = self.paciente_activo["id"]
                    pac_nombre = self.paciente_activo["nombre"]
                    self.after(0, lambda: self._completar_agendamiento(pac_id, pac_nombre, fecha_hora, motivo, es_reprogramacion=es_reprogramacion))
                    return
                else:
                    # Si es reprogramación sin nombre, buscar la última cita registrada para actualizarla
                    from database import listar_citas_db
                    citas_ult = listar_citas_db(limite=1)
                    if citas_ult and es_reprogramacion:
                        pac_nombre = citas_ult[0].get("nombre_paciente", "Paciente")
                        pac_id = citas_ult[0].get("paciente_id")
                        self.after(0, lambda: self._completar_agendamiento(pac_id, pac_nombre, fecha_hora, motivo, es_reprogramacion=True))
                        return

                    self._actualizar_status("⚠️ Indique el nombre del paciente", t["amarillo"], t["card_hover"])
                    preguntar_paciente_cita()
                    self.after(0, lambda: self.caja_salida.insert(
                        "end",
                        "⚠️ Indique el nombre del paciente para la cita.\n"
                        "Ejemplo: \"Bimo, una cita para Mateo Ramírez para el martes a las 3\".\n\n"
                    ))
                    return

            # 2. SI SÍ SE MENCIONÓ NOMBRE (Búsqueda inteligente automática):
            self.after(0, lambda: self._resolver_paciente_cita(paciente_nom, fecha_hora, motivo, es_reprogramacion=es_reprogramacion))
            return

        # ----------------------------------------------------
        # CASO 2: CANCELAR O ELIMINAR CITA POR VOZ
        # ----------------------------------------------------
        elif tipo == "CANCELAR_CITA":
            paciente_nom = resultado_ia.get("nombre_paciente", "").strip()
            fecha = resultado_ia.get("fecha", "").strip()
            if fecha == "No especificado":
                fecha = None

            # Si no dijo nombre pero hay un paciente activo en consulta:
            if (not paciente_nom or paciente_nom.lower() == "no especificado") and self.paciente_activo:
                paciente_nom = self.paciente_activo["nombre"]

            from calendar_sync import eliminar_cita
            from voice_assistant import decir_cancelacion_cita

            citas_borradas = eliminar_cita(nombre_paciente=paciente_nom if paciente_nom != "No especificado" else None, fecha=fecha)

            datos_clinica = cargar_datos_clinica()
            nom_doc = datos_clinica.get("nombre_doctor", "Mateo")

            if citas_borradas:
                decir_cancelacion_cita(nom_doc, paciente_nom)
                self._actualizar_status("● Cita Cancelada y Eliminada", t["aqua"], t["card_hover"])
                self.after(0, lambda: self.caja_salida.insert(
                    "end",
                    f"🗑️ CANCELACIÓN CONFIRMADA:\nSe eliminaron {len(citas_borradas)} cita(s) asociadas a '{paciente_nom or 'la fecha'}' en la agenda y Google Calendar.\n\n"
                    f"🔊 BIMO: \"Doctor {nom_doc}, la cita ha sido cancelada y eliminada del calendario.\"\n\n"
                ))
            else:
                hablar_asincrono(f"Doctor {nom_doc}, no encontré citas pendientes para {paciente_nom}.")
                self.after(0, lambda: self.caja_salida.insert("end", f"ℹ️ No se encontraron citas pendientes para '{paciente_nom}'.\n\n"))

            self.widget_agenda.actualizar_citas()
            try:
                app_root = self.winfo_toplevel()
                if hasattr(app_root, "floating_widget") and app_root.floating_widget and app_root.floating_widget.winfo_exists():
                    app_root.floating_widget.actualizar_agenda()
            except Exception:
                pass

        # ----------------------------------------------------
        # CASO 3: CONSULTA MÉDICA PUNTUAL (FÁRMACOS / GUÍA) O IGNORAR
        # ----------------------------------------------------
        elif tipo == "CONSULTA_MEDICA":
            respuesta = resultado_ia.get("respuesta_asistente", "Doctor, por favor especifique el término médico o posología requerida.")
            self._actualizar_status("● Consulta Médica", t["aqua"], t["card_hover"])
            self.after(0, lambda: self.caja_salida.insert("end", f"🩺 BIMO (Guía Médica):\n\"{respuesta}\"\n\n"))
            hablar_asincrono(respuesta)
            from audio_feedback import sonar_fin_dictado
            sonar_fin_dictado()

        elif tipo in ("IGNORAR", "CONVERSACION"):
            # Charla ajena a la medicina: Bimo permanece en silencio y no se desvía
            self._actualizar_status("● Escucha Activa Lista (Di 'Bimo')", t["aqua"], t["card_hover"])
            from audio_feedback import sonar_fin_dictado
            sonar_fin_dictado()
            return

        # ----------------------------------------------------
        # CASO 4: HISTORIA CLÍNICA ODONTOLÓGICA Y ODONTOGRAMA
        # ----------------------------------------------------
        else:
            if not es_dictado_manual:
                # La escucha activa de fondo queda delimitada a citas y consultas cortas.
                # Las historias clínicas y PDFs se reservan al dictado manual para máxima precisión.
                self._actualizar_status("● Escucha Activa Lista (Di 'Bimo')", t["aqua"], t["card_hover"])
                hablar_asincrono("Doctor, para registrar la historia clínica completa y generar el PDF, por favor presione el botón Iniciar Dictado Manual.")
                self.after(0, self._mostrar_tarjeta_aviso_dictado_manual)
                return

            filiacion = resultado_ia.get("datos_filiacion", {})
            nombre_paciente = filiacion.get("nombre", "").strip()

            # MEMORIA CONTEXTUAL CLÍNICA:
            # Si el doctor no repitió el nombre del paciente (ej. solo dijo "el costo es de 160 y abono 40"):
            if not nombre_paciente or nombre_paciente.lower() in ("no especificado", "none", "", "paciente", "paciente_consulta"):
                if self.paciente_activo and self.paciente_activo.get("nombre"):
                    nombre_paciente = self.paciente_activo["nombre"]
                    filiacion["nombre"] = nombre_paciente
                    if self.paciente_activo.get("edad"):
                        filiacion["edad"] = self.paciente_activo["edad"]
                    if self.paciente_activo.get("documento"):
                        filiacion["documento"] = self.paciente_activo["documento"]
                    print(f"[CONTEXTO CLÍNICO] Paciente activo en consulta recuperado: {nombre_paciente}")
                else:
                    # Buscar si en el texto dictado se mencionó el nombre de algún paciente registrado
                    from database import buscar_pacientes
                    pacs_db = buscar_pacientes()
                    t_low = texto_crudo.lower()
                    for p_cand in pacs_db:
                        nom_c = p_cand["nombre"].lower()
                        partes_nom = [part for part in nom_c.split() if len(part) >= 3]
                        if partes_nom and any(part in t_low for part in partes_nom):
                            nombre_paciente = p_cand["nombre"]
                            filiacion["nombre"] = nombre_paciente
                            filiacion["edad"] = f"{p_cand.get('edad', 25)} años"
                            filiacion["documento"] = p_cand.get("documento")
                            print(f"[CONTEXTO CLÍNICO] Paciente detectado por mención en texto: {nombre_paciente}")
                            break
                    if not nombre_paciente or nombre_paciente.lower() in ("no especificado", "none", "", "paciente"):
                        nombre_paciente = "Paciente_Consulta"
                        filiacion["nombre"] = nombre_paciente

            doc = str(filiacion.get("documento", "")).strip()
            cedula_faltante = not doc or doc.lower() in ("no especificado", "none", "")

            # Si ya hay un paciente activo en consulta con cédula:
            if cedula_faltante and self.paciente_activo and self.paciente_activo.get("documento"):
                filiacion["documento"] = self.paciente_activo["documento"]
                cedula_faltante = False

            # NO cortar la voz ni interrumpir al profesional por altavoz mientras habla.
            # Bimo continúa estructurando y registra la consulta con un banner inferior no intrusivo.
            self._finalizar_guardado_historia_clinica(resultado_ia, filiacion, nombre_paciente, cedula_faltante=cedula_faltante)

    def _finalizar_guardado_historia_clinica(self, resultado_ia, filiacion, nombre_paciente, cedula_faltante=False):
        t = self.theme
        paciente_id = registrar_o_actualizar_paciente(filiacion)
        
        # 1. Consolidación inteligente de consulta del mismo día (evita duplicados de 1 minuto)
        from database import obtener_consulta_del_dia, actualizar_consulta_existente
        consulta_hoy = obtener_consulta_del_dia(paciente_id)
        if consulta_hoy:
            try:
                prev_json = json.loads(consulta_hoy.get("json_clinico", "{}"))

                # A) Preservar filiación original (edad, cédula, sexo) si el segundo dictado no los repitió
                prev_fil = prev_json.get("datos_filiacion", {})
                new_fil = resultado_ia.setdefault("datos_filiacion", {})
                for k_fil in ("edad", "documento", "sexo", "telefono", "direccion", "ocupacion"):
                    val_new = new_fil.get(k_fil)
                    if not val_new or str(val_new).strip().lower() in ("no especificado", "n/e", "none", ""):
                        val_prev = prev_fil.get(k_fil)
                        if val_prev and str(val_prev).strip().lower() not in ("no especificado", "n/e", "none", ""):
                            new_fil[k_fil] = val_prev
                            filiacion[k_fil] = val_prev

                # B) Fusionar odontograma: conservar piezas previas y actualizar las modificadas
                prev_odonto_lista = prev_json.get("odontograma", [])
                new_odonto = resultado_ia.get("odontograma", [])
                if not new_odonto:
                    resultado_ia["odontograma"] = prev_odonto_lista
                else:
                    prev_odonto = {p.get("pieza_dental"): p for p in prev_odonto_lista if p.get("pieza_dental")}
                    for p in new_odonto:
                        p_num = p.get("pieza_dental")
                        prev_odonto[p_num] = p
                    resultado_ia["odontograma"] = list(prev_odonto.values())

                # C) Fusionar motivo, enfermedad, diagnóstico y plan sin sobreescribir con "No especificado"
                m_prev = prev_json.get("motivo_consulta", "")
                m_new = resultado_ia.get("motivo_consulta", "")
                if not m_new or m_new == "No especificado":
                    resultado_ia["motivo_consulta"] = m_prev
                elif m_prev and m_prev != "No especificado" and m_new not in m_prev:
                    resultado_ia["motivo_consulta"] = f"{m_prev} / {m_new}".strip(" / ")

                enf_prev = prev_json.get("enfermedad_actual", "")
                enf_new = resultado_ia.get("enfermedad_actual", "")
                if not enf_new or enf_new == "No especificado":
                    resultado_ia["enfermedad_actual"] = enf_prev

                d_prev = prev_json.get("diagnostico", "")
                d_new = resultado_ia.get("diagnostico", "")
                if not d_new or d_new == "No especificado":
                    resultado_ia["diagnostico"] = d_prev
                elif d_prev and d_prev != "No especificado" and d_new not in d_prev:
                    resultado_ia["diagnostico"] = f"{d_prev} | {d_new}".strip(" | ")

                pl_prev = prev_json.get("plan_tratamiento", "")
                pl_new = resultado_ia.get("plan_tratamiento", "")
                if not pl_new or pl_new == "No especificado":
                    resultado_ia["plan_tratamiento"] = pl_prev
                elif pl_prev and pl_prev != "No especificado" and pl_new not in pl_prev:
                    resultado_ia["plan_tratamiento"] = f"{pl_prev} | {pl_new}".strip(" | ")

                # D) Fusionar evaluación de ortodoncia
                if not resultado_ia.get("evaluacion_ortodoncia") and prev_json.get("evaluacion_ortodoncia"):
                    resultado_ia["evaluacion_ortodoncia"] = prev_json["evaluacion_ortodoncia"]

                # E) Fusionar pagos y honorarios
                p_new = resultado_ia.get("pagos")
                p_prev = prev_json.get("pagos")
                if isinstance(p_new, dict) and (float(p_new.get("costo_total") or 0.0) > 0 or float(p_new.get("abono") or 0.0) > 0 or float(p_new.get("saldo_pendiente") or 0.0) > 0):
                    resultado_ia["pagos"] = p_new
                elif isinstance(p_prev, dict) and (float(p_prev.get("costo_total") or 0.0) > 0 or float(p_prev.get("abono") or 0.0) > 0 or float(p_prev.get("saldo_pendiente") or 0.0) > 0):
                    resultado_ia["pagos"] = p_prev

                # F) Fusionar cita programada si la nueva no trajo cita
                if not resultado_ia.get("cita_programada") and prev_json.get("cita_programada"):
                    resultado_ia["cita_programada"] = prev_json["cita_programada"]

                print(f"[CONSOLIDACION] Atención previa de hoy detectada para {nombre_paciente}. Datos clínicos y financieros fusionados.")
            except Exception as e_merge:
                print(f"[CONSOLIDACION ERROR] {e_merge}")

        # Mostrar el resumen formateado con TODOS los datos consolidados (nunca 'No especificado' en datos previos)
        resumen_humano = self._formatear_resumen_clinico(resultado_ia)
        self.after(0, lambda: self.caja_salida.insert("end", resumen_humano))

        # Recordar como paciente activo en consulta para citas subsiguientes automáticas
        self.paciente_activo = {
            "id": paciente_id,
            "nombre": nombre_paciente,
            "edad": filiacion.get("edad"),
            "documento": filiacion.get("documento")
        }
        self.after(0, lambda: self.lbl_paciente_activo.configure(
            text=f"👤 Paciente: {nombre_paciente} ({filiacion.get('edad', 'N/E')}a)",
            text_color=t["aqua"]
        ))

        # Eliminar archivo PDF previo si existe para no dejar documentos duplicados
        ruta_antigua_pdf = consulta_hoy.get("ruta_pdf") if consulta_hoy else None

        self._actualizar_status("Generando PDF y Odontograma Visual...", t["azul_acero"], t["card_hover"])
        ruta_pdf = crear_historia_clinica(resultado_ia, paciente_id=paciente_id)
        self.ultima_ruta_pdf = ruta_pdf

        if ruta_antigua_pdf and os.path.exists(ruta_antigua_pdf) and os.path.abspath(ruta_antigua_pdf) != os.path.abspath(ruta_pdf):
            try:
                os.remove(ruta_antigua_pdf)
                print(f"[PDF ATOMICO] Expediente anterior reemplazado y eliminado: {ruta_antigua_pdf}")
            except Exception as e_del:
                print(f"[PDF ATOMICO WARNING] {e_del}")

        sesion = get_sesion_activa()
        medico_id = sesion["id"] if sesion else None
        
        if consulta_hoy:
            actualizar_consulta_existente(consulta_hoy["id"], resultado_ia, ruta_pdf=ruta_pdf)
        else:
            guardar_consulta_db(paciente_id=paciente_id, json_clinico=resultado_ia, ruta_pdf=ruta_pdf, medico_id=medico_id)

        # Detectar si dentro del dictado clínico se ordenó una cita futura para este mismo paciente
        cita_info = resultado_ia.get("cita_programada", {})
        if cita_info and (cita_info.get("agendar") or cita_info.get("detectada") or cita_info.get("dias_relativos")):
            f_cita = cita_info.get("fecha_hora", "")
            dias_rel = cita_info.get("dias_relativos")

            # CÁLCULO MATEMÁTICO EXACTO DE FECHA FUTURA (Suma días reales al día de hoy)
            if dias_rel:
                try:
                    num_d = int("".join([c for c in str(dias_rel) if c.isdigit()]) or 30)
                    dt_calc = datetime.datetime.now() + datetime.timedelta(days=num_d)
                    f_cita = dt_calc.strftime("%Y-%m-%d 10:00:00")
                except Exception:
                    pass
            elif not f_cita or f_cita.lower() in ("no especificado", "none", ""):
                dt_calc = datetime.datetime.now() + datetime.timedelta(days=15)
                f_cita = dt_calc.strftime("%Y-%m-%d 10:00:00")

            m_cita = cita_info.get("motivo") or f"Control post-tratamiento de {nombre_paciente}"
            self.after(800, lambda p=paciente_id, n=nombre_paciente, f=f_cita, m=m_cita: self._completar_agendamiento(p, n, f, m))

        # Comprobar si la cédula está pendiente
        doc_actual = filiacion.get("documento")
        cedula_pendiente = (not doc_actual or str(doc_actual).strip().lower() in ("no especificado", "none", ""))

        if ruta_pdf:
            msg_estado = "● Consulta de Hoy Actualizada" if consulta_hoy else "● Consulta y Odontograma Registrados"
            self._actualizar_status(msg_estado, t["aqua"], t["card_hover"])
            self.after(0, lambda: self.btn_abrir_pdf.configure(state="normal", fg_color=t["aqua"], text_color="#ffffff"))
            self.after(0, lambda: self._renderizar_tarjetas_clinicas(resultado_ia, ruta_pdf, cedula_faltante=cedula_pendiente, paciente_id=paciente_id, es_actualizacion=bool(consulta_hoy)))
        else:
            self._actualizar_status("⚠️ Error al generar PDF", t["amarillo"], t["card_hover"])

    def _renderizar_tarjetas_clinicas(self, datos: dict, ruta_pdf: str = None, cedula_faltante: bool = False, paciente_id: int = None, es_actualizacion: bool = False):
        import threading
        if threading.current_thread() != threading.main_thread():
            self.after(0, lambda: self._renderizar_tarjetas_clinicas(datos, ruta_pdf, cedula_faltante, paciente_id, es_actualizacion))
            return

        t = self.theme
        try:
            for w in list(self.cards_scroll.winfo_children()):
                try:
                    w.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        fil = datos.get("datos_filiacion", {})
        nom = fil.get("nombre", "Paciente")
        ced = fil.get("documento") or "No especificado"
        edad = fil.get("edad", "N/E")
        tel = fil.get("contacto_emergencia") or fil.get("telefono") or "No especificado"
        motivo = datos.get("motivo_consulta", "Sin motivo especificado")
        diag = datos.get("diagnostico", "Sin diagnóstico especificado")
        plan = datos.get("plan_tratamiento", "Sin plan especificado")
        odonto = datos.get("odontograma", [])

        # Banner de confirmación de actualización unificada
        if es_actualizacion:
            banner_up = ctk.CTkFrame(self.cards_scroll, fg_color="#064e3b" if t["mode"] == "dark" else "#d1fae5", corner_radius=18, border_width=1, border_color=t["aqua"])
            banner_up.pack(fill="x", padx=10, pady=(4, 8))

            top_up = ctk.CTkFrame(banner_up, fg_color="transparent")
            top_up.pack(fill="x", padx=16, pady=(10, 4))
            ctk.CTkLabel(top_up, text="✅ HISTORIA CLÍNICA CONSOLIDADA Y ACTUALIZADA", font=("Segoe UI", 11, "bold"), text_color=t["aqua"]).pack(side="left")

            ctk.CTkLabel(
                banner_up, 
                text=f"Se consolidaron los nuevos tratamientos y odontograma en el expediente de hoy para {nom} (C.I.: {ced}).\nEl PDF anterior fue reemplazado por la versión definitiva unificada de 3 páginas.",
                font=("Segoe UI", 10), text_color=t["text_primary"], justify="left"
            ).pack(anchor="w", padx=16, pady=(0, 10))

        # Banner interactivo no intrusivo si falta la cédula
        if cedula_faltante:
            banner_c = ctk.CTkFrame(self.cards_scroll, fg_color="#1e1b4b" if t["mode"] == "dark" else "#ede9fe", corner_radius=18, border_width=1, border_color=t["aqua"])
            banner_c.pack(fill="x", padx=10, pady=(4, 8))

            top_b = ctk.CTkFrame(banner_c, fg_color="transparent")
            top_b.pack(fill="x", padx=16, pady=(10, 2))
            ctk.CTkLabel(top_b, text="💡 PACIENTE NUEVO — CÉDULA DE IDENTIDAD", font=("Segoe UI", 11, "bold"), text_color=t["aqua"]).pack(side="left")

            ctk.CTkLabel(banner_c, text=f"BIMO archivó la consulta preliminar de {nom}. Cuando sea oportuno, ingresa su cédula aquí:", font=("Segoe UI", 10), text_color=t["text_primary"]).pack(anchor="w", padx=16, pady=(0, 6))

            row_input = ctk.CTkFrame(banner_c, fg_color="transparent")
            row_input.pack(fill="x", padx=16, pady=(0, 10))

            ent_c = ctk.CTkEntry(row_input, height=36, width=220, placeholder_text="Ejemplo: 1724567890", font=("Segoe UI", 11, "bold"), fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"], corner_radius=18)
            ent_c.pack(side="left", padx=(0, 10))

            def asignar_cedula():
                c_val = ent_c.get().strip().replace(" ", "")
                if len(c_val) >= 4:
                    fil["documento"] = c_val
                    registrar_o_actualizar_paciente(fil)
                    from generador_pdf import crear_historia_clinica
                    crear_historia_clinica(datos, paciente_id=paciente_id)
                    self.after(0, lambda: self._renderizar_tarjetas_clinicas(datos, ruta_pdf, cedula_faltante=False, paciente_id=paciente_id))

            ctk.CTkButton(row_input, text="💾 Asignar Cédula", width=130, height=36, font=("Segoe UI", 11, "bold"), fg_color=t["azul_acero"], hover_color=t.get("aqua", "#00F5D4"), corner_radius=18, command=asignar_cedula).pack(side="left")
            ent_c.bind("<Return>", lambda e: asignar_cedula())

        # 1. Card Filiación Soft 3D
        c_fil = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=20, border_width=1, border_color=t["border"])
        c_fil.pack(fill="x", padx=10, pady=6)

        top_fil = ctk.CTkFrame(c_fil, fg_color="transparent")
        top_fil.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(top_fil, text=f"👤 {nom}", font=("Segoe UI", 15, "bold"), text_color=t["text_primary"]).pack(side="left")
        ctk.CTkLabel(top_fil, text=f"🆔 Cédula: {ced}", font=("Segoe UI", 11, "bold"), text_color=t["aqua"], fg_color=t["card_hover"], corner_radius=14, padx=12, pady=4).pack(side="right")

        meta_str = f"Edad: {edad} años  |  Contacto: {tel}"
        ctk.CTkLabel(c_fil, text=meta_str, font=("Segoe UI", 10, "bold"), text_color=t["text_muted"]).pack(anchor="w", padx=18, pady=(0, 14))

        # 2. Card Diagnóstico y Tratamiento Soft 3D
        c_diag = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=20, border_width=1, border_color=t["border"])
        c_diag.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(c_diag, text="🩺 DIAGNÓSTICO & TRATAMIENTO", font=("Segoe UI", 12, "bold"), text_color=t["azul_acero"]).pack(anchor="w", padx=18, pady=(14, 4))
        ctk.CTkLabel(c_diag, text=f"• Motivo: {motivo}", font=("Segoe UI", 11), text_color=t["text_primary"], anchor="w", justify="left").pack(fill="x", padx=18, pady=(2, 2))
        ctk.CTkLabel(c_diag, text=f"• Diagnóstico: {diag}", font=("Segoe UI", 11, "bold"), text_color=t["aqua"], anchor="w", justify="left").pack(fill="x", padx=18, pady=(2, 2))
        ctk.CTkLabel(c_diag, text=f"• Plan Sugerido: {plan}", font=("Segoe UI", 11), text_color=t["text_primary"], anchor="w", justify="left").pack(fill="x", padx=18, pady=(2, 14))

        # 3. Card Odontograma Digitalizado Soft 3D
        c_odonto = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=20, border_width=1, border_color=t["border"])
        c_odonto.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(c_odonto, text="🦷 ODONTOGRAMA DIGITALIZADO (PIEZAS FDI)", font=("Segoe UI", 12, "bold"), text_color=t["amarillo"]).pack(anchor="w", padx=18, pady=(14, 6))

        if odonto:
            for item in odonto:
                p = item.get("pieza_dental") or item.get("pieza") or item.get("diente") or ""
                h = item.get("procedimientos_o_hallazgos", [])
                h_str = ", ".join(h) if isinstance(h, list) else str(h)
                
                h_lower = h_str.lower()
                if any(k in h_lower for k in ["ausent", "perd", "extrac", "exodoncia", "extraíd", "extraida", "extraído", "extraido", "sacar", "sacaron"]):
                    color_badge = "#94a3b8"
                    icon_badge = "⚪"
                elif any(k in h_lower for k in ["caries", "dolor", "fractura", "pulpitis", "infecci"]):
                    color_badge = t.get("fucsia", "#ef4444")
                    icon_badge = "🔴"
                else:
                    color_badge = t.get("azul_pastel", "#38bdf8")
                    icon_badge = "🔵"

                row_p = ctk.CTkFrame(c_odonto, fg_color="transparent")
                row_p.pack(fill="x", padx=18, pady=2)
                ctk.CTkLabel(row_p, text=f"{icon_badge} Pieza {p}:", font=("Segoe UI", 11, "bold"), text_color=color_badge, width=85, anchor="w").pack(side="left")
                ctk.CTkLabel(row_p, text=h_str, font=("Segoe UI", 10, "bold"), text_color=t["text_primary"], anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkFrame(c_odonto, height=10, fg_color="transparent").pack()
        else:
            ctk.CTkLabel(c_odonto, text="Estructuras dentales sin alteraciones patológicas registradas.", font=("Segoe UI", 10), text_color=t["text_muted"]).pack(anchor="w", padx=18, pady=(0, 14))

        # 4. Card Control de Pagos y Saldos Soft 3D
        pagos_data = datos.get("pagos", {})
        c_costo = float(pagos_data.get("costo_total") or 0.0)
        c_abono = float(pagos_data.get("abono") or 0.0)
        c_saldo = float(pagos_data.get("saldo_pendiente") if pagos_data.get("saldo_pendiente") is not None else max(0.0, round(c_costo - c_abono, 2)))

        card_pago = ctk.CTkFrame(self.cards_scroll, fg_color=t["bg_dark"], corner_radius=20, border_width=1, border_color=t["border"])
        card_pago.pack(fill="x", padx=10, pady=6)

        top_pg = ctk.CTkFrame(card_pago, fg_color="transparent")
        top_pg.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(top_pg, text="💳 CONTROL DE PAGOS & ESTADO DE CUENTA", font=("Segoe UI", 12, "bold"), text_color=t["aqua"]).pack(side="left")

        # Badge interactivo tipo PÍLDORA de estado de cuenta
        if c_costo > 0 and c_saldo <= 0:
            badge_p_col = "#10b981"
            badge_p_bg = "#064e3b" if t["mode"] == "dark" else "#d1fae5"
            badge_p_txt = "✅ SALDO CANCELADO"
        elif c_saldo > 0:
            badge_p_col = "#fbbf24"
            badge_p_bg = "#451a03" if t["mode"] == "dark" else "#fef3c7"
            badge_p_txt = f"⚠️ SALDO RESTANTE: ${c_saldo:.2f}"
        else:
            badge_p_col = t.get("text_muted", "#94a3b8")
            badge_p_bg = t.get("card_hover", "#334155")
            badge_p_txt = "● CUENTAS AL DIA"

        ctk.CTkLabel(top_pg, text=badge_p_txt, font=("Segoe UI", 11, "bold"), text_color=badge_p_col, fg_color=badge_p_bg, corner_radius=14, padx=14, pady=4).pack(side="right")

        costo_f_str = f"${c_costo:.2f}" if c_costo > 0 else "Por definir"
        abono_f_str = f"${c_abono:.2f}" if c_abono > 0 else "$0.00"
        saldo_f_str = f"${c_saldo:.2f}" if c_saldo > 0 else "$0.00"
        metodo_f_str = pagos_data.get("metodo_pago") or "Efectivo"

        detalles_fin = f"• Costo del Tratamiento: {costo_f_str}   |   Abono Recibido: {abono_f_str}   |   Saldo Pendiente: {saldo_f_str}\n• Método de Pago: {metodo_f_str}"
        if pagos_data.get("notas"):
            detalles_fin += f"   |   Concepto: {pagos_data['notas']}"

        ctk.CTkLabel(card_pago, text=detalles_fin, font=("Segoe UI", 10, "bold"), text_color=t["text_primary"], justify="left", anchor="w").pack(fill="x", padx=18, pady=(2, 8))

        from ui.payment_modal import VentanaPagosModal
        def _abrir_modal_pagos_dictation():
            from database import obtener_consulta_del_dia
            c_hoy = obtener_consulta_del_dia(paciente_id) if paciente_id else None
            c_id_pago = c_hoy.get("id") if c_hoy else None
            VentanaPagosModal(
                self, datos, paciente_id=paciente_id, consulta_id=c_id_pago, ruta_pdf=ruta_pdf,
                on_update_callback=lambda d_up, r_up: self.after(0, lambda: self._renderizar_tarjetas_clinicas(d_up, r_up, cedula_faltante=cedula_faltante, paciente_id=paciente_id, es_actualizacion=es_actualizacion)),
                theme=t
            )

        btn_pago_act = ctk.CTkButton(
            card_pago, text="💵 Ventanita de Pagos & Saldos", height=36, width=220,
            font=("Segoe UI", 11, "bold"), fg_color=t.get("azul_acero", "#1e3a8a"),
            hover_color=t.get("aqua", "#00F5D4"), text_color="#ffffff",
            corner_radius=18, command=_abrir_modal_pagos_dictation
        )
        btn_pago_act.pack(anchor="w", padx=18, pady=(0, 12))

        # 5. Botones de acción clínica tipo PÍLDORA (Vista previa nativa, Corrección de datos y Apertura)
        if ruta_pdf:
            bar_actions = ctk.CTkFrame(self.cards_scroll, fg_color="transparent")
            bar_actions.pack(fill="x", padx=10, pady=(8, 14))

            btn_prev = ctk.CTkButton(
                bar_actions, text="👁️ Vista Previa del PDF", height=44,
                font=("Segoe UI", 12, "bold"), fg_color=t["aqua"], hover_color=t.get("azul_acero", "#7C3AED"),
                text_color="#ffffff", corner_radius=22,
                command=lambda r=ruta_pdf: self._mostrar_vista_previa_pdf(r)
            )
            btn_prev.pack(side="left", fill="x", expand=True, padx=(0, 6))

            btn_edit = ctk.CTkButton(
                bar_actions, text="✏️ Corregir Datos / Regenerar", height=44,
                font=("Segoe UI", 11, "bold"), fg_color="#334155", hover_color="#475569",
                text_color="#ffffff", corner_radius=22,
                command=lambda d=datos, r=ruta_pdf, p=paciente_id: self._abrir_modal_correccion(d, r, p)
            )
            btn_edit.pack(side="left", fill="x", expand=True, padx=6)

            from config import abrir_archivo_o_carpeta_nativo
            btn_ext = ctk.CTkButton(
                bar_actions, text="↗ Abrir", width=85, height=44,
                font=("Segoe UI", 11, "bold"), fg_color=t["azul_acero"], hover_color=t.get("azul_pastel", "#38bdf8"),
                text_color="#ffffff", corner_radius=22,
                command=lambda r=ruta_pdf: abrir_archivo_o_carpeta_nativo(r)
            )
            btn_ext.pack(side="right", padx=(6, 0))

    def _mostrar_vista_previa_pdf(self, ruta_pdf):
        """Abre la ventana modal con la vista previa nativa de alta definición del PDF."""
        if ruta_pdf and os.path.exists(ruta_pdf):
            VentanaVistaPreviaPDF(self, ruta_pdf, self.theme)
        else:
            print(f"[PDF PREVIEW] Archivo no encontrado: {ruta_pdf}")

    def _abrir_modal_correccion(self, datos, ruta_pdf, paciente_id):
        """Abre el diálogo modal interactivo para corregir cualquier dato dictado por error."""
        VentanaCorreccionExpediente(
            self, datos, ruta_pdf, paciente_id, self.theme,
            on_guardar=self._ejecutar_guardado_correccion
        )

    def _ejecutar_guardado_correccion(self, datos_actualizados, fil_actualizada, ruta_pdf_antigua, paciente_id):
        """
        Aplica las correcciones en base de datos, regenera el PDF con los nuevos datos
        y ELIMINA ESTRICTAMENTE el PDF anterior para que nunca queden dos archivos duplicados.
        """
        from database import get_connection, registrar_o_actualizar_paciente
        from generador_pdf import crear_historia_clinica

        # 1. Actualizar paciente en SQLite
        p_id = registrar_o_actualizar_paciente(fil_actualizada)

        # 2. Regenerar nuevo PDF definitivo
        datos_actualizados["datos_filiacion"] = fil_actualizada
        nueva_ruta = crear_historia_clinica(datos_actualizados, paciente_id=p_id)

        # 3. ELIMINACIÓN ESTRICTA DEL PDF ANTERIOR
        if ruta_pdf_antigua and os.path.exists(ruta_pdf_antigua) and os.path.abspath(ruta_pdf_antigua) != os.path.abspath(nueva_ruta):
            try:
                os.remove(ruta_pdf_antigua)
                print(f"[PDF CLEANUP] PDF anterior eliminado tras corrección: {ruta_pdf_antigua}")
                dir_antiguo = os.path.dirname(ruta_pdf_antigua)
                if os.path.exists(dir_antiguo) and not os.listdir(dir_antiguo):
                    os.rmdir(dir_antiguo)
            except Exception as e:
                print(f"[PDF CLEANUP ERROR]: {e}")

        self.ultima_ruta_pdf = nueva_ruta
        self.btn_abrir_pdf.configure(state="normal")

        # 4. Actualizar consulta en base de datos
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE consultas SET 
                    motivo_consulta = ?, diagnostico = ?, plan_tratamiento = ?, 
                    json_clinico = ?, ruta_pdf = ?
                WHERE paciente_id = ? AND DATE(fecha_hora) = DATE('now', 'localtime')
            """, (
                datos_actualizados.get("motivo_consulta", ""),
                datos_actualizados.get("diagnostico", ""),
                datos_actualizados.get("plan_tratamiento", ""),
                json.dumps(datos_actualizados, ensure_ascii=False),
                nueva_ruta,
                p_id
            ))
            conn.commit()

        # 5. Re-renderizar tarjetas con los datos corregidos
        self.after(0, lambda: self._renderizar_tarjetas_clinicas(datos_actualizados, nueva_ruta, cedula_faltante=False, paciente_id=p_id))
        self._actualizar_status("● Expediente Actualizado", self.theme["aqua"], "#064e3b")

    def _resolver_paciente_cita(self, nombre_dictado, fecha_hora, motivo, es_reprogramacion=False):
        # A) Si coincide con el paciente actualmente en consulta
        if self.paciente_activo and (
            nombre_dictado.lower() in self.paciente_activo["nombre"].lower() or 
            self.paciente_activo["nombre"].lower() in nombre_dictado.lower()
        ):
            pac = self.paciente_activo
            self._completar_agendamiento(pac["id"], pac["nombre"], fecha_hora, motivo, es_reprogramacion=es_reprogramacion)
            return

        # B) Búsqueda en base de datos
        coincidencias = buscar_pacientes_por_nombre(nombre_dictado)

        # 1. Un solo paciente encontrado: Asignación inmediata (Sin pedir cédula)
        if len(coincidencias) == 1:
            pac = coincidencias[0]
            self._completar_agendamiento(pac["id"], pac["nombre"], fecha_hora, motivo, es_reprogramacion=es_reprogramacion)

        # 2. Dos o más homónimos: Preguntar con edad y cédula si no es reprogramación inmediata
        elif len(coincidencias) > 1 and not es_reprogramacion:
            preguntar_desambiguacion_homonimos_detallada(nombre_dictado, coincidencias)
            self._mostrar_modal_homonimos(nombre_dictado, fecha_hora, motivo, coincidencias)

        # 3. Paciente no registrado o reprogramación directa: Crear/reprogramar cita directa para ese nombre
        else:
            self._completar_agendamiento(None, nombre_dictado, fecha_hora, motivo, es_reprogramacion=es_reprogramacion)

    def _mostrar_modal_homonimos(self, nombre_paciente, fecha_hora, motivo, coincidencias):
        t = self.theme
        modal = ctk.CTkToplevel(self)
        modal.title("Desambiguación de Homónimos")
        modal.geometry("480x420")
        modal.attributes("-topmost", True)
        modal.configure(fg_color=t["bg_dark"])

        ctk.CTkLabel(modal, text="⚠️ PACIENTES HOMÓNIMOS ENCONTRADOS", font=("Segoe UI", 14, "bold"), text_color=t["amarillo"]).pack(pady=(20, 4))
        ctk.CTkLabel(modal, text=f"Se encontró más de un paciente llamado '{nombre_paciente}'.\nSelecciona a cuál corresponde la cita:", font=("Segoe UI", 11), text_color=t["text_muted"], justify="center").pack(pady=(0, 16))

        scroll = ctk.CTkScrollableFrame(modal, fg_color=t["card_dark"], corner_radius=10, height=200, border_width=1, border_color=t["border"])
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        for p in coincidencias:
            doc = p.get("documento") or f"ID{p['id']}"
            edad = f"{p.get('edad', 'N/E')} años" if p.get('edad') else ""
            btn_text = f"👤 {p['nombre']}  |  {edad}  |  Cédula: {doc}"
            
            btn = ctk.CTkButton(
                scroll, text=btn_text, font=("Segoe UI", 11, "bold"), height=38,
                fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
                corner_radius=t["corner_btn"],
                command=lambda pac=p: [modal.destroy(), self._completar_agendamiento(pac['id'], pac['nombre'], fecha_hora, motivo)]
            )
            btn.pack(fill="x", padx=10, pady=4)

        btn_nuevo = ctk.CTkButton(
            modal, text="➕ Es un Paciente Nuevo Diferente", height=38, font=("Segoe UI", 11),
            fg_color="#334155", hover_color="#475569", corner_radius=t["corner_btn"],
            command=lambda: [modal.destroy(), self._completar_agendamiento(None, nombre_paciente, fecha_hora, motivo)]
        )
        btn_nuevo.pack(fill="x", padx=20, pady=(0, 20))

    def _completar_agendamiento(self, paciente_id, nombre_paciente, fecha_hora, motivo, es_reprogramacion=False):
        import time
        from database import cancelar_o_eliminar_cita_db
        from voice_assistant import decir_confirmacion_cita, decir_reprogramacion_cita

        primer_nombre_paciente = nombre_paciente.lower().strip().split()[0] if nombre_paciente else "paciente"

        # Si es reprogramación o cambio de cita:
        if es_reprogramacion:
            # 1. Limpiar debounce para permitir el cambio inmediato
            if hasattr(self, "_citas_recientes_anti_bucle"):
                self._citas_recientes_anti_bucle.pop(primer_nombre_paciente, None)

            # 2. Eliminar automáticamente la cita anterior en SQLite y Google Calendar
            citas_borradas = cancelar_o_eliminar_cita_db(nombre_paciente=nombre_paciente)
            print(f"[CALENDAR REPROGRAMAR] Cita anterior borrada ({len(citas_borradas)} registros) para {nombre_paciente}")
        else:
            # FILTRO ANTI-DUPLICADOS ESTRICTO: Evitar agendar más de una cita para el mismo paciente en menos de 15 segundos
            if not hasattr(self, "_citas_recientes_anti_bucle"):
                self._citas_recientes_anti_bucle = {}
            ahora = time.time()
            if primer_nombre_paciente in self._citas_recientes_anti_bucle and ahora - self._citas_recientes_anti_bucle[primer_nombre_paciente] < 15.0:
                print(f"[CALENDAR ANTI-BUCLE] Cita duplicada prevenida para: {nombre_paciente} ({primer_nombre_paciente})")
                return
            self._citas_recientes_anti_bucle[primer_nombre_paciente] = ahora

        resultado_sync = agendar_cita(nombre_paciente, "", fecha_hora, descripcion=motivo, paciente_id=paciente_id, abrir_en_navegador=True)
        url_gcal = resultado_sync.get("url_gcal", "")

        datos_clinica = cargar_datos_clinica()
        nombre_doc = datos_clinica.get("nombre_doctor", "Mateo")

        # Voz femenina natural adaptada al tipo de acción
        if es_reprogramacion:
            decir_reprogramacion_cita(nombre_doc, nombre_paciente, fecha_hora)
        else:
            decir_confirmacion_cita(nombre_doc, nombre_paciente)

        def _actualizar_gui():
            t = self.theme
            if es_reprogramacion:
                self._actualizar_status("● Cita Reprogramada y Actualizada", t["aqua"], t["card_hover"])
                self.caja_salida.insert("end", f"🔄 CITA REPROGRAMADA Y ACTUALIZADA:\n• Paciente: {nombre_paciente} (ID: {paciente_id or 'Registrado'})\n• Nueva Fecha y Hora: {fecha_hora}\n• Motivo: {motivo}\n• La cita previa fue eliminada de la agenda automáticamente.\n\n🔊 BIMO: \"Doctor {nombre_doc}, la cita de {nombre_paciente} ha sido cambiada para la nueva fecha y la cita anterior fue eliminada.\"\n\n")
            else:
                self._actualizar_status("● Cita Agendada y Sincronizada", t["aqua"], t["card_hover"])
                self.caja_salida.insert("end", f"🗓️ CITA PROGRAMADA CON ÉXITO:\n• Paciente: {nombre_paciente} (ID: {paciente_id or 'Nuevo'})\n• Fecha y Hora: {fecha_hora}\n• Procedimiento: {motivo}\n\n🔊 BIMO: \"Doctor {nombre_doc}, cita agendada y sincronizada para {nombre_paciente}.\"\n\n")

            self.widget_agenda.actualizar_citas()

            try:
                app_root = self.winfo_toplevel()
                if hasattr(app_root, "floating_widget") and app_root.floating_widget and app_root.floating_widget.winfo_exists():
                    app_root.floating_widget.actualizar_agenda()
            except Exception:
                pass

        self.after(0, _actualizar_gui)

    def _formatear_resumen_clinico(self, datos: dict) -> str:
        fil = datos.get("datos_filiacion", {})
        paciente = fil.get("nombre", "No especificado")
        edad = fil.get("edad", "No especificado")
        doc = fil.get("documento", "No especificado")
        motivo = datos.get("motivo_consulta", "No especificado")
        diag = datos.get("diagnostico", "No especificado")
        plan = datos.get("plan_tratamiento", "No especificado")
        odonto = datos.get("odontograma", [])

        txt = "──────────────────────────────────────────────────────────\n"
        txt += "  📋  EXPEDIENTE CLÍNICO ODONTOLÓGICO DIGITALIZADO\n"
        txt += "──────────────────────────────────────────────────────────\n\n"
        txt += f"  👤  PACIENTE TITULAR:   {paciente}\n"
        txt += f"  🆔  CÉDULA / DOC:       {doc}\n"
        txt += f"  🎂  EDAD REGISTRADA:    {edad} años\n"
        if fil.get("contacto_emergencia") and fil.get("contacto_emergencia").lower() != "no especificado":
            txt += f"  📞  TELÉFONO CONTACTO:  {fil.get('contacto_emergencia')}\n"
        txt += "\n"
        txt += f"  🩺  MOTIVO DE CONSULTA:\n      {motivo}\n\n"
        txt += f"  🔬  DIAGNÓSTICO ODONTOLÓGICO:\n      {diag}\n\n"
        if plan and plan.lower() != "no especificado":
            txt += f"  💊  PLAN DE TRATAMIENTO SUGERIDO:\n      {plan}\n\n"

        txt += "  🦷  HALLAZGOS DEL ODONTOGRAMA:\n"
        if odonto:
            for item in odonto:
                p = item.get("pieza_dental") or item.get("pieza") or item.get("diente") or ""
                h = item.get("procedimientos_o_hallazgos", [])
                if isinstance(h, list):
                    h_str = ", ".join(h)
                else:
                    h_str = str(h)
                txt += f"      • Pieza {p}: {h_str}\n"
        else:
            txt += "      • Estructuras dentales sin alteraciones patológicas activas.\n"
        txt += "\n──────────────────────────────────────────────────────────\n\n"
        return txt

    def _mostrar_animacion_espera(self, activar: bool):
        if activar:
            self.after(0, lambda: self.progress_frame.pack(fill="x", padx=20, pady=(0, 10), before=self.caja_salida))
            self.after(0, self.progress_bar.start)
        else:
            self.after(0, self.progress_bar.stop)
            self.after(0, self.progress_frame.pack_forget)

    def _actualizar_status(self, texto, fg_color, bg_color):
        self.after(0, lambda: self.badge_estado.configure(text=f"● {texto}", text_color=fg_color, fg_color=bg_color))

    def _abrir_pdf_actual(self):
        if self.ultima_ruta_pdf and os.path.exists(self.ultima_ruta_pdf):
            try:
                os.startfile(self.ultima_ruta_pdf)
            except Exception as e:
                print(f"Error al abrir PDF: {e}")
