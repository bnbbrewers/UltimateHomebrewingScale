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

# Minimum interval between actual hardware reads (ms)
READ_INTERVAL_MS = 100

# Minimum delta (grams) required before exposing a new weight to callers.
# Set to 0 to disable value throttling.
REPORT_THRESHOLD_G = 1.0


class CalibratedScale:
    """
    Calibrated scale with tare functionality
    
    Uses piecewise linear interpolation between calibration points
    for accurate weight measurements across the full range.
    """
    
    def __init__(
        self,
        calibration_file=None,
        read_interval_ms=READ_INTERVAL_MS,
        report_threshold_g=REPORT_THRESHOLD_G,
    ):
        """
        Initialize the scale with calibration

        Args:
            calibration_file: Path to calibration JSON file (optional)
            read_interval_ms: Minimum ms between actual hardware reads (default 100)
            report_threshold_g: Minimum delta in grams before exposing a new
                weight value to callers (default 1.0, set 0 to disable)
        """
        self.calibration_file = calibration_file or CALIBRATION_FILE
        self.weight_unit = None
        self.calibration_points = []
        self.tare_offset = 0
        self.adc_buffer = []
        self._adc_sum = 0
        self._read_interval_ms = read_interval_ms
        self._last_read_ms = None
        self._cached_weight = None
        self._report_threshold_g = report_threshold_g
        self._reported_weight = None
        
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
        Read current weight with moving average for stability.

        Hardware is only queried once per _read_interval_ms; calls within
        that window return the last cached value immediately (non-blocking).
        A report threshold can additionally suppress very small jitter updates.

        Returns:
            Weight in grams (float), or None if no valid reading yet
        """
        raw_weight = self._acquire_weight(force=False)
        return self._apply_report_threshold(raw_weight)

    def _acquire_weight(self, force=False):
        """
        Read/refresh internal cached weight from hardware.

        Args:
            force: If True, bypass READ_INTERVAL_MS throttling.
        """
        now = time.ticks_ms()
        if (
            not force
            and self._last_read_ms is not None
            and time.ticks_diff(now, self._last_read_ms) < self._read_interval_ms
        ):
            return self._cached_weight

        self._last_read_ms = now
        adc_value = self.read_raw_adc()

        if adc_value is None:
            return self._cached_weight

        # Add to moving average
        self.adc_buffer.append(adc_value)
        self._adc_sum += adc_value
        if len(self.adc_buffer) > MOVING_AVERAGE_SIZE:
            self._adc_sum -= self.adc_buffer.pop(0)

        # Calculate average without re-summing full list each tick
        adc_avg = self._adc_sum / len(self.adc_buffer)

        # Convert to weight and apply tare offset
        weight = self._adc_to_weight(adc_avg) - self.tare_offset

        # if DEBUG_MODE and len(self.adc_buffer) == MOVING_AVERAGE_SIZE:
        #     if int(time.time() * 10) % 10 == 0:
        #         print(f"ADC: {adc_avg:.0f} | Weight: {weight:.1f}g | Tare: {self.tare_offset:.1f}g")

        self._cached_weight = weight
        return self._cached_weight

    def _apply_report_threshold(self, weight):
        """Throttle exposed values to reduce tiny UI-level jitter updates."""
        if weight is None:
            return None
        if self._report_threshold_g <= 0:
            self._reported_weight = weight
            return weight
        if self._reported_weight is None:
            self._reported_weight = weight
            return weight
        if abs(weight - self._reported_weight) >= self._report_threshold_g:
            self._reported_weight = weight
        return self._reported_weight
    
    def tare(self, num_samples=5, settle_ms=50):
        """
        Perform tare (zero current weight).

        Uses fewer samples with shorter settle time than the full moving
        average to keep blocking time under 300 ms.  Calls M5.update()
        between reads to prevent the system watchdog from rebooting.
        """
        self.adc_buffer.clear()
        self._adc_sum = 0
        self._reported_weight = None
        samples = []
        for _ in range(num_samples):
            self._last_read_ms = None
            # Force hardware reads for tare sampling, independent of report threshold.
            weight = self._acquire_weight(force=True)
            if weight is not None:
                weight += self.tare_offset
                samples.append(weight)
            try:
                import M5
                M5.update()
            except Exception:
                pass
            time.sleep_ms(settle_ms)

        if samples:
            self.tare_offset = sum(samples) / len(samples)
            self._cached_weight = None
            self._reported_weight = None
            self._last_read_ms = None
            if DEBUG_MODE:
                print("Tare set to: {:.1f}g".format(self.tare_offset))
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
