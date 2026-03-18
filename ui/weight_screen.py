"""
Generic weight screen with the same visual structure as WeightDisplay.
All LVGL objects are created once in __init__.
"""

import m5ui
import lvgl as lv


class WeightScreen:
    MODE_SIMPLE = "simple"
    MODE_COUNTDOWN_G = "countdown_g"
    MODE_COUNTDOWN_L = "countdown_l"

    def __init__(self, i18n=None):
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=0x000000)

        self._mode = self.MODE_SIMPLE
        self._target = 0
        self._density = 1.005
        self._tolerance = 0
        self._ok_visible = False
        self._last_raw_weight = None
        self._last_progress_pct = -1
        self._last_overloaded = None

        self._title_bg = lv.obj(self.page)
        self._title_bg.set_size(240, 50)
        self._title_bg.set_pos(0, 0)
        self._title_bg.set_style_bg_color(lv.color_hex(0x333333), 0)
        self._title_bg.set_style_bg_opa(255, 0)
        self._title_bg.set_style_border_width(0, 0)
        self._title_bg.set_style_radius(0, 0)

        self._title = m5ui.M5Label(
            "",
            x=0,
            y=26,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.page,
        )
        self._title.set_width(240)
        self._title.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._value = m5ui.M5Label(
            "0 g",
            x=0,
            y=96,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_24,
            parent=self.page,
        )
        self._value.set_width(240)
        self._value.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._progress = lv.bar(self.page)
        self._progress.set_size(200, 20)
        self._progress.set_pos(20, 162)
        self._progress.set_range(0, 100)
        self._progress.set_value(0, False)

        self._percent = m5ui.M5Label(
            "",
            x=0,
            y=188,
            text_c=0x888888,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._percent.set_width(240)
        self._percent.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

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

        self._ok_bg = lv.obj(self.page)
        self._ok_bg.set_size(240, 28)
        self._ok_bg.set_pos(0, 212)
        self._ok_bg.set_style_bg_color(lv.color_hex(0x4CAF50), 0)
        self._ok_bg.set_style_bg_opa(0, 0)
        self._ok_bg.set_style_border_width(0, 0)
        self._ok_bg.set_style_radius(0, 0)

        self._ok_label = m5ui.M5Label(
            "",
            x=0,
            y=219,
            text_c=0xFFFFFF,
            bg_c=0x4CAF50,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._ok_label.set_width(240)
        self._ok_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

    def root(self):
        return self.page

    def configure(self, title, mode, target=0, title_bg_color=0x333333, tolerance=0):
        self._mode = mode
        self._target = target
        self._tolerance = tolerance
        self._ok_visible = False
        self._last_raw_weight = None
        self._last_progress_pct = -1
        self._last_overloaded = None
        self.set_title(title)
        self.set_title_color(title_bg_color)
        self._percent.set_text("")
        self.set_status("")
        self.set_ok_visible(False)
        self.set_progress(0, overloaded=False)
        if mode == self.MODE_COUNTDOWN_L:
            self._value.set_text("0.00 L")
        else:
            self._value.set_text("0 g")

    def set_title(self, text):
        self._title.set_text(text)

    def set_title_color(self, color):
        self._title_bg.set_style_bg_color(lv.color_hex(color), 0)

    def set_status(self, text):
        self._status.set_text(text)

    def set_weight_text(self, text):
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
        self._percent.set_text("{}%".format(pct))
        if overloaded:
            self._progress.set_style_bg_color(lv.color_hex(0xF44336), lv.PART.INDICATOR)
            self._percent.set_style_text_color(lv.color_hex(0xF44336), 0)
        else:
            self._progress.set_style_bg_color(lv.color_hex(0x4CAF50), lv.PART.INDICATOR)
            self._percent.set_style_text_color(lv.color_hex(0x888888), 0)

    def set_ok_visible(self, visible):
        self._ok_visible = visible
        self._ok_label.set_text("OK" if visible else "")
        self._ok_bg.set_style_bg_opa(255 if visible else 0, 0)

    @staticmethod
    def _format_weight(weight):
        """Format weight as kg (>=1000g) or g (<1000g)."""
        if weight is None:
            return "---"
        abs_w = abs(weight)
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
            self._percent.set_text("")
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
            if progress < 0:
                progress = 0
            if progress > 100:
                progress = 100
            self.set_progress(progress, overloaded=overloaded)
            in_range = self._tolerance > 0 and abs(remaining) <= self._tolerance
            self.set_ok_visible(in_range)
            return

        # countdown_l
        volume = (weight / 1000.0) / self._density
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
