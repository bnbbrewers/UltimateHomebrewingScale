"""
Keg filler calibration flow.
"""

import gc
import time

from .base_app import BaseApp
from storage.keg_registry import (
    KEG_FILE,
    append_keg,
    build_select_items,
    default_keg_name,
    load_kegs,
    save_kegs,
)
from ui import screen_ids

try:
    import config
except Exception:
    config = None


DEFAULT_VOLUME_L = 18.0
MIN_VOLUME_L = 0.5
MAX_VOLUME_L = 60.0
VOLUME_STEP_L = 0.5
VOLUME_STEP = VOLUME_STEP_L
CALIBRATION_DURATION_MS = 10000
SAMPLE_INTERVAL_MS = 200

_STATE_EMPTY_PLATFORM_ACK = 1
_STATE_KEG_SELECT = 2
_STATE_CALIBRATION_1_ACK = 3
_STATE_CALIBRATING_WEIGHT = 4
_STATE_VOLUME_SELECT = 5
_STATE_CALIBRATION_DONE_ACK = 6
_STATE_FILLING_SETUP_ACK = 7
_STATE_ERROR_ACK = 8
_STATE_FILLING = 9

DEFAULT_SPUNDING_VALVE_INERTIA_ML = 200

_COLOR_KEG = 0x607D8B

__all__ = (
    "KegFillerApp",
    "DEFAULT_VOLUME_L",
    "MIN_VOLUME_L",
    "MAX_VOLUME_L",
    "VOLUME_STEP",
    "VOLUME_STEP_L",
    "CALIBRATION_DURATION_MS",
    "SAMPLE_INTERVAL_MS",
    "_STATE_EMPTY_PLATFORM_ACK",
    "_STATE_KEG_SELECT",
    "_STATE_CALIBRATION_1_ACK",
    "_STATE_CALIBRATING_WEIGHT",
    "_STATE_VOLUME_SELECT",
    "_STATE_CALIBRATION_DONE_ACK",
    "_STATE_FILLING_SETUP_ACK",
    "_STATE_ERROR_ACK",
    "_STATE_FILLING",
    "DEFAULT_SPUNDING_VALVE_INERTIA_ML",
)


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.time() * 1000)


def _ticks_add(ticks, delta):
    if hasattr(time, "ticks_add"):
        return time.ticks_add(ticks, delta)
    return ticks + delta


def _ticks_diff(left, right):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(left, right)
    return left - right


class KegFillerApp(BaseApp):
    APP_ID = "keg_filler_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None, keg_file=KEG_FILE):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._keg_file = keg_file
        self._simple_screen = None
        self._select_screen = None
        self._volume_screen = None
        self._weight_screen = None
        self._scale = None
        self._rotary = None
        self._relay = None
        self._state = _STATE_EMPTY_PLATFORM_ACK
        self._kegs = []
        self._items = []
        self._selected_idx = 0
        self._pending_name = None
        self._empty_weight_g = None
        self._selected_volume_l = DEFAULT_VOLUME_L
        self._selected_keg = None
        self._filling_stop_weight_g = 0
        self._samples = []
        self._calibration_started_at = 0
        self._next_sample_at = 0
        self._error_return_state = _STATE_EMPTY_PLATFORM_ACK

    def _simple(self):
        if self._simple_screen is None:
            self._simple_screen = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        return self._simple_screen

    def _select(self):
        if self._select_screen is None:
            self._select_screen = self.screen_manager.get(screen_ids.SELECT_ITEM)
        return self._select_screen

    def _volume(self):
        if self._volume_screen is None:
            self._volume_screen = self.screen_manager.get(screen_ids.KEG_VOLUME)
        return self._volume_screen

    def _weight(self):
        if self._weight_screen is None:
            self._weight_screen = self.screen_manager.get(screen_ids.WEIGHT)
        return self._weight_screen

    def on_exit(self):
        super().on_exit()
        self._close_relay()
        self._kegs = []
        self._items = []
        self._samples = []
        self._pending_name = None
        self._empty_weight_g = None
        self._scale = None
        self._rotary = None
        self._relay = None
        self._selected_keg = None
        self._filling_stop_weight_g = 0
        if self._select_screen:
            self._select_screen.set_items([])
        self._simple_screen = None
        self._select_screen = None
        self._volume_screen = None
        self._weight_screen = None
        gc.collect()

    def on_enter(self):
        super().on_enter()
        self._scale = self.hardware.scale
        self._rotary = self.hardware.rotary
        self._relay = getattr(self.hardware, "relay", None)
        self._close_relay()
        self._kegs = load_kegs(self._keg_file)
        gc.collect()
        self._items = []
        self._selected_idx = 0
        self._pending_name = None
        self._empty_weight_g = None
        self._selected_volume_l = DEFAULT_VOLUME_L
        self._selected_keg = None
        self._filling_stop_weight_g = 0
        self._samples = []
        self._show_empty_platform()

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"

        if self._state == _STATE_EMPTY_PLATFORM_ACK:
            self._tick_empty_platform_ack()
        elif self._state == _STATE_KEG_SELECT:
            self._tick_keg_select()
        elif self._state == _STATE_CALIBRATION_1_ACK:
            self._tick_calibration_1_ack()
        elif self._state == _STATE_CALIBRATING_WEIGHT:
            self._tick_calibrating_weight()
        elif self._state == _STATE_VOLUME_SELECT:
            self._tick_volume_select()
        elif self._state == _STATE_CALIBRATION_DONE_ACK:
            self._tick_calibration_done_ack()
        elif self._state == _STATE_FILLING_SETUP_ACK:
            self._tick_filling_setup_ack()
        elif self._state == _STATE_ERROR_ACK:
            self._tick_error_ack()
        elif self._state == _STATE_FILLING:
            self._tick_filling()
        return None

    def _show_empty_platform(self):
        self._simple().configure(
            title=self.t("keg.title"),
            message=self.t("keg.empty_platform"),
            title_bg_color=_COLOR_KEG,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._state = _STATE_EMPTY_PLATFORM_ACK

    def _show_select(self):
        self._items = build_select_items(self._kegs, self.t("keg.add"))
        if self._selected_idx >= len(self._items):
            self._selected_idx = max(0, len(self._items) - 1)
        self._select().configure(
            title=self.t("keg.select_title"),
            items=self._items,
            accent_color=_COLOR_KEG,
            selected_index=self._selected_idx,
        )
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        if self._rotary:
            self._rotary.reset()
        self._state = _STATE_KEG_SELECT

    def _show_calibration_step_1(self):
        self._simple().configure(
            title=self.t("keg.calibration_step_1_title"),
            message=self.t("keg.calibration_step_1_message"),
            title_bg_color=_COLOR_KEG,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._state = _STATE_CALIBRATION_1_ACK

    def _show_calibrating(self):
        self._simple().configure(
            title=self.t("keg.calibration_step_1_title"),
            message=self.t("keg.calibration_in_progress"),
            title_bg_color=_COLOR_KEG,
            show_ok_button=False,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)

    def _show_volume_select(self):
        self._selected_volume_l = DEFAULT_VOLUME_L
        self._volume().configure(
            title=self.t("keg.calibration_step_2_title"),
            volume_l=self._selected_volume_l,
            title_bg_color=_COLOR_KEG,
        )
        self.screen_manager.show(screen_ids.KEG_VOLUME)
        if self._rotary:
            self._rotary.reset()
        self._state = _STATE_VOLUME_SELECT

    def _show_filling_setup(self):
        keg = self._kegs[self._selected_idx]
        self._selected_keg = keg
        self._simple().configure(
            title=self.t("keg.filling_title", keg["name"]),
            message=self.t("keg.filling_setup_message"),
            title_bg_color=_COLOR_KEG,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._state = _STATE_FILLING_SETUP_ACK

    def _show_calibration_done(self):
        self._simple().configure(
            title=self.t("keg.calibrated_title"),
            message=self.t("keg.calibrated_message", self._pending_name),
            title_bg_color=_COLOR_KEG,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._state = _STATE_CALIBRATION_DONE_ACK

    def _show_error(self, message_key, return_state):
        self._error_return_state = return_state
        self._simple().configure(
            title=self.t("keg.error_title"),
            message=self.t(message_key),
            title_bg_color=_COLOR_KEG,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._state = _STATE_ERROR_ACK

    def _tick_empty_platform_ack(self):
        if not self.hardware.button.was_short_pressed():
            return
        if not self._scale:
            self._show_error("keg.scale_not_found", _STATE_EMPTY_PLATFORM_ACK)
            return
        if not self._scale.tare():
            self._show_error("keg.tare_error", _STATE_EMPTY_PLATFORM_ACK)
            return
        self._show_select()

    def _tick_keg_select(self):
        if not self._items:
            return
        self._selected_idx, changed = self._rotary_navigate(self._selected_idx, len(self._items))
        if changed:
            self._select().set_selected_index(self._selected_idx)
        if not self.hardware.button.was_short_pressed():
            return
        if self._selected_idx == len(self._items) - 1:
            self._pending_name = default_keg_name(self._kegs)
            self._show_calibration_step_1()
        else:
            self._show_filling_setup()

    def _tick_calibration_1_ack(self):
        if not self.hardware.button.was_short_pressed():
            return
        now = _ticks_ms()
        self._samples = []
        self._calibration_started_at = now
        self._next_sample_at = _ticks_add(now, SAMPLE_INTERVAL_MS)
        self._show_calibrating()
        self._state = _STATE_CALIBRATING_WEIGHT

    def _tick_calibrating_weight(self):
        now = _ticks_ms()
        if _ticks_diff(now, self._calibration_started_at) >= CALIBRATION_DURATION_MS:
            self._finish_calibration()
            return
        if _ticks_diff(now, self._next_sample_at) < 0:
            return
        self._next_sample_at = _ticks_add(now, SAMPLE_INTERVAL_MS)
        if not self._scale:
            return
        sample = self._scale.read_weight_filtered()
        if sample is not None:
            self._samples.append(float(sample))

    def _finish_calibration(self):
        if not self._samples:
            self._show_error("keg.calibration_no_sample", _STATE_CALIBRATION_1_ACK)
            return
        self._empty_weight_g = sum(self._samples) / len(self._samples)
        self._show_volume_select()

    def _tick_volume_select(self):
        delta = self._consume_rotary_delta()
        if delta:
            self._set_selected_volume(self._selected_volume_l + (delta * VOLUME_STEP_L))
        if not self.hardware.button.was_short_pressed():
            return
        updated = append_keg(
            self._kegs,
            self._pending_name,
            self._empty_weight_g,
            self._selected_volume_l,
        )
        if not save_kegs(self._keg_file, updated):
            self._show_error("keg.save_error", _STATE_KEG_SELECT)
            return
        self._kegs = updated
        self._selected_idx = len(self._kegs) - 1
        self._show_calibration_done()

    def _tick_calibration_done_ack(self):
        if self.hardware.button.was_short_pressed():
            self._selected_idx = len(self._kegs) - 1
            self._show_select()

    def _tick_filling_setup_ack(self):
        if self.hardware.button.was_short_pressed():
            self._start_filling()

    def _start_filling(self):
        if not self._scale:
            self._show_error("keg.scale_not_found", _STATE_KEG_SELECT)
            return
        if not self._relay_available():
            self._show_error("keg.relay_not_found", _STATE_KEG_SELECT)
            return
        if not self._selected_keg:
            self._show_select()
            return
        empty_weight_g = float(self._selected_keg["empty_weight_g"])
        target_weight_g = float(self._selected_keg["max_volume_l"]) * 1000.0
        inertia_g = _spunding_valve_inertia_ml()
        self._filling_stop_weight_g = empty_weight_g + target_weight_g - inertia_g
        if self._filling_stop_weight_g < empty_weight_g:
            self._filling_stop_weight_g = empty_weight_g
        screen = self._weight()
        screen.configure(
            title=self.t("keg.filling_title", self._selected_keg["name"]),
            mode=getattr(screen, "MODE_FILLING_L", "filling_l"),
            target=target_weight_g,
            empty_weight_g=empty_weight_g,
            title_bg_color=_COLOR_KEG,
        )
        self.screen_manager.show(screen_ids.WEIGHT)
        self._open_relay()
        self._state = _STATE_FILLING

    def _tick_filling(self):
        weight = self._read_and_update_weight(self._weight())
        if weight is None:
            return
        if weight >= self._filling_stop_weight_g:
            self._close_relay()

    def _tick_error_ack(self):
        if not self.hardware.button.was_short_pressed():
            return
        if self._error_return_state == _STATE_CALIBRATION_1_ACK:
            self._show_calibration_step_1()
        elif self._error_return_state == _STATE_KEG_SELECT:
            self._show_select()
        else:
            self._show_empty_platform()

    def _consume_rotary_delta(self):
        if not self._rotary:
            return 0
        if hasattr(self._rotary, "consume_delta"):
            return self._rotary.consume_delta()
        if hasattr(self._rotary, "get_rotary_value"):
            delta = self._rotary.get_rotary_value()
            if delta and hasattr(self._rotary, "reset_rotary_value"):
                self._rotary.reset_rotary_value()
            return delta
        return 0

    def _set_selected_volume(self, volume_l):
        if volume_l < MIN_VOLUME_L:
            volume_l = MIN_VOLUME_L
        elif volume_l > MAX_VOLUME_L:
            volume_l = MAX_VOLUME_L
        if volume_l == self._selected_volume_l:
            return
        self._selected_volume_l = volume_l
        self._volume().set_volume(self._selected_volume_l)

    def _open_relay(self):
        if self._relay and hasattr(self._relay, "set_on"):
            self._relay.set_on()

    def _close_relay(self):
        if self._relay and hasattr(self._relay, "set_off"):
            self._relay.set_off()

    def _relay_available(self):
        if not self._relay:
            return False
        if hasattr(self._relay, "is_available"):
            return self._relay.is_available()
        return True


def _spunding_valve_inertia_ml():
    if config is None:
        return DEFAULT_SPUNDING_VALVE_INERTIA_ML
    try:
        value = float(getattr(config, "KEG_SPUNDING_VALVE_INERTIA_ML", DEFAULT_SPUNDING_VALVE_INERTIA_ML))
    except Exception:
        return DEFAULT_SPUNDING_VALVE_INERTIA_ML
    if value < 0:
        return 0
    return value
