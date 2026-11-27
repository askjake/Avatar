import unittest

import numpy as np
from PIL import Image

from audio_monitor import AudioMonitor, BLOCK_SIZE, SAMPLE_RATE
from photo_avatar import ExpressionWarp
from voice_expression import VoiceExpression


class ExpressionTests(unittest.TestCase):
    def setUp(self):
        self.model = VoiceExpression()
        self.rng = np.random.default_rng(12)

    def feed(self, pitch, amp=0.12, blocks=35):
        t = np.arange(BLOCK_SIZE) / SAMPLE_RATE
        for _ in range(blocks):
            signal = amp * (np.sin(2*np.pi*pitch*t) + 0.45*np.sin(4*np.pi*pitch*t))
            self.model.update(signal, SAMPLE_RATE, np.sqrt(np.mean(signal**2)), 0.01)
        return self.model.pose

    def test_relative_to_speakers_own_register(self):
        for base in (95, 170, 275):
            with self.subTest(base=base):
                self.model = VoiceExpression()
                self.assertAlmostEqual(self.feed(base), 0)
                self.assertGreater(self.feed(base * 1.42), 0.65)
                self.assertLess(self.feed(base / 1.4), -0.65)

    def test_low_confidence_releases_and_volume_alone_is_neutral(self):
        self.feed(150)
        self.assertAlmostEqual(self.feed(150, amp=0.4), 0)
        self.feed(215)
        for _ in range(70):
            self.model.update(self.rng.normal(0, .1, BLOCK_SIZE), SAMPLE_RATE, .1, .01)
        self.assertLess(abs(self.model.pose), .005)
        self.assertLess(abs(self.feed(150, 0)), .005)

    def test_disabled_and_reenabled(self):
        audio = AudioMonitor()
        audio.enable_expressions(True)
        self.assertIsNotNone(audio._expression)
        audio.enable_expressions(False)
        self.assertEqual(audio.get_portrait_state(), (0, 0))
        audio.enable_expressions(True)
        self.assertIsNone(audio._expression.reference)

    def test_lip_corners_move_in_opposite_directions(self):
        rows = np.indices((160, 140))[0].astype(np.uint8)
        neutral = Image.fromarray(rows).convert('RGBA')
        warp = ExpressionWarp(neutral.size, [(45,50),(95,50)], (70,95), 25)
        for pose in (-1,1):
            head = neutral.copy()
            warp.apply(head, pose)
            self.assertGreater(pose * (head.getpixel((92,95))[0] - 95), 2)
            self.assertEqual(head.getpixel((70,95)), neutral.getpixel((70,95)))
