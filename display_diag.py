"""
Temporary display diagnostic, started by holding the button at power-on.

Screens with a header show header-coloured pixels along the bottom edge.
The panel and a plain LVGL header were cleared by the first round, and the
same screens render clean bottom rows in a desktop LVGL build, so each step
below adds one ingredient of the real screens -- the title label, a header
redrawn after display, the hop list configured before or after display.
Each step is announced on a black page, then shown for STEP_MS while the
operator notes the bottom edge. The device restarts when the test ends.
"""

import time

CONFIRM_MS = 2000
STEP_MS = 10000

_BLACK = 0x000000
_WHITE = 0xFFFFFF


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


_GREEN = 0x4CAF50
_BLUE = 0x1976D2
_TITLE = "Selectionner un houblon"
_ITEMS = ["Columbus", "Citra", "Mosaic", "Saaz"]
INTRO_MS = 4000


def _intro(m5, m5ui, lv, number, lines):
    """Black page naming the next step: it has no header, so no band."""
    page = m5ui.M5Page(bg_c=_BLACK)
    label = m5ui.M5Label(
        "\n".join(("Step {}/{}".format(number, _STEP_COUNT),) + lines),
        x=0,
        y=80,
        text_c=_WHITE,
        bg_c=_BLACK,
        bg_opa=0,
        font=lv.font_montserrat_16,
        parent=page,
    )
    label.set_width(240)
    label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    _show(page)
    _pump(m5, INTRO_MS)


_current = [None]


def _show(page):
    previous = _current[0]
    page.screen_load()
    _current[0] = page
    if previous is not None:
        previous.delete()


def _step_title_static(m5, m5ui, lv, UIHelper):
    page = m5ui.M5Page(bg_c=_BLACK)
    UIHelper.create_title(page, _TITLE, _GREEN)
    _show(page)
    _pump(m5, STEP_MS)


def _step_title_text_after_load(m5, m5ui, lv, UIHelper):
    page = m5ui.M5Page(bg_c=_BLACK)
    _, label = UIHelper.create_title(page, "", _GREEN)
    _show(page)
    _pump(m5, 1000)
    UIHelper.set_title(label, _TITLE)
    _pump(m5, STEP_MS)


def _step_header_recolour_after_load(m5, m5ui, lv, UIHelper):
    page = m5ui.M5Page(bg_c=_BLACK)
    bar, _ = UIHelper.create_title(page, "", _BLUE)
    _show(page)
    _pump(m5, 1000)
    UIHelper.set_title_color(bar, _GREEN)
    _pump(m5, STEP_MS)


def _step_select_configured_before_load(m5, m5ui, lv, UIHelper):
    from ui.select_item_screen import SelectItemScreen

    screen = SelectItemScreen()
    screen.configure(_TITLE, _ITEMS, _GREEN)
    _show(screen.root())
    _pump(m5, STEP_MS)


def _step_select_configured_after_load(m5, m5ui, lv, UIHelper):
    from ui.select_item_screen import SelectItemScreen

    screen = SelectItemScreen()
    _show(screen.root())
    _pump(m5, 1000)
    screen.configure(_TITLE, _ITEMS, _GREEN)
    _pump(m5, STEP_MS)


# (step, description shown before it)
_STEPS = (
    (_step_title_static, ("header + title", "drawn once")),
    (_step_title_text_after_load, ("header, title text", "set after display")),
    (_step_header_recolour_after_load, ("header recoloured", "after display")),
    (_step_select_configured_before_load, ("hop list", "configured first")),
    (_step_select_configured_after_load, ("hop list", "configured after")),
)
_STEP_COUNT = len(_STEPS)


def run(m5):
    """Run every step, then restart. Call after M5.begin(), before m5ui.init()."""
    import lvgl as lv
    import m5ui
    from ui.ui_helper import UIHelper

    m5ui.init()
    for number, (step, lines) in enumerate(_STEPS, 1):
        print("[DISPLAY_DIAG] step {}: {}".format(number, " ".join(lines)))
        _intro(m5, m5ui, lv, number, lines)
        step(m5, m5ui, lv, UIHelper)

    print("[DISPLAY_DIAG] done, restarting")
    import machine

    machine.reset()
