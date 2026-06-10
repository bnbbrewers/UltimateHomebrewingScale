"""
Generic weight screen with the same visual structure as WeightDisplay.
All LVGL objects are created once in __init__.
"""

import m5ui
import lvgl as lv

from .ui_helper import ACTION_BUTTON_Y, UIHelper

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False

if _DEBUG:
    from memory_debug import snapshot as mem_snapshot
else:
    def mem_snapshot(*args, **kwargs):
        return None

CUSTOM_WEIGHT_FONT_PATH = "S:/flash/assets/montserrat_40.bin"
ZERO_WEIGHT_DISPLAY_THRESHOLD_G = 1
PERCENT_TEXT_H = 16
PERCENT_BUTTON_GAP = 2
PERCENT_LABEL_Y = ACTION_BUTTON_Y - PERCENT_TEXT_H - PERCENT_BUTTON_GAP
PROGRESS_BAR_Y = PERCENT_LABEL_Y - 26


class WeightScreen:
    MODE_SIMPLE = "simple"
    MODE_COUNTDOWN_G = "countdown_g"
    MODE_FILLING_L = "filling_l"

    def __init__(self, i18n=None):
        mem_snapshot("weight.init.start", enabled=_DEBUG, collect=True)
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=0x000000)
        mem_snapshot("weight.after_page", enabled=_DEBUG, collect=True)
        self._weight_font = None
        mem_snapshot("weight.after_font", enabled=_DEBUG, collect=True)

        self._mode = self.MODE_SIMPLE
        self._target = 0
        self._empty_weight_g = 0
        self._density = 1.005
        self._tolerance = 0
        self._ok_visible = None
        self._last_raw_weight = None
        self._last_progress_pct = -1
        self._last_overloaded = None
        self._last_title_text = None
        self._last_title_color = None
        self._last_value_text = None
        self._last_status_text = None
        self._last_percent_text = None
        self._last_indicator_overloaded = None

        self._title_bg, self._title = UIHelper.create_title(
            self.page,
            "",
            0x333333,
        )
        mem_snapshot("weight.after_title", enabled=_DEBUG, collect=True)

        self._value = m5ui.M5Label(
            "0 g",
            x=0,
            y=96,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=self._fallback_weight_font(),
            parent=self.page,
        )
        self._value.set_width(240)
        self._value.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        mem_snapshot("weight.after_value_label", enabled=_DEBUG, collect=True)

        self._progress = m5ui.M5Bar(
            x=30, y=PROGRESS_BAR_Y, w=180, h=20,
            min_value=0, max_value=100, value=0,
            bg_c=0x3A3A3A, color=0x4CAF50,
            parent=self.page,
        )
        self._progress.set_bg_color(lv.color_hex(0x3A3A3A), 255, lv.PART.MAIN | lv.STATE.DEFAULT)
        mem_snapshot("weight.after_progress", enabled=_DEBUG, collect=True)

        self._percent = m5ui.M5Label(
            "",
            x=0,
            y=PERCENT_LABEL_Y,
            text_c=0x888888,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._percent.set_width(240)
        self._percent.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        mem_snapshot("weight.after_percent", enabled=_DEBUG, collect=True)

        self._status = m5ui.M5Label(
            "",
            x=0,
            y=210,
            text_c=0x6B7280,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._status.set_width(240)
        self._status.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        mem_snapshot("weight.after_status", enabled=_DEBUG, collect=True)

        self._ok_bg, self._ok_label = UIHelper.create_action_button(self.page)
        mem_snapshot("weight.after_ok_bg", enabled=_DEBUG, collect=True)
        mem_snapshot("weight.init.done", enabled=_DEBUG, collect=True)

    def _load_custom_weight_font(self):
        """
        Load custom font after LVGL/UI init.
        One explicit device path.
        """
        try:
            font = lv.binfont_create(CUSTOM_WEIGHT_FONT_PATH)
            if font:
                return font
            raise RuntimeError("lv.binfont_create returned None")
        except Exception as e:
            msg = "Weight font load failed ({}): {}".format(CUSTOM_WEIGHT_FONT_PATH, e)
            raise RuntimeError(msg)

    @staticmethod
    def _fallback_weight_font():
        try:
            return getattr(lv, "font_montserrat_24", lv.font_montserrat_16)
        except Exception:
            return None

    def _ensure_weight_font(self):
        if self._weight_font is not None:
            return self._weight_font
        self._weight_font = self._load_custom_weight_font()
        try:
            self._value.set_style_text_font(self._weight_font, 0)
        except Exception:
            try:
                self._value.set_font(self._weight_font)
            except Exception:
                pass
        return self._weight_font

    def release_resources(self):
        font = self._weight_font
        self._weight_font = None
        if font is None:
            return
        try:
            destroy = getattr(lv, "binfont_destroy", None)
            if destroy:
                destroy(font)
        except Exception:
            pass

    def root(self):
        return self.page

    def _ok_caption(self):
        if self._i18n:
            return self._i18n.t("common.ok")
        return "common.ok"

    def configure(
        self,
        title,
        mode,
        target=0,
        title_bg_color=0x333333,
        tolerance=0,
        empty_weight_g=0,
    ):
        self._mode = mode
        self._target = target
        self._tolerance = tolerance
        self._empty_weight_g = empty_weight_g
        self._ok_visible = None
        self._last_raw_weight = None
        self._last_progress_pct = -1
        self._last_overloaded = None
        self._last_indicator_overloaded = None
        self._ensure_weight_font()
        self.set_title(title)
        self.set_title_color(title_bg_color)
        self.set_ok_visible(False)

        if mode == self.MODE_SIMPLE:
            self._progress.set_flag(lv.obj.FLAG.HIDDEN, True)
            self._percent.set_flag(lv.obj.FLAG.HIDDEN, True)
            self._status.set_pos(0, 162)
            self._status.set_flag(lv.obj.FLAG.HIDDEN, False)
            self.set_status("")
            self.set_weight_text("0 g")
        else:
            self._progress.set_flag(lv.obj.FLAG.HIDDEN, False)
            self._percent.set_flag(lv.obj.FLAG.HIDDEN, False)
            self._set_percent_text("")
            self._status.set_pos(0, 210)
            self._status.set_flag(lv.obj.FLAG.HIDDEN, True)
            self.set_progress(0, overloaded=False)
            if mode == self.MODE_FILLING_L:
                self.set_weight_text("0.00 L")
            else:
                self.set_weight_text("0 g")

    def set_title(self, text):
        if text == self._last_title_text:
            return
        self._last_title_text = text
        UIHelper.set_title(self._title, text)

    def set_title_color(self, color):
        if color == self._last_title_color:
            return
        self._last_title_color = color
        UIHelper.set_title_color(self._title_bg, color)

    def set_status(self, text):
        if text == self._last_status_text:
            return
        self._last_status_text = text
        self._status.set_text(text)
        if self._mode == self.MODE_SIMPLE:
            self._status.set_flag(lv.obj.FLAG.HIDDEN, False)

    def set_weight_text(self, text):
        if text == self._last_value_text:
            return
        self._last_value_text = text
        self._value.set_text(text)

    def set_progress(self, percent, overloaded=False):
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        pct = int(percent)
        if pct == self._last_progress_pct and overloaded == self._last_overloaded:
            return
        self._last_progress_pct = pct
        self._last_overloaded = overloaded
        self._progress.set_value(pct, False)
        self._set_percent_text("{}%".format(pct))
        if overloaded != self._last_indicator_overloaded:
            self._last_indicator_overloaded = overloaded
            if overloaded:
                self._progress.set_bg_color(
                    lv.color_hex(0xF44336), 255, lv.PART.INDICATOR | lv.STATE.DEFAULT
                )
                self._percent.set_style_text_color(lv.color_hex(0xF44336), 0)
            else:
                self._progress.set_bg_color(
                    lv.color_hex(0x4CAF50), 255, lv.PART.INDICATOR | lv.STATE.DEFAULT
                )
                self._percent.set_style_text_color(lv.color_hex(0x888888), 0)

    def _set_percent_text(self, text):
        if text == self._last_percent_text:
            return
        self._last_percent_text = text
        self._percent.set_text(text)

    def set_ok_visible(self, visible):
        if visible == self._ok_visible:
            return
        self._ok_visible = visible
        UIHelper.set_action_button_visible(
            self._ok_bg,
            self._ok_label,
            visible,
            self._ok_caption(),
        )

    @staticmethod
    def _format_weight(weight):
        """Format weight as kg (>=1000g) or g (<1000g)."""
        if weight is None:
            return "---"
        abs_w = abs(weight)
        if abs_w <= ZERO_WEIGHT_DISPLAY_THRESHOLD_G:
            return "0 g"
        if abs_w >= 1000:
            if weight < 0:
                return "-{:.2f} kg".format(abs_w / 1000.0)
            return "{:.2f} kg".format(abs_w / 1000.0)
        g = int(round(abs_w))
        if weight < 0:
            return "-{} g".format(g)
        return "{} g".format(g)

    def update_from_weight(self, weight):
        if weight == self._last_raw_weight:
            return
        self._last_raw_weight = weight

        if self._mode == self.MODE_SIMPLE:
            self.set_weight_text(self._format_weight(weight))
            self._set_percent_text("")
            self.set_ok_visible(False)
            return

        if self._mode == self.MODE_COUNTDOWN_G:
            remaining = self._target - weight
            overloaded = remaining < 0
            if overloaded:
                self.set_weight_text("+" + self._format_weight(-remaining))
            else:
                self.set_weight_text(self._format_weight(remaining))
            if self._target > 0:
                progress = int((weight * 100) / self._target)
            else:
                progress = 0
            if abs(remaining) <= ZERO_WEIGHT_DISPLAY_THRESHOLD_G:
                progress = 100
            if progress < 0:
                progress = 0
            if progress > 100:
                progress = 100
            self.set_progress(progress, overloaded=overloaded)
            in_range = self._tolerance > 0 and abs(remaining) <= self._tolerance
            self.set_ok_visible(in_range)
            return

        # filling_l
        filled_weight = weight - self._empty_weight_g
        if filled_weight < 0:
            filled_weight = 0
        volume = (filled_weight / 1000.0) / self._density
        if self._target > 0:
            target_volume = (self._target / 1000.0) / self._density
            remaining_volume = target_volume - volume
            if remaining_volume < 0:
                remaining_volume = 0
            progress = int((volume * 100) / target_volume) if target_volume > 0 else 0
        else:
            remaining_volume = 0
            progress = 0
        if progress < 0:
            progress = 0
        if progress > 100:
            progress = 100
        self.set_weight_text("{:.2f} L".format(volume))
        self.set_progress(progress, overloaded=False)
        self.set_ok_visible(False)
