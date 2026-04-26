"""
Hidden scale calibration wizard app.

The UI lives here for now, while hardware access goes through the shared
HardwareManager devices.
"""

import json
import time

import lvgl as lv
import m5ui

from .base_app import BaseApp


CALIBRATION_POINTS = [0, 500, 5000, 20000]
CALIBRATION_DURATION = 30
CALIBRATION_FILE = "scale_calibration.json"

try:
    import config
    DEBUG_MODE = getattr(config, "DEBUG", False)
except Exception:
    DEBUG_MODE = False


class ScaleCalibrationWizardApp(BaseApp):
    APP_ID = "scale_calibration_wizard_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._scale = self.hardware.scale
        self._rotary = self.hardware.rotary

        self._page = None
        self._title_label = None
        self._step_label = None
        self._info_label = None
        self._status_label = None
        self._progress_bar = None

        self._current_step = 0
        self._adjusted_weights = list(CALIBRATION_POINTS)
        self._calibration_data = {}

        self._encoder_speed_multiplier = 1
        self._encoder_last_direction = 0
        self._encoder_momentum_count = 0
        self._last_encoder_change_time = 0

        self._measuring = False
        self._measurement_started_at = 0
        self._last_status_second = -1
        self._samples = []

    def _font(self, preferred_size=16):
        candidates = [
            "font_montserrat_{}".format(preferred_size),
            "font_montserrat_{}".format(preferred_size - 2),
            "font_montserrat_16",
            "font_montserrat_14",
            "font_montserrat_12",
            "font_montserrat_10",
        ]
        for name in candidates:
            if hasattr(lv, name):
                return getattr(lv, name)
        return None

    def _build_ui(self):
        self._page = m5ui.M5Page(bg_c=0x000000)
        self._title_label = m5ui.M5Label(
            "Scale Calibration",
            x=50,
            y=30,
            text_c=0x9CA3AF,
            bg_c=0x000000,
            bg_opa=0,
            font=self._font(16),
            parent=self._page,
        )
        self._step_label = m5ui.M5Label(
            "",
            x=65,
            y=75,
            text_c=0xE0E0E0,
            bg_c=0x000000,
            bg_opa=0,
            font=self._font(16),
            parent=self._page,
        )
        self._info_label = m5ui.M5Label(
            "",
            x=60,
            y=105,
            text_c=0x808080,
            bg_c=0x000000,
            bg_opa=0,
            font=self._font(10),
            parent=self._page,
        )
        self._status_label = m5ui.M5Label(
            "",
            x=70,
            y=150,
            text_c=0xE0E0E0,
            bg_c=0x000000,
            bg_opa=0,
            font=self._font(12),
            parent=self._page,
        )
        self._progress_bar = lv.bar(self._page)
        self._progress_bar.set_size(160, 8)
        self._progress_bar.set_pos(40, 195)
        self._progress_bar.set_range(0, 100)
        self._progress_bar.set_value(0, False)

    def on_enter(self):
        super().on_enter()
        self._scale = self.hardware.scale
        if self._page is None:
            self._build_ui()
        self._reset_state()
        self._page.screen_load()
        if self._rotary:
            self._rotary.reset()
        self._render()

    def _reset_state(self):
        self._current_step = 0
        self._adjusted_weights = list(CALIBRATION_POINTS)
        self._calibration_data = {}
        self._encoder_speed_multiplier = 1
        self._encoder_last_direction = 0
        self._encoder_momentum_count = 0
        self._last_encoder_change_time = 0
        self._measuring = False
        self._measurement_started_at = 0
        self._last_status_second = -1
        self._samples = []

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"

        if self._scale is None:
            self._status_label.set_text("Scale not found")
            return None

        if self._measuring:
            self._tick_measurement()
            return None

        if self._current_step >= len(CALIBRATION_POINTS):
            return None

        self._handle_encoder()

        button = self.hardware.button
        if button and button.was_short_pressed():
            self._start_measurement()

        return None

    def _render(self):
        if self._progress_bar:
            self._progress_bar.set_value(0, False)

        if self._current_step < len(CALIBRATION_POINTS):
            target = self._adjusted_weights[self._current_step]
            point = CALIBRATION_POINTS[self._current_step]
            self._step_label.set_text(
                "Step {}/{}: {}g".format(
                    self._current_step + 1,
                    len(CALIBRATION_POINTS),
                    point,
                )
            )
            self._info_label.set_text("Enc: adjust\nBtn: start")
            self._status_label.set_text("Target {}g".format(target))
            return

        self._step_label.set_text("Calibration complete")
        self._info_label.set_text("")
        self._status_label.set_text("Data saved")

    def _handle_encoder(self):
        if not self._rotary:
            return

        delta = self._rotary.consume_delta()
        if not delta:
            return

        current_time = time.ticks_ms()
        delta_time = time.ticks_diff(current_time, self._last_encoder_change_time)
        current_direction = 1 if delta > 0 else -1

        if delta_time < 500 and current_direction == self._encoder_last_direction:
            self._encoder_momentum_count += 1
            if self._encoder_momentum_count >= 3:
                self._encoder_speed_multiplier = 100
            elif self._encoder_momentum_count >= 2:
                self._encoder_speed_multiplier = 10
            else:
                self._encoder_speed_multiplier = 1
        else:
            if self._encoder_speed_multiplier == 100:
                self._encoder_speed_multiplier = 10
                self._encoder_momentum_count = 1
            else:
                self._encoder_speed_multiplier = 1
                self._encoder_momentum_count = 0

        self._encoder_last_direction = current_direction
        self._last_encoder_change_time = current_time

        weight = self._adjusted_weights[self._current_step]
        weight += delta * self._encoder_speed_multiplier
        self._adjusted_weights[self._current_step] = min(50000, max(0, weight))
        self._render()

    def _start_measurement(self):
        self._measuring = True
        self._measurement_started_at = time.ticks_ms()
        self._last_status_second = -1
        self._samples = []
        self._status_label.set_text("Measuring\n0/{}s".format(CALIBRATION_DURATION))
        if self._progress_bar:
            self._progress_bar.set_value(0, False)

    def _tick_measurement(self):
        adc_value = self._scale.read_raw_adc()
        if adc_value is not None:
            self._samples.append(adc_value)
            if DEBUG_MODE:
                print("ADC: {}".format(adc_value))

        elapsed_ms = time.ticks_diff(time.ticks_ms(), self._measurement_started_at)
        elapsed_s = elapsed_ms // 1000
        if elapsed_s != self._last_status_second:
            self._last_status_second = elapsed_s
            shown_s = min(CALIBRATION_DURATION, elapsed_s)
            self._status_label.set_text(
                "Measuring\n{}/{}s".format(shown_s, CALIBRATION_DURATION)
            )
            if self._progress_bar:
                pct = min(100, int((shown_s * 100) / CALIBRATION_DURATION))
                self._progress_bar.set_value(pct, False)

        if elapsed_ms >= CALIBRATION_DURATION * 1000:
            self._finish_measurement()

    def _finish_measurement(self):
        self._measuring = False
        if self._samples:
            average = sum(self._samples) / len(self._samples)
        else:
            average = 0

        weight = self._adjusted_weights[self._current_step]
        self._calibration_data[weight] = average
        self._status_label.set_text("Avg: {}".format(int(average)))
        if self._progress_bar:
            self._progress_bar.set_value(100, False)

        self._current_step += 1
        if self._current_step < len(CALIBRATION_POINTS):
            self._render()
            return

        self._render()
        if self._save_calibration_data():
            self._status_label.set_text("Calibration complete!\nData saved")

    def _save_calibration_data(self):
        try:
            calibration_points = []
            sorted_data = sorted(self._calibration_data.items(), key=lambda item: item[0])
            for step_index, item in enumerate(sorted_data):
                weight, adc_value = item
                if step_index < len(CALIBRATION_POINTS):
                    calibration_point = CALIBRATION_POINTS[step_index]
                else:
                    calibration_point = 0
                calibration_points.append(
                    {
                        "step": step_index,
                        "calibration_point": calibration_point,
                        "weight": int(weight),
                        "adc_average": float(adc_value),
                    }
                )

            data = {"scale": {"CalibrationPoints": calibration_points}}
            if DEBUG_MODE:
                print("Saving calibration data: {}".format(data))

            with open(CALIBRATION_FILE, "w") as f:
                json.dump(data, f)

            if self._scale and hasattr(self._scale, "_load_calibration"):
                self._scale._load_calibration()

            if DEBUG_MODE:
                print("Calibration data saved to {}".format(CALIBRATION_FILE))
            return True
        except Exception as exc:
            message = "Save error: {}".format(exc)
            self._status_label.set_text(message[:30])
            if DEBUG_MODE:
                print(message)
            return False
