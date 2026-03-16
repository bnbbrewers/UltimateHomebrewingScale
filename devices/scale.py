"""
Calibrated Scale Hardware Module
Handles reading weight from Unit Weight-I2C with calibration
"""

import json
import time
from unit import WeightI2CUnit
from hardware import I2C, Pin

# Import DEBUG mode from config
try:
    import config
    DEBUG_MODE = getattr(config, 'DEBUG', False)
except:
    DEBUG_MODE = False

# Configuration
CALIBRATION_FILE = "scale_calibration.json"
I2C_ADDRESS = 0x26
SCL_PIN = 15
SDA_PIN = 13

# Moving average for stable reading
MOVING_AVERAGE_SIZE = 10


class CalibratedScale:
    """
    Calibrated scale with tare functionality
    
    Uses piecewise linear interpolation between calibration points
    for accurate weight measurements across the full range.
    """
    
    def __init__(self, calibration_file=None):
        """
        Initialize the scale with calibration
        
        Args:
            calibration_file: Path to calibration JSON file (optional)
        """
        self.calibration_file = calibration_file or CALIBRATION_FILE
        self.weight_unit = None
        self.calibration_points = []
        self.tare_offset = 0
        self.adc_buffer = []
        self._adc_sum = 0
        
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
            with open(self.calibration_file, 'r') as f:
                data = json.load(f)
            
            points = data['scale']['CalibrationPoints']
            
            # Load all calibration points and sort by ADC value
            self.calibration_points = sorted(points, key=lambda p: p['adc_average'])
            
            if len(self.calibration_points) < 2:
                raise ValueError("At least 2 calibration points required")
            
            if DEBUG_MODE:
                print(f"Calibration loaded from {self.calibration_file}")
            
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
        """
        Read raw ADC value from sensor
        
        Returns:
            Raw ADC value (int), or None on error
        """
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
        self._adc_sum += adc_value
        if len(self.adc_buffer) > MOVING_AVERAGE_SIZE:
            self._adc_sum -= self.adc_buffer.pop(0)

        # Calculate average without re-summing full list each tick
        adc_avg = self._adc_sum / len(self.adc_buffer)
        
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
        """
        Perform tare (zero current weight)
        
        Returns:
            True if successful, False otherwise
        """
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
    
    def get_calibration_info(self):
        """
        Get calibration information
        
        Returns:
            Dictionary with calibration details
        """
        return {
            'num_points': len(self.calibration_points),
            'min_weight': self.calibration_points[0]['weight'] if self.calibration_points else 0,
            'max_weight': self.calibration_points[-1]['weight'] if self.calibration_points else 0,
            'tare_offset': self.tare_offset,
        }
    
    def is_stable(self, threshold=5.0, samples=5):
        """
        Check if weight reading is stable
        
        Args:
            threshold: Maximum allowed variation in grams
            samples: Number of recent samples to check
            
        Returns:
            True if stable, False otherwise
        """
        if len(self.adc_buffer) < samples:
            return False
        
        recent_weights = []
        for adc in self.adc_buffer[-samples:]:
            weight = self._adc_to_weight(adc) - self.tare_offset
            recent_weights.append(weight)
        
        # Check variation
        variation = max(recent_weights) - min(recent_weights)
        return variation < threshold
