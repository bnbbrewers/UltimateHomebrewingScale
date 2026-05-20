"""
Simple message screen for short status/info display.
All LVGL objects are created once in __init__.
"""

import m5ui
import lvgl as lv

from .ui_helper import (
    ACTION_BUTTON_Y,
    TITLE_Y_ONE_LINE,
    TITLE_Y_TWO_LINES,
    UIHelper,
    format_title_text,
)
from memory_debug import snapshot as mem_snapshot

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False


MESSAGE_LINE_HEIGHT = 18
MESSAGE_MAX_CHARS_PER_LINE = 24
MESSAGE_AREA_TOP = 50
MESSAGE_AREA_BOTTOM = ACTION_BUTTON_Y
MESSAGE_TITLE_GAP = 8


def _wrapped_line_count(text, max_chars=MESSAGE_MAX_CHARS_PER_LINE):
    total = 0
    for paragraph in str(text or "").split("\n"):
        if not paragraph:
            total += 1
            continue
        line_len = 0
        for word in paragraph.split(" "):
            word_len = len(word)
            if line_len and line_len + 1 + word_len > max_chars:
                total += 1
                line_len = word_len
            else:
                line_len = word_len if not line_len else line_len + 1 + word_len
        total += 1
    return max(1, total)


def message_area_top_for_title(title):
    formatted_title = format_title_text(title)
    if not formatted_title:
        return MESSAGE_AREA_TOP
    line_count = len(formatted_title.split("\n"))
    y = TITLE_Y_TWO_LINES if line_count > 1 else TITLE_Y_ONE_LINE
    line_height = 18 if line_count > 1 else 20
    return y + (line_count * line_height) + MESSAGE_TITLE_GAP


def centered_message_y(
    message,
    area_top=MESSAGE_AREA_TOP,
    area_bottom=MESSAGE_AREA_BOTTOM,
    line_height=MESSAGE_LINE_HEIGHT,
):
    line_count = _wrapped_line_count(message)
    text_height = line_count * line_height
    available_height = max(0, area_bottom - area_top)
    if text_height >= available_height:
        return area_top
    return area_top + ((available_height - text_height) // 2)


class SimpleMessageScreen:
    def __init__(self, i18n=None):
        mem_snapshot("simple.init.start", enabled=_DEBUG, collect=True)
        self._i18n = i18n
        self._message_area_top = MESSAGE_AREA_TOP
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
        self._message_area_top = message_area_top_for_title(title)

    def set_message(self, message):
        self._message_label.set_pos(
            20,
            centered_message_y(message, area_top=self._message_area_top),
        )
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
