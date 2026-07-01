"""
Updater screen.

Owns LVGL/m5ui widgets only. Update orchestration lives in updater.update_app.
"""

import lvgl as lv
import m5ui

from .ui_helper import UIHelper


class UpdaterScreen:
    _W = 240
    _BG = 0x000000
    _TITLE = 0x1565C0
    _TEXT = 0xFFFFFF
    _MUTED = 0x9CA3AF
    _DIM = 0x6B7280
    _PROGRESS_BG = 0x263238
    _PROGRESS = 0x4CAF50
    _ERROR = 0xD32F2F

    def __init__(self, i18n=None):
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=self._BG)

        self._title_bar, self._title_label = UIHelper.create_title(
            self.page,
            self._t("updater.title"),
            self._TITLE,
            width=self._W,
        )

        self._status_label = m5ui.M5Label(
            "",
            x=0,
            y=76,
            text_c=self._TEXT,
            bg_c=self._BG,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.page,
        )
        self._status_label.set_width(self._W)
        self._status_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._detail_label = m5ui.M5Label(
            "",
            x=18,
            y=112,
            text_c=self._MUTED,
            bg_c=self._BG,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._detail_label.set_width(204)
        self._detail_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._progress = m5ui.M5Bar(
            x=30,
            y=154,
            w=180,
            h=18,
            min_value=0,
            max_value=100,
            value=0,
            bg_c=self._PROGRESS_BG,
            color=self._PROGRESS,
            parent=self.page,
        )
        self._progress.set_bg_color(
            lv.color_hex(self._PROGRESS_BG),
            255,
            lv.PART.MAIN | lv.STATE.DEFAULT,
        )
        self._progress.set_bg_color(
            lv.color_hex(self._PROGRESS),
            255,
            lv.PART.INDICATOR | lv.STATE.DEFAULT,
        )

        self._percent_label = m5ui.M5Label(
            "0%",
            x=0,
            y=180,
            text_c=self._DIM,
            bg_c=self._BG,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._percent_label.set_width(self._W)
        self._percent_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._ok_bg, self._ok_label = UIHelper.create_action_button(self.page)
        self.set_ok_visible(False)

    def root(self):
        return self.page

    def configure(self, title=None, title_bg_color=None):
        UIHelper.set_title(self._title_label, title or self._t("updater.title"))
        if title_bg_color is not None:
            UIHelper.set_title_color(self._title_bar, title_bg_color)
        self._progress.set_bg_color(
            lv.color_hex(self._PROGRESS),
            255,
            lv.PART.INDICATOR | lv.STATE.DEFAULT,
        )
        self.set_progress(0)
        self.set_status(self._t("updater.ready"), "")
        self.set_ok_visible(False)

    def set_status(self, message, detail=""):
        self._status_label.set_text(self._fit(message, 28))
        self._detail_label.set_text(self._fit(detail, 44))

    def set_progress(self, percent):
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        pct = int(percent)
        self._progress.set_value(pct, False)
        self._percent_label.set_text("{}%".format(pct))

    def show_done(self, message):
        self.set_progress(100)
        text = str(message or "")
        if ", " in text:
            text = text.replace(", ", ",\n", 1)
        self._status_label.set_text(text)
        self._detail_label.set_text("")
        self.set_ok_visible(True)

    def show_error(self, message):
        UIHelper.set_title_color(self._title_bar, self._ERROR)
        self._progress.set_bg_color(
            lv.color_hex(self._ERROR),
            255,
            lv.PART.INDICATOR | lv.STATE.DEFAULT,
        )
        self.set_status(self._t("updater.error"), message)
        self.set_ok_visible(True)

    def set_ok_visible(self, visible):
        UIHelper.set_action_button_visible(
            self._ok_bg,
            self._ok_label,
            visible,
            self._t("common.ok"),
        )

    def _t(self, key):
        if self._i18n:
            return self._i18n.t(key)
        if key == "common.ok":
            return "OK"
        if key == "updater.title":
            return "Updater"
        if key == "updater.ready":
            return "Preparation..."
        if key == "updater.error":
            return "Erreur"
        return key

    @staticmethod
    def _fit(text, max_chars):
        text = str(text or "")
        if len(text) <= max_chars:
            return text
        if max_chars <= 3:
            return text[:max_chars]
        return text[: max_chars - 3] + "..."
