"""Small hop entry point that fetches data before loading the heavy UI flow."""

import gc

import config

from .base_app import BaseApp
from ui import screen_ids


_STATE_RECIPE = 1
_STATE_ACK = 2
_COLOR_HOP = 0x388E3C


class HopBootstrapApp(BaseApp):
    """Keep the large hop UI module out of memory during TLS handshakes."""

    APP_ID = "hop_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._api = self.apis.get("brewing")
        self._rotary = self.hardware.rotary
        self._batches = []
        self._batch_idx = 0
        self._state = _STATE_RECIPE
        self._delegate = None

    def on_enter(self):
        super().on_enter()
        gc.collect()
        self._load_batches()

    def on_exit(self):
        if self._delegate is not None:
            self._delegate.on_exit()
            self._delegate = None
        self._batches = []
        super().on_exit()

    def tick(self):
        if self._delegate is not None:
            return self._delegate.tick()
        if self._check_return_to_launcher():
            return "launcher"
        if self._state == _STATE_ACK:
            if self.hardware.button.was_short_pressed():
                return "launcher"
            return None
        if not self._batches:
            if self.hardware.button.was_short_pressed():
                return "launcher"
            return None

        self._batch_idx, changed = self._rotary_navigate(
            self._batch_idx, len(self._batches))
        if changed:
            self._select_screen().set_selected_index(self._batch_idx)
        if self.hardware.button.was_short_pressed():
            self._load_hops(self._batches[self._batch_idx].batch_id)
        return None

    def _select_screen(self):
        return self.screen_manager.get(screen_ids.SELECT_ITEM)

    def _load_batches(self):
        self._batches = self._api.get_batches() if self._api else []
        if self._has_api_error():
            self._show_network_error()
            return
        if len(self._batches) == 1:
            self._load_hops(self._batches[0].batch_id)
            return

        names = [batch.name for batch in self._batches]
        screen = self._select_screen()
        screen.configure(
            title=self.t("recipe.select_recipe") if names else self.t("recipe.no_recipe"),
            items=names if names else [self.t("common.back")],
            accent_color=_COLOR_HOP, selected_index=0)
        if self._rotary:
            self._rotary.reset()
        self._state = _STATE_RECIPE

    def _load_hops(self, batch_id):
        had_selection_screen = bool(self._batches)
        self._batches = []
        if had_selection_screen:
            screen = self.screen_manager.get(screen_ids.SELECT_ITEM)
            try:
                screen.set_items([])
            except Exception:
                pass
        self.screen_manager.memory_cleanup(
            loading_message=self.t("hop.loading_hops"),
            loading_color=_COLOR_HOP,
        )
        gc.collect()
        hops = self._api.get_hops_list(batch_id) if self._api else []
        if self._has_api_error():
            self._show_network_error()
            return
        self._start_delegate(batch_id, hops)

    def _start_delegate(self, batch_id, hops):
        from .hop_app import HopAssistantApp

        self._delegate = HopAssistantApp(
            self.screen_manager,
            self.hardware,
            self.apis,
            i18n=self.i18n,
            initial_batch_id=batch_id,
            initial_hops=hops,
        )
        self._delegate.on_enter()

    def _has_api_error(self):
        return self._api and getattr(self._api, "last_error", None) is not None

    def _show_network_error(self):
        self._show_msg(
            self.t("hop.title"), self.t("common.network_error"),
            _COLOR_HOP, show_ok=True)
        self._state = _STATE_ACK
