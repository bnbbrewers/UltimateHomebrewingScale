"""
Launcher screen. LVGL objects are created once and reused: an icon slot gets
its image the first time an entry needs it and is hidden, never destroyed,
when the entry goes away.
"""

import math
import m5ui
import lvgl as lv


class LauncherScreen:
    # Five apps plus the update entry, which only exists when a newer
    # release is available (updater.update_notice).
    _MAX_ITEMS = 6
    _SCREEN_W = 240
    _SCREEN_H = 240
    _CENTER_X = 120
    _CENTER_Y = 120
    _ICON_SIZE = 38
    _ICON_RADIUS = 102
    _ROUND_EDGE_MARGIN = 2
    _ARC_START = 105
    _ARC_TOTAL = 135
    # The five apps' spacing (135 / 4), kept whatever the number of entries:
    # the apps never move, and a sixth icon spread over the same arc would
    # put its black corners over its neighbours' discs.
    _ANGLE_STEP = 33.75
    _CAPTION_X = 120
    _CAPTION_W = 110
    _TITLE_Y = 104
    _TITLE_Y_WITH_DETAIL = 84
    _DETAIL_Y = 114

    def __init__(self, i18n=None):
        self._i18n = i18n
        self._items = []
        self._selected_index = 0
        self._icon_slots = []
        self._selection_indicator = None
        self._indicator_target_x = 0
        self._indicator_target_y = 0
        self._indicator_current_x = 0.0
        self._indicator_current_y = 0.0

        self.page = m5ui.M5Page(bg_c=0x000000)

        self._center_label = self._make_caption_label(self._TITLE_Y, lv.font_montserrat_24)
        # Lines 2-3 of an entry that carries caption_lines (the update's versions).
        self._detail_label = self._make_caption_label(self._DETAIL_Y, lv.font_montserrat_16)

        # Fixed white dot indicator (moved per selection)
        self._selection_indicator = lv.obj(self.page)
        self._selection_indicator.set_size(10, 10)
        self._selection_indicator.set_style_radius(5, 0)
        self._selection_indicator.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)
        self._selection_indicator.set_style_bg_opa(255, 0)
        self._selection_indicator.set_style_border_width(0, 0)

        for _ in range(self._MAX_ITEMS):
            self._icon_slots.append({"img": None, "path": None, "hidden": False})

    def _make_caption_label(self, y, font):
        label = m5ui.M5Label(
            "",
            x=self._CAPTION_X,
            y=y,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=font,
            parent=self.page,
        )
        label.set_width(self._CAPTION_W)
        label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        return label

    def root(self):
        return self.page

    def set_items(self, items):
        self._items = items if items else []
        if self._selected_index >= len(self._items):
            self._selected_index = 0
        self._sync_icons()
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

    def _label_text(self, item):
        """Translate an item's label through the key the item carries.

        The key travels with the item (app_registry fills it in) instead of
        living in a label-to-key table here, which could not be kept in step
        with the app list.
        """
        raw = item.get("label", "")
        key = item.get("i18n")
        if self._i18n is None or not key:
            return raw
        try:
            return self._i18n.t(key)
        except Exception:
            return raw

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
            self._show_caption("No app", "")
            self._selection_indicator.set_pos(-20, -20)
            return
        if new_index < 0:
            new_index = total - 1
        elif new_index >= total:
            new_index = 0
        old_index = self._selected_index
        self._selected_index = new_index
        item = self._items[self._selected_index]
        lines = item.get("caption_lines")
        if lines:
            self._show_caption(lines[0], "\n".join(lines[1:]))
        else:
            self._show_caption(self._label_text(item), "")
        self._move_indicator_to_selected()
        if old_index != new_index:
            self._play_selection_beep()

    def _show_caption(self, title, detail):
        self._center_label.set_y(self._TITLE_Y_WITH_DETAIL if detail else self._TITLE_Y)
        self._center_label.set_text(title)
        self._detail_label.set_text(detail)

    def _sync_icons(self):
        for i, slot in enumerate(self._icon_slots):
            img = slot["img"]
            if i >= len(self._items):
                if img is not None and not slot["hidden"]:
                    img.add_flag(lv.obj.FLAG.HIDDEN)
                    slot["hidden"] = True
                continue
            path = self._items[i].get("icon", "")
            if img is None:
                x, y = self.icon_position(i)
                img = m5ui.M5Image(path, x=x, y=y, parent=self.page)
                img.set_scale(1.0, 1.0)
                img.set_pivot(self._ICON_SIZE // 2, self._ICON_SIZE // 2)
                img.set_size(self._ICON_SIZE, self._ICON_SIZE)
                slot["img"] = img
                slot["path"] = path
                slot["hidden"] = False
                continue
            if slot["path"] != path:
                img.set_image(path)
                slot["path"] = path
            if slot["hidden"]:
                img.remove_flag(lv.obj.FLAG.HIDDEN)
                slot["hidden"] = False

    def _icon_angle(self, index):
        return float(self._ARC_START + self._ARC_TOTAL) - float(index) * self._ANGLE_STEP

    def icon_position(self, index):
        """Top-left corner of the icon at `index` on the wheel."""
        icon_radius = self._get_safe_icon_radius()
        angle_rad = math.radians(self._icon_angle(index))
        x = int(self._CENTER_X + icon_radius * math.cos(angle_rad) - (self._ICON_SIZE / 2))
        y = int(self._CENTER_Y + icon_radius * math.sin(angle_rad) - (self._ICON_SIZE / 2))
        x = self._clamp(x, 0, self._SCREEN_W - self._ICON_SIZE)
        y = self._clamp(y, 0, self._SCREEN_H - self._ICON_SIZE)
        return x, y

    def _move_indicator_to_selected(self):
        if not self._items:
            return
        if self._selected_index >= len(self._icon_slots):
            return

        icon_radius = self._get_safe_icon_radius()
        angle_rad = math.radians(self._icon_angle(self._selected_index))
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

    @staticmethod
    def _play_selection_beep():
        try:
            import M5
            M5.Speaker.tone(4000, 50)
        except Exception:
            pass
