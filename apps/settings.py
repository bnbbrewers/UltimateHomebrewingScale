"""
Settings - Application settings menu
"""

import gc
import time
import M5
from M5 import *
import m5ui
import lvgl as lv
from hardware import Rotary
from .base_app import BaseApp


class SettingsApp(BaseApp):
    """Settings menu application"""
    
    def __init__(self, i18n=None):
        """Initialize settings app"""
        super().__init__(i18n)
        
        # UI elements
        self.title_label = None
        self.menu_labels = []
        
        # State
        self.rotary = None
        self.selected_index = 0
        self.menu_items = [
            {'key': 'language', 'label': 'settings.language'},
            {'key': 'calibration', 'label': 'settings.calibration'},
            {'key': 'about', 'label': 'settings.about'},
        ]
    
    def create_ui(self):
        """Create the settings UI"""
        # Initialize rotary
        try:
            self.rotary = Rotary()
            self.rotary.reset_rotary_value()
        except:
            pass
        
        # Create page
        self.page = m5ui.M5Page(bg_c=0x000000)
        
        # Title
        self.title_label = m5ui.M5Label(
            self.t('settings.title'),
            x=60,
            y=30,
            text_c=0x9CA3AF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_16,
            parent=self.page
        )
        
        # Menu items
        y_pos = 80
        for i, item in enumerate(self.menu_items):
            color = 0xFFFFFF if i == 0 else 0x888888
            label = m5ui.M5Label(
                f"> {self.t(item['label'])}",
                x=40,
                y=y_pos,
                text_c=color,
                bg_c=0x000000,
                bg_opa=0,
                font=lv.font_montserrat_14,
                parent=self.page
            )
            self.menu_labels.append(label)
            y_pos += 35
        
        # Load page
        self.page.screen_load()
    
    def check_return_to_launcher(self):
        """Long press to return"""
        # TODO: Implement return gesture
        return False
    
    def update(self):
        """Update settings menu"""
        # TODO: Handle rotary encoder for menu navigation
        # TODO: Handle button press for selection
        # TODO: Implement language change
        pass


# Standalone entry point
if __name__ == "__main__":
    M5.begin()
    m5ui.init()
    app = SettingsApp(i18n=None)
    app.run()
