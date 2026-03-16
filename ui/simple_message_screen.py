"""
Simple message screen for short status/info display.
All LVGL objects are created once in __init__.
"""

import m5ui
import lvgl as lv


class SimpleMessageScreen:
    def __init__(self, i18n=None):
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=0x000000)

        self._title_bar = lv.obj(self.page)
        self._title_bar.set_size(240, 50)
        self._title_bar.set_pos(0, 0)
        self._title_bar.set_style_bg_color(lv.color_hex(0x333333), 0)
        self._title_bar.set_style_bg_opa(255, 0)
        self._title_bar.set_style_border_width(0, 0)
        self._title_bar.set_style_radius(0, 0)

        self._title_label = m5ui.M5Label(
            "",
            x=0,
            y=18,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.page,
        )
        self._title_label.set_width(240)
        self._title_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

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

    def root(self):
        return self.page

    def configure(self, title="", message="", title_bg_color=0x333333, text_color=0xE5E7EB):
        self.set_title(title)
        self.set_message(message)
        self.set_title_color(title_bg_color)
        self.set_text_color(text_color)

    def set_title(self, title):
        self._title_label.set_text(title)

    def set_message(self, message):
        self._message_label.set_text(message)

    def set_title_color(self, color):
        self._title_bar.set_style_bg_color(lv.color_hex(color), 0)

    def set_text_color(self, color):
        self._message_label.set_style_text_color(lv.color_hex(color), 0)
