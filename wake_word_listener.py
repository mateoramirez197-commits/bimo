import os
import sys
import time
import queue
import tempfile
import threading
from collections import deque
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from ai_engine import get_whisper_engine


_VOLUMEN_WINDOWS_ASEGURADO = False


def asegurar_volumen_microfono_windows():
    """
    Asegura automáticamente (una sola vez en segundo plano) que el micrófono predeterminado de Windows
    no esté silenciado (Mute=0) y tenga un nivel de ganancia óptimo (>= 92%).
    """
    global _VOLUMEN_WINDOWS_ASEGURADO
    if _VOLUMEN_WINDOWS_ASEGURADO or sys.platform != "win32":
        return
    _VOLUMEN_WINDOWS_ASEGURADO = True

    def _ajustar_bg():
        try:
            import ctypes
            from ctypes import POINTER, byref, c_float, c_int, c_uint, c_void_p
            import comtypes
            from comtypes import GUID, IUnknown, COMMETHOD, HRESULT, CLSCTX_ALL

            class IAudioEndpointVolume(IUnknown):
                _iid_ = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'RegisterControlChangeNotify', (['in'], c_void_p, 'pNotify')),
                    COMMETHOD([], HRESULT, 'UnregisterControlChangeNotify', (['in'], c_void_p, 'pNotify')),
                    COMMETHOD([], HRESULT, 'GetChannelCount', (['out'], POINTER(c_uint), 'pnChannelCount')),
                    COMMETHOD([], HRESULT, 'SetMasterVolumeLevel', (['in'], c_float, 'fLevelDB'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'SetMasterVolumeLevelScalar', (['in'], c_float, 'fLevel'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetMasterVolumeLevel', (['out'], POINTER(c_float), 'pfLevelDB')),
                    COMMETHOD([], HRESULT, 'GetMasterVolumeLevelScalar', (['out'], POINTER(c_float), 'pfLevel')),
                    COMMETHOD([], HRESULT, 'SetChannelVolumeLevel', (['in'], c_uint, 'nChannel'), (['in'], c_float, 'fLevelDB'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'SetChannelVolumeLevelScalar', (['in'], c_uint, 'nChannel'), (['in'], c_float, 'fLevel'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetChannelVolumeLevel', (['in'], c_uint, 'nChannel'), (['out'], POINTER(c_float), 'pfLevelDB')),
                    COMMETHOD([], HRESULT, 'GetChannelVolumeLevelScalar', (['in'], c_uint, 'nChannel'), (['out'], POINTER(c_float), 'pfLevel')),
                    COMMETHOD([], HRESULT, 'SetMute', (['in'], c_int, 'bMute'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetMute', (['out'], POINTER(c_int), 'pbMute')),
                ]

            class IMMDevice(IUnknown):
                _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'Activate', (['in'], POINTER(GUID), 'iid'), (['in'], c_uint, 'dwClsCtx'), (['in'], c_void_p, 'pActivationParams'), (['out'], POINTER(POINTER(IUnknown)), 'ppInterface')),
                ]

            class IMMDeviceEnumerator(IUnknown):
                _iid_ = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'EnumAudioEndpoints', (['in'], c_uint, 'dataFlow'), (['in'], c_uint, 'dwStateMask'), (['out'], POINTER(c_void_p), 'ppDevices')),
                    COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint', (['in'], c_uint, 'dataFlow'), (['in'], c_uint, 'role'), (['out'], POINTER(POINTER(IMMDevice)), 'ppEndpoint')),
                ]

            comtypes.CoInitialize()
            try:
                clsid_enum = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
                enumerator = comtypes.CoCreateInstance(clsid_enum, interface=IMMDeviceEnumerator, clsctx=CLSCTX_ALL)
                for role in (0, 1, 2):
                    dev = unk = ep = None
                    try:
                        dev = enumerator.GetDefaultAudioEndpoint(1, role)
                        unk = dev.Activate(byref(IAudioEndpointVolume._iid_), CLSCTX_ALL, None)
                        # QueryInterface hace AddRef; ctypes.cast no, y provocaba doble Release (crash)
                        ep = unk.QueryInterface(IAudioEndpointVolume)
                        if ep.GetMute():
                            ep.SetMute(0, None)
                        if ep.GetMasterVolumeLevelScalar() < 0.90:
                            ep.SetMasterVolumeLevelScalar(0.95, None)
                    except Exception:
                        pass
                    finally:
                        del dev, unk, ep
                del enumerator
            finally:
                # Los objetos COM deben liberarse en ESTE hilo antes de cerrar su apartamento:
                # si el recolector los libera después desde otro hilo (p. ej. el servidor móvil)
                # Windows lanza un access violation y BIMO se cierra sin aviso.
                import gc
                gc.collect()
                comtypes.CoUninitialize()
        except Exception:
            pass

    threading.Thread(target=_ajustar_bg, daemon=True).start()


# ==========================================
# SELECCIÓN INTELIGENTE DE MICRÓFONO (AUTOMÁTICO / ELEGIDO EN CONFIGURACIÓN)
# ==========================================
# Micrófonos virtuales (apps de cámara del celular, mezcladores, cables virtuales): suelen entregar
# silencio absoluto si la app no está conectada, por eso en modo Automático se dejan como último recurso.
_MIC_VIRTUALES_KW = (
    'camo', 'iriun', 'droidcam', 'epoccam', 'ivcam', 'stereo mix', 'mezcla est', 'what u hear',
    'loopback', 'cable output', 'vb-audio', 'voicemeeter', 'virtual', 'obs-', 'obs ', 'ndi ',
    'steam streaming', 'pc speaker', 'zoom audio', 'teams audio', 'wave link', 'sonar'
)
# Micrófonos externos dedicados (diadema, USB, solapa): se prefieren sobre el micrófono interno del laptop
_MIC_EXTERNOS_KW = (
    'usb', 'headset', 'auricular', 'diadema', 'audífono', 'audifono', 'headphone', 'yeti', 'rode',
    'fifine', 'maono', 'me6s', 'lavalier', 'solapa', 'jabra', 'hyperx', 'razer', 'logitech', 'shure',
    'samson', 'boya', 'airpods', 'buds', 'hands-free', 'manos libres', 'external', 'externo'
)
_MIC_MUERTOS = {}            # nombre_base -> timestamp hasta el que se evita (entregó silencio absoluto)
_CACHE_AUTO_MIC = {"ts": 0.0, "base": None}
_ULTIMO_MIC_ELEGIDO = {"nombre": "", "modo": "auto"}


def _nombre_base_mic(nombre) -> str:
    """Nombre normalizado y recortado (MME de Windows corta los nombres a 31 caracteres)."""
    import re as _re
    return _re.sub(r'\s+', ' ', str(nombre or '').lower()).strip()[:28]


def _mismo_mic(nombre_a, nombre_b) -> bool:
    a, b = _nombre_base_mic(nombre_a), _nombre_base_mic(nombre_b)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def es_microfono_virtual(nombre) -> bool:
    n = str(nombre or '').lower()
    return any(k in n for k in _MIC_VIRTUALES_KW)


def _puntaje_microfono(nombre, es_predeterminado=False) -> int:
    n = str(nombre or '').lower()
    puntaje = 0
    if any(k in n for k in _MIC_EXTERNOS_KW):
        puntaje += 20
    if es_predeterminado:
        puntaje += 5
    if es_microfono_virtual(n):
        puntaje -= 100
    return puntaje


def obtener_microfono_preferido() -> str:
    """Nombre del micrófono elegido en Configuración ('' = Automático)."""
    try:
        from config import cargar_datos_clinica
        val = str((cargar_datos_clinica() or {}).get("microfono_preferido") or "").strip()
        return "" if val.lower() in ("auto", "automatico", "automático") else val
    except Exception:
        return ""


def marcar_microfono_muerto(nombre, segundos=120.0):
    if nombre:
        _MIC_MUERTOS[_nombre_base_mic(nombre)] = time.time() + segundos
        _CACHE_AUTO_MIC["ts"] = 0.0
        print(f"[VOICE LISTENER] Micrófono '{nombre}' sin señal (silencio absoluto). Se usará otro disponible.")


def _mic_esta_muerto(nombre) -> bool:
    base = _nombre_base_mic(nombre)
    hasta = _MIC_MUERTOS.get(base, 0.0)
    if hasta and time.time() < hasta:
        return True
    if hasta:
        _MIC_MUERTOS.pop(base, None)
    return False


def invalidar_cache_microfono():
    _CACHE_AUTO_MIC["ts"] = 0.0
    _CACHE_AUTO_MIC["base"] = None


def listar_microfonos_disponibles() -> list:
    """
    Lista los micrófonos físicos/virtuales disponibles (uno por dispositivo real, sin duplicados por API).
    Retorna [{id, nombre, samplerate, virtual, predeterminado}].
    """
    resultado = []
    try:
        todos = sd.query_devices()
        try:
            apis = sd.query_hostapis()
        except Exception:
            apis = []

        def _prioridad_api(idx_api):
            try:
                nom_api = str(apis[idx_api].get('name', '')).lower()
            except Exception:
                nom_api = ''
            if 'mme' in nom_api:
                return 0
            if 'directsound' in nom_api:
                return 1
            if 'wasapi' in nom_api:
                return 2
            if 'wdm' in nom_api or 'ks' in nom_api:
                return 9
            return 3

        idx_def = None
        try:
            info_def = sd.query_devices(kind='input')
            idx_def = info_def.get('index', None) if info_def else None
            nombre_def = info_def.get('name', '') if info_def else ''
        except Exception:
            nombre_def = ''

        elegidos = {}
        for idx, d in enumerate(todos):
            if int(d.get('max_input_channels', 0)) <= 0:
                continue
            nom = str(d.get('name', f'Device {idx}'))
            nom_l = nom.lower()
            if any(k in nom_l for k in ('asignador de sonido', 'sound mapper', 'controlador primario', 'primary sound capture')):
                continue
            prio = _prioridad_api(int(d.get('hostapi', 0)))
            if prio >= 9:
                continue
            clave = None
            for k_exist in elegidos:
                if _mismo_mic(k_exist, nom):
                    clave = k_exist
                    break
            if clave is None:
                elegidos[nom] = (prio, idx, nom, int(d.get('default_samplerate', 44100)))
            else:
                prev = elegidos[clave]
                # Conservar el nombre más largo (WASAPI/DirectSound no truncan) y la API más compatible (MME)
                nom_largo = nom if len(nom) > len(prev[2]) else prev[2]
                if prio < prev[0]:
                    elegidos[clave] = (prio, idx, nom_largo, int(d.get('default_samplerate', 44100)))
                else:
                    elegidos[clave] = (prev[0], prev[1], nom_largo, prev[3])

        for _, (prio, idx, nom, sr) in elegidos.items():
            es_def = (idx == idx_def) or (bool(nombre_def) and _mismo_mic(nom, nombre_def))
            resultado.append({
                "id": idx,
                "nombre": nom,
                "samplerate": sr,
                "virtual": es_microfono_virtual(nom),
                "predeterminado": bool(es_def)
            })
        resultado.sort(key=lambda m: (-_puntaje_microfono(m["nombre"], m["predeterminado"]), m["nombre"].lower()))
    except Exception as e:
        print(f"[VOICE LISTENER] No se pudo listar micrófonos: {e}")
    return resultado


VARIANTES_BIMO = (
    'bimo', 'vimo', 'bymo', 'vymo', 'dimo', 'mimo',
    'beemo', 'bmo', 'bimbo', 'bimos', 'vimos',
    'bemo', 'vemo', 'pimo', 'bimu', 'vimu', 'bimoo', 'vimoo', 'beamo', 'bimoh', 'vimoh'
)

# Variantes fuertes para división de órdenes repetidas (NO verbos comunes como 'vimos' ni palabras como 'dimo'/'mimo')
VARIANTES_FUERTES_DIVIDIR = (
    'bimo', 'vimo', 'bímo', 'vímo', 'bymo', 'vymo',
    'bemo', 'vemo', 'beemo', 'bimoo', 'vimoo'
)

def _obtener_patron_variantes_bimo():
    import re
    variantes_todas = set(VARIANTES_BIMO)
    for v in list(VARIANTES_BIMO):
        variantes_todas.add(v.replace('i', 'í').replace('e', 'é'))
    return re.compile(r'\b(?:' + '|'.join(sorted(variantes_todas, key=len, reverse=True)) + r')\b', re.IGNORECASE)

_PATRON_VARIANTES_BIMO = _obtener_patron_variantes_bimo()

def _obtener_patron_variantes_fuertes():
    import re
    variantes_todas = set(VARIANTES_FUERTES_DIVIDIR)
    for v in list(VARIANTES_FUERTES_DIVIDIR):
        variantes_todas.add(v.replace('i', 'í').replace('e', 'é'))
    return re.compile(r'\b(?:' + '|'.join(sorted(variantes_todas, key=len, reverse=True)) + r')\b', re.IGNORECASE)

_PATRON_VARIANTES_FUERTES = _obtener_patron_variantes_fuertes()

def limpiar_alucinaciones_whisper(texto: str) -> str:
    """Quita al final palabras sueltas de alucinación comunes de Whisper (Música, Gracias, Subtítulos, etc.)."""
    if not texto:
        return ""
    import re
    t = texto.strip()
    patron = re.compile(
        r'(\s*[\(\[\{]?(?:m[uú]sica|music|subt[ií]tulos|subtitles|gracias|muchas gracias|aplausos|risas)[\)\]\}]?[\.\?!]*\s*)+$',
        re.IGNORECASE
    )
    t = patron.sub('', t).strip()
    t = re.sub(r'(\s*subt[ií]tulos(?:\s+por|\s+realizados|\s*\.\.\.).*)$', '', t, flags=re.IGNORECASE).strip()
    return t

def extraer_ultima_orden(texto: str) -> str:
    """
    Divide el texto por las apariciones de variantes fuertes de la palabra de activación
    (bimo, vimo, bímo, vímo...) SOLO si hay 2 o más apariciones Y el texto tiene menos
    de 30 palabras. En cualquier otro caso devuelve el texto completo, pasado solo
    por limpiar_alucinaciones_whisper().
    """
    if not texto:
        return ""
    import re
    t = limpiar_alucinaciones_whisper(texto).strip()
    if not t:
        return ""

    palabras = t.split()
    coincidencias = _PATRON_VARIANTES_FUERTES.findall(t)

    if len(coincidencias) >= 2 and len(palabras) < 30:
        partes = _PATRON_VARIANTES_FUERTES.split(t)
        if len(partes) > 1:
            for parte in reversed(partes[1:]):
                orden = parte.strip(' \t\r\n,;:.?!¿¡')
                w_orden = [w for w in re.split(r'\W+', orden) if w]
                if w_orden:
                    return orden
            orden_pre = partes[0].strip(' \t\r\n,;:.?!¿¡')
            w_pre = [w for w in re.split(r'\W+', orden_pre) if w and w.lower() not in ('hola', 'ola', 'oye', 'hey')]
            if w_pre:
                return orden_pre

    return t

def limpiar_variantes_bimo(texto: str) -> str:
    """Elimina todas las variantes de 'Bimo' y saludos iniciales comunes."""
    if not texto:
        return ""
    import re
    t = _PATRON_VARIANTES_BIMO.sub('', texto)
    t = re.sub(r'\bhola\b', '', t, flags=re.IGNORECASE)
    return t.strip(" ,.?!¿¡")


def _sondear_senal_microfono(dev_id, samplerate, segundos=0.4) -> bool:
    """Graba un instante y confirma que el micrófono entrega audio real (no silencio digital absoluto)."""
    try:
        sr = int(samplerate or 44100)
        n = int(sr * segundos)
        with sd.InputStream(device=dev_id, samplerate=sr, channels=1, dtype='int16') as s:
            datos, _ = s.read(n)
        if datos is None or len(datos) == 0:
            return False
        recorte = datos[int(len(datos) * 0.25):]  # descartar transitorio de apertura
        return bool(np.max(np.abs(recorte.astype(np.int32))) > 0)
    except Exception:
        return False


def _microfonos_prioritarios() -> list:
    """
    Devuelve [(dev_id, nombre, samplerate)] en el orden en que deben probarse:
    1) el micrófono elegido en Configuración (si está conectado y con señal),
    2) en Automático: externos/diadema/USB con señal > predeterminado > interno del laptop,
       dejando los virtuales (Camo, Mezcla estéreo...) y los sin señal como último recurso.
    """
    lista = listar_microfonos_disponibles()
    if not lista:
        return []
    preferido = obtener_microfono_preferido()
    ordenados = []

    if preferido:
        for m in lista:
            if _mismo_mic(m["nombre"], preferido) and not _mic_esta_muerto(m["nombre"]):
                ordenados.append(m)
                _ULTIMO_MIC_ELEGIDO.update({"nombre": m["nombre"], "modo": "manual"})
                break

    vivos = [m for m in lista if not _mic_esta_muerto(m["nombre"]) and m not in ordenados]
    reales = [m for m in vivos if not m["virtual"]]
    virtuales = [m for m in vivos if m["virtual"]]
    muertos = [m for m in lista if _mic_esta_muerto(m["nombre"]) and m not in ordenados]

    if not ordenados:
        # Modo automático: usar la elección reciente si sigue vigente; si no, sondear en orden de puntaje
        elegido = None
        cache_base = _CACHE_AUTO_MIC.get("base")
        if cache_base and (time.time() - _CACHE_AUTO_MIC.get("ts", 0.0)) < 45.0:
            for m in reales + virtuales:
                if _nombre_base_mic(m["nombre"]) == cache_base:
                    elegido = m
                    break
        if elegido is None:
            for m in (reales + virtuales)[:5]:
                if _sondear_senal_microfono(m["id"], m["samplerate"]):
                    elegido = m
                    break
                else:
                    marcar_microfono_muerto(m["nombre"], segundos=60.0)
            if elegido is not None:
                _CACHE_AUTO_MIC.update({"ts": time.time(), "base": _nombre_base_mic(elegido["nombre"])})
        if elegido is not None:
            ordenados.append(elegido)
            _ULTIMO_MIC_ELEGIDO.update({"nombre": elegido["nombre"], "modo": "auto"})

    for m in reales + virtuales + muertos:
        if m not in ordenados:
            ordenados.append(m)
    return [(m["id"], m["nombre"], m["samplerate"]) for m in ordenados]


def obtener_estado_microfono() -> dict:
    return dict(_ULTIMO_MIC_ELEGIDO)



def obtener_candidatos_microfono_predeterminado(samplerate_preferido=16000, refrescar=False):
    """
    Detecta automáticamente el micrófono predeterminado del sistema operativo (Windows)
    y genera una lista priorizada de combinaciones (device, samplerate, nombre_descriptivo)
    para garantizar que siempre se use el micrófono predeterminado activo sin intervención manual.
    """
    if refrescar:
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass

    asegurar_volumen_microfono_windows()

    candidatos_dispositivos = []
    vistos_dev = set()

    def _agregar_dev(dev_id, nombre, sr_nativo):
        if dev_id not in vistos_dev:
            vistos_dev.add(dev_id)
            candidatos_dispositivos.append((dev_id, nombre, int(sr_nativo or 44100)))

    # 0. Micrófono elegido en Configuración o el mejor micrófono con señal real (modo Automático).
    #    Si falla, se conserva debajo toda la cadena de respaldo original.
    try:
        for dev_p, nom_p, sr_p in _microfonos_prioritarios()[:1]:
            _agregar_dev(dev_p, nom_p, sr_p)
    except Exception as e_pri:
        print(f"[VOICE LISTENER] Aviso al priorizar micrófono: {e_pri}")

    # 1. Dispositivo de entrada predeterminado explícito reportado por el SO
    nombre_default = "Micrófono Predeterminado del Sistema"
    sr_default = 44100
    try:
        info_def = sd.query_devices(kind='input')
        if info_def and int(info_def.get('max_input_channels', 0)) > 0:
            idx_def = info_def.get('index', None)
            nombre_default = info_def.get('name', nombre_default)
            sr_default = int(info_def.get('default_samplerate', 44100))
            if idx_def is not None:
                _agregar_dev(int(idx_def), nombre_default, sr_default)
    except Exception:
        pass

    # 2. Dispositivo None (delega al enrutador predeterminado de PortAudio/Windows)
    _agregar_dev(None, nombre_default, sr_default)

    # 3. Sound Mapper / Controlador primario de captura de Windows (sigue dinámicamente al predeterminado)
    # y demás micrófonos físicos reales conectados como respaldo
    try:
        todos = sd.query_devices()
        # Primero los mapeadores dinámicos del sistema operativo
        for idx, d in enumerate(todos):
            if int(d.get('max_input_channels', 0)) <= 0:
                continue
            nom_l = str(d.get('name', '')).lower()
            if any(k in nom_l for k in ('asignador de sonido', 'sound mapper', 'controlador primario', 'primary sound capture')):
                _agregar_dev(idx, d.get('name', f'Device {idx}'), int(d.get('default_samplerate', 44100)))

        # Luego coincidencias exactas con el nombre del micrófono predeterminado en otras APIs (MME/DirectSound/WASAPI)
        nom_def_base = nombre_default.lower().split('(')[-1].replace(')', '').strip() if '(' in nombre_default else nombre_default.lower()
        for idx, d in enumerate(todos):
            if int(d.get('max_input_channels', 0)) <= 0:
                continue
            if int(d.get('hostapi', 0)) == 3:  # Evitar WDM-KS si MME/DirectSound/WASAPI están disponibles
                continue
            nom_d = str(d.get('name', ''))
            if nom_def_base and nom_def_base in nom_d.lower():
                _agregar_dev(idx, nom_d, int(d.get('default_samplerate', 44100)))

        # Finalmente cualquier micrófono físico real (excluyendo mezcla estéreo o altavoces loopback)
        for idx, d in enumerate(todos):
            if int(d.get('max_input_channels', 0)) <= 0:
                continue
            if int(d.get('hostapi', 0)) == 3:
                continue
            nom_d = str(d.get('name', ''))
            nom_l = nom_d.lower()
            if any(bad in nom_l for bad in ('stereo mix', 'mezcla estéreo', 'pc speaker', 'what u hear', 'loopback')):
                continue
            _agregar_dev(idx, nom_d, int(d.get('default_samplerate', 44100)))
    except Exception:
        pass

    # Construir combinaciones (device, samplerate, nombre)
    combinaciones = []
    for dev_id, nom_dev, sr_nat in candidatos_dispositivos:
        tasas = []
        for s in (sr_nat, samplerate_preferido, 44100, 48000, 16000):
            if s and int(s) not in tasas:
                tasas.append(int(s))
        for sr in tasas:
            combinaciones.append((dev_id, sr, nom_dev))

    return combinaciones


# Duración máxima de un segmento mientras se espera "Bimo" (fuera de ventana activa y dictado).
SEGMENTO_MAX_REPOSO_SEG = 8.0
# Si un segmento cortado trae "Bimo" + orden, se espera la continuación hasta este tiempo antes de ejecutarla sola.
ESPERA_ORDEN_PENDIENTE_SEG = 4.0


class SegmentoPorTope(np.ndarray):
    """Audio cortado por duración máxima (no por silencio): la frase pudo quedar a medias."""
    pass


class SegmentoOrden(np.ndarray):
    """Audio que empezó dentro de la ventana activa (tras "Bimo"): es la orden, aunque la ventana
    haya vencido mientras se grababa (con TV de fondo el segmento se alarga y antes se descartaba)."""
    pass


# Duración máxima de la orden tras "Bimo" (con ruido de fondo el silencio puede no llegar nunca)
SEGMENTO_MAX_ORDEN_SEG = 15.0


def aislar_voz_cercana(audio, samplerate, ventana_seg=0.03, relleno_seg=0.18):
    """
    Conserva los tramos fuertes (la voz cercana al micrófono) y descarta los débiles (TV, gente lejos).
    El doctor habla mucho más cerca del micrófono que la fuente de ruido, así que su voz tiene más energía.
    Si casi nada supera el umbral (todo es igual de fuerte), devuelve el audio original.
    """
    a = np.asarray(audio)
    n = max(1, int(samplerate * ventana_seg))
    bloques = len(a) // n
    if bloques < 10:
        return a
    x = a[:bloques * n].astype(np.float32).reshape(bloques, n)
    energia = np.sqrt((x ** 2).mean(axis=1))
    fondo = float(np.percentile(energia, 30))
    pico = float(np.percentile(energia, 95))
    if pico <= 0 or pico < fondo * 2.2:
        return a  # sin contraste claro entre voz y fondo: no tocar
    umbral = max(fondo * 1.9, pico * 0.22)
    fuerte = energia >= umbral
    pad = max(1, int(relleno_seg / ventana_seg))
    conservar = np.convolve(fuerte.astype(np.int32), np.ones(2 * pad + 1, dtype=np.int32), mode="same") > 0
    if conservar.sum() * n < samplerate * 0.35 or conservar.mean() > 0.92:
        return a
    return np.concatenate([a[i * n:(i + 1) * n] for i in np.flatnonzero(conservar)])


class BackgroundWakeListener:
    """
    Escucha activa continua ultra-reactiva conectada automáticamente al micrófono predeterminado:
    1. 100% en memoria RAM sin escritura a disco (cero latencia de I/O).
    2. Detección automática del micrófono predeterminado de Windows y su frecuencia nativa.
    3. Canal compartido sin colisiones (Tap directo) para dictado manual con botón (0ms de latencia).
    4. VAD adaptativo ultra-sensible compatible con micrófonos USB de baja ganancia (ej. ME6S).
    5. Perro guardián (Watchdog) auto-recuperable ante desconexión o cambio de micrófono.
    """
    def __init__(self, callback_comando, samplerate=16000):
        self.callback_comando = callback_comando
        self.samplerate = samplerate
        self.device_actual = None
        self.nombre_microfono = "Micrófono Predeterminado"
        self.activo = False
        self.pausado = False
        self.en_proceso = False
        self.tiempo_inicio_proceso = 0.0
        self.tiempo_ventana_activa = 0.0  # Ventana multi-turn para recibir órdenes tras decir 'Bimo'
        self.stream = None
        self.acumulador_voz = []
        self.hablando = False
        self.silencio_frames = 0
        self.pre_roll = deque(maxlen=10)  # ~600ms de pre-grabación para no cortar el inicio de "Bimo"
        self.ambient_floor = 8.0          # Piso de ruido inicial sensible para micrófonos USB y de estudio
        self._peak_voz = 0.0
        self._calibracion_frames = 0
        self._historial_volumen = deque(maxlen=60)  # Historial reciente (~4 s) para piso de ruido dinámico
        self._ultimo_error_callback = 0.0
        self._ultimo_warn_overflow = 0.0
        self._startup_skip_frames = 2     # Descartar primeros bloques tras iniciar stream
        self._lock = threading.Lock()
        self._hilo_watchdog = None
        self._cola_audio = queue.Queue(maxsize=3)
        self._hilo_worker = None
        self._duracion_actual_analisis = 4.0
        self._callback_tap_manual = None  # Tap en vivo para grabación por botón sin cerrar el hardware
        self._muestras_silencio_digital = 0  # Muestras seguidas en cero absoluto (micrófono virtual/desconectado)
        self._tuvo_senal = False             # True si el micrófono entregó audio real desde que se abrió
        self._nivel_actual = 0.0             # Nivel 0-100 para el medidor de Configuración
        self._num_dispositivos_win = None    # Para detectar micrófonos conectados/desconectados en caliente
        self._ultimo_chequeo_hotplug = 0.0
        self._orden_pendiente = ""           # Inicio de orden tras "Bimo" en un segmento cortado por tope
        self._orden_pendiente_desde = 0.0
        try:
            from audio_feedback import _asegurar_wav
            _asegurar_wav("bimo_ding.wav")
        except Exception:
            pass

    def iniciar_tap_manual(self, callback_frame):
        """
        Conecta la grabación manual por botón directamente al flujo del micrófono predeterminado
        sin cerrar ni reabrir el dispositivo de hardware (evita PaErrorCode y pérdidas de audio).
        """
        with self._lock:
            self._callback_tap_manual = callback_frame
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            if not self.activo:
                self.activo = True
            self.pausado = False
            if self.stream is None or not getattr(self.stream, "active", False):
                self._iniciar_stream(refrescar=False)
            return self.stream is not None and getattr(self.stream, "active", False), self.samplerate

    def detener_tap_manual(self):
        """Desconecta el tap de grabación manual y limpia los acumuladores de voz activa."""
        with self._lock:
            self._callback_tap_manual = None
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            self._startup_skip_frames = 1

    def activar_ventana_activa(self, segundos=10.0):
        """Abre una ventana activa de escucha para recibir órdenes directas sin exigir repetir 'Bimo'."""
        with self._lock:
            self.tiempo_ventana_activa = time.time() + segundos
            print(f"[VOICE LISTENER] Ventana de orden activa por {segundos}s...")

    def esta_en_ventana_activa(self) -> bool:
        return time.time() < self.tiempo_ventana_activa

    def _tomar_orden_pendiente(self) -> str:
        with self._lock:
            pendiente, self._orden_pendiente = self._orden_pendiente, ""
            return pendiente

    def _despachar_orden_pendiente_vencida(self):
        """Si la continuación de una orden cortada no llegó a tiempo, ejecutar lo que ya se tenía."""
        if not self._orden_pendiente:
            return
        esperando_mas = self.hablando or self.en_proceso or not self._cola_audio.empty()
        if esperando_mas or (time.time() - self._orden_pendiente_desde) < ESPERA_ORDEN_PENDIENTE_SEG:
            return
        pendiente = self._tomar_orden_pendiente()
        if pendiente:
            self.tiempo_ventana_activa = 0.0
            print(f"[VOICE LISTENER] Ejecutando orden sin continuación: \"{pendiente}\"")
            if self.callback_comando:
                self.callback_comando(pendiente)

    def iniciar(self):
        with self._lock:
            self.activo = True
            self.pausado = False
            if self.stream is None or not getattr(self.stream, "active", False):
                self._iniciar_stream(refrescar=False)
            if not self._hilo_worker or not self._hilo_worker.is_alive():
                self._hilo_worker = threading.Thread(target=self._worker_loop, daemon=True)
                self._hilo_worker.start()
            if not self._hilo_watchdog or not self._hilo_watchdog.is_alive():
                self._hilo_watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
                self._hilo_watchdog.start()
            # Pre-calentar motor Whisper local en segundo plano sin bloquear el arranque
            threading.Thread(target=self._precalentar_whisper, daemon=True).start()

    def _precalentar_whisper(self):
        try:
            get_whisper_engine()
        except Exception:
            pass

    def _iniciar_stream(self, refrescar=False):
        try:
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

            # Limpiar buffers de audio para evitar disparos con residuos
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            self.ambient_floor = 8.0
            self._calibracion_frames = 0
            if hasattr(self, '_historial_volumen'):
                self._historial_volumen.clear()
            self._startup_skip_frames = 2
            self._muestras_silencio_digital = 0
            self._tuvo_senal = False

            for intento_refresco in ([refrescar, True] if not refrescar else [True]):
                candidatos = obtener_candidatos_microfono_predeterminado(
                    samplerate_preferido=self.samplerate,
                    refrescar=intento_refresco
                )
                ultimo_error = None
                for dev_id, sr, nom_dev in candidatos:
                    try:
                        blocksize = max(1024, int(sr * 0.064))
                        kwargs_stream = dict(
                            samplerate=sr,
                            channels=1,
                            dtype='int16',
                            blocksize=blocksize,
                            # Búfer amplio: evita "input overflow" (audio perdido) cuando Whisper ocupa la CPU
                            latency='high',
                            callback=self._audio_callback,
                            finished_callback=self._on_stream_finished
                        )
                        if dev_id is not None:
                            kwargs_stream["device"] = dev_id
                        self.stream = sd.InputStream(**kwargs_stream)
                        self.stream.start()
                        self.samplerate = sr
                        self.device_actual = dev_id
                        self.nombre_microfono = nom_dev
                        print(f"[VOICE LISTENER] Micrófono activo: '{nom_dev}' (device={dev_id}, {self.samplerate}Hz, modo {obtener_estado_microfono().get('modo', 'auto')}).")
                        return
                    except Exception as e_sr:
                        ultimo_error = e_sr
                        self.stream = None
                if ultimo_error and intento_refresco:
                    print(f"[VOICE LISTENER] Error al inicializar InputStream de audio: {ultimo_error}")
        except Exception as e:
            print(f"[VOICE LISTENER] Error al inicializar InputStream de audio: {e}")

    def _on_stream_finished(self):
        print(f"[VOICE LISTENER] Stream finalizado por PortAudio: '{getattr(self, 'nombre_microfono', 'Desconocido')}'")

    def detener(self):
        with self._lock:
            self._orden_pendiente = ""
            self.activo = False
            self.pausado = True
            self._callback_tap_manual = None
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            self.en_proceso = False
            self.tiempo_ventana_activa = 0.0
            while not self._cola_audio.empty():
                try:
                    self._cola_audio.get_nowait()
                except Exception:
                    break
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

    def pausar(self):
        """Pausa temporalmente el procesamiento de voz activa manteniendo el stream listo."""
        with self._lock:
            self._orden_pendiente = ""
            self.pausado = True
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            self.en_proceso = False
            self.tiempo_ventana_activa = 0.0
            while not self._cola_audio.empty():
                try:
                    self._cola_audio.get_nowait()
                except Exception:
                    break

    def reanudar(self):
        """Reanuda la escucha activa con buffers limpios y supresión de transitorio inicial."""
        with self._lock:
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            self.en_proceso = False
            self._startup_skip_frames = 2
            self.pausado = False

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            if status and getattr(status, 'input_overflow', False):
                ahora_st = time.time()
                if ahora_st - getattr(self, '_ultimo_warn_overflow', 0.0) >= 30.0:
                    self._ultimo_warn_overflow = ahora_st
                    print(f"[VOICE LISTENER WARN] Desbordamiento de entrada (input_overflow): {status}")

            # 0. Salud del micrófono: detectar silencio digital absoluto y medir nivel para Configuración
            try:
                pico_crudo = int(np.max(np.abs(indata.astype(np.int32)))) if len(indata) else 0
                if pico_crudo == 0:
                    self._muestras_silencio_digital += int(frames)
                else:
                    self._muestras_silencio_digital = 0
                    self._tuvo_senal = True
                self._nivel_actual = min(100.0, (pico_crudo / 32767.0) * 100.0 * 3.0)
            except Exception:
                pass

            # 1. Si el usuario está grabando manualmente con el botón, alimentar directamente el tap manual
            tap = self._callback_tap_manual
            if tap is not None:
                try:
                    tap(indata.copy())
                except Exception:
                    pass
                return

            if not self.activo or self.pausado:
                return

            # Supresión de transitorio inicial al abrir el hardware de audio
            if self._startup_skip_frames > 0:
                self._startup_skip_frames -= 1
                return

            # FILTRO ANTI-RETROALIMENTACIÓN ACÚSTICA: Si Bimo está hablando por el altavoz, descartar audio entrante
            from voice_assistant import bimo_esta_hablando
            if bimo_esta_hablando():
                self.pre_roll.clear()
                self.acumulador_voz.clear()
                self.hablando = False
                self.silencio_frames = 0
                self._peak_voz = 0.0
                return

            datos = indata.flatten()
            # Restar componente continua (DC offset) para neutralizar ruidos de baja frecuencia/zumbidos
            datos_centrados = datos.astype(np.float32) - float(np.mean(datos))
            vol = float(np.abs(datos_centrados).mean())
            peak_frame = float(np.max(np.abs(datos_centrados))) if datos_centrados.size else 0.0
            self.pre_roll.append(datos.copy())
            if hasattr(self, '_historial_volumen'):
                self._historial_volumen.append(vol)

            if not self.hablando:
                self._calibracion_frames += 1
                # Calibración adaptativa en reposo para int16
                if self._calibracion_frames <= 10:
                    self.ambient_floor = max(3.0, min(800.0, 0.65 * self.ambient_floor + 0.35 * vol))
                elif vol < self.ambient_floor * 1.45:
                    self.ambient_floor = max(3.0, min(800.0, 0.92 * self.ambient_floor + 0.08 * vol))
                else:
                    self.ambient_floor = max(3.0, min(800.0, 0.985 * self.ambient_floor + 0.015 * vol))

                # Umbral firme por encima del ruido de fondo para no disparar con ruidos leves ni respiraciones
                mult_inicio = 1.65 if self.esta_en_ventana_activa() else 1.85
                umbral_inicio = max(14.0, min(1600.0, self.ambient_floor * mult_inicio + 8.0))

                if vol > umbral_inicio:
                    self._inicio_en_ventana = self.esta_en_ventana_activa() and self._callback_tap_manual is None
                    self.hablando = True
                    self.silencio_frames = 0
                    self._frames_voz_reales = 1
                    self._peak_voz = vol
                    self.acumulador_voz = list(self.pre_roll)
                    self.acumulador_voz.append(datos.copy())
            else:
                self.acumulador_voz.append(datos.copy())
                if vol > self._peak_voz:
                    self._peak_voz = vol
                if vol < self.ambient_floor:
                    self.ambient_floor = max(3.0, 0.97 * self.ambient_floor + 0.03 * vol)

                umbral_voz_activa = max(12.0, self.ambient_floor * 1.55 + 6.0)
                if vol > umbral_voz_activa:
                    self._frames_voz_reales = getattr(self, "_frames_voz_reales", 1) + 1

                # Umbral de silencio adaptativo basado en el piso de ruido y la caída respecto al pico de voz
                umbral_base = self.ambient_floor * 1.30 + 3.5
                umbral_relativo = min(self.ambient_floor * 2.1, self._peak_voz * 0.28)
                umbral_silencio = max(6.0, min(1000.0, max(umbral_base, umbral_relativo)))
                if hasattr(self, '_historial_volumen') and self._historial_volumen:
                    ruido_reciente = float(np.percentile(list(self._historial_volumen), 20))
                    umbral_silencio = max(umbral_silencio, float(ruido_reciente * 1.25 + 3.0))
                    if getattr(self, '_peak_voz', 0.0) > 0:
                        umbral_silencio = min(umbral_silencio, max(umbral_base * 2.0, self._peak_voz * 0.35))

                total_samples = sum(len(b) for b in self.acumulador_voz)
                duracion_actual_seg = total_samples / self.samplerate
                frames_voz_efectiva = max(1, len(self.acumulador_voz) - len(self.pre_roll) - self.silencio_frames)
                duracion_voz_seg = (frames_voz_efectiva * (len(datos) or 1024)) / self.samplerate

                if vol < umbral_silencio:
                    self.silencio_frames += 1

                    # Pausa inteligente en escucha activa para permitir que el doctor piense antes de enviar la orden:
                    # - En reposo diciendo solo "Bimo" (<= 1.6s de voz): 12 frames (~0.77s) para despertar rápido.
                    # - En ventana activa o dictando una orden tras "Bimo" (<= 4.5s de voz): 34 frames (~2.2s) de espera inteligente.
                    # - En dictado clínico extenso por voz activa (> 4.5s de voz): 38 frames (~2.4s) para pausas mientras piensa.
                    if not self.esta_en_ventana_activa() and duracion_voz_seg <= 1.6:
                        max_silencio = 12
                    elif duracion_voz_seg <= 4.5:
                        max_silencio = 34
                    else:
                        max_silencio = 38

                    if self.silencio_frames >= max_silencio:
                        frames_reales = getattr(self, "_frames_voz_reales", 1)
                        umbral_snr_pico = max(16.0, self.ambient_floor * 1.85 + 9.0)
                        if total_samples >= int(self.samplerate * 0.28) and frames_reales >= 3 and self._peak_voz >= umbral_snr_pico:
                            buf = list(self.acumulador_voz)
                            if buf:
                                audio_np = np.concatenate(buf)
                                if getattr(self, "_inicio_en_ventana", False):
                                    audio_np = audio_np.view(SegmentoOrden)
                                dur_seg = len(audio_np) / self.samplerate
                                print(f"[VAD] segmento {dur_seg:.1f}s piso={self.ambient_floor:.1f} umbral={umbral_silencio:.1f}")
                                self._despachar_analisis(audio_np)
                        self.acumulador_voz = []
                        self.hablando = False
                        self.silencio_frames = 0
                        self._frames_voz_reales = 0
                        self._peak_voz = 0.0
                else:
                    # Solo reiniciar completamente el contador de silencio si es voz clara por encima del umbral
                    umbral_voz_clara = max(umbral_silencio * 1.18, self.ambient_floor * 1.50 + 5.0)
                    if vol > umbral_voz_clara:
                        self.silencio_frames = 0
                    else:
                        self.silencio_frames = max(0, self.silencio_frames - 1)

                    # Corte de seguridad. En reposo (esperando "Bimo") los segmentos son cortos: con ruido de fondo
                    # parecido a voz (TV, video, conversación) el silencio nunca llega y antes se acumulaban 25 s,
                    # con lo que "Bimo" se analizaba tarde o enterrado en ruido. En ventana activa o dictado: 120 s.
                    es_orden = getattr(self, "_inicio_en_ventana", False) and self._callback_tap_manual is None
                    en_reposo = not es_orden and not (self.esta_en_ventana_activa() or self._callback_tap_manual is not None)
                    if es_orden:
                        limite_seg = SEGMENTO_MAX_ORDEN_SEG
                    elif en_reposo:
                        limite_seg = SEGMENTO_MAX_REPOSO_SEG
                    else:
                        limite_seg = 120.0
                    if total_samples >= int(self.samplerate * limite_seg):
                        buf = list(self.acumulador_voz)
                        resto = []
                        if (en_reposo or es_orden) and len(buf) > 4:
                            # Cortar en el bloque más silencioso del último ~1.5 s (pausa entre palabras)
                            # y conservar lo que sigue para el próximo segmento: "Bimo" no queda partido.
                            ventana = min(len(buf) - 2, max(2, int(1.5 * self.samplerate / max(1, len(datos)))))
                            vols = [float(np.abs(b.astype(np.float32)).mean()) for b in buf[-ventana:]]
                            corte = len(buf) - ventana + int(np.argmin(vols)) + 1
                            buf, resto = buf[:corte], buf[corte:]
                        if buf:
                            audio_np = np.concatenate(buf)
                            if es_orden:
                                audio_np = audio_np.view(SegmentoOrden)
                            elif en_reposo:
                                audio_np = audio_np.view(SegmentoPorTope)
                            dur_seg = len(audio_np) / self.samplerate
                            print(f"[VAD] segmento {dur_seg:.1f}s (tope) piso={self.ambient_floor:.1f} umbral={umbral_silencio:.1f}")
                            self._despachar_analisis(audio_np)
                        self.acumulador_voz = list(resto)
                        self.hablando = bool(resto)
                        if es_orden:
                            self._inicio_en_ventana = False  # lo que sigue a la orden ya no es parte de ella
                        self.silencio_frames = 0
                        self._frames_voz_reales = len(resto)
                        self._peak_voz = max((float(np.abs(b.astype(np.float32)).mean()) for b in resto), default=0.0)
        except Exception:
            ahora_err = time.time()
            if ahora_err - getattr(self, '_ultimo_error_callback', 0.0) >= 10.0:
                self._ultimo_error_callback = ahora_err
                import traceback
                print(f"[VOICE LISTENER CALLBACK ERROR]\n{traceback.format_exc()}")
            self.acumulador_voz = []
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            return

    def _despachar_analisis(self, audio_np):
        """Encola el audio para procesamiento asíncrono (cola de hasta 3 segmentos)."""
        try:
            self._cola_audio.put_nowait(audio_np)
        except queue.Full:
            print("[VOICE LISTENER WARN] Cola de audio llena (3 segmentos). Descartando el más antiguo.")
            try:
                self._cola_audio.get_nowait()
            except Exception:
                pass
            try:
                self._cola_audio.put_nowait(audio_np)
            except Exception:
                pass

    def _worker_loop(self):
        """Hilo dedicado a procesar secuencialmente la cola de audio sin bloquear el callback de sonido."""
        while self.activo:
            try:
                audio_np = self._cola_audio.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self.en_proceso = True
                self.tiempo_inicio_proceso = time.time()
                self._analizar_audio(audio_np)
            except Exception as e_w:
                print(f"[VOICE LISTENER WORKER ERROR]: {e_w}")
            finally:
                self.en_proceso = False
                try:
                    self._cola_audio.task_done()
                except Exception:
                    pass

    def _analizar_audio(self, audio_np):
        try:
            por_tope = isinstance(audio_np, SegmentoPorTope)
            es_orden = isinstance(audio_np, SegmentoOrden)
            audio_np = np.asarray(audio_np)
            # 1. Filtro de energía acústica y duración en memoria RAM (hasta 120s)
            duracion_seg = len(audio_np) / self.samplerate
            self._duracion_actual_analisis = duracion_seg
            if duracion_seg < 0.25 or duracion_seg > 120.0:
                return

            # Normalización, remuestreo a 16000Hz y Control Automático de Ganancia (AGC equilibrado)
            from ai_engine import normalizar_audio_para_stt
            # Con TV o conversación de fondo: quedarse con la voz cercana (la del doctor) antes de transcribir
            audio_np = aislar_voz_cercana(audio_np, self.samplerate)
            _, audio_float, tiene_energia = normalizar_audio_para_stt(audio_np, samplerate=self.samplerate)
            if not tiene_energia or audio_float.size == 0:
                return

            # 2. Transcripción de alta precisión (Groq whisper-large-v3-turbo con fallback local)
            texto = ""
            es_mock_whisper = hasattr(get_whisper_engine, "assert_called")
            if not es_mock_whisper and (duracion_seg >= 0.35):
                try:
                    from ai_engine import transcribir_audio
                    texto = transcribir_audio(audio_float)
                except Exception as e_man_par:
                    print(f"[VOICE LISTENER PARIDAD WARN]: Fallback a transcripción directa ({e_man_par})")
                    texto = ""

            if not texto:
                # Transcripción rápida local optimizada para activación y órdenes cortas
                model = get_whisper_engine()
                
                # Inyección dinámica de vocabulario aprendido en el prompt de Whisper
                vocab_aprendido = ""
                try:
                    from database import obtener_vocabulario_aprendido
                    aprendidos = obtener_vocabulario_aprendido(limite=40)
                    if aprendidos:
                        vocab_aprendido = " Apellidos aprendidos: " + ", ".join(aprendidos) + "."
                except Exception:
                    vocab_aprendido = ""

                # IMPORTANTE: NO incluir 'Bimo' en prompt_sesgo para evitar que Whisper lo alucine ante ruidos de sala
                prompt_sesgo = f"Consulta clínica de odontología. Citas, pacientes, Llumiquinga, Guaminga, Toapanta, Quispe, Simbaña, Tituaña, Chiluisa, Pilataxi.{vocab_aprendido}"
                segmentos, _ = model.transcribe(
                    audio_float,
                    language="es",
                    initial_prompt=prompt_sesgo,
                    vad_filter=False,  # El VAD por energía ya aisló la frase; evitar recorte de clips cortos
                    beam_size=1,
                    temperature=0.0,
                    condition_on_previous_text=False
                )

                texto_partes = []
                for s in segmentos:
                    # Filtrar si Whisper detecta alta probabilidad de no-voz
                    if s.no_speech_prob > 0.75:
                        continue
                    texto_partes.append(s.text)

                if not texto_partes:
                    return

                texto = " ".join(texto_partes).strip()
            if not texto or len(texto) < 3:
                return

            texto = limpiar_alucinaciones_whisper(texto)
            if not texto or len(texto) < 3:
                return

            import re
            import unicodedata
            texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower()).strip()
            # Quitar tildes ('Bímo', 'Vímo') para comparar la palabra de activación
            texto_limpio = ''.join(c for c in unicodedata.normalize('NFD', texto_limpio) if unicodedata.category(c) != 'Mn')
            # Unir 'bi mo' / 'vi mo' cuando Whisper separa la palabra en dos
            texto_limpio = re.sub(r'\b([bv]i)\s+(mo)\b', r'\1\2', texto_limpio)
            palabras = texto_limpio.split()

            # Verificar si estamos dentro de la ventana activa multi-turn (el usuario YA dijo 'Bimo' previamente)
            if self.esta_en_ventana_activa() or es_orden:
                palabras_activas = [w for w in palabras if w not in ('eh', 'este', 'em', 'mm', 'ah', 'oh')]
                # Si fue solo un suspiro, muletilla o ruido corto mientras el doctor piensa, mantener la ventana activa abierta
                if len(palabras_activas) < 2 and duracion_seg < 1.8:
                    print(f"[VOICE LISTENER] Pausa/muletilla detectada en ventana activa; esperando orden completa...")
                    return
                self.tiempo_ventana_activa = 0.0
                texto_cmd = extraer_ultima_orden(texto) or texto
                pendiente = self._tomar_orden_pendiente()
                if pendiente:
                    # Continuación de una orden que quedó cortada en el segmento anterior
                    texto_cmd = f"{pendiente} {texto_cmd}".strip()
                print(f"[VOICE LISTENER] Comando recibido dentro de ventana activa: \"{texto_cmd}\"")
                if self.callback_comando:
                    self.callback_comando(texto_cmd)
                return

            # 3. Regla de activación ESTRICTA: SOLO activar cuando se pronuncie claramente la palabra clave 'Bimo'
            def _es_variacion_bimo(p: str) -> bool:
                return p.strip().lower() in VARIANTES_BIMO

            idx_bimo = -1
            for i, w in enumerate(palabras):
                if _es_variacion_bimo(w):
                    idx_bimo = i
                    break

            if idx_bimo == -1:
                return

            # Exigir que 'Bimo' esté al inicio de la frase de invocación (ej. "Bimo...", "Hola Bimo...", "Oye Bimo...").
            # En un segmento cortado por tope (ruido de fondo continuo) la frase del doctor puede venir después
            # de palabras ajenas (TV, video): se acepta en cualquier posición y se descarta lo anterior.
            es_invocacion = False
            if por_tope:
                es_invocacion = True
                m_bimo = _PATRON_VARIANTES_FUERTES.search(texto)
                if m_bimo and m_bimo.start() > 0:
                    texto = texto[m_bimo.start():]
                palabras = palabras[idx_bimo:]
            elif idx_bimo <= 3:
                es_invocacion = True
            elif idx_bimo <= 5 and any(w in palabras[:idx_bimo] for w in ['hola', 'ola', 'oye', 'hey', 'ok', 'favor', 'asistente', 'por', 'buenas', 'buenos', 'disculpa']):
                es_invocacion = True

            if not es_invocacion:
                return

            print(f"[VOICE LISTENER] Activación confirmada por Bimo: \"{texto}\"")
            # 1. Feedback acústico instantáneo (0ms de latencia)
            try:
                from audio_feedback import sonar_inicio_dictado
                sonar_inicio_dictado()
            except Exception:
                pass

            # 2. Activar ventana activa con pausa inteligente (15s para dictar con calma)
            self.activar_ventana_activa(15.0)

            # 3. Filtro de Ruido (BLOQUE 2):
            # Si solo dijo "Bimo" / "Hola Bimo" para despertarlo, abrir micrófono y esperar la orden completa
            palabras_comando = [w for w in palabras if not _es_variacion_bimo(w) and w not in ('hola', 'ola', 'oye', 'hey', 'ok', 'por', 'favor', 'buenas', 'buenos', 'dias', 'tardes', 'noches')]
            if len(palabras_comando) == 0 or (duracion_seg < 1.5 and len(palabras_comando) == 0):
                print(f"[VOICE LISTENER] Activación inicial 'Bimo' detectada. Micrófono abierto con pausa inteligente.")
                if self.callback_comando:
                    self.callback_comando("__BIMO_WAKE_LISTENING__")
                return

            texto_cmd = extraer_ultima_orden(texto) or texto
            if por_tope:
                # La orden pudo quedar a medias: esperar la continuación (siguiente segmento) y unirlas
                with self._lock:
                    self._orden_pendiente = texto_cmd
                    self._orden_pendiente_desde = time.time()
                print(f"[VOICE LISTENER] Orden posiblemente incompleta, esperando continuación: \"{texto_cmd}\"")
                if self.callback_comando:
                    self.callback_comando("__BIMO_WAKE_LISTENING__")
                return
            if self.callback_comando:
                self.callback_comando(texto_cmd)

        except Exception as e:
            print(f"[VOICE LISTENER] Error al procesar comando de voz: {e}")
        finally:
            self.en_proceso = False

    def _watchdog_loop(self):
        """Monitorea la salud del audio para evitar que el sistema se vuelva sordo o pierda el micrófono predeterminado."""
        while self.activo:
            for _ in range(4):
                time.sleep(0.5)
                if not self.activo:
                    break
                try:
                    self._despachar_orden_pendiente_vencida()
                except Exception as e_p:
                    print(f"[VOICE LISTENER WATCHDOG] Error con orden pendiente: {e_p}")
            if not self.activo:
                break

            # 1. Recuperar en caso de bloqueo en procesamiento (watchdog adaptativo)
            timeout_adaptativo = max(6.0, getattr(self, "_duracion_actual_analisis", 4.0) * 1.5)
            if self.en_proceso and (time.time() - self.tiempo_inicio_proceso) > timeout_adaptativo:
                print(f"[VOICE LISTENER WATCHDOG] Reiniciando bandera de proceso tras timeout adaptativo ({timeout_adaptativo:.1f}s)...")
                self.en_proceso = False

            # 2. Recuperar stream si se detuvo o fue desconectado/cambiado en Windows
            if (not self.pausado or self._callback_tap_manual is not None) and (self.stream is None or not getattr(self.stream, "active", False)):
                st = self.stream
                act = getattr(st, "active", None) if st else None
                stp = getattr(st, "stopped", None) if st else None
                cls = getattr(st, "closed", None) if st else None
                print(f"[VOICE LISTENER WATCHDOG] Stream inactivo detectado (active={act}, stopped={stp}, closed={cls}). Auto-recuperando micrófono predeterminado...")
                with self._lock:
                    self._iniciar_stream(refrescar=True)
                continue

            # 3. Micrófono "vivo" pero sin señal (ej. Camo sin celular conectado): cambiar a otro con audio real
            try:
                sr_act = int(self.samplerate or 16000)
                # Solo si nunca entregó audio desde que se abrió (Camo sin celular, micrófono silenciado),
                # o si es un micrófono virtual. Así no se descartan micrófonos con supresión de ruido
                # (Krisp, NVIDIA Broadcast) que entregan ceros mientras nadie habla.
                sin_senal_nunca = not getattr(self, "_tuvo_senal", False)
                if (self.stream is not None and self._muestras_silencio_digital >= sr_act * 5
                        and (sin_senal_nunca or es_microfono_virtual(self.nombre_microfono))):
                    marcar_microfono_muerto(self.nombre_microfono, segundos=120.0)
                    with self._lock:
                        self._iniciar_stream(refrescar=True)
                    continue
            except Exception:
                pass

            # 4. Micrófono conectado/desconectado en caliente (solo Windows, sin interrumpir dictados en curso)
            try:
                if sys.platform == "win32" and (time.time() - self._ultimo_chequeo_hotplug) >= 6.0:
                    self._ultimo_chequeo_hotplug = time.time()
                    import ctypes
                    num_dev = int(ctypes.windll.winmm.waveInGetNumDevs())
                    if self._num_dispositivos_win is None:
                        self._num_dispositivos_win = num_dev
                    elif num_dev != self._num_dispositivos_win:
                        en_reposo = (not self.hablando and not self.en_proceso and self._callback_tap_manual is None
                                     and not self.esta_en_ventana_activa())
                        if en_reposo:
                            print(f"[VOICE LISTENER WATCHDOG] Cambio de micrófonos detectado ({self._num_dispositivos_win} -> {num_dev}). Re-evaluando el mejor micrófono...")
                            self._num_dispositivos_win = num_dev
                            invalidar_cache_microfono()
                            with self._lock:
                                self._iniciar_stream(refrescar=True)
            except Exception:
                pass

    def reconfigurar_microfono(self) -> dict:
        """Aplica de inmediato el micrófono elegido en Configuración (o vuelve a Automático)."""
        preferido = obtener_microfono_preferido()
        if (
            preferido
            and self.stream is not None
            and getattr(self.stream, "active", False)
            and _mismo_mic(self.nombre_microfono, preferido)
        ):
            return {"status": "ok", "sin_cambios": True, "microfono": self.nombre_microfono, **obtener_estado_microfono()}

        invalidar_cache_microfono()
        with self._lock:
            if self._callback_tap_manual is not None:
                return {"status": "pendiente", "message": "Se aplicará al terminar el dictado actual."}
            self._iniciar_stream(refrescar=True)
        return {"status": "ok", "microfono": self.nombre_microfono, **obtener_estado_microfono()}

