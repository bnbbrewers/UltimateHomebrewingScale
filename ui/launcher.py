"""
Circular Launcher for Ultimate Homebrewing Scale
M5Stack Dial - UIFlow2 / LVGL

Features:
- Circular menu with icons arranged in arc
- Rotary encoder navigation
- Center label shows selected item
- Visual selection feedback
- Configurable via launcher_config.py
"""

import sys
import math
import gc
import M5
from M5 import *
import m5ui
import lvgl as lv
from hardware import Rotary

# Import DEBUG mode
try:
    import config
    DEBUG = getattr(config, 'DEBUG', False)
except:
    DEBUG = False

# Import configuration
try:
    from .launcher_config import LAUNCHER_ITEMS, LAUNCHER_CONFIG, SCREEN_CONFIG
except ImportError:
    print("Error: ui/launcher_config.py not found!")
    print("Please create ui/launcher_config.py with LAUNCHER_ITEMS configuration")
    sys.exit(1)

# Note: i18n is now passed to launcher via main.py


class CircularLauncher:
    """Circular menu launcher for M5Stack Dial"""
    
    def __init__(self, i18n_instance=None):
        """
        Initialize the launcher
        
        Args:
            i18n_instance: I18n instance for translations (optional)
        
        Note:
            M5Stack should already be initialized by main.py
        """
        # Free memory before starting
        gc.collect()
        
        # Store i18n instance
        self.i18n_instance = i18n_instance
        
        # Configuration
        self.items = sorted(LAUNCHER_ITEMS, key=lambda x: x['order'])
        self.config = LAUNCHER_CONFIG
        self.screen = SCREEN_CONFIG
        
        # State
        self.selected_index = 0
        self.is_running = True
        self.rotary = None
        self._selected_module = None
        
        # Animation state for smooth indicator movement
        self.indicator_target_x = 0
        self.indicator_target_y = 0
        self.indicator_current_x = 0
        self.indicator_current_y = 0
        
        # UI elements
        self.page = None
        self.center_label = None
        self.selection_indicator = None  # Visual indicator for selected icon
        self.icon_objects = []  # Store icon references for size animation
        
        # Create UI
        self._create_ui()
        
        # Initialize encoder
        self._init_encoder()
        
        if DEBUG:
            print(f"Launcher initialized with {len(self.items)} items")
    
    def _get_translated_label(self, label):
        """Get translated label for menu item"""
        if not self.i18n_instance:
            return label
        
        # Map label to i18n key
        label_map = {
            'Home': 'launcher.home',
            'Scale': 'launcher.scale',
            'Malt': 'launcher.malt',
            'Hop': 'launcher.hop',
            'Keg': 'launcher.keg',
            'Settings': 'launcher.settings',
        }
        
        key = label_map.get(label, None)
        if key:
            return self.i18n_instance.t(key)
        return label
    
    def show(self):
        """Show the launcher UI"""
        if self.page:
            self.page.screen_load()
            self.is_running = True
    
    def cleanup(self):
        """Destroy all LVGL objects and release memory.

        The LVGL page is NOT deleted here — the app's create_ui() will call
        screen_load() which replaces it naturally. Deleting it first and then
        calling M5.update() causes a LVGL deadlock on M5Stack Dial.
        Python-side references are cleared so GC can reclaim the objects once
        the new screen is loaded.
        """
        # Release Python references (LVGL objects stay alive until the app
        # loads its own page and LVGL discards the previous one)
        self.page                = None
        self.center_label        = None
        self.selection_indicator = None
        self.icon_objects        = []
        gc.collect()
    
    def _init_encoder(self):
        """Initialize rotary encoder"""
        try:
            self.rotary = Rotary()
            self.rotary.reset_rotary_value()
            if DEBUG:
                print("Encoder initialized")
        except Exception as e:
            if DEBUG:
                print(f"Warning: Could not initialize encoder: {e}")
            self.rotary = None
    
    def _create_ui(self):
        """Create the circular launcher UI"""
        # Create M5UI page
        self.page = m5ui.M5Page(bg_c=self.config['bg_color'])
        
        # Create icons in circular arrangement
        self._create_circular_icons()
        
        # Create selection indicator (white dot)
        self._create_selection_indicator()
        
        # Create center label
        self._create_center_label()
        
        # Initial selection
        self._update_selection(0)
        
        # Load page
        self.page.screen_load()
        
        if DEBUG:
            print("UI created successfully")
    
    def _create_circular_icons(self):
        """Create icons arranged in an arc"""
        num_items = len(self.items)
        if num_items == 0:
            if DEBUG:
                print("Warning: No launcher items configured!")
            return
        
        # Get arc configuration
        arc_start = self.config.get('arc_start_angle', 90)
        arc_total = self.config.get('arc_total_angle', 150)
        
        # Calculate angle step for the arc
        if num_items > 1:
            angle_step = arc_total / (num_items - 1)
        else:
            angle_step = 0
        
        icon_size = self.config['icon_size']
        radius = self.config['icon_radius']
        center_x = self.screen['center_x']
        center_y = self.screen['center_y']
        
        for i, item in enumerate(self.items):
            # Calculate position along the arc (reversed order)
            angle_deg = arc_start + arc_total - (i * angle_step)
            angle_rad = math.radians(angle_deg)
            
            x = int(center_x + radius * math.cos(angle_rad) - icon_size / 2)
            y = int(center_y + radius * math.sin(angle_rad) - icon_size / 2)
            
            # Create icon and store reference for animation
            icon = self._create_icon(item['icon'], x, y, icon_size)
            self.icon_objects.append({
                'icon': icon,
                'base_x': x,
                'base_y': y,
                'angle': angle_deg
            })
            
            if DEBUG:
                print(f"Item {i}: {item['label']} at ({x}, {y})")
        
        # Free memory after creating all icons
        gc.collect()
    
    def _create_icon(self, icon_path, x, y, size):
        """Create an icon image using M5UI"""
        try:
            img = m5ui.M5Image(
                icon_path,
                x=x,
                y=y,
                parent=self.page
            )
            # Set size after creation
            img.set_size(size, size)
            return img
        except Exception as e:
            if DEBUG:
                print(f"Icon error: {e}")
            return None
    
    def _create_selection_indicator(self):
        """Create a small white dot as selection indicator"""
        # Create a small circle (10px diameter) using LVGL
        self.selection_indicator = lv.obj(self.page)
        self.selection_indicator.set_size(10, 10)
        self.selection_indicator.set_style_radius(5, 0)  # Make it circular
        self.selection_indicator.set_style_bg_color(lv.color_hex(0xFFFFFF), 0)  # White
        self.selection_indicator.set_style_bg_opa(255, 0)  # Fully opaque
        self.selection_indicator.set_style_border_width(0, 0)  # No border
    
    def _create_placeholder_icon(self, x, y, size):
        """Create a placeholder icon when image is missing"""
        # Just return None - icon will be skipped        
        if DEBUG:
            print(f"Placeholder at ({x}, {y})")
        return None
    
    def _create_center_label(self):
        """Create the label in the right side, centered between leftmost icon and screen edge"""
        screen_width = self.screen['width']
        center_x = self.screen['center_x']
        center_y = self.screen['center_y']
        
        font = lv.font_montserrat_24
        label_height = 32  # Approximate height for font_24
        
        # Find the leftmost point of the arc (180° = 9 o'clock, furthest left)
        # This is the most protruding icon position
        icon_size = self.config['icon_size']
        radius = self.config['icon_radius']
        
        # At 180°, cos(180°) = -1, so X is minimum
        leftmost_icon_x = center_x + radius * math.cos(math.radians(180)) - icon_size / 2
        # Add icon width + indicator size + margin
        left_boundary = leftmost_icon_x + icon_size + 10 + 10  # icon + indicator + margin
        
        # Calculate label space: from left boundary to screen edge
        available_width = screen_width - left_boundary - 10  # 10px right margin
        label_x = left_boundary
        
        # Create M5UI Label
        self.center_label = m5ui.M5Label(
            "",
            x=int(label_x),
            y=center_y - (label_height // 2),
            text_c=self.config['label_color'],
            bg_c=self.config['bg_color'],
            bg_opa=0,
            font=font,
            parent=self.page
        )
        
        # Set label size and center alignment
        self.center_label.set_size(int(available_width), label_height)
        self.center_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    
    
    def _update_selection(self, new_index):
        """Update the selected item"""
        if new_index < 0:
            new_index = len(self.items) - 1
        elif new_index >= len(self.items):
            new_index = 0
        
        # Update index
        old_index = self.selected_index
        self.selected_index = new_index
        
        # Update visual feedback - move indicator to selected icon
        self._update_selection_indicator()
        
        # Update center label with translated text
        selected_item = self.items[self.selected_index]
        translated_label = self._get_translated_label(selected_item['label'])
        self.center_label.set_text(translated_label)
        
        # Play selection sound (short beep)
        if old_index != new_index:
            self._play_selection_beep()
        
        if DEBUG:
            print(f"Selected: {translated_label}")
    
    def _update_selection_indicator(self):
        """Move the white dot indicator to the selected icon position"""
        if not self.selection_indicator:
            return
        
        # Calculate position of selected icon
        num_items = len(self.items)
        arc_start = self.config.get('arc_start_angle', 90)
        arc_total = self.config.get('arc_total_angle', 120)
        
        if num_items > 1:
            angle_step = arc_total / (num_items - 1)
        else:
            angle_step = 0
        
        # Calculate angle for selected item (reversed order)
        angle_deg = arc_start + arc_total - (self.selected_index * angle_step)
        angle_rad = math.radians(angle_deg)
        
        radius = self.config['icon_radius']
        icon_size = self.config['icon_size']
        center_x = self.screen['center_x']
        center_y = self.screen['center_y']
        
        # Place indicator on the radial line between center and icon (like clock hand)
        # Position it very close to icon
        indicator_radius = radius - (icon_size // 2) - 3  # 3px inside from icon edge (very close)
        
        indicator_x = int(center_x + indicator_radius * math.cos(angle_rad) - 5)
        indicator_y = int(center_y + indicator_radius * math.sin(angle_rad) - 5)
        
        # Initialize on first call (no animation)
        if self.indicator_current_x == 0 and self.indicator_current_y == 0:
            self.indicator_current_x = indicator_x
            self.indicator_current_y = indicator_y
            self.indicator_target_x = indicator_x
            self.indicator_target_y = indicator_y
            self.selection_indicator.set_pos(indicator_x, indicator_y)
        else:
            # Set target position for smooth animation
            self.indicator_target_x = indicator_x
            self.indicator_target_y = indicator_y
    
    def _play_selection_beep(self):
        """Play a short beep sound for selection feedback"""
        try:
            # Short beep at 4000Hz for 50ms
            M5.Speaker.tone(4000, 50)
        except Exception as e:
            # Speaker might not be available
            pass
    
    def _check_encoder(self):
        """Check rotary encoder for changes"""
        if not self.rotary:
            return
        
        try:
            # Read encoder delta
            encoder_delta = self.rotary.get_rotary_value()
            
            if encoder_delta != 0:
                # Reset rotary value after reading
                self.rotary.reset_rotary_value()
                
                # Update selection (inverted: clockwise = previous, counter-clockwise = next)
                direction = -1 if encoder_delta > 0 else 1
                new_index = self.selected_index + direction
                self._update_selection(new_index)
                
        except Exception as e:
            if DEBUG:
                print(f"Encoder error: {e}")
    
    def _check_button(self):
        """Check if center button is pressed – store selection and exit loop."""
        if M5.BtnA.isPressed():
            self._selected_module = self.items[self.selected_index]['module']
            self.is_running = False
    
    def _animate_indicator(self):
        """Smoothly animate the indicator to target position"""
        # Interpolation factor (higher = faster, 0.5 = faster and smooth)
        lerp_factor = 0.5
        
        # Calculate difference
        dx = self.indicator_target_x - self.indicator_current_x
        dy = self.indicator_target_y - self.indicator_current_y
        
        # If close enough, snap to target
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            self.indicator_current_x = self.indicator_target_x
            self.indicator_current_y = self.indicator_target_y
        else:
            # Smoothly interpolate
            self.indicator_current_x += dx * lerp_factor
            self.indicator_current_y += dy * lerp_factor
        
        # Update visual position
        self.selection_indicator.set_pos(
            int(self.indicator_current_x),
            int(self.indicator_current_y)
        )
    
    
    def update(self):
        """Update loop - check encoder, button, and animate indicator"""
        self._check_encoder()
        self._check_button()
        self._animate_indicator()
    
    def run(self):
        """
        Run the launcher loop.

        Returns
        -------
        str or None
            The 'module' key of the selected item when the user confirms,
            or None if the loop exits without a selection.
        """
        import time
        self._selected_module = None

        if DEBUG:
            print("\nLauncher running...")

        try:
            while self.is_running:
                M5.update()
                self.update()
                time.sleep_ms(50)

        except KeyboardInterrupt:
            raise   # propagate to main.py's while loop so it can break cleanly
        except Exception as e:
            if DEBUG:
                print(f"Launcher error: {e}")
            sys.print_exception(e)

        return self._selected_module


# Entry point
if __name__ == "__main__":
    try:
        if DEBUG:
            print("=" * 50)
            print("Ultimate Homebrewing Scale - Launcher")
            print("=" * 50)
        
        # Create and run launcher
        launcher = CircularLauncher()
        launcher.run()
    
    except KeyboardInterrupt:
        if DEBUG:
            print("\nExiting...")
    except Exception as e:
        print(f"Fatal error: {e}")
        import sys
        sys.print_exception(e)
