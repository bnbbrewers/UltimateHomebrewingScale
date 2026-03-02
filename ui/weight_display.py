"""
Weight Display Component
Reusable UI component for displaying weight with multiple modes
"""

import m5ui
import lvgl as lv

try:
    import config
    DEBUG_MODE = getattr(config, 'DEBUG', False)
except Exception:
    DEBUG_MODE = False

# Material Design 500 colours – less aggressive than pure RGB primaries
_COLOR_RED    = 0xF44336
_COLOR_ORANGE = 0xFF9800
_COLOR_AMBER  = 0xFFC107
_COLOR_GREEN  = 0x4CAF50

# Try to load custom font at module level
CUSTOM_FONT = None
try:
    CUSTOM_FONT = lv.binfont_create("S:/flash/assets/montserrat_40.bin")
except:
    pass


def _get_font(preferred_size=16):
    """
    Return an available LVGL font with fallbacks
    
    Args:
        preferred_size: Preferred font size
    
    Returns:
        LVGL font object or None
    """
    # Available fonts in UIFlow2: 10, 12, 14, 16, 18, 20, 22, 24, 26, 28
    # Try to get the closest available size, starting from largest
    
    if preferred_size >= 48:
        # Try largest fonts first for very large requests
        sizes_to_try = [28, 26, 24, 22, 20, 18, 16, 14, 12]
    elif preferred_size >= 32:
        sizes_to_try = [28, 26, 24, 22, 20, 18, 16, 14, 12]
    elif preferred_size >= 24:
        sizes_to_try = [24, 26, 22, 20, 18, 16, 14, 12]
    elif preferred_size >= 16:
        sizes_to_try = [16, 18, 20, 14, 12]
    else:
        sizes_to_try = [14, 12, 16, 18, 20]
    
    # Try each size in order
    for size in sizes_to_try:
        font_name = f"font_montserrat_{size}"
        if hasattr(lv, font_name):
            return getattr(lv, font_name)
    
    # Ultimate fallback - try common sizes
    for size in [16, 14, 12, 20, 24]:
        font_name = f"font_montserrat_{size}"
        if hasattr(lv, font_name):
            return getattr(lv, font_name)
    
    return None


class WeightDisplay:
    """
    Reusable weight display component
    
    Supports multiple display modes:
    - "simple": Direct weight display
    - "countdown_g": Shows remaining weight to reach target (grams)
    - "countdown_l": Shows remaining volume to reach target (liters)
    
    Features:
    - Customizable title with background color
    - Main weight display (large font)
    - Optional remaining weight/volume display
    - Progress bar with color gradient (red → orange → green)
    - Percentage display
    """
    
    def __init__(self, parent, title="", mode="simple", target=0,
                 x=0, y=20, width=240, height=200,
                 title_bg_color=0x333333, density=1.01, scale=None,
                 tolerance=0, on_confirm=None):
        """
        Initialize weight display component
        
        Args:
            parent: LVGL parent object (M5Page)
            title: Title text displayed at top
            mode: Display mode ("simple", "countdown_g", "countdown_l")
            target: Target weight/volume for countdown modes
            x, y: Position on screen
            width, height: Component dimensions
            title_bg_color: Background color for title (hex RGB)
            density: Liquid density for volume conversion (kg/L)
            scale: CalibratedScale instance (optional). When provided, update()
                   reads weight from the scale directly.
            tolerance: Accepted deviation in grams around target to show OK label.
                       0 disables the OK label entirely.
            on_confirm: Optional callback called when the user confirms the weight
                        (button press while is_ok() is True). Signature: on_confirm()
        """
        self.parent = parent
        self.mode = mode
        self.target = target
        self.density = density
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.scale = scale
        self.tolerance = tolerance
        self.on_confirm = on_confirm
        self._ok_visible = False

        # UI elements
        self.title_bg = None
        self.title_label = None
        self.weight_label = None
        self.remaining_label = None
        self.progress_bar = None
        self.percentage_label = None
        self.ok_bg = None
        self.ok_label = None

        # Create UI
        self._create_ui(title, title_bg_color)

        # Tare the scale so the display always starts from zero
        if self.scale is not None:
            self.scale.tare()
    
    def _create_ui(self, title, title_bg_color):
        """Create all UI elements"""
        
        # Title background (colored bar) - Full width from top
        if title:
            title_height = self.y + 30
            
            # Background bar from top (y=0) to y + 30
            self.title_bg = lv.obj(self.parent)
            self.title_bg.set_size(240, title_height)  # Full width, from top
            self.title_bg.set_pos(0, 0)  # Start at top of screen
            self.title_bg.set_style_bg_color(lv.color_hex(title_bg_color), 0)
            self.title_bg.set_style_bg_opa(255, 0)
            self.title_bg.set_style_border_width(0, 0)
            self.title_bg.set_style_radius(0, 0)  # No radius to reach edges
            
            # Title label (centered on round screen)
            title_center_y = self.y + 15  # Middle of title bar
            
            self.title_label = m5ui.M5Label(
                title,
                x=0,  # Start at left edge
                y=title_center_y - 8,
                text_c=0xFFFFFF,
                bg_c=title_bg_color,
                bg_opa=0,
                font=_get_font(16),
                parent=self.parent
            )
            # Set width to full screen and center align
            self.title_label.set_width(240)
            self.title_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        
        # Main weight label (large, centered)
        # Use custom font if available, otherwise fallback to largest available
        main_font = CUSTOM_FONT if CUSTOM_FONT else _get_font(48)
        
        self.weight_label = m5ui.M5Label(
            "0 g",
            x=0,  # Start at left edge
            y=self.y + 80,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=main_font,
            parent=self.parent
        )
        # Set width to full screen and center align
        self.weight_label.set_width(240)
        self.weight_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        
        # Remaining label (for countdown_l mode only)
        if self.mode == "countdown_l":
            self.remaining_label = m5ui.M5Label(
                "Reste: 0 L",
                x=self.x + 40,
                y=self.y + 100,
                text_c=0x888888,
                bg_c=0x000000,
                bg_opa=0,
                font=_get_font(14),
                parent=self.parent
            )
        
        # Progress bar (for countdown modes)
        if self.mode in ["countdown_g", "countdown_l"]:
            self.progress_bar = lv.bar(self.parent)
            self.progress_bar.set_size(200, 20)
            self.progress_bar.set_pos(self.x + 20, self.y + 140)
            self.progress_bar.set_range(0, 100)
            self.progress_bar.set_value(0, False)
            
            # Percentage label
            self.percentage_label = m5ui.M5Label(
                "0%",
                x=0,
                y=self.y + 165,
                text_c=0x888888,
                bg_c=0x000000,
                bg_opa=0,
                font=_get_font(14),
                parent=self.parent
            )
            self.percentage_label.set_width(240)
            self.percentage_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        # OK banner – shown at bottom when weight is within tolerance of target
        # Same construction as the title bar: colored lv.obj + white M5Label on top
        _OK_BAR_H = 30
        _OK_BAR_Y = 240 - _OK_BAR_H   # flush with bottom edge

        if self.mode == "countdown_g" and self.tolerance > 0:
            self.ok_bg = lv.obj(self.parent)
            self.ok_bg.set_size(240, _OK_BAR_H)
            self.ok_bg.set_pos(0, _OK_BAR_Y)
            self.ok_bg.set_style_bg_color(lv.color_hex(_COLOR_GREEN), 0)
            self.ok_bg.set_style_bg_opa(0, 0)   # hidden initially
            self.ok_bg.set_style_border_width(0, 0)
            self.ok_bg.set_style_radius(0, 0)

            self.ok_label = m5ui.M5Label(
                "",
                x=0,
                y=_OK_BAR_Y + (_OK_BAR_H // 2) - 9,
                text_c=0xFFFFFF,
                bg_c=_COLOR_GREEN,
                bg_opa=0,
                font=_get_font(16),
                parent=self.parent
            )
            self.ok_label.set_width(240)
            self.ok_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    
    def update(self, current_weight=None):
        """
        Update display with current weight.

        If a scale was provided at construction time and current_weight is not
        given, the weight is read directly from the scale.
        
        Args:
            current_weight: Current weight in grams (float), or None to read
                            from the attached scale.
        """
        if current_weight is None:
            if self.scale is None:
                return
            current_weight = self.scale.read_weight()
        if current_weight is None:
            return
        
        if self.mode == "simple":
            self._update_simple(current_weight)
        elif self.mode == "countdown_g":
            self._update_countdown_g(current_weight)
        elif self.mode == "countdown_l":
            self._update_countdown_l(current_weight)

        # Fire callback when weight is confirmed by button press
        if self.on_confirm is not None and self.is_ok():
            try:
                import M5
                if M5.BtnA.wasPressed():
                    self.on_confirm()
            except Exception:
                pass
    
    def _update_simple(self, weight):
        """Update display in simple mode"""
        self.weight_label.set_text(self._format_weight(weight, "g"))
    
    def _update_countdown_g(self, weight):
        """Update display in countdown grams mode"""
        overshoot = weight - self.target
        overloaded = overshoot > 0
        progress = min(100, (weight / self.target * 100) if self.target > 0 else 0)
        
        if overloaded:
            # Show excess weight in red ("+X g" above target)
            excess_text = "+" + self._format_weight(overshoot, "g")
            self.weight_label.set_text(excess_text)
            self.weight_label.set_style_text_color(lv.color_hex(_COLOR_RED), 0)
        else:
            remaining = self.target - weight
            self.weight_label.set_text(self._format_weight(remaining, "g"))
            self.weight_label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        
        # Update progress bar
        if self.progress_bar:
            self.progress_bar.set_value(int(progress), False)
            color = _COLOR_RED if overloaded else self._get_progress_color(progress)
            self.progress_bar.set_style_bg_color(lv.color_hex(color), lv.PART.INDICATOR)
        
        # Update percentage label
        if self.percentage_label:
            if overloaded:
                self.percentage_label.set_text("surcharge")
                self.percentage_label.set_style_text_color(lv.color_hex(_COLOR_RED), 0)
            else:
                self.percentage_label.set_text(f"{int(progress)}%")
                self.percentage_label.set_style_text_color(lv.color_hex(0x888888), 0)

        # OK banner – visible when weight is within ±tolerance of target
        if self.ok_label is not None:
            in_range = self.tolerance > 0 and abs(weight - self.target) <= self.tolerance
            if in_range != self._ok_visible:
                self._ok_visible = in_range
                self.ok_label.set_text("OK" if in_range else "")
                if self.ok_bg is not None:
                    self.ok_bg.set_style_bg_opa(255 if in_range else 0, 0)

    def is_ok(self):
        """Return True when weight is within tolerance, or always in DEBUG mode."""
        return DEBUG_MODE or self._ok_visible

    def _update_countdown_l(self, weight):
        """Update display in countdown liters mode"""
        # Convert weight (grams) to volume (liters)
        volume = (weight / 1000) / self.density
        target_volume = (self.target / 1000) / self.density
        
        # Calculate remaining
        remaining_volume = max(0, target_volume - volume)
        progress = min(100, (volume / target_volume * 100) if target_volume > 0 else 0)
        
        # Update labels
        self.weight_label.set_text(f"{volume:.2f} L")
        if self.remaining_label:
            self.remaining_label.set_text(f"Reste: {remaining_volume:.2f} L")
        
        # Update progress bar
        if self.progress_bar:
            self.progress_bar.set_value(int(progress), False)
            
            # Update color based on progress
            color = self._get_progress_color(progress)
            self.progress_bar.set_style_bg_color(lv.color_hex(color), lv.PART.INDICATOR)
        
        # Update percentage
        if self.percentage_label:
            self.percentage_label.set_text(f"{int(progress)}%")
    
    def _format_weight(self, weight, unit="g"):
        """
        Format weight for display
        
        Args:
            weight: Weight in grams
            unit: Unit string ("g", "kg", "L")
        
        Returns:
            Formatted string (e.g., "234 g", "1.23 kg")
        """
        if unit == "kg":
            # Force kg with 2 decimals
            return f"{weight / 1000:.2f} kg"
        elif unit == "L":
            return f"{weight:.2f} L"
        else:
            # Automatic g/kg switching
            if abs(weight) >= 1000:
                # Display as "X.XX kg" with 2 decimals
                return f"{weight / 1000:.2f} kg"
            else:
                # Display as "X g" without decimals
                return f"{int(round(weight))} g"
    
    def _get_progress_color(self, progress):
        """Return a Material Design colour for the progress bar (0-100)."""
        if progress < 33:
            return _COLOR_RED
        elif progress < 66:
            return _COLOR_ORANGE
        elif progress < 90:
            return _COLOR_AMBER
        else:
            return _COLOR_GREEN
    
    def set_target(self, target):
        """
        Set new target weight/volume
        
        Args:
            target: New target in grams
        """
        self.target = target
    
    def set_mode(self, mode):
        """
        Change display mode
        
        Args:
            mode: New mode ("simple", "countdown_g", "countdown_l")
        """
        if mode != self.mode:
            self.mode = mode
            # Recreate UI elements if needed
            # TODO: Implement dynamic mode switching if needed
    
    def set_title(self, title):
        """
        Update title text
        
        Args:
            title: New title text
        """
        if self.title_label:
            self.title_label.set_text(title)
    
    def cleanup(self):
        """Cleanup UI elements"""
        elements = [
            self.title_bg,
            self.title_label,
            self.weight_label,
            self.remaining_label,
            self.progress_bar,
            self.percentage_label,
            self.ok_bg,
            self.ok_label,
        ]
        
        for element in elements:
            if element:
                try:
                    element.delete()
                except:
                    pass
