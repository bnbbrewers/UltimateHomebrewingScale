"""
Selectable List Component
Reusable UI component for the round M5Stack Dial screen (240x240).

Circle-safe layout (r = cy = 120 px):
  W_max at y  =  2 * sqrt(120^2 - (y-120)^2)

  y=21  -> W_max=136 px  -> title label uses 130 px  (safe)
  y=37  -> W_max=170 px  -> 2nd wrapped line          (safe)
  y=60  -> W_max=208 px  -> far items use 140 px      (safe)
  y=218 -> W_max=139 px  -> far items use 135 px      (safe)

Full layout (default constants):

  y=  0 +--------------------------------------------+  accent bar  h=56
        |      TITLE / INSTRUCTION  (font-12)         |  w=130 px centred, wraps if needed
        |        optional 2nd line                    |
  y= 56 +--------------------------------------------+
  y= 60    [item  -2]  dark grey  font-12  w=135 px  ...
  y= 78    [item  -1]  grey       font-14  w=180 px  ...
  y= 80 +-----------------------------------------+
  y=110 |          [  SELECTED ITEM  ]             |  accent band  h=58  r=16
  y=168 |  full text, wraps to a second line       |
  y=170 +-----------------------------------------+
  y=170    [item  +1]  grey       font-14  w=180 px  ...
  y=202    [item  +2]  dark grey  font-12  w=135 px  ...
  y=222         3 / 12

Navigate: rotary encoder.  Confirm: button press.

Typical usage
-------------
    lst = SelectableList(
        page, items,
        title="Selectionner une recette",
        accent_color=0x1976D2
    )
    # Inside update():
    delta = rotary.get_rotary_value()
    if delta:
        rotary.reset_rotary_value()
        lst.handle_encoder(delta)

    if M5.BtnA.isPressed():
        result = lst.handle_button()   # -> (index, text)  or  None
"""

import m5ui
import lvgl as lv


# -- Font helper ---------------------------------------------------------------

def _get_font(size):
    """Return an LVGL Montserrat font at the requested size.

    Fallback tries the nearest even sizes downward first, then upward,
    so a missing font always resolves to a smaller (never larger) size.
    """
    candidates = [size]
    for delta in range(2, 12, 2):
        if size - delta >= 10:
            candidates.append(size - delta)
    for delta in range(2, 12, 2):
        candidates.append(size + delta)
    for s in candidates:
        name = f"font_montserrat_{s}"
        if hasattr(lv, name):
            return getattr(lv, name)
    return None


# -- Component -----------------------------------------------------------------

class SelectableList:
    """
    Selectable list for the round 240x240 M5Stack Dial screen.

    Header bar (y=0..55, full width, accent colour)
    ------------------------------------------------
    White font-12 title text, centred horizontally at y=21, max 130 px wide.
    Wraps to a second line if needed (2nd line at y~37, both safe for round screen).

    Parameters
    ----------
    parent : M5Page / lv.obj
    items : list[str]
        Items to display; replaceable via set_items().
    title : str
        Instruction text shown in the accent bar (e.g. "Selectionner une recette").
    accent_color : int
        24-bit hex colour for the bar and the selection band.
        - recipes  -> 0x1976D2  (blue)
        - malts    -> 0xF57C00  (amber)
        - hops     -> 0x388E3C  (green)
    """

    # -- Screen ----------------------------------------------------------------
    _W   = 240
    _R   = 120   # circle radius = cy

    # -- Title bar -------------------------------------------------------------
    # At y=18: chord = 2*sqrt(120^2-102^2) = 140 px  -> 130 px label is safe
    # 2nd wrapped line at y=34: chord = 173 px        -> 130 px still safe
    _BAR_H   = 56
    _TITLE_W = 130
    _TITLE_Y = 18
    _GAP_BAR = 4     # gap between bar bottom and first item slot

    # -- Horizontal safety margin (px each side, keeps text inside the disc) --
    _MARGIN  = 8

    # -- Item slot heights -----------------------------------------------------
    _FAR_H   = 16
    _NEAR_H  = 30
    _SEL_H   = 28    # single line font-16 (~20 px) + padding
    _CNT_H   = 18
    _GAP     = 2
    _GAP_CNT = 4

    # -- Font sizes ------------------------------------------------------------
    _F_TITLE = 12   # small enough for long strings to wrap safely within _TITLE_W
    _F_FAR   = 12
    _F_NEAR  = 14
    _F_SEL   = 16
    _F_CNT   = 12

    # -- Colours ---------------------------------------------------------------
    _C_BG    = 0x000000
    _C_TITLE = 0xFFFFFF
    _C_SEL   = 0xFFFFFF
    _C_NEAR  = 0x909090
    _C_FAR   = 0x484848
    _C_CNT   = 0x585858

    # -- Construction ----------------------------------------------------------

    def __init__(self, parent, items, title="", accent_color=0x1976D2):
        self.parent         = parent
        self.items          = list(items) if items else []
        self.accent_color   = accent_color
        self.selected_index = 0

        self._title_bar   = None
        self._title_lbl   = None
        self._band        = None
        self._labels      = []
        self._slot_chars  = []   # max chars per slot, computed in _build
        self._counter_lbl = None

        self._build(title)
        self._refresh()

    # -- Private helpers -------------------------------------------------------

    def _list_height(self):
        """Height of the 5-slot block + counter."""
        return (
            self._FAR_H  + self._GAP +
            self._NEAR_H + self._GAP +
            self._SEL_H  + self._GAP +
            self._NEAR_H + self._GAP +
            self._FAR_H  +
            self._GAP_CNT + self._CNT_H
        )

    def _safe_width(self, y_center):
        """Circle-safe label width at a given vertical centre position."""
        dist_sq = (y_center - self._R) * (y_center - self._R)
        if dist_sq >= self._R * self._R:
            return 0
        chord = int(2.0 * (self._R * self._R - dist_sq) ** 0.5)
        return max(0, chord - 2 * self._MARGIN)

    @staticmethod
    def _max_chars(width_px, font_size):
        """Max chars that safely fit in width_px for the given Montserrat size.

        px/char values are conservative (worst-case wide characters) so that
        _fit() always fires before LVGL clips silently.
        """
        ppc = {12: 9, 14: 10, 16: 11, 18: 12, 20: 13}.get(font_size,
              max(1, int(font_size * 0.7)))
        return max(4, width_px // ppc)

    def _make_label(self, text, x, y, color, font, width):
        """Create a centre-aligned M5Label with transparent background."""
        lbl = m5ui.M5Label(
            text, x=x, y=y,
            text_c=color, bg_c=self._C_BG, bg_opa=0,
            font=font, parent=self.parent
        )
        lbl.set_width(width)
        lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        return lbl

    def _make_solid_bar(self, x, y, w, h, color, radius=0, opa=255):
        """Create a solid-colour lv.obj rectangle."""
        bar = lv.obj(self.parent)
        bar.set_size(w, h)
        bar.set_pos(x, y)
        bar.set_style_bg_color(lv.color_hex(color), 0)
        bar.set_style_bg_opa(opa, 0)
        bar.set_style_border_width(0, 0)
        bar.set_style_radius(radius, 0)
        try:
            bar.set_style_shadow_width(0, 0)
        except Exception:
            pass
        return bar

    def _build(self, title):
        """Build all LVGL objects once at construction time."""
        y = self._BAR_H + self._GAP_BAR  # list starts here

        # -- Title bar (lowest Z-layer) ----------------------------------------
        self._title_bar = self._make_solid_bar(
            0, 0, self._W, self._BAR_H, self.accent_color, radius=0
        )

        # Title: white, font-12, fixed safe width centred horizontally
        lbl_x = (self._W - self._TITLE_W) // 2
        self._title_lbl = self._make_label(
            title, lbl_x, self._TITLE_Y,
            self._C_TITLE, _get_font(self._F_TITLE), self._TITLE_W
        )
        try:
            self._title_lbl.set_long_mode(lv.LABEL_LONG.WRAP)
        except Exception:
            pass

        list_top = y

        # -- Slot definitions (slot_h, font_size, colour) ----------------------
        slot_defs = [
            (self._FAR_H,  self._F_FAR,  self._C_FAR),
            (self._NEAR_H, self._F_NEAR, self._C_NEAR),
            (self._SEL_H,  self._F_SEL,  self._C_SEL),
            (self._NEAR_H, self._F_NEAR, self._C_NEAR),
            (self._FAR_H,  self._F_FAR,  self._C_FAR),
        ]

        # Pre-compute per-slot widths and char limits from circle geometry
        slot_widths = []
        self._slot_chars = []
        sy = y
        for slot_h, fsz, _ in slot_defs:
            y_center = sy + slot_h // 2
            w = self._safe_width(y_center)
            slot_widths.append(w)
            self._slot_chars.append(self._max_chars(w, fsz))
            sy += slot_h + self._GAP

        # -- Selection band (behind labels) ------------------------------------
        sel_w  = slot_widths[2]
        band_y = list_top + (self._FAR_H + self._GAP) + (self._NEAR_H + self._GAP)
        self._band = self._make_solid_bar(
            (self._W - sel_w) // 2, band_y,
            sel_w, self._SEL_H,
            self.accent_color, radius=16
        )

        # -- Item labels (after band -> rendered on top) -----------------------
        for (slot_h, fsz, color), width in zip(slot_defs, slot_widths):
            x      = (self._W - width) // 2
            line_h = fsz + 4
            y_text = y + max(0, (slot_h - line_h) // 2)

            lbl = self._make_label("", x, y_text, color, _get_font(fsz), width)
            try:
                lbl.set_height(line_h)
            except Exception:
                pass

            self._labels.append(lbl)
            y += slot_h + self._GAP

        # -- Position counter --------------------------------------------------
        y += self._GAP_CNT - self._GAP
        self._counter_lbl = self._make_label(
            "", 0, y, self._C_CNT, _get_font(self._F_CNT), self._W
        )

    # -- Internal refresh ------------------------------------------------------

    @staticmethod
    def _fit(text, max_chars):
        """Truncate text to max_chars, replacing the last 3 with '...'."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars - 3] + "..."

    def _refresh(self):
        """Redraw all item labels to reflect the current selection index."""
        n = len(self.items)
        for i, offset in enumerate((-2, -1, 0, 1, 2)):
            idx  = self.selected_index + offset
            text = self.items[idx] if 0 <= idx < n else ""
            self._labels[i].set_text(self._fit(text, self._slot_chars[i]))

        if self._counter_lbl:
            self._counter_lbl.set_text(
                f"{self.selected_index + 1} / {n}" if n else ""
            )

    # -- Public API ------------------------------------------------------------

    def handle_encoder(self, delta):
        """
        Move the selection in response to a rotary-encoder delta.

        Convention (matches the launcher):
            delta > 0  (clockwise)       -> next item
            delta < 0  (anti-clockwise)  -> previous item
        """
        if not self.items:
            return
        n = len(self.items)
        direction = 1 if delta > 0 else -1
        self.selected_index = max(0, min(n - 1, self.selected_index + direction))
        self._refresh()

    def handle_button(self):
        """
        Confirm the current selection.

        Returns
        -------
        tuple(int, str) or None
            (index, text) of the selected item, or None if the list is empty.
        """
        if not self.items:
            return None
        return (self.selected_index, self.items[self.selected_index])

    def set_items(self, items, reset=True):
        """
        Replace the list contents.

        Parameters
        ----------
        items : list[str]
        reset : bool
            Resets selection to index 0 when True (default).
        """
        self.items = list(items) if items else []
        if reset or self.selected_index >= len(self.items):
            self.selected_index = 0
        self._refresh()

    def get_selected(self):
        """Return (index, text) of the current selection, or None."""
        if not self.items:
            return None
        return (self.selected_index, self.items[self.selected_index])

    def set_title(self, text):
        """Update the title / instruction text in the bar."""
        if self._title_lbl:
            self._title_lbl.set_text(text)

    def set_accent_color(self, color):
        """
        Change the accent colour at runtime (bar + selection band).

        Parameters
        ----------
        color : int
            24-bit hex colour.
        """
        self.accent_color = color
        for obj in (self._title_bar, self._band):
            if obj:
                obj.set_style_bg_color(lv.color_hex(color), 0)

    def cleanup(self):
        """Delete all LVGL objects and release memory."""
        for lbl in self._labels:
            if lbl:
                try:
                    lbl.delete()
                except Exception:
                    pass
        self._labels = []

        for obj in (self._title_bar, self._title_lbl, self._band, self._counter_lbl):
            if obj:
                try:
                    obj.delete()
                except Exception:
                    pass

        self._title_bar   = None
        self._title_lbl   = None
        self._band        = None
        self._counter_lbl = None
