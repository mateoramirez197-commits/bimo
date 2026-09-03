"""
BIMO PRO - Motor de Micro-Animaciones Fluidas UI/UX
Proporciona animaciones de escala al pasar el mouse (hover micro-scale),
efectos de respiración / pulso para el micrófono y aperturas suaves de tarjetas.
"""


def ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)

def ease_out_cubic(t: float) -> float:
    return 1.0 - pow(1.0 - t, 3)

def bind_hover_microscale(widget, normal_h: int = 52, hover_h: int = 58, expand_font: bool = True):
    """
    Aplica animación de micro-escala fluida a 60 FPS al pasar el ratón (hover)
    """
    state = {'anim_id': None, 'current_h': float(normal_h)}

    orig_font = None
    hover_font = None
    try:
        f = widget.cget('font')
        if isinstance(f, tuple) and len(f) >= 2:
            orig_font = f
            hover_font = (f[0], f[1] + 1, 'bold' if len(f) < 3 else f[2])
    except Exception:
        pass

    def on_enter(event=None):
        if state['anim_id']:
            try:
                widget.after_cancel(state['anim_id'])
            except Exception:
                pass

        if expand_font and hover_font:
            try:
                widget.configure(font=hover_font)
            except Exception:
                pass

        total_frames = 6
        frame = 0

        def _step():
            nonlocal frame
            frame += 1
            t = frame / total_frames
            ease = ease_out_quad(t)
            h = normal_h + (hover_h - normal_h) * ease
            state['current_h'] = h
            try:
                widget.configure(height=int(h))
            except Exception:
                return

            if frame < total_frames:
                state['anim_id'] = widget.after(14, _step)
            else:
                state['anim_id'] = None

        _step()

    def on_leave(event=None):
        if state['anim_id']:
            try:
                widget.after_cancel(state['anim_id'])
            except Exception:
                pass

        if expand_font and orig_font:
            try:
                widget.configure(font=orig_font)
            except Exception:
                pass

        total_frames = 6
        frame = 0

        def _step():
            nonlocal frame
            frame += 1
            t = frame / total_frames
            ease = ease_out_quad(t)
            h = hover_h - (hover_h - normal_h) * ease
            state['current_h'] = h
            try:
                widget.configure(height=int(h))
            except Exception:
                return

            if frame < total_frames:
                state['anim_id'] = widget.after(14, _step)
            else:
                state['anim_id'] = None

        _step()

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
