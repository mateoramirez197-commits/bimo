# -*- coding: utf-8 -*-
"""
tests/test_bimo_ruido_fondo.py
"Bimo" con ruido de fondo parecido a voz (TV, video, conversación):
1. En reposo, el audio continuo se corta en segmentos cortos (<= 8 s) en lugar de 25 s.
2. El corte se hace en una pausa: el audio restante pasa al siguiente segmento sin perderse.
3. En un segmento cortado, "Bimo" se acepta aunque vaya después de palabras ajenas.
4. Una orden partida entre dos segmentos se une antes de ejecutarse.
5. Si la continuación no llega, la orden se ejecuta sola tras la espera.
6. En un segmento normal (cortado por silencio) se mantiene la regla estricta: "Bimo" al inicio.
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from wake_word_listener import (  # noqa: E402
    BackgroundWakeListener,
    SegmentoOrden,
    SegmentoPorTope,
    SEGMENTO_MAX_ORDEN_SEG,
    SEGMENTO_MAX_REPOSO_SEG,
    ESPERA_ORDEN_PENDIENTE_SEG,
    aislar_voz_cercana,
)

SR = 16000


def _listener(comandos):
    with patch("sounddevice.InputStream"):
        l = BackgroundWakeListener(callback_comando=lambda c: comandos.append(c), samplerate=SR)
    l.activo = True
    l.pausado = False
    l._startup_skip_frames = 0
    l.tiempo_ventana_activa = 0.0
    return l


def _whisper(texto):
    seg = MagicMock()
    seg.no_speech_prob = 0.05
    seg.text = texto
    motor = MagicMock()
    motor.return_value.transcribe.return_value = ([seg], None)
    return motor


def _audio(segundos, por_tope=False):
    t = np.linspace(0, segundos, int(SR * segundos), endpoint=False)
    a = (np.sin(2 * np.pi * 220 * t) * 6000).astype(np.int16)
    return a.view(SegmentoPorTope) if por_tope else a


class TestBimoConRuidoDeFondo(unittest.TestCase):

    def test_01_ruido_continuo_se_corta_en_segmentos_cortos(self):
        comandos = []
        l = _listener(comandos)
        despachados = []
        l._despachar_analisis = lambda audio: despachados.append(audio)
        np.random.seed(7)
        for _ in range(20):
            l._audio_callback(np.random.randint(-40, 40, 1024, dtype=np.int16), 1024, None, None)
        # 30 s de "voz" continua (TV) con pequeñas variaciones de volumen
        for i in range(470):
            amp = 1500 if i % 9 else 900
            l._audio_callback(np.random.randint(-amp, amp, 1024, dtype=np.int16), 1024, None, None)
        self.assertGreaterEqual(len(despachados), 3)
        for seg in despachados:
            self.assertIsInstance(seg, SegmentoPorTope)
            self.assertLessEqual(len(seg) / SR, SEGMENTO_MAX_REPOSO_SEG + 0.1)
        # Nada se pierde: lo despachado + lo que sigue acumulado cubre todo el audio con voz
        total = sum(len(s) for s in despachados) + sum(len(b) for b in l.acumulador_voz)
        self.assertGreaterEqual(total, 470 * 1024)

    @patch("audio_feedback.sonar_inicio_dictado")
    def test_02_bimo_despues_de_ruido_en_segmento_cortado(self, _ding):
        comandos = []
        l = _listener(comandos)
        with patch("wake_word_listener.get_whisper_engine", _whisper("y en la novela de hoy dijeron que Bimo")):
            l._analizar_audio(_audio(8.0, por_tope=True))
        self.assertTrue(l.esta_en_ventana_activa())
        self.assertIn("__BIMO_WAKE_LISTENING__", comandos)

    @patch("audio_feedback.sonar_inicio_dictado")
    def test_03_orden_partida_se_une(self, _ding):
        comandos = []
        l = _listener(comandos)
        with patch("wake_word_listener.get_whisper_engine", _whisper("la tele sigue Bimo agenda una cita para mañana")):
            l._analizar_audio(_audio(8.0, por_tope=True))
        self.assertEqual(comandos, ["__BIMO_WAKE_LISTENING__"])
        with patch("wake_word_listener.get_whisper_engine", _whisper("a las tres con Juan Pérez")):
            l._analizar_audio(_audio(2.0))
        self.assertEqual(len(comandos), 2)
        self.assertIn("agenda una cita para mañana", comandos[1])
        self.assertIn("a las tres con Juan Pérez", comandos[1])
        self.assertNotIn("tele", comandos[1])

    @patch("audio_feedback.sonar_inicio_dictado")
    def test_04_orden_sin_continuacion_se_ejecuta_sola(self, _ding):
        comandos = []
        l = _listener(comandos)
        with patch("wake_word_listener.get_whisper_engine", _whisper("Bimo qué hora es")):
            l._analizar_audio(_audio(8.0, por_tope=True))
        l._despachar_orden_pendiente_vencida()  # todavía dentro de la espera
        self.assertEqual(comandos, ["__BIMO_WAKE_LISTENING__"])
        l._orden_pendiente_desde = time.time() - ESPERA_ORDEN_PENDIENTE_SEG - 0.1
        l._despachar_orden_pendiente_vencida()
        self.assertEqual(len(comandos), 2)
        self.assertIn("qué hora es", comandos[1])
        self.assertEqual(l._orden_pendiente, "")

    def test_06_orden_con_tv_se_corta_en_15s_y_se_marca_como_orden(self):
        comandos = []
        l = _listener(comandos)
        despachados = []
        l._despachar_analisis = lambda audio: despachados.append(audio)
        np.random.seed(3)
        for _ in range(20):
            l._audio_callback(np.random.randint(-40, 40, 1024, dtype=np.int16), 1024, None, None)
        l.activar_ventana_activa(15.0)
        for i in range(400):  # ~25 s de voz + TV sin silencio
            amp = 1500 if i % 9 else 900
            l._audio_callback(np.random.randint(-amp, amp, 1024, dtype=np.int16), 1024, None, None)
        self.assertTrue(despachados)
        self.assertIsInstance(despachados[0], SegmentoOrden)
        self.assertLessEqual(len(despachados[0]) / SR, SEGMENTO_MAX_ORDEN_SEG + 0.1)

    def test_07_orden_se_ejecuta_aunque_la_ventana_venza_mientras_se_graba(self):
        comandos = []
        l = _listener(comandos)
        l.tiempo_ventana_activa = 0.0  # la ventana ya venció
        with patch("wake_word_listener.get_whisper_engine", _whisper("agenda una cita para Juan mañana a las tres")):
            l._analizar_audio(_audio(16.0).view(SegmentoOrden))
        self.assertEqual(len(comandos), 1)
        self.assertIn("agenda una cita", comandos[0])

    def test_08_aislar_voz_cercana_descarta_la_tv(self):
        np.random.seed(5)
        tv = np.random.randint(-500, 500, SR * 6).astype(np.int16)
        voz = tv.copy()
        voz[SR * 2:SR * 3] = np.random.randint(-6000, 6000, SR).astype(np.int16)  # 1 s de doctor cerca
        limpio = aislar_voz_cercana(voz, SR)
        self.assertLess(len(limpio) / SR, 2.0)
        self.assertGreater(len(limpio) / SR, 0.9)
        # Audio parejo (sin contraste voz / fondo): no se toca
        self.assertEqual(len(aislar_voz_cercana(tv, SR)), len(tv))

    def test_05_segmento_normal_mantiene_regla_estricta(self):
        comandos = []
        l = _listener(comandos)
        with patch("wake_word_listener.get_whisper_engine", _whisper("ayer en la reunión hablamos mucho del Bimo nuevo")):
            l._analizar_audio(_audio(3.0))
        self.assertEqual(comandos, [])
        self.assertFalse(l.esta_en_ventana_activa())


if __name__ == "__main__":
    unittest.main(verbosity=2)
