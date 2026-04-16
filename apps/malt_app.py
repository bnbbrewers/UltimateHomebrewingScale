"""
Memory-safe grain assistant app (business logic only).
"""

import gc
import time

import config

from .base_app import BaseApp
from ui import screen_ids

_STATE_RECIPE = 1
_STATE_MALT = 2
_STATE_WEIGHT = 3
_STATE_DONE = 4
_STATE_MESSAGE_ACK = 5
_COLOR_MALT = 0xD4840A
_COLOR_RECIPE = _COLOR_MALT


class GrainAssistantApp(BaseApp):
    APP_ID = "malt_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._api = self.apis.get("brewing")
        self._scale = self.hardware.scale
        self._rotary = self.hardware.rotary

        self._select_screen = self.screen_manager.get(screen_ids.SELECT_ITEM)
        self._weigh_screen = self.screen_manager.get(screen_ids.WEIGHT)

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
        if config.DEBUG:
            gc.collect()
            print("[MEM] grain.on_exit before_cleanup free={}".format(gc.mem_free()))
        self._batches = []
        self._malts = []
        self._select_screen.set_items([])

    def on_enter(self):
        super().on_enter()
        try:
            import lvgl as lv
            lv.image_cache_drop(None)
        except Exception:
            pass
        gc.collect()
        self._load_batches()

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        if self._state == _STATE_RECIPE:
            self._tick_recipe()
        elif self._state == _STATE_MALT:
            self._tick_malt()
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
        self._show_msg(
            self.t("grain.title"), self.t("recipe.loading_recipes"), _COLOR_RECIPE)
        self._batches = self._api.get_batches() if self._api else []
        names = [b.name for b in self._batches]
        self._batch_idx = 0
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        self._select_screen.configure(
            title=self.t("recipe.select_recipe") if names else self.t("recipe.no_recipe"),
            items=names, accent_color=_COLOR_RECIPE, selected_index=0)
        if self._rotary:
            self._rotary.reset()
        self._state = _STATE_RECIPE
        gc.collect()
        if config.DEBUG:
            print("[MEM] grain.batches_loaded free={}".format(gc.mem_free()))

    def _load_malts(self):
        self._show_msg(
            self.t("grain.title"), self.t("grain.loading_grains"), _COLOR_MALT)
        batch_id = self._batches[self._batch_idx].batch_id
        self._batches = []
        gc.collect()

        self._malts = self._api.get_malts(batch_id) if self._api else []
        self._malt_idx = 0
        names = [m.name for m in self._malts]

        if names:
            self.screen_manager.show(screen_ids.SELECT_ITEM)
            self._select_screen.configure(
                title=self.t("grain.select_malt"), items=names,
                accent_color=_COLOR_MALT, selected_index=0)
            self._state = _STATE_MALT
        elif self._show_msg(
                self.t("grain.title"), self.t("grain.no_malts"),
                _COLOR_MALT, show_ok=True):
            self._state = _STATE_MESSAGE_ACK
        else:
            self.screen_manager.show(screen_ids.SELECT_ITEM)
            self._select_screen.configure(
                title=self.t("grain.no_malts"), items=[],
                accent_color=_COLOR_MALT, selected_index=0)
            self._state = _STATE_MALT

        if self._rotary:
            self._rotary.reset()
        if config.DEBUG:
            gc.collect()
            print("[MEM] grain.malts_loaded free={}".format(gc.mem_free()))

    # ── tick handlers ──────────────────────────────────────────────

    def _tick_recipe(self):
        if not self._batches:
            return
        self._batch_idx, changed = self._rotary_navigate(
            self._batch_idx, len(self._batches))
        if changed:
            self._select_screen.set_selected_index(self._batch_idx)
        if self.hardware.button.was_short_pressed():
            self._load_malts()

    def _tick_malt(self):
        if not self._malts:
            return
        self._malt_idx, changed = self._rotary_navigate(
            self._malt_idx, len(self._malts))
        if changed:
            self._select_screen.set_selected_index(self._malt_idx)
        if self.hardware.button.was_short_pressed():
            self._start_weighing()

    def _tick_weigh(self):
        if self._scale is None:
            self._weigh_screen.set_status("Scale not found")
            return
        weight = self._scale.read_weight()
        if weight is None:
            return
        self._weigh_screen.update_from_weight(weight)
        remaining = self._target_g - weight
        in_range = abs(remaining) <= config.GRAIN_WEIGHT_TOLERANCE
        if in_range != self._last_in_range:
            self._last_in_range = in_range
            self._weigh_screen.set_status(self.t("common.ok") if in_range else "")
        if (in_range or config.DEBUG) and self.hardware.button.was_short_pressed():
            self._malts.pop(self._malt_idx)
            gc.collect()
            if config.DEBUG:
                print("[MEM] grain.malt_validated remaining={} free={}".format(
                    len(self._malts), gc.mem_free()))
            if self._malts:
                if self._malt_idx >= len(self._malts):
                    self._malt_idx = len(self._malts) - 1
                names = [m.name for m in self._malts]
                self.screen_manager.show(screen_ids.SELECT_ITEM)
                self._select_screen.configure(
                    title=self.t("grain.select_malt"), items=names,
                    accent_color=_COLOR_MALT, selected_index=self._malt_idx)
                self._state = _STATE_MALT
            elif self._show_msg(
                    self.t("grain.title"), self.t("grain.all_malts_done"),
                    _COLOR_MALT, show_ok=True):
                self._state = _STATE_MESSAGE_ACK
            else:
                self._done_at = time.ticks_ms()
                self._state = _STATE_DONE

    # ── weighing ───────────────────────────────────────────────────

    def _start_weighing(self):
        self.screen_manager.show(screen_ids.WEIGHT)
        malt = self._malts[self._malt_idx]
        self._target_g = int(malt.amount * 1000)
        self._weigh_screen.configure(
            title=malt.name, mode="countdown_g", target=self._target_g,
            title_bg_color=0xD4840A, tolerance=config.GRAIN_WEIGHT_TOLERANCE)
        self._weigh_screen.set_status(self.t("scale.tare_ready"))
        self._last_in_range = None
        if self._scale:
            self._scale.tare()
        self._state = _STATE_WEIGHT
        if config.DEBUG:
            gc.collect()
            print("[MEM] grain.start_weigh '{}' target={}g free={}".format(
                malt.name, self._target_g, gc.mem_free()))
