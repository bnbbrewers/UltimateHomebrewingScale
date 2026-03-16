"""
Generic select-item screen with the same UI as former SelectableList.
All LVGL objects are created once in __init__.
"""

import m5ui
import lvgl as lv


class SelectItemScreen:
    _W = 240
    _R = 120
    _BAR_H = 56
    _TITLE_W = 130
    _TITLE_Y = 18
    _GAP_BAR = 4
    _MARGIN = 8
    _FAR_H = 16
    _NEAR_H = 30
    _SEL_H = 28
    _CNT_H = 18
    _GAP = 2
    _GAP_CNT = 4
    _F_TITLE = 14
    _F_FAR = 14
    _F_NEAR = 14
    _F_SEL = 16
    _F_CNT = 14
    _C_BG = 0x000000
    _C_TITLE = 0xFFFFFF
    _C_SEL = 0xFFFFFF
    _C_NEAR = 0x909090
    _C_FAR = 0x484848
    _C_CNT = 0x585858

    def __init__(self):
        self.page = m5ui.M5Page(bg_c=self._C_BG)
        self._items = []
        self._selected_index = 0
        self._accent_color = 0x1976D2

        self._title_bar = None
        self._title_lbl = None
        self._band = None
        self._labels = []
        self._slot_chars = []
        self._counter_lbl = None

        self._build("")
        self._refresh()

    def root(self):
        return self.page

    def configure(self, title, items, accent_color, selected_index=0):
        self.set_title(title)
        self.set_accent_color(accent_color)
        self.set_items(items, selected_index=selected_index)

    def set_items(self, items, selected_index=0):
        self._items = list(items) if items else []
        self.set_selected_index(selected_index)

    def set_title(self, title):
        if self._title_lbl:
            self._title_lbl.set_text(title)

    def set_accent_color(self, accent_color):
        self._accent_color = accent_color
        if self._title_bar:
            self._title_bar.set_style_bg_color(lv.color_hex(accent_color), 0)
        if self._band:
            self._band.set_style_bg_color(lv.color_hex(accent_color), 0)

    def set_selected_index(self, index):
        if not self._items:
            self._selected_index = 0
            self._refresh()
            return
        if index < 0:
            index = 0
        if index >= len(self._items):
            index = len(self._items) - 1
        self._selected_index = index
        self._refresh()

    def get_selected_index(self):
        return self._selected_index

    def _safe_width(self, y_center):
        dist_sq = (y_center - self._R) * (y_center - self._R)
        if dist_sq >= self._R * self._R:
            return 0
        chord = int(2.0 * (self._R * self._R - dist_sq) ** 0.5)
        return max(0, chord - 2 * self._MARGIN)

    @staticmethod
    def _max_chars(width_px, font_size):
        table = {12: 9, 14: 10, 16: 11, 18: 12, 20: 13}
        ppc = table.get(font_size, max(1, int(font_size * 0.7)))
        return max(4, width_px // ppc)

    def _make_label(self, text, x, y, color, font, width):
        lbl = m5ui.M5Label(
            text,
            x=x,
            y=y,
            text_c=color,
            bg_c=self._C_BG,
            bg_opa=0,
            font=font,
            parent=self.page,
        )
        lbl.set_width(width)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        return lbl

    def _make_solid_bar(self, x, y, w, h, color, radius=0, opa=255):
        bar = lv.obj(self.page)
        bar.set_size(w, h)
        bar.set_pos(x, y)
        bar.set_style_bg_color(lv.color_hex(color), 0)
        bar.set_style_bg_opa(opa, 0)
        bar.set_style_border_width(0, 0)
        bar.set_style_radius(radius, 0)
        bar.set_style_shadow_width(0, 0)
        return bar

    def _build(self, title):
        y = self._BAR_H + self._GAP_BAR

        self._title_bar = self._make_solid_bar(
            0, 0, self._W, self._BAR_H, self._accent_color, radius=0
        )
        lbl_x = (self._W - self._TITLE_W) // 2
        self._title_lbl = self._make_label(
            title, lbl_x, self._TITLE_Y, self._C_TITLE, lv.font_montserrat_14, self._TITLE_W
        )

        slot_defs = [
            (self._FAR_H, self._F_FAR, self._C_FAR, lv.font_montserrat_14),
            (self._NEAR_H, self._F_NEAR, self._C_NEAR, lv.font_montserrat_14),
            (self._SEL_H, self._F_SEL, self._C_SEL, lv.font_montserrat_16),
            (self._NEAR_H, self._F_NEAR, self._C_NEAR, lv.font_montserrat_14),
            (self._FAR_H, self._F_FAR, self._C_FAR, lv.font_montserrat_14),
        ]

        slot_widths = []
        self._slot_chars = []
        sy = y
        for slot_h, fsz, _color, _font in slot_defs:
            y_center = sy + slot_h // 2
            w = self._safe_width(y_center)
            slot_widths.append(w)
            self._slot_chars.append(self._max_chars(w, fsz))
            sy += slot_h + self._GAP

        sel_w = slot_widths[2]
        band_y = y + (self._FAR_H + self._GAP) + (self._NEAR_H + self._GAP)
        self._band = self._make_solid_bar(
            (self._W - sel_w) // 2, band_y, sel_w, self._SEL_H, self._accent_color, radius=16
        )

        for (slot_h, fsz, color, font), width in zip(slot_defs, slot_widths):
            x = (self._W - width) // 2
            line_h = fsz + 4
            y_text = y + max(0, (slot_h - line_h) // 2)
            lbl = self._make_label("", x, y_text, color, font, width)
            lbl.set_height(line_h)
            self._labels.append(lbl)
            y += slot_h + self._GAP

        y += self._GAP_CNT - self._GAP
        self._counter_lbl = self._make_label(
            "", 0, y, self._C_CNT, lv.font_montserrat_14, self._W
        )

    @staticmethod
    def _fit(text, max_chars):
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3] + "..."

    def _refresh(self):
        n = len(self._items)
        for i, offset in enumerate((-2, -1, 0, 1, 2)):
            idx = self._selected_index + offset
            text = self._items[idx] if 0 <= idx < n else ""
            self._labels[i].set_text(self._fit(text, self._slot_chars[i]))

        if self._counter_lbl:
            if n:
                self._counter_lbl.set_text(str(self._selected_index + 1) + " / " + str(n))
            else:
                self._counter_lbl.set_text("")
