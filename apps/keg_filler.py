"""
Keg Filler - Automated keg filling with volume tracking
"""

import gc
import time
import M5
from M5 import *
import m5ui
import lvgl as lv
from .base_app import BaseApp
from devices.scale import CalibratedScale


class KegFillerApp(BaseApp):
    """Keg filling automation with volume tracking"""
    
    def __init__(self, i18n=None):
        """Initialize keg filler"""
        super().__init__(i18n)
        
        # Initialize scale
        try:
            self.scale = CalibratedScale()
        except Exception as e:
            print(f"Warning: Scale not available ({e})")
            self.scale = None
        
        # UI elements
        self.title_label = None
        self.volume_label = None
        self.status_label = None
        self.progress_bar = None
        
        # State
        self.target_volume = 0
        self.current_volume = 0
        self.is_filling = False
        self.beer_density = 1.01  # kg/L (approximate)
    
    def create_ui(self):
        """Create the keg filler UI"""
        # Create page
        self.page = m5ui.M5Page(bg_c=0x000000)
        
        # Title
        self.title_label = m5ui.M5Label(
            self.t('keg.title'),
            x=60,
            y=30,
            text_c=0x9CA3AF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.page
        )
        
        # Volume display
        self.volume_label = m5ui.M5Label(
            "0 L",
            x=70,
            y=90,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_32,
            parent=self.page
        )
        
        # Progress bar
        self.progress_bar = lv.bar(self.page)
        self.progress_bar.set_size(160, 10)
        self.progress_bar.set_pos(40, 150)
        self.progress_bar.set_range(0, 100)
        self.progress_bar.set_value(0, False)
        
        # Status
        self.status_label = m5ui.M5Label(
            self.t('keg.ready'),
            x=50,
            y=180,
            text_c=0x888888,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page
        )
        
        # Load page
        self.page.screen_load()
    
    def check_return_to_launcher(self):
        """Long press to return"""
        # TODO: Implement return gesture
        return False
    
    def update(self):
        """Update keg filler display"""
        if self.scale:
            # Read current weight
            weight = self.scale.read_weight()
            if weight is not None:
                # Convert weight (grams) to volume (liters)
                # weight (g) / 1000 = weight (kg)
                # weight (kg) / density (kg/L) = volume (L)
                self.current_volume = (weight / 1000) / self.beer_density
                self.volume_label.set_text(f"{self.current_volume:.2f} L")
                
                # TODO: Update progress bar
                # TODO: Handle start/stop filling
                # TODO: Auto-stop at target volume


# Standalone entry point
if __name__ == "__main__":
    M5.begin()
    m5ui.init()
    app = KegFillerApp(i18n=None)
    app.run()
