"""
Simple message screen for short status/info display.
All LVGL objects are created once in __init__.
"""

import m5ui
import lvgl as lv

from .ui_helper import UIHelper
from memory_debug import snapshot as mem_snapshot

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False


class SimpleMessageScreen:
    def __init__(self, i18n=None):
        mem_snapshot("simple.init.start", enabled=_DEBUG, collect=True)
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=0x000000)
        mem_snapshot("simple.after_page", enabled=_DEBUG, collect=True)

        self._title_bar, self._title_label = UIHelper.create_title(
            self.page,
            "",
            0x333333,
        )
        mem_snapshot("simple.after_title", enabled=_DEBUG, collect=True)

        self._message_label = m5ui.M5Label(
            "",
            x=20,
            y=100,
            text_c=0xE5E7EB,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.page,
        )
        self._message_label.set_width(200)
        self._message_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        mem_snapshot("simple.after_message", enabled=_DEBUG, collect=True)

        self._ok_bg, self._ok_label = UIHelper.create_action_button(self.page)
        mem_snapshot("simple.after_ok_bg", enabled=_DEBUG, collect=True)
        mem_snapshot("simple.init.done", enabled=_DEBUG, collect=True)

    def root(self):
        return self.page

    def _ok_caption(self):
        if self._i18n:
            return self._i18n.t("common.ok")
        return "common.ok"

    def configure(
        self,
        title="",
        message="",
        title_bg_color=0x333333,
        text_color=0xE5E7EB,
        show_ok_button=False,
    ):
        self.set_title(title)
        self.set_message(message)
        self.set_title_color(title_bg_color)
        self.set_text_color(text_color)
        self.set_ok_visible(show_ok_button)

    def set_title(self, title):
        UIHelper.set_title(self._title_label, title)

    def set_message(self, message):
        self._message_label.set_text(message)

    def set_title_color(self, color):
        UIHelper.set_title_color(self._title_bar, color)

    def set_text_color(self, color):
        self._message_label.set_style_text_color(lv.color_hex(color), 0)

    def set_ok_visible(self, visible):
        UIHelper.set_action_button_visible(
            self._ok_bg,
            self._ok_label,
            visible,
            self._ok_caption(),
        )
