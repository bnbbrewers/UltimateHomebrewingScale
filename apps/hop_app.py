"""
Memory-safe hop assistant app (business logic only).
"""

import gc

import runtime_debug

from .recipe_app import RecipeApp
from ui import screen_ids

_STATE_RECIPE = 1
_STATE_PREP_ACK = 2
_STATE_SELECT_HOP = 3
_STATE_SELECT_STEP = 4
_STATE_PLACE_RECIPIENT_ACK = 5
_STATE_WEIGHT = 6
_STATE_HOP_DONE_ACK = 7
_STATE_ALL_DONE_ACK = 8
_STATE_LOADING_RECIPES = 9
_COLOR_HOP = 0x388E3C


def _hop_weight_tolerance():
    return runtime_debug.setting("HOP_WEIGHT_TOLERANCE", 1)


class _HopNameItems:
    def __init__(self, hops_list):
        self._hops_list = hops_list

    def __len__(self):
        return len(self._hops_list)

    def __getitem__(self, index):
        return self._hops_list[index]["name"]


class _HopStepItems:
    def __init__(self, app, steps):
        self._app = app
        self._steps = steps

    def __len__(self):
        return len(self._steps)

    def __getitem__(self, index):
        step_name, amount = self._steps[index]
        vessel_number = self._app._vessel_number_for_step(step_name)
        return self._app._step_line(vessel_number, step_name, amount)


class HopAssistantApp(RecipeApp):
    APP_ID = "hop_app"
    COLOR = _COLOR_HOP
    TITLE_KEY = "hop.title"
    TRACE_PREFIX = "hop"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._api = self.apis.get("brewing")
        self._rotary = self.hardware.rotary
        self._scale = self.hardware.scale

        self._select_screen = None
        self._weigh_screen = None

        self._state = _STATE_RECIPE
        self._batches = []
        self._batch_idx = 0
        self._batch_id = None
        self._prep_flow_active = False
        self._hops_list = []
        self._vessel_numbers_by_step = {}
        self._current_hop_idx = 0
        self._step_idx = 0
        self._target_g = 0
        self._last_in_range = None

    def on_exit(self):
        super().on_exit()
        self._batches = []
        self._hops_list = []
        self._vessel_numbers_by_step = {}
        self._batch_id = None
        self._prep_flow_active = False
        if self._select_screen:
            self._select_screen.set_items([])
        self._select_screen = None
        self._weigh_screen = None
        gc.collect()
        runtime_debug.snapshot("hop.on_exit.after_cleanup", collect=False)

    def on_enter(self):
        super().on_enter()
        self._state = _STATE_LOADING_RECIPES
        gc.collect()
        self.screen_manager.memory_cleanup(
            loading_message=self.t("recipe.loading_recipes"),
            loading_color=_COLOR_HOP,
        )

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        if self._state == _STATE_LOADING_RECIPES:
            self._load_batches()
        elif self._state == _STATE_RECIPE:
            return self._tick_recipe()
        elif self._state == _STATE_PREP_ACK:
            return self._tick_ack(self._on_prep_ok)
        elif self._state == _STATE_SELECT_HOP:
            self._tick_select_hop()
        elif self._state == _STATE_SELECT_STEP:
            self._tick_select_step()
        elif self._state == _STATE_PLACE_RECIPIENT_ACK:
            return self._tick_ack(self._start_weighing)
        elif self._state == _STATE_WEIGHT:
            return self._tick_weight()
        elif self._state == _STATE_HOP_DONE_ACK:
            return self._tick_ack(self._on_hop_done_ok)
        elif self._state == _STATE_ALL_DONE_ACK:
            return self._tick_ack(None)
        return None

    # ── generic ack handler ────────────────────────────────────────

    def _tick_ack(self, on_ok):
        if self.hardware.button.was_short_pressed():
            if on_ok:
                return on_ok()
            return "launcher"
        return None

    def _on_prep_ok(self):
        if self._prep_flow_active and self._batch_id and self._api:
            self._prep_flow_active = False
            self._enter_hop_weighing_flow()
            return None
        return "launcher"

    def _on_hop_done_ok(self):
        if not self._hops_list:
            self._show_msg(
                self.t("hop.title"), self.t("hop.all_hops_weighed"),
                _COLOR_HOP, show_ok=True)
            self._state = _STATE_ALL_DONE_ACK
        else:
            self._current_hop_idx = 0
            self._step_idx = 0
            self._show_hop_select()
        return None

    # ── flow ───────────────────────────────────────────────────────

    def _enter_hop_weighing_flow(self):
        if not self._hops_list:
            self._show_msg(
                self.t("hop.title"), self.t("hop.no_hops"),
                _COLOR_HOP, show_ok=True)
            self._prep_flow_active = False
            self._state = _STATE_PREP_ACK
            return
        self._show_hop_select()
        if self._rotary:
            self._rotary.reset()
        runtime_debug.log("[MEM] hop.sessions_ready hops={}", len(self._hops_list))
        runtime_debug.snapshot("hop.sessions_ready", collect=False)

    def _reload_hops_list(self):
        self._hops_list = self._fetch_hops_list()
        gc.collect()

    # ── display helpers ────────────────────────────────────────────

    @staticmethod
    def _fmt_g(amount):
        a = float(amount)
        if abs(a - round(a)) < 0.05:
            return str(int(round(a)))
        t = "{:.1f}".format(a)
        return t[:-2] if t.endswith(".0") else t

    def _step_line(self, vessel_number, sn, amt):
        return self.t("hop.step_line", vessel_number, sn, self._fmt_g(amt))

    @staticmethod
    def _to_target_g(amount):
        a = float(amount)
        g = int(round(a))
        if g == 0 and a > 0:
            g = int(round(a * 1000))
        return max(0, g)

    def _show_hop_select(self):
        names = _HopNameItems(self._hops_list)
        self._current_hop_idx = min(self._current_hop_idx, max(0, len(names) - 1))
        self._select().configure(
            title=self.t("hop.select_hop"), items=names,
            accent_color=_COLOR_HOP, selected_index=self._current_hop_idx)
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        if self._rotary:
            self._rotary.reset()
        self._state = _STATE_SELECT_HOP

    def _show_step_select(self):
        hop = self._hops_list[self._current_hop_idx]
        lines = _HopStepItems(self, hop["steps"])
        self._step_idx = min(self._step_idx, max(0, len(lines) - 1))
        self._select().configure(
            title=hop["name"], items=lines,
            accent_color=_COLOR_HOP, selected_index=self._step_idx)
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        if self._rotary:
            self._rotary.reset()
        self._state = _STATE_SELECT_STEP

    # ── tick handlers ──────────────────────────────────────────────

    def _tick_recipe(self):
        if not self._batches:
            if self.hardware.button.was_short_pressed():
                return "launcher"
            return
        self._batch_idx, changed = self._rotary_navigate(self._batch_idx, len(self._batches))
        if changed:
            self._select().set_selected_index(self._batch_idx)
        if self.hardware.button.was_short_pressed():
            self._load_hops()

    def _tick_select_hop(self):
        if not self._hops_list:
            return
        self._current_hop_idx, changed = self._rotary_navigate(
            self._current_hop_idx, len(self._hops_list))
        if changed:
            self._select().set_selected_index(self._current_hop_idx)
        if self.hardware.button.was_short_pressed():
            self._step_idx = 0
            self._show_step_select()

    def _tick_select_step(self):
        hop = self._hops_list[self._current_hop_idx]
        steps = hop["steps"]
        if not steps:
            return
        self._step_idx, changed = self._rotary_navigate(self._step_idx, len(steps))
        if changed:
            self._select().set_selected_index(self._step_idx)
        if self.hardware.button.was_short_pressed():
            self._show_place_recipient_prompt()

    def _tick_weight(self):
        if self._weighing_reached_target(_hop_weight_tolerance()):
            return self._complete_current_step()
        return None

    # ── weighing ───────────────────────────────────────────────────

    def _show_place_recipient_prompt(self):
        hop = self._hops_list[self._current_hop_idx]
        step = hop["steps"][self._step_idx]
        vessel_number = self._vessel_number_for_step(step[0])
        self._show_msg(
            self.t("hop.title"),
            self.t("hop.place_recipient", vessel_number),
            _COLOR_HOP,
            show_ok=True,
        )
        self._state = _STATE_PLACE_RECIPIENT_ACK

    def _start_weighing(self):
        hop = self._hops_list[self._current_hop_idx]
        step = hop["steps"][self._step_idx]
        vessel_number = self._vessel_number_for_step(step[0])
        self._begin_weighing(
            self.t("hop.weigh_title", hop["name"], vessel_number),
            self._to_target_g(step[1]),
            _hop_weight_tolerance(),
            _STATE_WEIGHT,
        )
        runtime_debug.log("[MEM] hop.start_weigh hop={} target={}g",
            hop["name"], self._target_g)
        runtime_debug.snapshot("hop.start_weigh", collect=False)

    def _complete_current_step(self):
        hop = self._hops_list[self._current_hop_idx]
        hop_name = hop["name"]
        hop["steps"].pop(self._step_idx)
        gc.collect()
        runtime_debug.log("[MEM] hop.step_done hop={} remaining={}",
            hop_name, len(hop["steps"]))
        runtime_debug.snapshot("hop.step_done", collect=False)
        if hop["steps"]:
            if self._step_idx >= len(hop["steps"]):
                self._step_idx = len(hop["steps"]) - 1
            self._show_step_select()
            return None
        del self._hops_list[self._current_hop_idx]
        if self._current_hop_idx >= len(self._hops_list):
            self._current_hop_idx = max(0, len(self._hops_list) - 1)
        self._step_idx = 0
        self._show_msg(
            self.t("hop.title"), self.t("hop.hop_weighed", hop_name),
            _COLOR_HOP, show_ok=True)
        self._state = _STATE_HOP_DONE_ACK
        return None

    # ── API loading ────────────────────────────────────────────────

    def _load_batches(self):
        super()._load_batches(self._load_hops, _STATE_RECIPE)

    def _fetch_hops_list(self):
        if not self._api:
            return []
        hops_list = self._api.get_hops_list(self._batch_id)
        if getattr(self._api, "last_error", None) is not None:
            return []
        if not hops_list:
            return []
        return hops_list

    def _show_network_error(self):
        self._show_msg(
            self.t("hop.title"), self.t("common.network_error"),
            _COLOR_HOP, show_ok=True)
        self._prep_flow_active = False
        self._state = _STATE_PREP_ACK

    @staticmethod
    def _build_step_vessel_numbers(hops_list):
        vessel_numbers = {}
        for hop in hops_list:
            for step_name, _amount in hop.get("steps", []):
                if step_name not in vessel_numbers:
                    vessel_numbers[step_name] = len(vessel_numbers) + 1
        return vessel_numbers

    def _vessel_number_for_step(self, step_name):
        return self._vessel_numbers_by_step.get(step_name, 0)

    @staticmethod
    def _count_distinct_steps(hops_list):
        return len(HopAssistantApp._build_step_vessel_numbers(hops_list))

    def _load_hops(self):
        self._batch_id = self._batches[self._batch_idx].batch_id
        self._batches = []
        self._release_screens_for_hops_loading()
        gc.collect()
        runtime_debug.snapshot("hop.load_hops.pre_api", collect=False)
        self._hops_list = self._fetch_hops_list()
        if self._api_failed():
            self._show_network_error()
            return
        self._finish_hops_load()

    def _finish_hops_load(self):
        self._vessel_numbers_by_step = self._build_step_vessel_numbers(self._hops_list)
        recipient_count = len(self._vessel_numbers_by_step)
        gc.collect()
        runtime_debug.snapshot("hop.load_hops.post_api", collect=False)

        if recipient_count > 0:
            self._show_msg(
                self.t("hop.title"),
                self.t("hop.prepare_recipients", recipient_count),
                _COLOR_HOP, show_ok=True)
            self._prep_flow_active = True
            self._state = _STATE_PREP_ACK
        else:
            self._show_msg(
                self.t("hop.title"), self.t("hop.no_hops"),
                _COLOR_HOP, show_ok=True)
            self._prep_flow_active = False
            self._state = _STATE_PREP_ACK

        if self._rotary:
            self._rotary.reset()
        runtime_debug.log("[MEM] hop.hops_loaded recipients={}", recipient_count)
        runtime_debug.snapshot("hop.hops_loaded", collect=False)

    def _release_screens_for_hops_loading(self):
        self._release_screens_before_loading(self.t("hop.loading_hops"))
