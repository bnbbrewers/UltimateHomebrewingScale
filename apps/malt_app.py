"""
Memory-safe grain assistant app (business logic only).
"""

import gc
import time

import runtime_debug

from .recipe_app import RecipeApp
from ui import screen_ids

_STATE_RECIPE = 1
_STATE_MALT = 2
_STATE_WEIGHT = 3
_STATE_DONE = 4
_STATE_MESSAGE_ACK = 5
_STATE_LOADING_RECIPES = 6
_STATE_PLACE_RECIPIENT_ACK = 7
_COLOR_MALT = 0xD4840A
_COLOR_RECIPE = _COLOR_MALT


def _grain_weight_tolerance():
    return runtime_debug.setting("GRAIN_WEIGHT_TOLERANCE", 10)


class GrainAssistantApp(RecipeApp):
    APP_ID = "malt_app"
    COLOR = _COLOR_MALT
    TITLE_KEY = "grain.title"
    TRACE_PREFIX = "grain"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._api = self.apis.get("brewing")
        self._scale = self.hardware.scale
        self._rotary = self.hardware.rotary

        self._select_screen = None
        self._weigh_screen = None

        self._state = _STATE_RECIPE
        self._batches = []
        self._batch_idx = 0
        self._malts = []
        self._malt_idx = 0
        self._target_g = 0
        self._done_at = 0
        self._last_in_range = None

    def on_exit(self):
        super().on_exit()
        self._batches = []
        self._malts = []
        if self._select_screen:
            self._select_screen.set_items([])
        gc.collect()
        runtime_debug.log("[MEM] grain.on_exit after_cleanup free={}", runtime_debug.mem_free())

    def on_enter(self):
        super().on_enter()
        self._select_screen = None
        self._weigh_screen = None
        self._state = _STATE_LOADING_RECIPES
        gc.collect()
        self.screen_manager.memory_cleanup(
            loading_message=self.t("recipe.loading_recipes"),
            loading_color=_COLOR_RECIPE,
        )

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        if self._state == _STATE_LOADING_RECIPES:
            self._load_batches()
        elif self._state == _STATE_RECIPE:
            return self._tick_recipe()
        elif self._state == _STATE_MALT:
            self._tick_malt()
        elif self._state == _STATE_PLACE_RECIPIENT_ACK:
            self._tick_ack(self._start_weighing)
        elif self._state == _STATE_WEIGHT:
            self._tick_weigh()
        elif self._state == _STATE_DONE:
            if time.ticks_diff(time.ticks_ms(), self._done_at) >= 2000:
                return "launcher"
        elif self._state == _STATE_MESSAGE_ACK:
            if self.hardware.button.was_short_pressed():
                return "launcher"
        return None

    # ── loading / display ──────────────────────────────────────────

    def _load_batches(self):
        super()._load_batches(self._load_malts, _STATE_RECIPE)

    def _load_malts(self):
        batch_id = self._batches[self._batch_idx].batch_id
        self._batches = []
        self._release_screens_for_malt_loading()
        gc.collect()

        self._malts = self._api.get_malts(batch_id) if self._api else []
        if self._api_failed():
            self._show_network_error()
            return
        gc.collect()
        self._malt_idx = 0
        names = [m.name for m in self._malts]

        if names:
            self._select().configure(
                title=self.t("grain.select_malt"), items=names,
                accent_color=_COLOR_MALT, selected_index=0)
            self.screen_manager.show(screen_ids.SELECT_ITEM)
            self._state = _STATE_MALT
        elif self._show_msg(
                self.t("grain.title"), self.t("grain.no_malts"),
                _COLOR_MALT, show_ok=True):
            self._state = _STATE_MESSAGE_ACK
        else:
            self._select().configure(
                title=self.t("grain.no_malts"), items=[],
                accent_color=_COLOR_MALT, selected_index=0)
            self.screen_manager.show(screen_ids.SELECT_ITEM)
            self._state = _STATE_MALT

        if self._rotary:
            self._rotary.reset()
        runtime_debug.log("[MEM] grain.malts_loaded free={}", runtime_debug.mem_free())

    def _show_network_error(self):
        if self._show_msg(
                self.t("grain.title"), self.t("common.network_error"),
                _COLOR_MALT, show_ok=True):
            self._state = _STATE_MESSAGE_ACK

    def _release_screens_for_malt_loading(self):
        self._release_screens_before_loading(self.t("grain.loading_grains"))

    # ── tick handlers ──────────────────────────────────────────────

    def _tick_recipe(self):
        if not self._batches:
            if self.hardware.button.was_short_pressed():
                return "launcher"
            return
        self._batch_idx, changed = self._rotary_navigate(
            self._batch_idx, len(self._batches))
        if changed:
            self._select().set_selected_index(self._batch_idx)
        if self.hardware.button.was_short_pressed():
            self._load_malts()

    def _tick_malt(self):
        if not self._malts:
            return
        self._malt_idx, changed = self._rotary_navigate(
            self._malt_idx, len(self._malts))
        if changed:
            self._select().set_selected_index(self._malt_idx)
        if self.hardware.button.was_short_pressed():
            self._show_place_recipient_prompt()

    def _tick_ack(self, on_ok):
        if self.hardware.button.was_short_pressed():
            on_ok()

    def _tick_weigh(self):
        if self._weighing_reached_target(_grain_weight_tolerance()):
            self._malts.pop(self._malt_idx)
            gc.collect()
            runtime_debug.log("[MEM] grain.malt_validated remaining={} free={}",
                              len(self._malts), runtime_debug.mem_free())
            if self._malts:
                if self._malt_idx >= len(self._malts):
                    self._malt_idx = len(self._malts) - 1
                names = [m.name for m in self._malts]
                self._select().configure(
                    title=self.t("grain.select_malt"), items=names,
                    accent_color=_COLOR_MALT, selected_index=self._malt_idx)
                self.screen_manager.show(screen_ids.SELECT_ITEM)
                self._state = _STATE_MALT
            elif self._show_msg(
                    self.t("grain.title"), self.t("grain.all_malts_done"),
                    _COLOR_MALT, show_ok=True):
                self._state = _STATE_MESSAGE_ACK
            else:
                self._done_at = time.ticks_ms()
                self._state = _STATE_DONE

    # ── weighing ───────────────────────────────────────────────────

    def _show_place_recipient_prompt(self):
        if not self._show_msg(
                self.t("grain.title"), self.t("grain.place_recipient"),
                _COLOR_MALT, show_ok=True):
            self._start_weighing()
            return
        self._state = _STATE_PLACE_RECIPIENT_ACK

    def _start_weighing(self):
        malt = self._malts[self._malt_idx]
        self._begin_weighing(
            malt.name,
            int(malt.amount * 1000),
            _grain_weight_tolerance(),
            _STATE_WEIGHT,
        )
        runtime_debug.log("[MEM] grain.start_weigh '{}' target={}g free={}",
                          malt.name, self._target_g, runtime_debug.mem_free())
