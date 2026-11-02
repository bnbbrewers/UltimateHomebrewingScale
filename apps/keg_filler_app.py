"""
Keg filler calibration flow.
"""

import gc

import runtime_debug
# Aliased to the historical private names: they are this module's clock, and
# the fill timing tests inject a fake through them.
from ticks import ticks_add as _ticks_add, ticks_diff as _ticks_diff, ticks_ms as _ticks_ms

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
import units


# The metric picker. units.keg_volume_settings() holds the same values for
# every system, in its display unit; these stay for the metric flow and tests.
DEFAULT_VOLUME_L = 18.0
MIN_VOLUME_L = 0.5
MAX_VOLUME_L = 60.0
VOLUME_STEP_L = 0.5
VOLUME_STEP = VOLUME_STEP_L
CALIBRATION_DURATION_MS = 10000
SAMPLE_INTERVAL_MS = 200

# The filling loop is the only loop in the project that drives an actuator.
# read_weight_filtered() returns its cached value when the ADC read fails, so a
# dead load cell would otherwise hold the valve open forever. No absolute
# timeout: a legitimately slow fill must never be cut short. The stall window
# is KEG_FILL_STALL_TIMEOUT_S, clamped so the guard can never be switched off.
FILL_STALL_TOLERANCE_G = 5
DEFAULT_FILL_STALL_TIMEOUT_S = 10
MIN_FILL_STALL_TIMEOUT_S = 3
MAX_FILL_STALL_TIMEOUT_S = 600
FILL_STALL_TIMEOUT_MS = DEFAULT_FILL_STALL_TIMEOUT_S * 1000

_STATE_EMPTY_PLATFORM_ACK = 1
_STATE_KEG_SELECT = 2
_STATE_CALIBRATION_1_ACK = 3
_STATE_CALIBRATING_WEIGHT = 4
_STATE_VOLUME_SELECT = 5
_STATE_CALIBRATION_DONE_ACK = 6
_STATE_FILLING_SETUP_ACK = 7
_STATE_ERROR_ACK = 8
_STATE_FILLING = 9
_STATE_FILLING_DONE_ACK = 10
_STATE_FILLING_DONE_SELECT = 11
_STATE_FILLING_STALLED_ACK = 12
_STATE_BATCH_SELECT = 13
_STATE_WAIT_HTTP = 14

# States where the dial has no other role, so it carries the back gesture.
# The fill and its two prompts are among them only so the dial is drained:
# the gesture is ignored there, it must never lead to reopening the valve.
_DIAL_FREE_STATES = (
    _STATE_EMPTY_PLATFORM_ACK,
    _STATE_CALIBRATION_1_ACK,
    _STATE_CALIBRATING_WEIGHT,
    _STATE_CALIBRATION_DONE_ACK,
    _STATE_FILLING_SETUP_ACK,
    _STATE_ERROR_ACK,
    _STATE_FILLING,
    _STATE_FILLING_DONE_ACK,
    _STATE_FILLING_STALLED_ACK,
)
# Free-dial states where the gesture does nothing. They fall through to their
# normal tick, so the fill loop never misses a stop or stall check.
_BACK_IGNORED_STATES = (
    _STATE_CALIBRATION_DONE_ACK,
    _STATE_FILLING,
    _STATE_FILLING_DONE_ACK,
    _STATE_FILLING_STALLED_ACK,
)

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
    "FILL_STALL_TOLERANCE_G",
    "DEFAULT_FILL_STALL_TIMEOUT_S",
    "MIN_FILL_STALL_TIMEOUT_S",
    "MAX_FILL_STALL_TIMEOUT_S",
    "FILL_STALL_TIMEOUT_MS",
    "_STATE_EMPTY_PLATFORM_ACK",
    "_STATE_KEG_SELECT",
    "_STATE_CALIBRATION_1_ACK",
    "_STATE_CALIBRATING_WEIGHT",
    "_STATE_VOLUME_SELECT",
    "_STATE_CALIBRATION_DONE_ACK",
    "_STATE_FILLING_SETUP_ACK",
    "_STATE_ERROR_ACK",
    "_STATE_FILLING",
    "_STATE_FILLING_DONE_ACK",
    "_STATE_FILLING_DONE_SELECT",
    "_STATE_FILLING_STALLED_ACK",
    "DEFAULT_SPUNDING_VALVE_INERTIA_ML",
)


class KegFillerApp(BaseApp):
    APP_ID = "keg_filler_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None, keg_file=KEG_FILE):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._keg_file = keg_file
        self._http_batches = []
        self._http_batch_idx = 0
        self._fill_context = None
        self._fill_session_active = False
        self._fill_result_saved = False
        self._fill_net_g = 0
        self._simple_screen = None
        self._select_screen = None
        self._volume_screen = None
        self._weight_screen = None
        self._scale = None
        self._rotary = None
        self._relay = None
        self._state = _STATE_EMPTY_PLATFORM_ACK
        self._kegs = []
        self._reset_state()

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

    def _reset_state(self):
        """Reset every per-session field. Leaves self._kegs to the caller."""
        self._items = []
        self._selected_idx = 0
        self._pending_name = None
        self._empty_weight_g = None
        self._selected_volume_l = DEFAULT_VOLUME_L
        self._selected_keg = None
        self._filling_stop_weight_g = 0
        self._filling_done_items = []
        self._filling_done_selected_idx = 0
        self._samples = []
        self._calibration_started_at = 0
        self._next_sample_at = 0
        self._fill_reference_weight_g = None
        self._fill_reference_at = 0
        self._fill_stall_timeout_s = DEFAULT_FILL_STALL_TIMEOUT_S
        self._error_return_state = _STATE_EMPTY_PLATFORM_ACK

    def on_exit(self):
        super().on_exit()
        self._close_relay()
        if self._events:
            if self._fill_session_active and not self._fill_result_saved:
                self._save_fill_result("filling.completed" if self._state == _STATE_FILLING_DONE_ACK else "filling.cancelled")
            self._events.resume()
        self._reset_state()
        self._kegs = []
        self._scale = None
        self._rotary = None
        self._relay = None
        if self._select_screen:
            self._select_screen.set_items([])
        self._simple_screen = None
        self._select_screen = None
        self._volume_screen = None
        self._weight_screen = None
        gc.collect()
        runtime_debug.snapshot("keg.on_exit", collect=False)

    def on_enter(self):
        super().on_enter()
        self._scale = self.hardware.scale
        self._rotary = self.hardware.rotary
        # The relay driver is imported on first read of hardware.relay. Defer
        # it to _start_filling: boot_safety.force_relay_off() already drove the
        # pad low at boot, and RelayDevice.__init__ closes the relay itself.
        self._relay = None
        self._reset_state()
        self._kegs = load_kegs(self._keg_file)
        gc.collect()
        self._fill_context = None
        self._fill_session_active = False
        self._fill_result_saved = False
        if self._events:
            self._show_http_batches()
        else:
            self._show_empty_platform()
        runtime_debug.snapshot("keg.on_enter", collect=False)

    def inhibits_standby(self):
        """Hold the device awake from the moment the valve opens.

        A slow fill moves the weight by less than the standby tolerance
        between two samples, so idle detection would let the device deep
        sleep mid-fill: the valve closes safely, but the fill is cut short
        and its state is lost. The completion and stall prompts are covered
        too, since the weight is then perfectly stable by definition, and a
        stalled fill must still be resumable once the line is fixed.
        """
        return self._state in (
            _STATE_FILLING, _STATE_FILLING_DONE_ACK, _STATE_FILLING_STALLED_ACK)

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        if (self._state in _DIAL_FREE_STATES and self._check_back(self._state)
                and self._state not in _BACK_IGNORED_STATES):
            return self._on_back()

        if self._state == _STATE_BATCH_SELECT:
            return self._tick_http_batch()
        elif self._state == _STATE_WAIT_HTTP:
            self._start_filling()
        elif self._state == _STATE_EMPTY_PLATFORM_ACK:
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
        elif self._state == _STATE_FILLING_DONE_ACK:
            self._tick_filling_done_ack()
        elif self._state == _STATE_FILLING_STALLED_ACK:
            self._tick_filling_stalled_ack()
        elif self._state == _STATE_FILLING_DONE_SELECT:
            return self._tick_filling_done_select()
        return None

    def _show_http_batches(self):
        api = self.apis.get("brewing")
        if not hasattr(api, "get_plan"):
            # A webhook-only setup has no valid batch context for filling events.
            # Keep the local filler available; SCALE_API forbids unbound results.
            self._show_empty_platform()
            return
        self._http_batches = api.get_batches(phases=("packaging",))
        self._select().configure(
            title=str(api.last_error) if api.last_error else "Select packaging batch",
            items=[b.name for b in self._http_batches] or ["No packaging batches - return"],
            accent_color=_COLOR_KEG, selected_index=0)
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        self._http_batch_idx = 0
        self._state = _STATE_BATCH_SELECT

    def _tick_http_batch(self):
        if not self._http_batches:
            if self.hardware.button.was_short_pressed():
                return "launcher"
            return
        self._http_batch_idx, changed = self._rotary_navigate(self._http_batch_idx, len(self._http_batches))
        if changed:
            self._select().set_selected_index(self._http_batch_idx)
        if not self.hardware.button.was_short_pressed():
            return
        api = self.apis.get("brewing")
        try:
            plan = api.get_plan(self._http_batches[self._http_batch_idx].batch_id)
            self._fill_context = api.context(plan)
        except Exception as error:
            self._show_error(str(error), _STATE_EMPTY_PLATFORM_ACK)
            return
        self._http_batches = []
        self._show_empty_platform()

    def _event_weight(self, weight):
        if self._selected_keg:
            return weight - float(self._selected_keg["empty_weight_g"])
        return weight

    def _save_fill_result(self, kind):
        if not self._events or not self._fill_context or self._fill_result_saved:
            return True
        if self._events.complete(kind, self._fill_net_g, self._weight_stable()):
            self._fill_result_saved = True
            self._fill_session_active = False
            return True
        return False

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
        self._selected_volume_l = units.volume_display_to_l(units.keg_volume_settings()[0])
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
        # Calibration is the only user of KEG_VOLUME. Drop our reference first,
        # then let the manager delete the tree: the filling phase that follows
        # allocates WEIGHT and its 40pt binfont.
        self._volume_screen = None
        self._release_volume_screen()
        runtime_debug.snapshot("keg.volume_screen_released", collect=False)
        self._simple().configure(
            title=self.t("keg.calibrated_title"),
            message=self.t("keg.calibrated_message", self._pending_name),
            title_bg_color=_COLOR_KEG,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._state = _STATE_CALIBRATION_DONE_ACK

    def _release_volume_screen(self):
        release = getattr(self.screen_manager, "release", None)
        if not release:
            return
        try:
            release(screen_ids.KEG_VOLUME)
        except Exception:
            pass

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
            self._step_selected_volume(delta)
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
        if self._events:
            if not self._events.suspend():
                self._state = _STATE_WAIT_HTTP
                return
        if self._events and self._fill_context and not self._fill_session_active:
            if not self._events.can_record():
                self._events.resume()
                self._show_error(self._events.error, _STATE_KEG_SELECT)
                return
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
        target_weight_g = units.volume_l_to_weight_g(self._selected_keg["max_volume_l"])
        inertia_g = _spunding_valve_inertia_ml()
        self._filling_stop_weight_g = empty_weight_g + target_weight_g - inertia_g
        if self._filling_stop_weight_g < empty_weight_g:
            self._filling_stop_weight_g = empty_weight_g
        screen = self._weight()
        screen.configure(
            title=self.t("keg.filling_title", self._selected_keg["name"]),
            mode=getattr(screen, "MODE_FILLING_L", "filling_l"),
            target=target_weight_g,
            progress_target=self._filling_stop_weight_g - empty_weight_g,
            empty_weight_g=empty_weight_g,
            title_bg_color=_COLOR_KEG,
        )
        self.screen_manager.show(screen_ids.WEIGHT)
        self._fill_reference_weight_g = None
        self._fill_reference_at = _ticks_ms()
        self._fill_stall_timeout_s = _fill_stall_timeout_s()
        if self._events and self._fill_context and not self._fill_session_active:
            self._events.begin(self._fill_context)
            self._fill_session_active = True
            self._fill_result_saved = False
            self._fill_net_g = 0
        self._open_relay()
        runtime_debug.snapshot("keg.filling_started", collect=False)
        self._state = _STATE_FILLING

    def _tick_filling(self):
        weight = self._read_and_update_weight(self._weight())
        if weight is None:
            return
        if self._selected_keg:
            self._fill_net_g = max(0, weight - float(self._selected_keg["empty_weight_g"]))
        if weight >= self._filling_stop_weight_g:
            self._close_relay()
            # The valve is closed before persistence or any network work resumes.
            if self._events:
                self._save_fill_result("filling.completed")
                self._events.resume()
            self._weight().set_ok_visible(True)
            self._state = _STATE_FILLING_DONE_ACK
            return
        self._check_fill_stalled(weight)

    def _check_fill_stalled(self, weight):
        reference = self._fill_reference_weight_g
        if reference is None or abs(weight - reference) > FILL_STALL_TOLERANCE_G:
            self._fill_reference_weight_g = weight
            self._fill_reference_at = _ticks_ms()
            return
        elapsed_ms = _ticks_diff(_ticks_ms(), self._fill_reference_at)
        if elapsed_ms < self._fill_stall_timeout_s * 1000:
            return
        self._close_relay()
        self._show_filling_stalled()

    def _show_filling_done_select(self):
        # The keg is full and about to be swapped, so the next fill starts from
        # the setup prompt like any other.
        keg_name = ""
        if self._selected_keg:
            keg_name = self._selected_keg.get("name", "")
        self._filling_done_items = [
            self.t("keg.fill_same", keg_name),
            self.t("keg.fill_other"),
            self.t("keg.return_menu"),
        ]
        self._filling_done_selected_idx = 0
        self._select().configure(
            title=self.t("keg.filling_done_title"),
            items=self._filling_done_items,
            accent_color=_COLOR_KEG,
            selected_index=0,
        )
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        if self._rotary:
            self._rotary.reset()
        self._state = _STATE_FILLING_DONE_SELECT

    def _show_filling_stalled(self):
        self._simple().configure(
            title=self.t("keg.filling_stalled_title"),
            message=self.t("keg.filling_stalled_message", self._fill_stall_timeout_s),
            title_bg_color=_COLOR_KEG,
            show_ok_button=True,
            ok_label=self.t("keg.resume"),
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._state = _STATE_FILLING_STALLED_ACK

    def _tick_filling_stalled_ack(self):
        # Recovery, not a new fill: the keg is still on the platform, still
        # holding the tare this fill was measured against. Resuming must not
        # prompt the operator to place the keg, and must not re-tare.
        # _start_filling re-arms the stall window from scratch.
        if self.hardware.button.was_short_pressed():
            self._start_filling()

    def _tick_filling_done_ack(self):
        if self.hardware.button.was_short_pressed():
            if not self._save_fill_result("filling.completed"):
                self._weight().set_status(self._events.error or "Result save failed")
                return
            self._show_filling_done_select()

    def _tick_filling_done_select(self):
        if not self._filling_done_items:
            self._show_select()
            return None
        idx, changed = self._rotary_navigate(
            self._filling_done_selected_idx, len(self._filling_done_items)
        )
        if changed:
            self._filling_done_selected_idx = idx
            self._select().set_selected_index(idx)
        if not self.hardware.button.was_short_pressed():
            return None
        if idx == 0:
            self._show_filling_setup()
            return None
        if idx == 1:
            self._show_select()
            return None
        return "launcher"

    def _tick_error_ack(self):
        if self.hardware.button.was_short_pressed():
            self._leave_error()

    def _leave_error(self):
        if self._error_return_state == _STATE_CALIBRATION_1_ACK:
            self._show_calibration_step_1()
        elif self._error_return_state == _STATE_KEG_SELECT:
            self._show_select()
        else:
            self._show_empty_platform()

    def _on_back(self):
        state = self._state
        if state == _STATE_EMPTY_PLATFORM_ACK:
            return "launcher"
        if state in (_STATE_CALIBRATION_1_ACK, _STATE_FILLING_SETUP_ACK):
            self._show_select()
        elif state == _STATE_CALIBRATING_WEIGHT:
            self._samples = []
            self._show_calibration_step_1()
        elif state == _STATE_ERROR_ACK:
            self._leave_error()
        return None

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

    def _step_selected_volume(self, delta):
        """Move the picker by ``delta`` notches, in the display unit."""
        _default, minimum, maximum, step, _decimals = units.keg_volume_settings()
        # A volume converted from litres never lands exactly on the gallon
        # grid: snap it first, so the notches stay on round values.
        shown = round(units.volume_l_to_display(self._selected_volume_l) / step) * step
        shown += delta * step
        if shown < minimum:
            shown = minimum
        elif shown > maximum:
            shown = maximum
        self._set_selected_volume(units.volume_display_to_l(shown))

    def _set_selected_volume(self, volume_l):
        if volume_l == self._selected_volume_l:
            return
        self._selected_volume_l = volume_l
        self._volume().set_volume(self._selected_volume_l)

    def _acquire_relay(self):
        if self._relay is None:
            self._relay = getattr(self.hardware, "relay", None)
        return self._relay

    def _open_relay(self):
        relay = self._acquire_relay()
        if relay and hasattr(relay, "set_on"):
            relay.set_on()

    def _close_relay(self):
        # Never acquire here. on_exit runs on every app switch, and closing a
        # relay that was never opened would import the driver for nothing.
        relay = self._relay
        if relay and hasattr(relay, "set_off"):
            relay.set_off()

    def _relay_available(self):
        relay = self._acquire_relay()
        if not relay:
            return False
        if hasattr(relay, "is_available"):
            return relay.is_available()
        return True


def _spunding_valve_inertia_ml():
    try:
        value = float(runtime_debug.setting(
            "KEG_SPUNDING_VALVE_INERTIA_ML", DEFAULT_SPUNDING_VALVE_INERTIA_ML))
    except Exception:
        return DEFAULT_SPUNDING_VALVE_INERTIA_ML
    if value < 0:
        return 0
    return value


def _fill_stall_timeout_s():
    try:
        value = int(runtime_debug.setting(
            "KEG_FILL_STALL_TIMEOUT_S", DEFAULT_FILL_STALL_TIMEOUT_S))
    except Exception:
        return DEFAULT_FILL_STALL_TIMEOUT_S
    if value < MIN_FILL_STALL_TIMEOUT_S:
        return MIN_FILL_STALL_TIMEOUT_S
    if value > MAX_FILL_STALL_TIMEOUT_S:
        return MAX_FILL_STALL_TIMEOUT_S
    return value
