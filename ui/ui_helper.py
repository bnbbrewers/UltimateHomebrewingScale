"""
Small UI construction helpers shared by screens.

Keep pure helpers importable on desktop; import LVGL/m5ui only inside methods
that actually build widgets on the device.
"""


SCREEN_W = 240
TITLE_LABEL_W = 130
TITLE_BAR_H = 50
TITLE_FONT_SIZE = 16
TITLE_MAX_LINES = 2
TITLE_MAX_CHARS_PER_LINE = 13
TITLE_Y_ONE_LINE = 18
TITLE_Y_TWO_LINES = 10
ACTION_BUTTON_W = 240
ACTION_BUTTON_H = 40
ACTION_BUTTON_X = 0
ACTION_BUTTON_Y = 212
ACTION_BUTTON_LABEL_X = 0
ACTION_BUTTON_LABEL_Y = 215
ACTION_BUTTON_COLOR = 0x4CAF50


def format_title_text(text, max_chars_per_line=TITLE_MAX_CHARS_PER_LINE, max_lines=TITLE_MAX_LINES):
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    if len(clean) <= max_chars_per_line:
        return clean

    words = clean.split(" ")
    lines = []
    current = ""

    for word in words:
        candidate = word if not current else current + " " + word
        if len(candidate) <= max_chars_per_line:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = word
        else:
            lines.append(word)
            current = ""
        if len(lines) >= max_lines - 1:
            break

    remaining = []
    if current:
        remaining.append(current)
    consumed = " ".join(lines + remaining).split()
    consumed_count = len(consumed)
    if consumed_count < len(words):
        remaining.extend(words[consumed_count:])

    if remaining:
        lines.append(" ".join(remaining))

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return "\n".join(lines)


class UIHelper:
    @staticmethod
    def _title_y(title):
        return TITLE_Y_TWO_LINES if "\n" in title else TITLE_Y_ONE_LINE

    @staticmethod
    def _title_font(title):
        import lvgl as lv

        if "\n" in title:
            return lv.font_montserrat_14
        return lv.font_montserrat_16

    @staticmethod
    def _set_font(label, font):
        try:
            label.set_style_text_font(font, 0)
            return
        except Exception:
            pass
        try:
            label.set_font(font)
        except Exception:
            pass

    @staticmethod
    def set_title(label, title):
        formatted_title = format_title_text(title)
        label.set_text(formatted_title)
        label.set_pos((SCREEN_W - TITLE_LABEL_W) // 2, UIHelper._title_y(formatted_title))
        UIHelper._set_font(label, UIHelper._title_font(formatted_title))

    @staticmethod
    def set_title_color(title_bar, color):
        import lvgl as lv

        title_bar.set_style_bg_color(lv.color_hex(color), 0)

    @staticmethod
    def create_title(parent, title, color, width=SCREEN_W, label_width=TITLE_LABEL_W):
        import lvgl as lv
        import m5ui

        title_bar = lv.obj(parent)
        title_bar.set_size(width, TITLE_BAR_H)
        title_bar.set_pos(0, 0)
        title_bar.set_style_bg_color(lv.color_hex(color), 0)
        title_bar.set_style_bg_opa(255, 0)
        title_bar.set_style_border_width(0, 0)
        title_bar.set_style_radius(0, 0)

        formatted_title = format_title_text(title)
        label_x = (width - label_width) // 2
        title_label = m5ui.M5Label(
            formatted_title,
            x=label_x,
            y=UIHelper._title_y(formatted_title),
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=UIHelper._title_font(formatted_title),
            parent=parent,
        )
        title_label.set_width(label_width)
        title_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        return title_bar, title_label

    @staticmethod
    def create_action_button(parent):
        import lvgl as lv
        import m5ui

        button_bg = lv.obj(parent)
        button_bg.set_size(ACTION_BUTTON_W, ACTION_BUTTON_H)
        button_bg.set_pos(ACTION_BUTTON_X, ACTION_BUTTON_Y)
        button_bg.set_style_bg_color(lv.color_hex(ACTION_BUTTON_COLOR), 0)
        button_bg.set_style_bg_opa(0, 0)
        button_bg.set_style_border_width(0, 0)
        button_bg.set_style_radius(0, 0)

        button_label = m5ui.M5Label(
            "",
            x=ACTION_BUTTON_LABEL_X,
            y=ACTION_BUTTON_LABEL_Y,
            text_c=0xFFFFFF,
            bg_c=ACTION_BUTTON_COLOR,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=parent,
        )
        button_label.set_width(ACTION_BUTTON_W)
        button_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        return button_bg, button_label

    @staticmethod
    def set_action_button_visible(button_bg, button_label, visible, label):
        button_label.set_text(label if visible else "")
        button_bg.set_style_bg_opa(255 if visible else 0, 0)
