import unittest
from unittest.mock import patch

import numpy as np

from audio_monitor import AudioMonitor
from photo_avatar import FeaturePatch, PhotoAvatarRenderer


class PhotoMotionTests(unittest.TestCase):
    def setUp(self):
        rgb = np.random.default_rng(3).integers(0, 256, (60, 80, 3), dtype=np.uint8)
        self.patch = FeaturePatch(rgb, (40, 30), 22, 18, 0.0)

    def test_neutral_is_original_texture(self):
        for animate in (self.patch.blink, self.patch.mouth):
            np.testing.assert_array_equal(animate(0), self.patch.source)

    def test_features_keep_their_boundary(self):
        for animate in (self.patch.blink, self.patch.mouth):
            frame = animate(1)
            np.testing.assert_array_equal(frame[:, [0, -1]], self.patch.source[:, [0, -1]])
            np.testing.assert_array_equal(frame[[0, -1]], self.patch.source[[0, -1]])
            self.assertTrue(np.any(frame != self.patch.source))

    def test_audio_envelope_respects_calibration(self):
        audio = AudioMonitor(sensitivity=2)
        audio.baseline = 0.03
        self.assertEqual(audio.photo_level_for(0.049), 0)
        self.assertLess(audio.photo_level_for(0.06), audio.photo_level_for(0.07))
        self.assertEqual(audio.photo_level_for(1), 3)

    def test_attack_and_release_at_different_frame_rates(self):
        results = []
        for fps in (20, 60):
            renderer = PhotoAvatarRenderer.__new__(PhotoAvatarRenderer)
            renderer.t0 = renderer.last_frame = renderer.mouth = 0
            renderer.next_blink = 5
            renderer.blink_start = None
            with patch('photo_avatar.time.monotonic') as clock:
                for i in range(1, fps + 1):
                    clock.return_value = i / fps
                    renderer._tick(3 if i <= fps // 2 else 0)
            results.append(renderer.mouth)
        self.assertAlmostEqual(*results)
        self.assertLess(results[0], 0.03)
