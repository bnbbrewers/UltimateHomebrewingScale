"""
Hop Assistant - Weighing assistant for hops with Brewfather integration
"""

import gc
import time
import M5
from M5 import *
import m5ui
import lvgl as lv
from .base_app import BaseApp
from devices.scale import CalibratedScale


class HopAssistantApp(BaseApp):
    """Hop weighing assistant with API integration"""
    
    def __init__(self, i18n=None):
        """Initialize hop assistant"""
        super().__init__(i18n)
        
        # Initialize scale
        try:
            self.scale = CalibratedScale()
        except Exception as e:
            print(f"Warning: Scale not available ({e})")
            self.scale = None
        
        # UI elements
        self.title_label = None
        self.weight_label = None
        self.status_label = None
        
        # State
        self.target_weight = 0
        self.current_weight = 0
    
    def create_ui(self):
        """Create the hop assistant UI"""
        # Create page
        self.page = m5ui.M5Page(bg_c=0x000000)
        
        # Title
        self.title_label = m5ui.M5Label(
            self.t('hop.title'),
            x=60,
            y=30,
            text_c=0x9CA3AF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.page
        )
        
        # Weight display
        self.weight_label = m5ui.M5Label(
            "0 g",
            x=60,
            y=90,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_32,
            parent=self.page
        )
        
        # Status
        self.status_label = m5ui.M5Label(
            self.t('hop.select_hop'),
            x=40,
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
        """Long press to return (placeholder - implement gesture)"""
        # TODO: Implement return gesture
        return False
    
    def update(self):
        """Update hop assistant display"""
        if self.scale:
            # Read current weight
            weight = self.scale.read_weight()
            if weight is not None:
                self.current_weight = weight
                self.weight_label.set_text(f"{weight:.1f} g")
                
                # TODO: Compare with target weight
                # TODO: Show visual feedback
                # TODO: API integration to fetch hop data


# Standalone entry point
if __name__ == "__main__":
    M5.begin()
    m5ui.init()
    app = HopAssistantApp(i18n=None)
    app.run()
