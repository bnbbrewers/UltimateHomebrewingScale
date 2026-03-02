"""
Base Application Class for Ultimate Homebrewing Scale
Provides common functionality for all applications
"""

import gc
import time
import M5
from M5 import *
import m5ui
import lvgl as lv

# Import settings from config
try:
    import config
    DEBUG = getattr(config, 'DEBUG', False)
    _BREWING_SOFTWARE = getattr(config, 'BREWING_SOFTWARE', 'brewfather')
except:
    DEBUG = False
    _BREWING_SOFTWARE = 'brewfather'


def _load_brewing_api():
    """
    Instantiate the brewing software API defined in config.BREWING_SOFTWARE.
    WiFi is managed by the API itself (BrewingSoftwareAPI._get calls _ensure_wifi).
    Returns the API instance or None if loading fails.
    """
    try:
        if _BREWING_SOFTWARE == 'brewfather':
            from api.brewfather_api import BrewfatherAPI
            return BrewfatherAPI()
        else:
            if DEBUG:
                print(f"Unknown BREWING_SOFTWARE: '{_BREWING_SOFTWARE}'")
            return None
    except Exception as e:
        if DEBUG:
            print(f"Warning: Could not load brewing API '{_BREWING_SOFTWARE}': {e}")
        return None


class BaseApp:
    """Base class for all applications in the Ultimate Homebrewing Scale"""
    
    def __init__(self, i18n=None):
        """
        Initialize the base application
        
        Args:
            i18n: I18n instance for translations (optional)
        
        Note:
            M5Stack should already be initialized by main.py
            Do NOT call M5.begin() or m5ui.init() here
        """
        self.i18n = i18n
        self.is_running = True
        self.page = None

        # Brewing software API instance (loaded from config.BREWING_SOFTWARE)
        self.api = _load_brewing_api()

        # Long press detection for return to launcher
        self.btn_press_start = 0
        self.btn_is_pressed = False
        self.LONG_PRESS_DURATION = 3000  # 3 seconds in milliseconds
        
        # Free memory before creating UI
        gc.collect()
    
    def t(self, key, *args, **kwargs):
        """
        Translate a key using i18n
        
        Args:
            key: Translation key (e.g., 'scale.tare_ready')
            *args: Positional arguments for format()
            **kwargs: Keyword arguments for format()
        
        Returns:
            Translated string or key if i18n not available
        """
        if self.i18n:
            return self.i18n.t(key, *args, **kwargs)
        return key
    
    def create_ui(self):
        """
        Create the application UI
        Override this method in subclasses
        """
        raise NotImplementedError("Subclasses must implement create_ui()")
    
    def update(self):
        """
        Update application state (called every frame)
        Override this method in subclasses
        """
        pass
    
    def cleanup(self):
        """
        Cleanup resources before exiting
        Override this method in subclasses for specific cleanup
        """
        # Clean up UI page if it exists
        if self.page:
            try:
                # Delete LVGL objects to free memory
                self.page.delete()
            except:
                pass
            self.page = None
        
        # Force garbage collection
        gc.collect()
    
    def check_return_to_launcher(self):
        """
        Check if user wants to return to launcher (long press button)
        
        Returns:
            True if should return to launcher
        
        Note:
            Long press (3s) on center button = return to launcher
        """
        # Detect button press start
        if M5.BtnA.isPressed():
            if not self.btn_is_pressed:
                # Button just pressed
                self.btn_is_pressed = True
                self.btn_press_start = time.ticks_ms()
            else:
                # Button still pressed, check duration
                press_duration = time.ticks_diff(time.ticks_ms(), self.btn_press_start)
                if press_duration >= self.LONG_PRESS_DURATION:
                    if DEBUG:
                        print("Long press detected - returning to launcher")
                    return True
        else:
            # Button released
            self.btn_is_pressed = False
        
        return False
    
    def run(self):
        """
        Main application loop
        Override this method in subclasses or use the default implementation
        """
        # Create UI
        self.create_ui()
        
        # Main loop
        while self.is_running:
            M5.update()
            
            # Check for return to launcher
            if self.check_return_to_launcher():
                break
            
            # Update application
            self.update()
            
            # Small delay to prevent CPU overload
            time.sleep_ms(50)
        
        # Cleanup before exiting
        self.cleanup()
    
    def exit(self):
        """Request application exit"""
        self.is_running = False
