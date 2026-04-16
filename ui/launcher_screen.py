"""
Launcher screen. LVGL objects are created once in __init__.
"""

import math
import m5ui
import lvgl as lv


_LABEL_I18N_MAP = {
    "Scale": "launcher.scale",
    "Malt": "launcher.malt",
    "Hop": "launcher.hop",
    "Keg": "launcher.keg",
    "Settings": "launcher.settings",
}


class LauncherScreen:
    _MAX_ITEMS = 5
    _SCREEN_W = 240
    _SCREEN_H = 240
    _CENTER_X = 120
    _CENTER_Y = 120
    _ICON_SIZE = 38
    _ICON_RADIUS = 102
    _ROUND_EDGE_MARGIN = 2
    _ARC_START = 105
    _ARC_TOTAL = 135

    def __init__(self, i18n=None):
        self._i18n = i18n
        self._items = []
        self._selected_index = 0
        self._icon_slots = []
        self._selection_indicator = None
        self._icons_initialized = False
        self._indicator_target_x = 0
        self._indicator_target_y = 0
        self._indicator_current_x = 0.0
        self._indicator_current_y = 0.0

        self.page = m5ui.M5Page(bg_c=0x000000)

        self._center_label = m5ui.M5Label(
            "",
            x=120,
            y=104,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_24,
            parent=self.page,
        )
        self._center_label.set_width(110)
        self._center_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        # Fixed white dot indicator (moved per selection)
        self._selection_indicator = lv.obj(self.page)
        self._selection_indicator.set_size(10, 10)
        self._selection_indicator.set_style_radius(5, 0)
        self._selection_indicator.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self._selection_indicator.set_style_bg_opa(255, 0)
        self._selection_indicator.set_style_border_width(0, 0)

        # Pre-create icon slots once (actual images loaded when set_items is called).
        for _ in range(self._MAX_ITEMS):
            self._icon_slots.append({
                "img": None,
                "x": 0,
                "y": 0,
                "angle": 0.0,
            })

    def root(self):
        return self.page

    def set_items(self, items):
        self._items = items if items else []
        if self._selected_index >= len(self._items):
            self._selected_index = 0
        if not self._icons_initialized:
            self._create_icons_once()
            self._icons_initialized = True
        self._update_selection(self._selected_index)

    def set_selected_index(self, index):
        if not self._items:
            self._selected_index = 0
            return
        if index < 0:
            index = len(self._items) - 1
        elif index >= len(self._items):
            index = 0
        self._update_selection(index)

    def move_selection(self, direction):
        self.set_selected_index(self._selected_index + direction)

    def get_selected_index(self):
        return self._selected_index

    def _label_text(self, raw):
        if self._i18n is None:
            return raw
        key = _LABEL_I18N_MAP.get(raw)
        if key is None:
            return raw
        return self._i18n.t(key)

    def handle_rotary_delta(self, delta):
        if not self._items:
            return
        # Original behavior: clockwise = previous, counter-clockwise = next.
        direction = -1 if delta > 0 else 1
        self._update_selection(self._selected_index + direction)

    def animate_indicator(self):
        if self._selection_indicator is None:
            return
        lerp = 0.5
        dx = self._indicator_target_x - self._indicator_current_x
        dy = self._indicator_target_y - self._indicator_current_y
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            self._indicator_current_x = float(self._indicator_target_x)
            self._indicator_current_y = float(self._indicator_target_y)
        else:
            self._indicator_current_x += dx * lerp
            self._indicator_current_y += dy * lerp
        self._selection_indicator.set_pos(int(self._indicator_current_x), int(self._indicator_current_y))

    def _update_selection(self, new_index):
        total = len(self._items)
        if total == 0:
            self._selected_index = 0
            self._center_label.set_text("No app")
            self._selection_indicator.set_pos(-20, -20)
            return
        if new_index < 0:
            new_index = total - 1
        elif new_index >= total:
            new_index = 0
        self._selected_index = new_index
        center = self._label_text(self._items[self._selected_index].get("label", ""))
        self._center_label.set_text(center)
        self._move_indicator_to_selected()

    def _create_icons_once(self):
        total = len(self._items)
        if total <= 0:
            return
        icon_radius = self._get_safe_icon_radius()

        if total > 1:
            angle_step = float(self._ARC_TOTAL) / float(total - 1)
        else:
            angle_step = 0.0

        for i in range(min(total, self._MAX_ITEMS)):
            item = self._items[i]
            angle_deg = float(self._ARC_START + self._ARC_TOTAL) - (float(i) * angle_step)
            angle_rad = math.radians(angle_deg)
            x = int(self._CENTER_X + icon_radius * math.cos(angle_rad) - (self._ICON_SIZE / 2))
            y = int(self._CENTER_Y + icon_radius * math.sin(angle_rad) - (self._ICON_SIZE / 2))
            x = self._clamp(x, 0, self._SCREEN_W - self._ICON_SIZE)
            y = self._clamp(y, 0, self._SCREEN_H - self._ICON_SIZE)

            icon_path = item.get("icon", "")
            img = m5ui.M5Image(
                icon_path,
                x=x,
                y=y,
                parent=self.page,
            )
            img.set_scale(1.0, 1.0)
            img.set_pivot(self._ICON_SIZE // 2, self._ICON_SIZE // 2)
            img.set_size(self._ICON_SIZE, self._ICON_SIZE)
            self._icon_slots[i]["img"] = img
            self._icon_slots[i]["x"] = x
            self._icon_slots[i]["y"] = y
            self._icon_slots[i]["angle"] = angle_deg

    def _move_indicator_to_selected(self):
        if not self._items:
            return
        if self._selected_index >= len(self._icon_slots):
            return

        total = len(self._items)
        if total > 1:
            angle_step = float(self._ARC_TOTAL) / float(total - 1)
        else:
            angle_step = 0.0

        icon_radius = self._get_safe_icon_radius()
        angle_deg = float(self._ARC_START + self._ARC_TOTAL) - (float(self._selected_index) * angle_step)
        angle_rad = math.radians(angle_deg)
        indicator_radius = icon_radius - (self._ICON_SIZE // 2) - 13
        ix = int(self._CENTER_X + indicator_radius * math.cos(angle_rad) - 5)
        iy = int(self._CENTER_Y + indicator_radius * math.sin(angle_rad) - 5)
        ix = self._clamp(ix, 0, self._SCREEN_W - 10)
        iy = self._clamp(iy, 0, self._SCREEN_H - 10)
        if self._indicator_current_x == 0.0 and self._indicator_current_y == 0.0:
            self._indicator_current_x = float(ix)
            self._indicator_current_y = float(iy)
            self._selection_indicator.set_pos(ix, iy)
        self._indicator_target_x = ix
        self._indicator_target_y = iy

    @staticmethod
    def _clamp(value, min_value, max_value):
        if value < min_value:
            return min_value
        if value > max_value:
            return max_value
        return value

    def _get_safe_icon_radius(self):
        # Keep full icon square inside the round display.
        dial_radius = min(self._CENTER_X, self._CENTER_Y)
        icon_half_diagonal = (math.sqrt(2.0) * self._ICON_SIZE) / 2.0
        max_safe_radius = int(dial_radius - icon_half_diagonal - self._ROUND_EDGE_MARGIN)
        return self._clamp(self._ICON_RADIUS, 0, max_safe_radius)
