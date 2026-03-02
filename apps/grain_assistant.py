"""
Grain Assistant - Weighing assistant for malt/grain with Brewfather integration

State machine
-------------
    LOADING_RECIPES  ->  SELECT_RECIPE
                              |
                         (button press)
                              |
                         LOADING_MALTS  ->  SELECT_MALT
                                                |
                                           (button press)
                                                |
                                            WEIGHING
                                          (isPressed -> back to SELECT_MALT)
                                          (long press  -> launcher)
"""

import gc
import time
import M5
from M5 import *
import m5ui
import lvgl as lv
from hardware import Rotary

from .base_app import BaseApp
from ui.selectable_list import SelectableList

# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
_STATE_LOADING_RECIPES = 0
_STATE_SELECT_RECIPE   = 1
_STATE_LOADING_MALTS   = 2
_STATE_SELECT_MALT     = 3
_STATE_WEIGHING        = 4
_STATE_ALL_DONE        = 5

# ---------------------------------------------------------------------------
# Accent colour – read from the launcher config entry for this module so the
# app always matches its icon.  Falls back to amber if the config is missing.
# ---------------------------------------------------------------------------
def _app_color():
    try:
        from ui.launcher_config import LAUNCHER_ITEMS
        for item in LAUNCHER_ITEMS:
            if item.get('module') == 'grain_assistant':
                return item['color']
    except Exception:
        pass
    return 0xD4840A   # golden amber fallback

_APP_COLOR = _app_color()


class GrainAssistantApp(BaseApp):
    """Grain weighing assistant with API integration."""

    def __init__(self, i18n=None):
        super().__init__(i18n)

        # Scale: initialised lazily when weighing starts, not at app launch.
        # CalibratedScale() does I2C communication that can block for 30+ s
        # if the hardware is not connected.
        self.scale = None

        # Rotary encoder
        self.encoder = Rotary()
        self.encoder.reset_rotary_value()

        # Data
        self._batches         = []   # List[Batch]
        self._malts           = []   # List[Malt]
        self._selected_batch  = None
        self._selected_malt   = None

        # UI
        self._status_lbl     = None
        self._sel_list       = None
        self._weight_display = None

        # State
        self._state     = _STATE_LOADING_RECIPES
        self._done_at   = None   # ticks_ms timestamp set when all malts are done

    # -----------------------------------------------------------------------
    # BaseApp interface
    # -----------------------------------------------------------------------

    def create_ui(self):
        """Create the page and show the initial loading message."""
        self.page = m5ui.M5Page(bg_c=0x000000)

        # Centred status / loading label – reused throughout the app
        self._status_lbl = m5ui.M5Label(
            self.t('grain.loading_batches'),
            x=40, y=103,
            text_c=0x9CA3AF,
            bg_c=0x000000, bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page
        )
        self._status_lbl.set_width(160)
        self._status_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self.page.screen_load()
        self._state = _STATE_LOADING_RECIPES

    def update(self):
        """Called every frame by the base run() loop."""
        if self._state == _STATE_LOADING_RECIPES:
            self._load_recipes()

        elif self._state == _STATE_SELECT_RECIPE:
            self._handle_recipe_selection()

        elif self._state == _STATE_LOADING_MALTS:
            self._load_malts()

        elif self._state == _STATE_SELECT_MALT:
            self._handle_malt_selection()

        elif self._state == _STATE_WEIGHING:
            self._handle_weighing()

        elif self._state == _STATE_ALL_DONE:
            if time.ticks_diff(time.ticks_ms(), self._done_at) >= 3000:
                self.exit()   # returns to launcher

    def cleanup(self):
        if self._sel_list:
            self._sel_list.cleanup()
            self._sel_list = None
        if self._weight_display:
            self._weight_display.cleanup()
            self._weight_display = None
        super().cleanup()

    # -----------------------------------------------------------------------
    # Loading steps (blocking – happen on first relevant update() call)
    # -----------------------------------------------------------------------

    def _load_recipes(self):
        """Fetch batches from the API, then transition to SELECT_RECIPE."""
        self._batches = self.api.get_batches() if self.api else []
        self._build_recipe_list()
        self._state = _STATE_SELECT_RECIPE

    def _load_malts(self):
        """Fetch malts for the selected batch, then transition to SELECT_MALT."""
        if self.api and self._selected_batch:
            self._malts = self.api.get_malts(self._selected_batch.batch_id)
        else:
            self._malts = []
        self._build_malt_list()
        self._state = _STATE_SELECT_MALT

    # -----------------------------------------------------------------------
    # List builders
    # -----------------------------------------------------------------------

    def _build_recipe_list(self):
        """Replace loading label with the recipe SelectableList."""
        self._hide_status()

        if not self._batches:
            self._show_status(self.t('grain.no_batches'))
            return

        names = [b.name for b in self._batches]
        self._sel_list = SelectableList(
            parent=self.page,
            items=names,
            title=self.t('grain.select_recipe'),
            accent_color=_APP_COLOR,
        )
        self.encoder.reset_rotary_value()

    def _build_malt_list(self):
        """Replace loading label with the malt SelectableList."""
        self._hide_status()

        if not self._malts:
            self._show_status(self.t('grain.no_malts'))
            return

        # Display each malt as "Name  NNNg"
        items = [
            m.name
            for m in self._malts
        ]
        self._sel_list = SelectableList(
            parent=self.page,
            items=items,
            title=self.t('grain.select_malt'),
            accent_color=_APP_COLOR,
        )
        self.encoder.reset_rotary_value()

    # -----------------------------------------------------------------------
    # Input handlers
    # -----------------------------------------------------------------------

    def _handle_recipe_selection(self):
        if self._sel_list is None:
            return

        delta = self.encoder.get_rotary_value()
        if delta:
            self.encoder.reset_rotary_value()
            self._sel_list.handle_encoder(delta)

        if M5.BtnA.wasPressed():
            result = self._sel_list.handle_button()
            if result is not None:
                idx, _ = result
                self._selected_batch = self._batches[idx]

                # Tear down recipe list, show loading
                self._sel_list.cleanup()
                self._sel_list = None
                gc.collect()

                self._show_status(self.t('grain.loading_malts'))
                self._state = _STATE_LOADING_MALTS

    def _handle_malt_selection(self):
        if self._sel_list is None:
            return

        delta = self.encoder.get_rotary_value()
        if delta:
            self.encoder.reset_rotary_value()
            self._sel_list.handle_encoder(delta)

        if M5.BtnA.wasPressed():
            result = self._sel_list.handle_button()
            if result is not None:
                idx, _ = result
                self._selected_malt = self._malts[idx]

                self._sel_list.cleanup()
                self._sel_list = None
                gc.collect()

                self._start_weighing()

    # -----------------------------------------------------------------------
    # Weighing
    # -----------------------------------------------------------------------

    def _start_weighing(self):
        """Initialise scale (lazy) and show WeightDisplay for the selected malt."""
        malt = self._selected_malt
        target_g = int(malt.amount * 1000)   # amount is in kg → convert to g

        # Lazy scale init – may take a moment on first call
        if self.scale is None:
            try:
                from devices.scale import CalibratedScale
                self.scale = CalibratedScale()
            except Exception as e:
                self._show_status("Scale error: {}".format(e))
                return

        from ui.weight_display import WeightDisplay
        self._weight_display = WeightDisplay(
            parent=self.page,
            title=malt.name,
            mode="countdown_g",
            target=target_g,
            title_bg_color=_APP_COLOR,
            scale=self.scale,
            tolerance=10,
            on_confirm=self._on_malt_confirmed,
        )
        self.encoder.reset_rotary_value()
        self._state = _STATE_WEIGHING

    def _handle_weighing(self):
        """Tick the WeightDisplay – it fires on_confirm itself when ready."""
        if self._weight_display is not None:
            self._weight_display.update()

    def _on_malt_confirmed(self):
        """Called by WeightDisplay when the user confirms the weight."""
        if self._selected_malt in self._malts:
            self._malts.remove(self._selected_malt)
        self._selected_malt = None

        self._weight_display.cleanup()
        self._weight_display = None
        gc.collect()

        if self._malts:
            self._build_malt_list()
            self._state = _STATE_SELECT_MALT
        else:
            self._show_status(self.t('grain.all_malts_done'))
            self._done_at = time.ticks_ms()
            self._state = _STATE_ALL_DONE

    # -----------------------------------------------------------------------
    # Status label helpers
    # -----------------------------------------------------------------------

    def _show_status(self, text):
        """Display a centred status message (hides list if any)."""
        if self._status_lbl:
            self._status_lbl.set_text(text)

    def _hide_status(self):
        """Clear the status label text."""
        if self._status_lbl:
            self._status_lbl.set_text("")


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    M5.begin()
    m5ui.init()
    app = GrainAssistantApp(i18n=None)
    app.run()
