import customtkinter as ctk
from config import (
    obtener_tema_activo_dict, MOBILE_SERVER_PORT
)
from mobile_mic_server import obtener_ip_local, generar_codigo_qr_url

class MobileView(ctk.CTkFrame):
    def __init__(self, master):
        self.theme = obtener_tema_activo_dict()
        super().__init__(master, fg_color="transparent")
        self._build_ui()

    def _build_ui(self):
        t = self.theme

        # Header Superior Pulido
        top_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=68, corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        top_bar.pack(fill="x", padx=16, pady=(12, 10))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(top_bar, text="📱 Software en tu Smartphone", font=("Segoe UI", 16, "bold"), text_color=t["text_primary"]).pack(side="left", padx=16)
        
        badge = ctk.CTkLabel(
            top_bar, text="🔒 Enlace Clínico Encriptado SSL / TLS", font=("Segoe UI", 11, "bold"),
            text_color=t["aqua"], fg_color=t["card_hover"], corner_radius=12, padx=12, pady=4
        )
        badge.pack(side="right", padx=16)

        # Card central con el código QR y esquinas suaves
        card = ctk.CTkFrame(self, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"], width=640, height=540)
        card.pack(pady=10)
        card.pack_propagate(False)

        ip = obtener_ip_local()
        url_movil = f"https://{ip}:{MOBILE_SERVER_PORT}"

        ctk.CTkLabel(card, text="CONEXIÓN SEGURA CON TU SMARTPHONE", font=("Segoe UI", 14, "bold"), text_color=t["aqua"]).pack(pady=(18, 8))

        pil_qr = generar_codigo_qr_url(url_movil)
        ctk_qr = ctk.CTkImage(light_image=pil_qr, dark_image=pil_qr, size=(200, 200))

        lbl_qr = ctk.CTkLabel(card, text="", image=ctk_qr)
        lbl_qr.pack(pady=2)

        ctk.CTkLabel(card, text="Escanea la cámara con tu teléfono para abrir Bimo Clinic desde tu celular", font=("Segoe UI", 11, "bold"), text_color=t["text_muted"]).pack(pady=(4, 8))

        # Guía visual de 4 pasos
        box_guia = ctk.CTkFrame(card, fg_color=t["bg_dark"], corner_radius=14, border_width=1, border_color=t["border"])
        box_guia.pack(fill="x", padx=30, pady=(14, 18))

        pasos = [
            ("1", "Conecta tu teléfono a la red Wi-Fi de la clínica."),
            ("2", "Abre la cámara de tu teléfono y escanea el código QR."),
            ("3", "Toca 'Avanzado' -> 'Continuar a Bimo Clinic' (certificado local SSL/TLS)."),
            ("4", "Usa tu teléfono como copiloto clínico y visualiza historias clínicas en PDF directamente desde tu celular.")
        ]

        for num, texto in pasos:
            row = ctk.CTkFrame(box_guia, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            
            badge_num = ctk.CTkLabel(
                row, text=num, width=22, height=22, font=("Segoe UI", 10, "bold"),
                text_color="#ffffff", fg_color=t["aqua"], corner_radius=11
            )
            badge_num.pack(side="left", padx=(0, 10))
            
            ctk.CTkLabel(row, text=texto, font=("Segoe UI", 11), text_color=t["text_primary"]).pack(side="left", fill="x")
