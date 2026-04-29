"""
Small UI construction helpers shared by screens.

Keep pure helpers importable on desktop; import LVGL/m5ui only inside methods
that actually build widgets on the device.
"""


SCREEN_W = 240
TITLE_BAR_H = 50
TITLE_FONT_SIZE = 16
TITLE_MAX_LINES = 2
TITLE_MAX_CHARS_PER_LINE = 16


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
    def create_title(parent, title, color, width=SCREEN_W):
        import lvgl as lv
        import m5ui

        title_bar = lv.obj(parent)
        title_bar.set_size(width, TITLE_BAR_H)
        title_bar.set_pos(0, 0)
        title_bar.set_style_bg_color(lv.color_hex(color), 0)
        title_bar.set_style_bg_opa(255, 0)
        title_bar.set_style_border_width(0, 0)
        title_bar.set_style_radius(0, 0)
        title_bar.set_style_shadow_width(0, 0)

        formatted_title = format_title_text(title)
        label_y = 6 if "\n" in formatted_title else 18
        title_label = m5ui.M5Label(
            formatted_title,
            x=0,
            y=label_y,
            text_c=0xFFFFFF,
            bg_c=color,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=parent,
        )
        title_label.set_width(width)
        title_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        return title_bar, title_label
