# -*- coding: utf-8 -*-
"""
tests/test_escucha_activa_robusta.py
Pruebas de robustez para escucha activa continua (PortAudio / VAD / watchdog):
1. _audio_callback blindado ante excepciones sin detener el stream.
2. VAD dinámico: 3 frases de 1.5s separadas por 1s de silencio con ruido de fondo constante (~60) generan 3 segmentos separados.
3. Límite de seguridad: fuera de la ventana activa, voz continua de 40s se corta en un segmento de como máximo 25s.
4. Extracción de la última orden con variantes fuertes, preservación de dictados clínicos y limpieza de alucinaciones.
5. reconfigurar_microfono no reinicia el stream si el micrófono elegido ya está activo.
6. _reproducir_audio usa OutputStream con dtype float32 sin provocar TypeErrors.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from wake_word_listener import (
    BackgroundWakeListener,
    extraer_ultima_orden,
    limpiar_alucinaciones_whisper,
    limpiar_variantes_bimo,
)
from voice_assistant import _reproducir_audio


def test_audio_callback_excepcion_no_relanzada_y_recupera():
    """Un _audio_callback que recibe un bloque que provoca una excepción interna NO debe relanzarla, y el siguiente bloque debe procesarse normal."""
    with patch("sounddevice.InputStream"):
        listener = BackgroundWakeListener(callback_comando=lambda cmd: None, samplerate=16000)
        listener.activo = True
        listener.pausado = False
        listener._startup_skip_frames = 0
        listener.hablando = True
        listener.acumulador_voz = [np.zeros(512, dtype=np.int16)]

        class BloqueCorrupto:
            def __len__(self):
                return 1024

            def astype(self, dtype):
                return np.zeros(1024, dtype=dtype)

            def flatten(self):
                raise RuntimeError("Fallo interno simulado en callback de audio")

        # No debe lanzar excepción
        listener._audio_callback(BloqueCorrupto(), 1024, None, None)

        # El estado VAD debe haber sido reiniciado limpiamente
        assert listener.acumulador_voz == []
        assert listener.hablando is False
        assert listener.silencio_frames == 0
        assert listener._peak_voz == 0.0

        # El siguiente bloque normal debe procesarse sin errores
        bloque_normal = np.zeros(1024, dtype=np.int16)
        listener._audio_callback(bloque_normal, 1024, None, None)
        assert listener.activo is True


def test_tres_frases_separadas_por_silencio_con_ruido_constante():
    """Simula 3 frases de 1.5 s separadas por 1 s de silencio, con ruido de fondo constante (amplitud 60): deben salir 3 segmentos separados, no uno."""
    with patch("sounddevice.InputStream"):
        listener = BackgroundWakeListener(callback_comando=lambda cmd: None, samplerate=16000)
        listener.activo = True
        listener.pausado = False
        listener._startup_skip_frames = 0
        listener.tiempo_ventana_activa = 0.0

        despachados = []
        listener._despachar_analisis = lambda audio: despachados.append(audio)

        np.random.seed(42)
        bloque_ruido = lambda: np.random.randint(-60, 60, size=1024, dtype=np.int16)
        bloque_voz = lambda: np.random.randint(-2000, 2000, size=1024, dtype=np.int16)

        # Pre-calibrar con ruido de fondo
        for _ in range(25):
            listener._audio_callback(bloque_ruido(), 1024, None, None)

        # 3 frases: 1.5s de voz (~24 bloques) + 1.0s de silencio (~18 bloques de ruido constante)
        for _ in range(3):
            for _ in range(24):
                listener._audio_callback(bloque_voz(), 1024, None, None)
            for _ in range(18):
                listener._audio_callback(bloque_ruido(), 1024, None, None)

        assert len(despachados) == 3, f"Se esperaban 3 segmentos separados, se obtuvieron {len(despachados)}"


def test_corte_seguridad_fuera_ventana_activa_maximo_25s():
    """Fuera de la ventana activa, voz continua de 40 s debe cortarse en un segmento de como máximo 25 s."""
    with patch("sounddevice.InputStream"):
        listener = BackgroundWakeListener(callback_comando=lambda cmd: None, samplerate=16000)
        listener.activo = True
        listener.pausado = False
        listener._startup_skip_frames = 0
        listener.tiempo_ventana_activa = 0.0
        listener._callback_tap_manual = None

        despachados = []
        listener._despachar_analisis = lambda audio: despachados.append(audio)

        np.random.seed(42)
        bloque_ruido = lambda: np.random.randint(-60, 60, size=1024, dtype=np.int16)
        bloque_voz = lambda: np.random.randint(-2000, 2000, size=1024, dtype=np.int16)

        # Pre-calibrar con ruido
        for _ in range(15):
            listener._audio_callback(bloque_ruido(), 1024, None, None)

        # 40s de voz continua = 625 bloques de 1024 muestras a 16000Hz
        for _ in range(625):
            listener._audio_callback(bloque_voz(), 1024, None, None)

        assert len(despachados) >= 1, "Debe haber despachado al menos un segmento por corte de seguridad"
        duracion_primer_segmento = len(despachados[0]) / 16000.0
        # Debe cortarse en un segmento de como máximo 25 s (con tolerancia de 1 bloque ~0.064s)
        assert duracion_primer_segmento <= 25.1, f"El primer segmento duró {duracion_primer_segmento:.2f}s, debía ser <= 25s"


def test_extraccion_ultima_orden():
    """Pruebas de extracción de la última orden: dictado clínico intacto vs repeticiones con alucinaciones."""
    # 1. Dictado clínico con 'vimos' no debe cortarse ni perder datos
    dictado_clinico = "Bimo, paciente Ana Pérez de 30 años, la vimos hace un mes con caries en la 16, hoy se le hizo resina."
    res_clinico = extraer_ultima_orden(dictado_clinico)
    assert "Ana Pérez" in res_clinico
    assert "30 años" in res_clinico

    # 2. Orden repetida con alucinación final de Whisper
    entrada_repetida = "Vimos que hora es. Vimo, ¿qué citas tengo mañana? Vimo, ¿qué citas tengo mañana? Música"
    res_repetida = extraer_ultima_orden(entrada_repetida)
    assert "citas tengo mañana" in res_repetida.lower()
    assert "música" not in res_repetida.lower()
    assert "musica" not in res_repetida.lower()

    # 3. Variaciones fonéticas y alucinaciones comunes de Whisper
    assert "hora es" in extraer_ultima_orden("Bimo, ¿qué hora es? Gracias.").lower()
    assert "gracias" not in extraer_ultima_orden("Bimo, ¿qué hora es? Gracias.").lower()

    # 4. Comprobación de limpieza de variantes
    assert limpiar_variantes_bimo("Vimo") == ""
    assert limpiar_variantes_bimo("Bímo") == ""
    assert limpiar_variantes_bimo("Vimos") == ""
    assert "citas" in limpiar_variantes_bimo("Vimo citas")


def test_reconfigurar_microfono_mismo_activo_sin_cambios():
    """reconfigurar_microfono con el mismo micrófono activo no llama a _iniciar_stream."""
    with patch("sounddevice.InputStream"):
        listener = BackgroundWakeListener(callback_comando=lambda cmd: None, samplerate=16000)
        listener.stream = MagicMock()
        listener.stream.active = True
        mic_nombre = "Microphone (3- ME6S)"
        listener.nombre_microfono = mic_nombre

        with patch("wake_word_listener.obtener_microfono_preferido", return_value=mic_nombre):
            with patch.object(listener, "_iniciar_stream") as mock_iniciar:
                res = listener.reconfigurar_microfono()
                assert mock_iniciar.call_count == 0, "_iniciar_stream no debió ser llamado al ser el mismo micrófono"
                assert res.get("sin_cambios") is True
                assert res.get("status") == "ok"


def test_reproducir_audio_output_stream_float32():
    """_reproducir_audio con sounddevice simulado: el OutputStream debe recibir dtype='float32' y datos float32."""
    with patch("voice_assistant._generar_audio_edge", return_value=None), \
         patch("voice_assistant.asyncio.run"), \
         patch("soundfile.read") as mock_sf_read, \
         patch("sounddevice.OutputStream") as mock_output_stream, \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=2048), \
         patch("os.remove"):

        # Simular lectura devolviendo float32
        fake_audio = np.zeros((100, 2), dtype=np.float32)
        mock_sf_read.return_value = (fake_audio, 24000)

        mock_stream_instance = MagicMock()
        mock_output_stream.return_value.__enter__.return_value = mock_stream_instance

        _reproducir_audio("Cita confirmada")

        assert mock_output_stream.called, "OutputStream debió ser instanciado"
        call_kwargs = mock_output_stream.call_args[1]
        assert call_kwargs.get("dtype") == "float32", f"El dtype esperado es 'float32', se recibió {call_kwargs.get('dtype')}"
        assert call_kwargs.get("channels") == 2

        assert mock_stream_instance.write.called, "stream.write debió ser llamado"
        datos_escritos = mock_stream_instance.write.call_args[0][0]
        assert datos_escritos.dtype == np.float32, f"Los datos escritos deben ser float32, se recibió {datos_escritos.dtype}"
