"""
BIMO PRO - Motor de Micro-Animaciones Fluidas UI/UX
Proporciona animaciones de escala al pasar el mouse (hover micro-scale),
efectos de respiración / pulso para el micrófono y aperturas suaves de tarjetas.
"""


def ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)

def ease_out_cubic(t: float) -> float:
    return 1.0 - pow(1.0 - t, 3)

def bind_hover_microscale(widget, scale_factor: float = 1.15, duration_ms: int = 150):
    """
    Aplica animación de micro-escala fluida a 60 FPS enfocándose ÚNICAMENTE 
    en el tamaño de fuente, evitando recálculos del geometry manager (stutter).
    """
    state = {'anim_id': None, 'curr_size': 0.0}

    orig_font = None
    orig_name = "Segoe UI"
    orig_size = 12
    orig_weight = ""

    try:
        f = widget.cget('font')
        if isinstance(f, tuple) and len(f) >= 2:
            orig_font = f
            orig_name = f[0]
            orig_size = float(f[1])
            if len(f) >= 3:
                orig_weight = f[2]
        elif hasattr(f, 'cget'):
            orig_font = f
            orig_name = f.cget("family")
            orig_size = float(f.cget("size"))
            orig_weight = f.cget("weight")
    except Exception:
        pass

    target_size = orig_size * scale_factor
    state['curr_size'] = orig_size

    def _anim_step(start_s, end_s, frame, total_frames):
        if state['anim_id']:
            widget.after_cancel(state['anim_id'])
            state['anim_id'] = None
            
        frame += 1
        t = frame / total_frames
        ease = ease_out_cubic(t)
        new_s = start_s + (end_s - start_s) * ease
        state['curr_size'] = new_s

        try:
            if orig_weight:
                widget.configure(font=(orig_name, int(new_s), orig_weight))
            else:
                widget.configure(font=(orig_name, int(new_s)))
        except Exception:
            return

        if frame < total_frames:
            state['anim_id'] = widget.after(16, lambda: _anim_step(start_s, end_s, frame, total_frames))
        else:
            state['anim_id'] = None

    def on_enter(event=None):
        if not orig_font: return
        total_f = max(1, duration_ms // 16)
        _anim_step(state['curr_size'], target_size, 0, total_f)

    def on_leave(event=None):
        if not orig_font: return
        total_f = max(1, duration_ms // 16)
        _anim_step(state['curr_size'], orig_size, 0, total_f)

    widget.bind('<Enter>', on_enter, add='+')
    widget.bind('<Leave>', on_leave, add='+')

def animar_despliegue_tarjeta(frame_tarjeta, altura_final: int = 140, duration_ms: int = 220):
    """
    Despliega suavemente una tarjeta o sección de historial con aceleración cúbica.
    """
    total_ticks = max(1, int(duration_ms / 16))
    tick = 0
    try:
        frame_tarjeta.configure(height=2)
    except Exception:
        pass

    def _tick():
        nonlocal tick
        tick += 1
        t = tick / total_ticks
        ease = ease_out_cubic(t)
        curr_h = int(2 + (altura_final - 2) * ease)
        try:
            frame_tarjeta.configure(height=curr_h)
        except Exception:
            return

        if tick < total_ticks:
            frame_tarjeta.after(16, _tick)
        else:
            try:
                frame_tarjeta.configure(height=altura_final)
            except Exception:
                pass

    _tick()
