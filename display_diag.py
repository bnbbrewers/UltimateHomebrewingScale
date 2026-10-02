"""
Temporary display diagnostic, started by holding the button at power-on.

Some screens show header-coloured pixels along the bottom edge. The steps
below tell a panel/driver fault (the top rows wrap to the bottom even without
LVGL) from an LVGL rendering one. Each step lasts STEP_MS; the operator notes
what the bottom edge shows. The device restarts when the test ends.
"""

import time

CONFIRM_MS = 2000
STEP_MS = 12000

_BLACK = 0x000000
_WHITE = 0xFFFFFF
_RED = 0xFF0000

# 4-px stripes on rows 0-19, then a block down to row 49 like a header.
_STRIPES = (
    (0, 4, 0xFF0000),
    (4, 4, 0x00FF00),
    (8, 4, 0x0000FF),
    (12, 4, 0xFFFFFF),
    (16, 4, 0xFFFF00),
    (20, 30, 0xFF00FF),
)


def _pump(m5, ms):
    # m5ui.init() schedules lv.task_handler() itself; never call it here.
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        m5.update()
        time.sleep_ms(20)


def _lcd_text(m5, lines, y=110):
    lcd = m5.Lcd
    lcd.setFont(lcd.FONTS.DejaVu18)
    lcd.setTextColor(_WHITE, _BLACK)
    for index, line in enumerate(lines):
        lcd.drawCenterString(line, 120, y + index * 22)


def requested(m5):
    """True when the button is held for CONFIRM_MS right after M5.begin()."""
    m5.update()
    if not m5.BtnA.isPressed():
        return False
    m5.Lcd.fillScreen(_BLACK)
    _lcd_text(m5, ("Display test", "keep holding"), y=100)
    end = time.ticks_add(time.ticks_ms(), CONFIRM_MS)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        m5.update()
        if not m5.BtnA.isPressed():
            m5.Lcd.fillScreen(_BLACK)
            return False
        time.sleep_ms(20)
    m5.Lcd.fillScreen(_BLACK)
    _lcd_text(m5, ("Display test", "release button"), y=100)
    while m5.BtnA.isPressed():
        m5.update()
        time.sleep_ms(20)
    return True


def _lvgl_page(m5ui, lv, header_y, lines):
    page = m5ui.M5Page(bg_c=_BLACK)
    header = lv.obj(page)
    header.set_size(240, 50)
    header.set_pos(0, header_y)
    header.set_style_bg_color(lv.color_hex(_RED), 0)
    header.set_style_bg_opa(255, 0)
    header.set_style_border_width(0, 0)
    header.set_style_radius(0, 0)
    label = m5ui.M5Label(
        "\n".join(lines),
        x=0,
        y=110,
        text_c=_WHITE,
        bg_c=_BLACK,
        bg_opa=0,
        font=lv.font_montserrat_16,
        parent=page,
    )
    label.set_width(240)
    label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    return page


def run(m5):
    """Run every step, then restart. Call after M5.begin(), before m5ui.init()."""
    lcd = m5.Lcd

    print("[DISPLAY_DIAG] step 1: M5GFX stripes on rows 0-49")
    lcd.fillScreen(_BLACK)
    for y, h, color in _STRIPES:
        lcd.fillRect(0, y, 240, h, color)
    _lcd_text(m5, ("1/4  no LVGL", "stripes on top", "bottom?"))
    _pump(m5, STEP_MS)

    print("[DISPLAY_DIAG] step 2: M5GFX, top rows black")
    lcd.fillScreen(_BLACK)
    _lcd_text(m5, ("2/4  no LVGL", "top rows black", "bottom?"))
    _pump(m5, STEP_MS)

    import lvgl as lv
    import m5ui

    m5ui.init()

    print("[DISPLAY_DIAG] step 3: LVGL red header on rows 0-49")
    _lvgl_page(m5ui, lv, 0, ("3/4  LVGL", "header rows 0-49", "bottom?")).screen_load()
    _pump(m5, STEP_MS)

    print("[DISPLAY_DIAG] step 4: LVGL red header on rows 20-69")
    _lvgl_page(m5ui, lv, 20, ("4/4  LVGL", "header rows 20-69", "bottom?")).screen_load()
    _pump(m5, STEP_MS)

    print("[DISPLAY_DIAG] done, restarting")
    import machine

    machine.reset()
