"""Map relative vocal prosody to a signed portrait pose (frown .. smile)."""
import math

import numpy as np


def voiced_pitch(block, rate):
    """First strong periodic peak after DC removal, or None for unvoiced audio."""
    signal = np.asarray(block, dtype=np.float64)
    signal = signal - signal.mean()
    first = int(rate / 450)
    last = min(math.ceil(rate / 65), len(signal) // 2 - 1)
    if first + 2 >= last:
        return None
    # Normalize by the energy of the two overlapping slices at each lag.
    power = np.r_[0, np.cumsum(signal * signal)]
    lags = np.arange(first - 1, last + 2)
    denom = power[-1] - power[lags] + power[len(signal) - lags]
    corr = np.correlate(signal, signal, 'full')[len(signal) - 1 + lags]
    score = 2 * corr / np.maximum(denom, 1e-12)
    peaks = np.flatnonzero((score[1:-1] > score[:-2]) & (score[1:-1] >= score[2:])) + 1
    if not len(peaks):
        return None
    strong = peaks[score[peaks] >= max(0.72, 0.91 * score[peaks].max())]
    return rate / lags[strong[0]] if len(strong) else None


class VoiceExpression:
    def __init__(self):
        self.reference = None
        self.reference_db = 0.0
        self.voiced_seconds = 0.0
        self.unvoiced_seconds = 0.0
        self.pose = 0.0

    def update(self, block, rate, rms, gate):
        dt = len(block) / rate
        pitch = voiced_pitch(block, rate) if rms > gate else None
        target = 0.0
        if pitch is not None:
            note = 12 * math.log2(pitch)
            db = 20 * math.log10(max(rms, 1e-9))
            if self.reference is None:
                self.reference, self.reference_db = note, db
            self.unvoiced_seconds = 0.0
            self.voiced_seconds += dt
            # Learn the speaker quickly at startup, then track gradual drift.
            learning = -math.expm1(-dt / (0.35 if self.voiced_seconds < 0.7 else 12))
            self.reference += learning * (note - self.reference)
            self.reference_db += learning * (db - self.reference_db)
            delta = note - self.reference
            if self.voiced_seconds >= 0.7:
                strength = min(1, max(0, (abs(delta) - 1.4) / 4))
                energy = np.clip((db - self.reference_db) * np.sign(delta) / 12, -1, 1)
                target = math.copysign(strength * (0.8 + 0.2 * energy), delta)
        else:
            self.unvoiced_seconds += dt
            if self.unvoiced_seconds < 0.12:
                target = self.pose  # bridge consonants and short gaps
        tau = 0.19 if target else 0.32
        self.pose += (target - self.pose) * -math.expm1(-dt / tau)
        return self.pose
