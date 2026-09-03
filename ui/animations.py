# BIMO PRO - CERO DESTELLOS
# Todas las animaciones manuales basadas en timers (.after) han sido deshabilitadas
# para priorizar la estabilidad nativa del hardware en Windows, eliminando cualquier
# tipo de flickering, destello o stuttering grfico.
# CustomTkinter maneja el hover nativamente.

def bind_hover_lift_and_fade(*args, **kwargs):
    # Dummy func
    pass

def bind_hover_microscale(*args, **kwargs):
    # Dummy func
    pass

def animar_despliegue_tarjeta(frame_tarjeta, altura_final: int = 140, duration_ms: int = 220):
    try:
        frame_tarjeta.configure(height=altura_final)
    except:
        pass
