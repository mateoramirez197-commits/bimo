# BIMO PRO - Motor de Micro-Animaciones Fluidas UI/UX
# Implementa Lift (Traslacin en el eje Y) y Color Fade (Interpolacin RGB),
# acelerados por hardware para evitar destellos y stuttering.

def ease_out_cubic(t: float) -> float:
    return 1.0 - pow(1.0 - t, 3)

def hex_to_rgb(hex_str):
    if not isinstance(hex_str, str): return (255, 255, 255)
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    if len(hex_str) != 6:
        return (255, 255, 255)
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb: tuple) -> str:
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def interpolate_color(c1: tuple, c2: tuple, t: float) -> str:
    r = c1[0] + (c2[0] - c1[0]) * t
    g = c1[1] + (c2[1] - c1[1]) * t
    b = c1[2] + (c2[2] - c1[2]) * t
    return rgb_to_hex((r, g, b))

def bind_hover_lift_and_fade(widget, normal_rely=0.5, hover_rely=0.3, 
                             normal_color="#FFFFFF", hover_color="#8B5CF6", 
                             duration_ms=180, is_text_color=False, is_dock_button=False):
    state = {'anim_id': None, 'curr_val': 0.0}
    
    if isinstance(normal_color, tuple) or isinstance(normal_color, list):
        normal_color = normal_color[0]
    if isinstance(hover_color, tuple) or isinstance(hover_color, list):
        hover_color = hover_color[0]
        
    if not isinstance(normal_color, str) or not normal_color.startswith('#'):
        normal_color = "#FFFFFF"
    if not isinstance(hover_color, str) or not hover_color.startswith('#'):
        hover_color = "#8B5CF6"

    rgb_normal = hex_to_rgb(normal_color)
    rgb_hover = hex_to_rgb(hover_color)

    def _anim_step(start_v, end_v, frame, total_frames):
        if state['anim_id']:
            widget.after_cancel(state['anim_id'])
            state['anim_id'] = None
            
        frame += 1
        t = frame / total_frames
        ease = ease_out_cubic(t)
        new_val = start_v + (end_v - start_v) * ease
        state['curr_val'] = new_val

        curr_color = interpolate_color(rgb_normal, rgb_hover, new_val)

        try:
            if is_text_color:
                widget.configure(text_color=curr_color)
            else:
                widget.configure(fg_color=curr_color)
            
            if is_dock_button:
                widget.place_configure(rely=normal_rely - (normal_rely - hover_rely)*new_val)
        except Exception:
            return

        if frame < total_frames:
            state['anim_id'] = widget.after(16, lambda: _anim_step(start_v, end_v, frame, total_frames))
        else:
            state['anim_id'] = None

    def on_enter(event=None):
        total_f = max(1, duration_ms // 16)
        _anim_step(state['curr_val'], 1.0, 0, total_f)

    def on_leave(event=None):
        total_f = max(1, duration_ms // 16)
        _anim_step(state['curr_val'], 0.0, 0, total_f)

    widget.bind('<Enter>', on_enter, add='+')
    widget.bind('<Leave>', on_leave, add='+')

def bind_hover_microscale(widget, scale_factor=1.15):
    try:
        norm_color = widget.cget("fg_color")
        hover_c = widget.cget("hover_color")
        if not norm_color or norm_color == "transparent":
            return
        if not hover_c or hover_c == "transparent":
            return
        bind_hover_lift_and_fade(widget, normal_color=norm_color, hover_color=hover_c, is_dock_button=False)
    except Exception:
        pass

def animar_despliegue_tarjeta(frame_tarjeta, altura_final: int = 140, duration_ms: int = 220):
    total_ticks = max(1, int(duration_ms / 16))
    tick = 0
    try: frame_tarjeta.configure(height=2)
    except: pass

    def _tick():
        nonlocal tick
        tick += 1
        t = tick / total_ticks
        ease = ease_out_cubic(t)
        curr_h = int(2 + (altura_final - 2) * ease)
        try: frame_tarjeta.configure(height=curr_h)
        except: return
        if tick < total_ticks:
            frame_tarjeta.after(16, _tick)
        else:
            try: frame_tarjeta.configure(height=altura_final)
            except: pass
    _tick()
