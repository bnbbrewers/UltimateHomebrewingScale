"""
Ultimate Homebrewing Scale - Basic Scale Application
Displays weight from Unit Weight-I2C with calibration and tare functionality
"""

import time
import M5
from M5 import *
import m5ui
import lvgl as lv
from .base_app import BaseApp
from devices.scale import CalibratedScale
from ui.weight_display import WeightDisplay

# Import DEBUG mode from config
try:
    import config
    DEBUG_MODE = getattr(config, 'DEBUG', False)
except:
    DEBUG_MODE = False


# CalibratedScale is now imported from devices.scale


class ScaleApp(BaseApp):
    """Main scale application"""
    
    def __init__(self, i18n=None):
        """
        Initialize the application
        
        Args:
            i18n: I18n instance for translations
        
        Note:
            M5Stack is already initialized by main.py
        """
        # Initialize base app
        super().__init__(i18n)
        
        # Initialize scale hardware
        self.scale = CalibratedScale()
        
        # UI variables
        self.weight_display = None
        self.status_label = None
        
        # State
        self.is_taring = False
        self.tare_start_time = 0
        
        # Display stabilization
        self.last_reading = None  # Track last sensor reading
        self.UPDATE_THRESHOLD = 0.6  # Only update display if change > 0.6g from last reading
        
        if DEBUG_MODE:
            print("Scale App initialized")
    
    def create_ui(self):
        """Create LVGL user interface (override from BaseApp)"""
        # Create page
        self.page = m5ui.M5Page(bg_c=0x000000)
        
        # Create weight display component
        self.weight_display = WeightDisplay(
            parent=self.page,
            title=self.t('scale.title'),
            mode="simple",
            target=0,
            x=0,
            y=10,
            width=240,
            height=180,
            title_bg_color=0x1E40AF  # Blue background
        )
        
        # Status label (small, bottom)
        self.status_label = m5ui.M5Label(
            self.t('scale.tare_ready'),
            x=60,
            y=200,
            text_c=0x888888,
            bg_c=0x000000,
            bg_opa=0,
            font=self._get_font(14),
            parent=self.page
        )
        
        # Load page
        self.page.screen_load()
        
        # Perform initial tare after UI is ready
        self._initial_tare()
    
    def _get_font(self, preferred_size=16):
        """Return an available LVGL font with fallbacks"""
        candidates = [
            f"font_montserrat_{preferred_size}",
            f"font_montserrat_{preferred_size - 2}",
            "font_montserrat_16",
            "font_montserrat_14",
            "font_montserrat_12",
        ]
        for name in candidates:
            if hasattr(lv, name):
                return getattr(lv, name)
        return None
    
    def _initial_tare(self):
        """Perform initial tare at startup"""
        if DEBUG_MODE:
            print("Performing initial tare...")
        
        self.status_label.set_text(self.t('scale.initial_tare'))
        
        try:
            # Wait a bit for the sensor to stabilize
            for _ in range(10):
                M5.update()
                time.sleep_ms(100)
            
            # Perform tare
            success = self.scale.tare()
            
            if success:
                self.status_label.set_text("Ready")
                # Reset last reading to force immediate update after tare
                self.last_reading = None
                if DEBUG_MODE:
                    print("Initial tare completed")
            else:
                self.status_label.set_text(self.t('scale.tare_error'))
                if DEBUG_MODE:
                    print("Initial tare failed")
            
            # Show message briefly then switch to normal
            time.sleep(1)
            self.status_label.set_text(self.t('scale.tare_ready'))
            
        except Exception as e:
            if DEBUG_MODE:
                print(f"Initial tare error: {e}")
            self.status_label.set_text(self.t('scale.tare_ready'))
    
    def _format_weight(self, weight):
        """
        Format weight for display with thousands separator
        
        Args:
            weight: Weight in grams (float)
            
        Returns:
            Formatted string (e.g. "1 234" or "12 345")
        """
        if weight is None:
            return "---"
        
        # Round to nearest integer
        weight_int = round(weight)
        
        # Handle negatives
        sign = "-" if weight_int < 0 else ""
        weight_int = abs(weight_int)
        
        # Convert to string
        weight_str = str(weight_int)
        
        # Add spaces every 3 digits (right to left)
        if len(weight_str) > 3:
            # For thousands
            parts = []
            while len(weight_str) > 3:
                parts.insert(0, weight_str[-3:])
                weight_str = weight_str[:-3]
            parts.insert(0, weight_str)
            weight_str = " ".join(parts)
        
        return sign + weight_str
    
    def _check_button(self):
        """Check if button was pressed and handle tare"""
        if M5.BtnA.isPressed() and not self.is_taring:
            self.is_taring = True
            self.tare_start_time = time.ticks_ms()
            self.status_label.set_text(self.t('scale.taring'))
            
            # Perform tare
            try:
                success = self.scale.tare()
                
                if success:
                    self.status_label.set_text(self.t('scale.tare_done'))
                    # Reset last reading to force immediate update after tare
                    self.last_reading = None
                else:
                    self.status_label.set_text(self.t('scale.tare_error'))
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Tare error: {e}")
                self.status_label.set_text(self.t('scale.tare_error'))
    
    def update(self):
        """Update weight display and handle tare timeout (override from BaseApp)"""
        try:
            # Check button
            self._check_button()
            
            # Check if tare message should be reset
            if self.is_taring and time.ticks_diff(time.ticks_ms(), self.tare_start_time) > 2000:
                self.is_taring = False
                self.status_label.set_text(self.t('scale.tare_ready'))
            
            # Update weight display (unless taring in progress)
            if not self.is_taring:
                weight = self.scale.read_weight()
                if self.weight_display and weight is not None:
                    # Only update display if change from last reading exceeds threshold
                    if self.last_reading is None:
                        # First reading - always display
                        self.weight_display.update(weight)
                    elif abs(weight - self.last_reading) >= self.UPDATE_THRESHOLD:
                        # Significant change from last reading - update display
                        self.weight_display.update(weight)
                    # else: change < threshold, don't update display
                    
                    # Always update last_reading with current reading
                    self.last_reading = weight
        except Exception as e:
            if DEBUG_MODE:
                print(f"Update error: {e}")
    
    # run() and cleanup() methods are inherited from BaseApp


# Entry point for standalone testing (not used in production)
if __name__ == "__main__":
    try:
        # Standalone mode: initialize M5Stack
        M5.begin()
        m5ui.init()
        
        # Create and launch application
        app = ScaleApp(i18n=None)
        app.run()
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import sys
        sys.print_exception(e)
