"""
Memory-safe grain assistant app (business logic only).
"""

import gc
import time

from .base_app import BaseApp
from ui import screen_ids

_STATE_RECIPE = 1
_STATE_MALT = 2
_STATE_WEIGH = 3
_STATE_DONE = 4
_COLOR_MALT = 0xD4840A
_COLOR_RECIPE = _COLOR_MALT


class GrainAssistantApp(BaseApp):
    APP_ID = "grain_assistant"

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

    def on_enter(self):
        super().on_enter()
        self._load_batches()

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"

        if self._state == _STATE_RECIPE:
            self._tick_recipe()
        elif self._state == _STATE_MALT:
            self._tick_malt()
        elif self._state == _STATE_WEIGH:
            self._tick_weigh()
        elif self._state == _STATE_DONE:
            if time.ticks_diff(time.ticks_ms(), self._done_at) >= 2000:
                return "launcher"
        return None

    def _load_batches(self):
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        self._select_screen.configure(
            title=self.t("grain.loading_batches"),
            items=[],
            accent_color=_COLOR_RECIPE,
            selected_index=0,
        )

        self._batches = self._api.get_batches() if self._api else []
        names = []
        for batch in self._batches:
            names.append(batch.name)
        self._batch_idx = 0

        if names:
            self._select_screen.configure(
                title=self.t("grain.select_recipe"),
                items=names,
                accent_color=_COLOR_RECIPE,
                selected_index=0,
            )
        else:
            self._select_screen.configure(
                title=self.t("grain.no_batches"),
                items=[],
                accent_color=_COLOR_RECIPE,
                selected_index=0,
            )

        if self._rotary:
            self._rotary.reset_rotary_value()
        self._state = _STATE_RECIPE
        gc.collect()

    def _tick_recipe(self):
        if not self._batches:
            return
        if self._rotary:
            delta = self._rotary.get_rotary_value()
            if delta:
                self._rotary.reset_rotary_value()
                if delta > 0:
                    self._batch_idx += 1
                else:
                    self._batch_idx -= 1
                if self._batch_idx < 0:
                    self._batch_idx = 0
                if self._batch_idx >= len(self._batches):
                    self._batch_idx = len(self._batches) - 1
                self._select_screen.set_selected_index(self._batch_idx)
        if self.hardware.button.wasPressed():
            self._load_malts()

    def _load_malts(self):
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        self._select_screen.configure(
            title=self.t("grain.loading_malts"),
            items=[],
            accent_color=_COLOR_MALT,
            selected_index=0,
        )

        # Extract only what's needed, then release all batch objects before
        # the second API call to recover heap space and reduce fragmentation.
        batch_id = self._batches[self._batch_idx].batch_id
        self._batches = []
        gc.collect()

        try:
            _buf = bytearray(40000)
            del _buf
        except MemoryError:
            pass
        gc.collect()

        if self._api:
            self._malts = self._api.get_malts(batch_id)
        else:
            self._malts = []
        self._malt_idx = 0

        names = []
        for malt in self._malts:
            names.append(malt.name)

        if names:
            self._select_screen.configure(
                title=self.t("grain.select_malt"),
                items=names,
                accent_color=_COLOR_MALT,
                selected_index=0,
            )
        else:
            self._select_screen.configure(
                title=self.t("grain.no_malts"),
                items=[],
                accent_color=_COLOR_MALT,
                selected_index=0,
            )
        if self._rotary:
            self._rotary.reset_rotary_value()
        self._state = _STATE_MALT

    def _tick_malt(self):
        if not self._malts:
            return
        if self._rotary:
            delta = self._rotary.get_rotary_value()
            if delta:
                self._rotary.reset_rotary_value()
                if delta > 0:
                    self._malt_idx += 1
                else:
                    self._malt_idx -= 1
                if self._malt_idx < 0:
                    self._malt_idx = 0
                if self._malt_idx >= len(self._malts):
                    self._malt_idx = len(self._malts) - 1
                self._select_screen.set_selected_index(self._malt_idx)
        if self.hardware.button.wasPressed():
            self._start_weighing()

    def _start_weighing(self):
        self.screen_manager.show(screen_ids.WEIGHT)
        malt = self._malts[self._malt_idx]
        self._target_g = int(malt.amount * 1000)
        self._weigh_screen.configure(
            title=malt.name,
            mode="countdown_g",
            target=self._target_g,
            title_bg_color=0xD4840A,
            tolerance=10,
        )
        self._weigh_screen.set_status(self.t("scale.tare_ready"))
        if self._scale:
            self._scale.tare()
        self._state = _STATE_WEIGH

    def _tick_weigh(self):
        if self._scale is None:
            self._weigh_screen.set_status("Scale not found")
            return

        weight = self._scale.read_weight()
        if weight is None:
            return

        self._weigh_screen.update_from_weight(weight)
        remaining = self._target_g - weight
        in_range = abs(remaining) <= 10
        if in_range:
            self._weigh_screen.set_status(self.t("common.ok"))
        else:
            self._weigh_screen.set_status("")

        if in_range and self.hardware.button.wasPressed():
            self._malts.pop(self._malt_idx)
            if self._malts:
                if self._malt_idx >= len(self._malts):
                    self._malt_idx = len(self._malts) - 1
                names = []
                for malt in self._malts:
                    names.append(malt.name)
                self.screen_manager.show(screen_ids.SELECT_ITEM)
                self._select_screen.configure(
                    title=self.t("grain.select_malt"),
                    items=names,
                    accent_color=_COLOR_MALT,
                    selected_index=self._malt_idx,
                )
                self._state = _STATE_MALT
            else:
                self.screen_manager.show(screen_ids.SELECT_ITEM)
                self._select_screen.configure(
                    title=self.t("grain.all_malts_done"),
                    items=[],
                    accent_color=_COLOR_MALT,
                    selected_index=0,
                )
                self._done_at = time.ticks_ms()
                self._state = _STATE_DONE
