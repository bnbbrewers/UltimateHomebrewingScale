"""Deterministic test scale and virtual relay. No sensor/actuator imports."""
import math
import runtime_debug
from ticks import ticks_ms, ticks_diff


class SimulatedScale:
    simulated = True

    def __init__(self):
        self.target = float(runtime_debug.setting('SIMULATION_WEIGHT_G', 1000))
        self.rate = float(runtime_debug.setting('SIMULATION_RATE_G_S', 100))
        self.mode = runtime_debug.setting('SIMULATION_MODE', 'ramp')
        self.weight = self.target if self.mode == "fixed" else 0.0
        self._at = ticks_ms()
        self._samples = []
        self._sample_at = None
        self._relay_on = False
        self._fixed_pending = False

    def set_target(self, grams):
        grams = float(grams)
        if not math.isfinite(grams) or not 0 <= grams <= 10000000:
            raise ValueError('Simulation target must be 0..10000000 g')
        self.target = grams
        if self.mode == "fixed":
            self.weight = grams
        self._at = ticks_ms()
        self._samples = []

    def set_weight(self, grams):
        grams = float(grams)
        if not math.isfinite(grams) or not -100000 <= grams <= 10000000:
            raise ValueError('Simulation weight must be -100000..10000000 g')
        self.weight = grams
        self._fixed_pending = False
        self.target = grams
        if self.mode == "fixed":
            self.weight = grams
        self._at = ticks_ms()
        self._samples = []

    def read_weight_filtered(self):
        now = ticks_ms()
        if self._fixed_pending and ticks_diff(now, self._tare_at) >= 500:
            self.weight = self.target
            self._fixed_pending = False
        elapsed = max(0, ticks_diff(now, self._at)) / 1000
        self._at = now
        if self.mode == 'ramp' and (not getattr(self, '_filling', False) or self._relay_on):
            delta = self.target - self.weight
            step = max(0, self.rate) * elapsed
            self.weight += min(step, delta) if delta >= 0 else max(-step, delta)
        if self._sample_at is None or ticks_diff(now, self._sample_at) >= 100:
            self._sample_at = now
            self._samples.append(self.weight)
            self._samples = self._samples[-10:]
        return self.weight

    def tare(self):
        self._filling = False
        self.weight = 0.0
        self._fixed_pending = self.mode == "fixed"
        self._tare_at = ticks_ms()
        self._at = self._tare_at
        self._samples = []
        self._sample_at = None
        return True

    def is_stable(self, threshold=5.0, samples=5):
        if len(self._samples) < samples:
            return False
        values = self._samples[-samples:]
        return max(values) - min(values) < threshold

    def prepare_fill(self, empty_weight_g, target_weight_g, resume=False):
        self._filling = True
        if not resume:
            self.weight = float(empty_weight_g)
        self.set_target(float(empty_weight_g) + float(target_weight_g))


class SimulatedRelay:
    simulated = True

    def __init__(self, scale):
        self.scale = scale
        self.scale._relay_on = False

    def set_on(self):
        self.scale._at = ticks_ms()
        self.scale._relay_on = True

    def set_off(self):
        self.scale._relay_on = False

    def is_on(self):
        return self.scale._relay_on

    def is_available(self):
        return True
