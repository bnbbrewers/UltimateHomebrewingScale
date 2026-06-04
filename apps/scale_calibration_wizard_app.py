"""
Hidden scale calibration wizard app.

Keeps calibration state and hardware flow here, while screen widgets live in
ui.scale_calibration_wizard_screen.
"""

import json
import time

from .base_app import BaseApp
from ui import screen_ids
from memory_debug import snapshot as mem_snapshot


CALIBRATION_POINTS = [0, 500, 5000, 20000]
CALIBRATION_DURATION = 30
CALIBRATION_FILE = "scale_calibration.json"
SAMPLE_INTERVAL_MS = 100
MEM_SNAPSHOT_INTERVAL_MS = 5000
INTRO_COLOR = 0x00897B

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

        self._screen = None
        self._intro_acknowledged = False

        self._current_step = 0
        self._adjusted_weights = list(CALIBRATION_POINTS)
        self._calibration_data = {}

        self._encoder_speed_multiplier = 1
        self._encoder_last_direction = 0
        self._encoder_momentum_count = 0
        self._last_encoder_change_time = 0

        self._measuring = False
        self._measurement_started_at = 0
        self._next_sample_at = 0
        self._next_mem_snapshot_at = 0
        self._last_status_second = -1
        self._sample_sum = 0
        self._sample_count = 0
        self._waiting_restart_confirmation = False

    def on_enter(self):
        super().on_enter()
        self._scale = self.hardware.scale
        self._reset_state()
        self._show_intro()
        self._mem_snapshot("calibration.on_enter", collect=True)

    def _reset_state(self):
        self._intro_acknowledged = False
        self._current_step = 0
        self._adjusted_weights = list(CALIBRATION_POINTS)
        self._calibration_data = {}
        self._encoder_speed_multiplier = 1
        self._encoder_last_direction = 0
        self._encoder_momentum_count = 0
        self._last_encoder_change_time = 0
        self._measuring = False
        self._measurement_started_at = 0
        self._next_sample_at = 0
        self._next_mem_snapshot_at = 0
        self._last_status_second = -1
        self._sample_sum = 0
        self._sample_count = 0
        self._waiting_restart_confirmation = False

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"

        if self._waiting_restart_confirmation:
            button = self.hardware.button
            if button and button.was_short_pressed():
                self._soft_reset()
            return None

        if not self._intro_acknowledged:
            button = self.hardware.button
            if button and button.was_short_pressed():
                self._intro_acknowledged = True
                self._show_wizard()
            return None

        if self._scale is None:
            self._screen.render_error(self._t("scale_calibration.scale_not_found"))
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

    def _show_intro(self):
        screen = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        if not screen:
            self._intro_acknowledged = True
            self._show_wizard()
            return
        screen.configure(
            title=self._t("scale_calibration.title"),
            message=self._lines(
                "scale_calibration.intro_message_line1",
                "scale_calibration.intro_message_line2",
            ),
            title_bg_color=INTRO_COLOR,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._flush_lvgl()

    def _show_wizard(self):
        if self._screen is None:
            self._screen = self.screen_manager.get(screen_ids.CALIBRATION_WIZARD)
        self.screen_manager.show(screen_ids.CALIBRATION_WIZARD)
        if self._rotary:
            self._rotary.reset()
        self._render()

    def _render(self):
        if self._current_step < len(CALIBRATION_POINTS):
            target = self._adjusted_weights[self._current_step]
            point = CALIBRATION_POINTS[self._current_step]
            self._screen.render_step(
                self._current_step,
                len(CALIBRATION_POINTS),
                point,
                target,
            )
            return

        self._screen.render_complete()

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
        now = time.ticks_ms()
        self._measuring = True
        self._measurement_started_at = now
        self._next_sample_at = now
        self._next_mem_snapshot_at = time.ticks_add(now, MEM_SNAPSHOT_INTERVAL_MS)
        self._last_status_second = -1
        self._sample_sum = 0
        self._sample_count = 0
        self._screen.render_measuring(0, CALIBRATION_DURATION)
        self._mem_snapshot("calibration.measurement.start", collect=True)

    def _tick_measurement(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_sample_at) >= 0:
            adc_value = self._scale.read_raw_adc()
            self._next_sample_at = time.ticks_add(now, SAMPLE_INTERVAL_MS)
            if adc_value is not None:
                self._sample_sum += adc_value
                self._sample_count += 1
                if DEBUG_MODE:
                    print("ADC: {}".format(adc_value))

        if time.ticks_diff(now, self._next_mem_snapshot_at) >= 0:
            self._mem_snapshot("calibration.measurement.tick", collect=False)
            self._next_mem_snapshot_at = time.ticks_add(now, MEM_SNAPSHOT_INTERVAL_MS)

        elapsed_ms = time.ticks_diff(now, self._measurement_started_at)
        elapsed_s = elapsed_ms // 1000
        if elapsed_s != self._last_status_second:
            self._last_status_second = elapsed_s
            self._screen.render_measuring(elapsed_s, CALIBRATION_DURATION)

        if elapsed_ms >= CALIBRATION_DURATION * 1000:
            self._finish_measurement()

    def _finish_measurement(self):
        self._measuring = False
        self._mem_snapshot("calibration.measurement.finish.before_average", collect=True)
        if self._sample_count:
            average = self._sample_sum / self._sample_count
        else:
            average = 0
        self._sample_sum = 0
        self._sample_count = 0
        self._mem_snapshot("calibration.measurement.finish.after_clear", collect=True)

        weight = self._adjusted_weights[self._current_step]
        self._calibration_data[weight] = average
        self._screen.render_average(average)

        self._current_step += 1
        if self._current_step < len(CALIBRATION_POINTS):
            self._render()
            return

        self._render()
        save_ok = self._save_calibration_data()
        self._show_restart_prompt(save_ok)

    def _show_restart_prompt(self, save_ok):
        if save_ok:
            message = self._t("scale_calibration.restart_after_success")
        else:
            message = self._t("scale_calibration.restart_after_save_error")

        screen = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        if not screen:
            return
        screen.configure(
            title=self._t("scale_calibration.title"),
            message=message,
            title_bg_color=INTRO_COLOR,
            show_ok_button=True,
        )
        self._waiting_restart_confirmation = True
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._flush_lvgl()

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
            self._mem_snapshot("calibration.saved", collect=True)
            return True
        except Exception as exc:
            message = self._t("scale_calibration.save_error", exc)
            if DEBUG_MODE:
                print(message)
            return False

    def _soft_reset(self):
        import machine

        if hasattr(machine, "soft_reset"):
            machine.soft_reset()
        else:
            machine.reset()

    def _t(self, key, *args):
        if self.i18n:
            return self.i18n.t(key, *args)
        if key == "scale_calibration.scale_not_found":
            return "Scale not found"
        if key == "scale_calibration.title":
            return "Scale Calibration"
        if key == "scale_calibration.intro_message_line1":
            return "Connect your scale"
        if key == "scale_calibration.intro_message_line2":
            return "OK to continue"
        if key == "scale_calibration.complete_saved_line1":
            return "Calibration complete!"
        if key == "scale_calibration.complete_saved_line2":
            return "Data saved"
        if key == "scale_calibration.restart_after_success":
            return "Calibration complete, OK to restart"
        if key == "scale_calibration.restart_after_save_error":
            return "Calibration file save error"
        if key == "scale_calibration.save_error":
            return "Save error: {}".format(*args)
        return key

    def _mem_snapshot(self, tag, collect=False):
        mem_snapshot(tag, enabled=DEBUG_MODE, collect=collect)

    def _lines(self, key1, key2):
        return self._t(key1) + "\n" + self._t(key2)
