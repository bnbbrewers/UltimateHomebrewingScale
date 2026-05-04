"""
Settings screen. Objects created once in __init__.
"""

import m5ui
import lvgl as lv

from .ui_helper import UIHelper


class SettingsScreen:
    def __init__(self, i18n=None):
        self._i18n = i18n
        self._items = []
        self._selected = 0

        self.page = m5ui.M5Page(bg_c=0x000000)

        self._title_bar, self._title = UIHelper.create_title(
            self.page,
            self._t("settings.title", "Settings"),
            0x333333,
        )

        self._status = m5ui.M5Label(
            "Rotate and press",
            x=0,
            y=198,
            text_c=0x6B7280,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._status.set_width(240)
        self._status.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._labels = []
        y = 70
        for _ in range(4):
            lbl = m5ui.M5Label(
                "",
                x=24,
                y=y,
                text_c=0x8B8B8B,
                bg_c=0x000000,
                bg_opa=0,
                font=lv.font_montserrat_14,
                parent=self.page,
            )
            lbl.set_width(192)
            lbl.set_style_text_align(lv.TEXT_ALIGN.LEFT, 0)
            self._labels.append(lbl)
            y += 28

    def root(self):
        return self.page

    def set_items(self, items, selected_index=0):
        self._items = items if items else []
        if self._items:
            if selected_index < 0:
                selected_index = 0
            if selected_index >= len(self._items):
                selected_index = len(self._items) - 1
            self._selected = selected_index
        else:
            self._selected = 0
        self._refresh()

    def set_selected_index(self, index):
        if not self._items:
            self._selected = 0
            self._refresh()
            return
        if index < 0:
            index = 0
        if index >= len(self._items):
            index = len(self._items) - 1
        self._selected = index
        self._refresh()

    def set_status(self, text):
        self._status.set_text(text)

    def get_selected_index(self):
        return self._selected

    def _refresh(self):
        total = len(self._items)
        for i in range(len(self._labels)):
            if i < total:
                text = self._items[i]
                prefix = "> " if i == self._selected else "  "
                self._labels[i].set_text(prefix + text)
                color = 0xFFFFFF if i == self._selected else 0x8B8B8B
                self._labels[i].set_style_text_color(lv.color_hex(color), 0)
            else:
                self._labels[i].set_text("")

    def _t(self, key, fallback):
        if self._i18n is None:
            return fallback
        return self._i18n.t(key)
