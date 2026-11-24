"""audio_monitor.py - mic capture, RMS amplitude -> mouth level (0..3)."""
import threading, time
import numpy as np

SAMPLE_RATE = 16000
BLOCK_SIZE = 512

# Base RMS thresholds for level 1 / 2 / 3 (before calibration offset + sensitivity scaling)
BASE_THRESHOLDS = (0.01, 0.03, 0.08)


class AudioMonitor:
    def __init__(self, device=None, sensitivity=1.0):
        self.device = device
        self.sensitivity = sensitivity
        self.baseline = 0.0          # measured noise floor
        self._lock = threading.Lock()
        self._rms = 0.0
        self._level = 0
        self._cal = None             # list while calibrating
        self._stream = None
        self.error = None

    # ---- level mapping (pure function, easy to unit-test) ----
    def level_for(self, rms):
        t1, t2, t3 = (self.baseline + t * self.sensitivity for t in BASE_THRESHOLDS)
        if rms < t1:
            return 0
        if rms < t2:
            return 1
        if rms < t3:
            return 2
        return 3

    def _callback(self, indata, frames, time_info, status):
        block = indata[:, 0]
        rms = float(np.sqrt(np.mean(block ** 2)))
        with self._lock:
            self._rms = rms
            if self._cal is not None:
                self._cal.append(rms)
            self._level = self.level_for(rms)

    def get_state(self):
        """Returns (level 0-3, rms, listening). listening = quiet room sound (level 1)."""
        with self._lock:
            return self._level, self._rms, self._level == 1

    def start(self):
        import sounddevice as sd  # imported here so the module loads without audio hardware
        self.stop()
        try:
            self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK_SIZE,
                                          dtype="float32", device=self.device, callback=self._callback)
            self._stream.start()
            self.error = None
        except Exception as e:  # bad device, no mic, permission denied...
            self.error = str(e)
            self._stream = None

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop(); self._stream.close()
            except Exception:
                pass
            self._stream = None

    def calibrate(self, seconds=1.0):
        """Sample ambient noise (stay quiet!) and set the noise-floor baseline."""
        with self._lock:
            self._cal = []
        time.sleep(seconds)
        with self._lock:
            samples, self._cal = self._cal, None
        if samples:
            # clamp so talking during calibration can't make the avatar deaf
            self.baseline = min(float(np.mean(samples)), 0.05)
        return self.baseline
