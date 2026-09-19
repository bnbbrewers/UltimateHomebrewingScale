"""Shared base for the two apps that weigh a recipe out of the brewing API.

Malt and Hop differ in what they weigh and in how they walk their own steps,
but they open the same way: fetch the batches, let the operator pick one,
release the screens before the next API call, weigh against a tolerance. Those
parts were duplicated line for line, so a fix to one of them only ever reached
half the device.

Subclasses keep their own state machine: everything here either takes the
caller's state as an argument or returns without touching it.

core.app_manager evicts this module with whichever app imported it, so it does
not stay resident for a session that never opens Malt or Hop.
"""

import gc

import runtime_debug

from .base_app import BaseApp
from ui import screen_ids


class RecipeApp(BaseApp):
    #: Accent colour of the app, used by every screen it configures.
    COLOR = 0x333333
    #: Translation key for the app's own title.
    TITLE_KEY = ""
    #: Tag prefix for the memory traces, e.g. "grain" or "hop".
    TRACE_PREFIX = "recipe"

    def _select(self):
        if self._select_screen is None:
            self._select_screen = self.screen_manager.get(screen_ids.SELECT_ITEM)
        return self._select_screen

    def _weight(self):
        if self._weigh_screen is None:
            self._weigh_screen = self.screen_manager.get(screen_ids.WEIGHT)
        return self._weigh_screen

    def _api_failed(self):
        return bool(self._api) and getattr(self._api, "last_error", None) is not None

    def _load_batches(self, on_single_batch, recipe_state):
        """Fetch the batches and show the picker.

        A single batch skips the picker: `on_single_batch` is called instead.
        `recipe_state` is the caller's own "picking a recipe" state, set once
        the list is on screen.
        """
        self._batches = self._api.get_batches() if self._api else []
        if self._api_failed():
            self._show_network_error()
            return
        names = [b.name for b in self._batches]
        self._batch_idx = 0
        if len(self._batches) == 1:
            on_single_batch()
            return
        self._select().configure(
            title=self.t("recipe.select_recipe") if names else self.t("recipe.no_recipe"),
            items=names if names else [self.t("common.back")],
            accent_color=self.COLOR,
            selected_index=0,
        )
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        if self._rotary:
            self._rotary.reset()
        self._state = recipe_state
        gc.collect()
        runtime_debug.snapshot("{}.batches_loaded".format(self.TRACE_PREFIX))

    def _show_network_error(self):
        """Report the failed call. Subclasses set the state they return to."""
        raise NotImplementedError

    def _release_screens_before_loading(self, loading_message):
        """Drop both screens and let the manager reclaim them.

        Called between picking a batch and the API call that follows: the
        response, the TLS buffers and a live screen tree do not fit in the C
        heap at the same time.
        """
        select_screen = self._select_screen
        if select_screen:
            try:
                select_screen.set_items([])
            except Exception:
                pass
        self._select_screen = None
        self._weigh_screen = None
        cleanup = getattr(self.screen_manager, "memory_cleanup", None)
        if cleanup is None:
            self._show_msg(self.t(self.TITLE_KEY), loading_message, self.COLOR)
            return
        try:
            cleanup(loading_message=loading_message, loading_color=self.COLOR)
        except TypeError:
            # Older manager signature, still used by some tests.
            cleanup(loading_message=loading_message)

    def _begin_weighing(self, title, target_g, tolerance, weight_state):
        """Configure the weight screen and tare, the way both apps do it."""
        self._target_g = target_g
        screen = self._weight()
        screen.configure(
            title=title,
            mode="countdown_g",
            target=target_g,
            title_bg_color=self.COLOR,
            tolerance=tolerance,
        )
        self.screen_manager.show(screen_ids.WEIGHT)
        screen.set_status(self.t("scale.tare_ready"))
        self._last_in_range = None
        if self._scale:
            self._scale.tare()
        self._state = weight_state

    def _weighing_reached_target(self, tolerance):
        """True when the operator confirmed a weight inside the tolerance.

        Updates the on-screen OK marker as a side effect. In debug mode the
        button is accepted at any weight, so a flow can be walked without the
        hardware.
        """
        weight = self._read_and_update_weight(self._weight())
        if weight is None:
            return False
        in_range = abs(self._target_g - weight) <= tolerance
        if in_range != self._last_in_range:
            self._last_in_range = in_range
            self._weight().set_status(self.t("common.ok") if in_range else "")
        if not (in_range or runtime_debug.DEBUG):
            return False
        return bool(self.hardware.button.was_short_pressed())
