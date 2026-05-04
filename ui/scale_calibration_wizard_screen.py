"""
Scale calibration wizard screen.

Owns LVGL/m5ui widgets only. Calibration state and hardware flow stay in the
app layer.
"""

import lvgl as lv
import m5ui

from .ui_helper import UIHelper


class ScaleCalibrationWizardScreen:
    _W = 240
    _R = 120
    _EDGE_MARGIN = 10
    _PROGRESS_Y = 198
    _PROGRESS_H = 12
    _C_BG = 0x000000
    _C_ACCENT = 0x00897B
    _C_ACCENT_DARK = 0x004D40
    _C_START = 0x4CAF50
    _C_TEXT = 0xFFFFFF
    _C_MUTED = 0x9CA3AF
    _C_DIM = 0x6B7280
    _C_PROGRESS_BG = 0x263238

    def __init__(self, i18n=None):
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=self._C_BG)

        self._title_bar, self._title_label = UIHelper.create_title(
            self.page,
            self._t("scale_calibration.title"),
            self._C_ACCENT,
            width=self._W,
        )

        self._step_label = m5ui.M5Label(
            "",
            x=0,
            y=68,
            text_c=self._C_MUTED,
            bg_c=self._C_BG,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._step_label.set_width(self._W)
        self._step_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._target_label = m5ui.M5Label(
            "",
            x=0,
            y=100,
            text_c=self._C_TEXT,
            bg_c=self._C_BG,
            bg_opa=0,
            font=lv.font_montserrat_24,
            parent=self.page,
        )
        self._target_label.set_width(self._W)
        self._target_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._info_label = m5ui.M5Label(
            "",
            x=0,
            y=178,
            text_c=self._C_DIM,
            bg_c=self._C_BG,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._info_label.set_width(self._W)
        self._info_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._status_label = m5ui.M5Label(
            "",
            x=0,
            y=142,
            text_c=self._C_MUTED,
            bg_c=self._C_BG,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._status_label.set_width(self._W)
        self._status_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        progress_w = self._safe_width(self._PROGRESS_Y + self._PROGRESS_H // 2)
        progress_x = (self._W - progress_w) // 2
        self._progress_bar = m5ui.M5Bar(
            x=progress_x,
            y=self._PROGRESS_Y,
            w=progress_w,
            h=self._PROGRESS_H,
            min_value=0,
            max_value=100,
            value=0,
            bg_c=self._C_PROGRESS_BG,
            color=self._C_ACCENT,
            parent=self.page,
        )
        self._progress_bar.set_bg_color(
            lv.color_hex(self._C_PROGRESS_BG),
            255,
            lv.PART.MAIN | lv.STATE.DEFAULT,
        )
        self._progress_bar.set_bg_color(
            lv.color_hex(self._C_ACCENT),
            255,
            lv.PART.INDICATOR | lv.STATE.DEFAULT,
        )

        self._start_bg, self._start_label = UIHelper.create_action_button(self.page)
        self._set_start_visible(False)

    def root(self):
        return self.page

    def show(self):
        self.page.screen_load()

    def render_step(self, step_index, total_steps, calibration_point, target_weight):
        self._set_progress(0)
        self._set_progress_visible(False)
        self._set_start_visible(True)
        self._step_label.set_text(
            self._t(
                "scale_calibration.step",
                step_index + 1,
                total_steps,
                calibration_point,
            )
        )
        self._info_label.set_text("")
        self._target_label.set_text(
            self._t("scale_calibration.target", target_weight)
        )
        self._status_label.set_text(
            self._lines(
                "scale_calibration.adjust_target_hint_line1",
                "scale_calibration.adjust_target_hint_line2",
            )
        )

    def render_measuring(self, elapsed_seconds, duration_seconds):
        shown_s = min(duration_seconds, elapsed_seconds)
        self._set_start_visible(False)
        self._set_progress_visible(True)
        self._info_label.set_text("")
        self._status_label.set_text(
            self._lines(
                "scale_calibration.measuring_label",
                "scale_calibration.measuring_progress",
                shown_s,
                duration_seconds,
            )
        )
        if duration_seconds:
            pct = int((shown_s * 100) / duration_seconds)
        else:
            pct = 100
        self._set_progress(pct)

    def render_average(self, average_adc):
        self._set_start_visible(False)
        self._set_progress_visible(True)
        self._info_label.set_text("")
        self._status_label.set_text(
            self._t("scale_calibration.average", int(average_adc))
        )
        self._set_progress(100)

    def render_complete(self, message=None):
        self._set_start_visible(False)
        self._set_progress_visible(False)
        self._step_label.set_text(self._t("scale_calibration.complete"))
        self._target_label.set_text(self._t("scale_calibration.done"))
        self._info_label.set_text("")
        if message is None:
            message = self._t("scale_calibration.data_saved")
        self._status_label.set_text(message)
        self._set_progress(0)

    def render_status(self, message):
        self._status_label.set_text(message)

    def render_error(self, message):
        self._set_start_visible(False)
        self._set_progress_visible(False)
        self._target_label.set_text(self._t("scale_calibration.error"))
        self._info_label.set_text("")
        self._status_label.set_text(message[:30])

    def _set_start_visible(self, visible):
        UIHelper.set_action_button_visible(
            self._start_bg,
            self._start_label,
            visible,
            self._t("scale_calibration.start_button"),
        )

    def _set_progress_visible(self, visible):
        self._progress_bar.set_flag(lv.obj.FLAG.HIDDEN, not visible)

    def _set_progress(self, percent):
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        self._progress_bar.set_value(int(percent), False)

    def _t(self, key, *args):
        if self._i18n:
            return self._i18n.t(key, *args)
        if key == "scale_calibration.title":
            return "Scale Calibration"
        if key == "scale_calibration.step":
            return "Step {}/{} - {}g".format(*args)
        if key == "scale_calibration.target":
            return "{} g".format(*args)
        if key == "scale_calibration.adjust_target_hint_line1":
            return "Turn"
        if key == "scale_calibration.adjust_target_hint_line2":
            return "to adjust target weight"
        if key == "scale_calibration.measuring_label":
            return "Measuring"
        if key == "scale_calibration.measuring_progress":
            return "{}/{}s".format(*args)
        if key == "scale_calibration.average":
            return "Avg: {}".format(*args)
        if key == "scale_calibration.complete":
            return "Calibration complete"
        if key == "scale_calibration.data_saved":
            return "Data saved"
        if key == "scale_calibration.done":
            return "Done"
        if key == "scale_calibration.error":
            return "Error"
        return key

    def _lines(self, key1, key2, *args):
        return self._t(key1) + "\n" + self._t(key2, *args)

    @classmethod
    def _safe_width(cls, y_center):
        dist_sq = (y_center - cls._R) * (y_center - cls._R)
        if dist_sq >= cls._R * cls._R:
            return 0
        chord = int(2.0 * (cls._R * cls._R - dist_sq) ** 0.5)
        return max(0, chord - 2 * cls._EDGE_MARGIN)
