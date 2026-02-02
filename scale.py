"""
Ultimate Homebrewing Scale - Basic Scale Application
Displays weight from Unit Weight-I2C with calibration and tare functionality
"""

import os
import sys
import json
import M5
from M5 import *
from unit import WeightI2CUnit
from hardware import I2C, Pin
import m5ui
import lvgl as lv
import time

# Configuration
CALIBRATION_FILE = "scale_calibration.json"
I2C_ADDRESS = 0x26
SCL_PIN = 15
SDA_PIN = 13
DEBUG_MODE = True  # Set to False to disable serial debug output

# Moving average for stable reading
MOVING_AVERAGE_SIZE = 10


class CalibratedScale:
    """Class to manage the scale with calibration and tare"""
    
    def __init__(self):
        """
        Initialize the scale with calibration
        Uses all calibration points for piecewise linear interpolation
        """
        self.weight_unit = None
        self.calibration_points = []
        self.tare_offset = 0
        self.adc_buffer = []
        
        # Initialize Weight Unit
        self._init_weight_unit()
        
        # Load calibration
        self._load_calibration()
        
        if DEBUG_MODE:
            print(f"Scale initialized with {len(self.calibration_points)} calibration points")
            for pt in self.calibration_points:
                print(f"  Point {pt['step']}: Weight={pt['weight']}g, ADC={pt['adc_average']}")
    
    def _init_weight_unit(self):
        """Initialize the Unit Weight-I2C"""
        try:
            # Create I2C bus object
            i2c_bus = I2C(0, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=100000)
            
            # Initialize Weight Unit with I2C bus and address
            self.weight_unit = WeightI2CUnit(i2c_bus, I2C_ADDRESS)
            
            if DEBUG_MODE:
                print("Weight Unit initialized successfully")
        except Exception as e:
            print(f"Error initializing Weight Unit: {e}")
            raise
    
    def _load_calibration(self):
        """Load calibration parameters from JSON file"""
        try:
            with open(CALIBRATION_FILE, 'r') as f:
                data = json.load(f)
            
            points = data['scale']['CalibrationPoints']
            
            # Load all calibration points and sort by ADC value
            self.calibration_points = sorted(points, key=lambda p: p['adc_average'])
            
            if len(self.calibration_points) < 2:
                raise ValueError("At least 2 calibration points required")
            
            if DEBUG_MODE:
                print(f"Calibration loaded from {CALIBRATION_FILE}")
            
        except Exception as e:
            print(f"Error loading calibration: {e}")
            raise
    
    def _adc_to_weight(self, adc_value):
        """
        Convert ADC value to weight (grams)
        Uses piecewise linear interpolation between calibration points
        
        Args:
            adc_value: Raw ADC value
            
        Returns:
            Weight in grams (float)
        """
        # Find the two calibration points that bracket the ADC value
        # If ADC is outside range, extrapolate from nearest segment
        
        # If ADC is below lowest point, use first segment
        if adc_value <= self.calibration_points[0]['adc_average']:
            pt1 = self.calibration_points[0]
            pt2 = self.calibration_points[1]
        
        # If ADC is above highest point, use last segment
        elif adc_value >= self.calibration_points[-1]['adc_average']:
            pt1 = self.calibration_points[-2]
            pt2 = self.calibration_points[-1]
        
        # Otherwise, find bracketing points
        else:
            pt1 = self.calibration_points[0]
            pt2 = self.calibration_points[1]
            
            for i in range(len(self.calibration_points) - 1):
                if (self.calibration_points[i]['adc_average'] <= adc_value <= 
                    self.calibration_points[i + 1]['adc_average']):
                    pt1 = self.calibration_points[i]
                    pt2 = self.calibration_points[i + 1]
                    break
        
        # Linear interpolation between pt1 and pt2
        adc1 = pt1['adc_average']
        adc2 = pt2['adc_average']
        weight1 = pt1['weight']
        weight2 = pt2['weight']
        
        # Avoid division by zero
        if adc2 == adc1:
            return weight1
        
        # Interpolate: weight = weight1 + (weight2 - weight1) * (adc - adc1) / (adc2 - adc1)
        weight = weight1 + (weight2 - weight1) * (adc_value - adc1) / (adc2 - adc1)
        
        return weight
    
    def read_raw_adc(self):
        """Read raw ADC value from sensor"""
        try:
            return self.weight_unit.get_adc_raw
        except Exception as e:
            if DEBUG_MODE:
                print(f"Error reading ADC: {e}")
            return None
    
    def read_weight(self):
        """
        Read current weight with moving average for stability
        
        Returns:
            Weight in grams (float), or None on error
        """
        adc_value = self.read_raw_adc()
        
        if adc_value is None:
            return None
        
        # Add to moving average
        self.adc_buffer.append(adc_value)
        if len(self.adc_buffer) > MOVING_AVERAGE_SIZE:
            self.adc_buffer.pop(0)
        
        # Calculate average
        adc_avg = sum(self.adc_buffer) / len(self.adc_buffer)
        
        # Convert to weight
        weight = self._adc_to_weight(adc_avg)
        
        # Apply tare offset
        weight -= self.tare_offset
        
        if DEBUG_MODE and len(self.adc_buffer) == MOVING_AVERAGE_SIZE:
            # Debug every 10 samples to avoid overload
            if int(time.time() * 10) % 10 == 0:
                print(f"ADC: {adc_avg:.0f} | Weight: {weight:.1f}g | Tare: {self.tare_offset:.1f}g")
        
        return weight
    
    def tare(self):
        """Perform tare (zero current weight)"""
        # Read multiple samples for stable tare
        samples = []
        for _ in range(20):
            weight = self.read_weight()
            if weight is not None:
                # Temporarily remove old offset to get actual weight
                weight += self.tare_offset
                samples.append(weight)
            time.sleep_ms(50)
        
        if samples:
            # Average samples
            self.tare_offset = sum(samples) / len(samples)
            if DEBUG_MODE:
                print(f"Tare set to: {self.tare_offset:.1f}g")
            return True
        return False


class ScaleApp:
    """Main scale application"""
    
    def __init__(self):
        """
        Initialize the application
        Uses all calibration points for accurate measurements
        """
        # Initialize M5Stack
        M5.begin()
        m5ui.init()
        
        # Initialize scale
        self.scale = CalibratedScale()
        
        # UI variables
        self.page = None
        self.weight_label = None
        self.status_label = None
        
        # State
        self.is_taring = False
        self.tare_start_time = 0
        
        # Create interface
        self._create_ui()
        
        if DEBUG_MODE:
            print("Scale App initialized")
        
        # Perform initial tare
        self._initial_tare()
    
    def _create_ui(self):
        """Create LVGL user interface"""
        # Create page
        self.page = m5ui.M5Page(bg_c=0x000000)
        
        # Weight label (large, centered)
        self.weight_label = m5ui.M5Label(
            "0",
            x=60,
            y=90,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=self._get_font(48),
            parent=self.page
        )
        
        # Status label (small, bottom)
        self.status_label = m5ui.M5Label(
            "Press to tare",
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
        
        self.status_label.set_text("Initial tare...")
        
        try:
            # Wait a bit for the sensor to stabilize
            for _ in range(10):
                M5.update()
                time.sleep_ms(100)
            
            # Perform tare
            success = self.scale.tare()
            
            if success:
                self.status_label.set_text("Ready")
                if DEBUG_MODE:
                    print("Initial tare completed")
            else:
                self.status_label.set_text("Tare error")
                if DEBUG_MODE:
                    print("Initial tare failed")
            
            # Show message briefly then switch to normal
            time.sleep(1)
            self.status_label.set_text("Press to tare")
            
        except Exception as e:
            if DEBUG_MODE:
                print(f"Initial tare error: {e}")
            self.status_label.set_text("Press to tare")
    
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
        if M5.BtnA.wasPressed() and not self.is_taring:
            self.is_taring = True
            self.tare_start_time = time.ticks_ms()
            self.status_label.set_text("Taring...")
            
            # Perform tare
            try:
                success = self.scale.tare()
                
                if success:
                    self.status_label.set_text("Tare done!")
                else:
                    self.status_label.set_text("Tare error")
            except Exception as e:
                if DEBUG_MODE:
                    print(f"Tare error: {e}")
                self.status_label.set_text("Tare error")
    
    def update(self):
        """Update weight display and handle tare timeout"""
        try:
            # Check button
            self._check_button()
            
            # Check if tare message should be reset
            if self.is_taring and time.ticks_diff(time.ticks_ms(), self.tare_start_time) > 2000:
                self.is_taring = False
                self.status_label.set_text("Press to tare")
            
            # Update weight display (unless taring in progress)
            if not self.is_taring:
                weight = self.scale.read_weight()
                weight_text = self._format_weight(weight)
                self.weight_label.set_text(weight_text)
        except Exception as e:
            if DEBUG_MODE:
                print(f"Update error: {e}")
    
    def run(self):
        """Main application loop"""
        if DEBUG_MODE:
            print("Scale App running...")
        
        try:
            while True:
                M5.update()  # Update M5 first to get button state
                self.update()
                time.sleep_ms(100)  # Update every 100ms
        except Exception as e:
            if DEBUG_MODE:
                print(f"Main loop error: {e}")
                import sys
                sys.print_exception(e)
            raise


# Entry point
if __name__ == "__main__":
    try:
        # Create and launch application
        # Uses all calibration points from the configuration file
        app = ScaleApp()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import sys
        sys.print_exception(e)
