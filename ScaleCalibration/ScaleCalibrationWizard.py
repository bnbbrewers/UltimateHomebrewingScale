import os, sys, io
import M5
from M5 import *
import m5ui
import lvgl as lv
from hardware import Pin
from hardware import I2C
from hardware import Rotary
from unit import WeightI2CUnit
import time
import json


# Configuration
CALIBRATION_POINTS = [0, 500, 5000, 20000]  # Default calibration points (grams)
CALIBRATION_DURATION = 30  # seconds
DEBUG_MODE = True  # Set to False to disable debug logging

# Global variables
page0 = None
title_label = None
info_step_label = None
info_label = None
status_label = None
progress_bar = None
i2c0 = None
weight_i2c_0 = None
rotary = None

# Wizard state
current_step = 0  # Current calibration index
adjusted_weights = list(CALIBRATION_POINTS)  # Adjustable weights
calibration_data = {}  # Stores results

# Encoder with momentum
last_encoder_change_time = 0
encoder_speed_multiplier = 1  # Start at 1g for precision
encoder_last_direction = 0
encoder_momentum_count = 0


def get_font(preferred_size: int = 16):
    """Return an available LVGL font, with fallbacks if missing."""
    candidates = [
        f"font_montserrat_{preferred_size}",
        f"font_montserrat_{preferred_size - 2}",
        "font_montserrat_16",
        "font_montserrat_14",
        "font_montserrat_12",
        "font_montserrat_10",
    ]
    for name in candidates:
        if hasattr(lv, name):
            return getattr(lv, name)
    return None


def setup():
    global page0, title_label, info_step_label, info_label, status_label, i2c0, weight_i2c_0, rotary
    
    M5.begin()
    m5ui.init()
    page0 = m5ui.M5Page(bg_c=0x000000)
    
    # Title - centered with softer color
    title_label = m5ui.M5Label(
        "Scale Calibration",
        x=50,
        y=30,
        text_c=0x9CA3AF,
        bg_c=0x000000,
        bg_opa=0,
        font=get_font(16),
        parent=page0,
    )
    
    # Current calibration step - larger
    info_step_label = m5ui.M5Label(
        "Step 1/4: 0g",
        x=65,
        y=75,
        text_c=0xE0E0E0,
        bg_c=0x000000,
        bg_opa=0,
        font=get_font(16),
        parent=page0,
    )
    
    # Instructions - smaller and more discreet
    info_label = m5ui.M5Label(
        "Rotary: adjust\nBtn: start",
        x=60,
        y=105,
        text_c=0x808080,
        bg_c=0x000000,
        bg_opa=0,
        font=get_font(9),
        parent=page0,
    )
    
    # Status - below instructions
    status_label = m5ui.M5Label(
        "",
        x=70,
        y=150,
        text_c=0xE0E0E0,
        bg_c=0x000000,
        bg_opa=0,
        font=get_font(12),
        parent=page0,
    )

    # Progress bar (LVGL) for calibration time
    global progress_bar
    progress_bar = lv.bar(page0)
    progress_bar.set_size(160, 8)
    progress_bar.set_pos(40, 195)
    progress_bar.set_range(0, 100)
    progress_bar.set_value(0, False)
    
    i2c0 = I2C(0, scl=Pin(15), sda=Pin(13), freq=100000)
    weight_i2c_0 = WeightI2CUnit(i2c0, 0x26)
    
    # Initialize rotary encoder (UIFlow2 2.4)
    rotary = Rotary()
    rotary.reset_rotary_value()
    
    update_display()
    page0.screen_load()


def is_button_pressed():
    """Check if button is pressed"""
    return M5.BtnA.wasPressed()


def update_display():
    """Refresh display with current state"""
    global title_label, info_step_label, info_label, status_label, current_step, adjusted_weights
    
    if current_step < len(CALIBRATION_POINTS):
        weight = adjusted_weights[current_step]
        step_name = f"{CALIBRATION_POINTS[current_step]}g"
        info_step_label.set_text(f"Step {current_step + 1}/4: {step_name}")
        info_label.set_text("Enc: adjust\nBtn: start")
        status_label.set_text(f"Target {weight}g")
    else:
        info_step_label.set_text("Calibration complete")
        info_label.set_text("")
        status_label.set_text("Data saved")


def read_adc_average(duration_seconds=30):
    """Read ADC during the window and return average"""
    global weight_i2c_0, status_label, progress_bar
    
    values = []
    start_time = time.ticks_ms()
    duration_ms = duration_seconds * 1000
    sample_count = 0
    
    status_label.set_text(f"Measuring\n0/{duration_seconds}s")
    if progress_bar:
        progress_bar.set_value(0, False)
    
    while time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
        M5.update()
        try:
            adc_value = weight_i2c_0.get_adc_raw
            if adc_value is not None:
                values.append(adc_value)
                sample_count += 1
                # Log ADC value to serial port (only in DEBUG mode)
                if DEBUG_MODE:
                    print(f"ADC: {adc_value}")
        except Exception as e:
            if DEBUG_MODE:
                print(f"ADC read error: {e}")
        
        # Update display roughly once a second
        elapsed = time.ticks_diff(time.ticks_ms(), start_time) // 1000
        if sample_count % 10 == 0:  # Roughly each second
            status_label.set_text(f"Measuring\n{elapsed}/{duration_seconds}s")
            if progress_bar:
                pct = min(100, int((elapsed * 100) / duration_seconds)) if duration_seconds else 100
                progress_bar.set_value(pct, False)
        
        time.sleep_ms(100)
    
    if len(values) > 0:
        average = sum(values) / len(values)
        status_label.set_text(f"Avg: {int(average)}")
        if progress_bar:
            progress_bar.set_value(100, False)
        return average
    return 0


def save_calibration_data():
    """Save calibration data to JSON"""
    global calibration_data
    
    try:
        # Build CalibrationPoints array with step, calibration_point, weight, and ADC average
        calibration_points = []
        # Sort by weight to maintain step order
        sorted_data = sorted(calibration_data.items(), key=lambda x: x[0])
        
        for step_index, (weight, adc_value) in enumerate(sorted_data):
            calibration_points.append({
                "step": step_index,
                "calibration_point": CALIBRATION_POINTS[step_index] if step_index < len(CALIBRATION_POINTS) else 0,
                "weight": int(weight),
                "adc_average": float(adc_value)
            })
        
        # Build complete data dictionary
        data = {
            "scale": {
                "CalibrationPoints": calibration_points
            }
        }
        
        if DEBUG_MODE:
            print(f"Saving calibration data: {data}")
        
        # Save JSON file to /flash root
        filename = "/flash/scale_calibration.json"
        with open(filename, 'w') as f:
            json.dump(data, f)
        
        if DEBUG_MODE:
            print(f"Calibration data saved to {filename}")
        
        return True
    except Exception as e:
        error_msg = f"Save error: {str(e)}"
        status_label.set_text(error_msg[:30])
        if DEBUG_MODE:
            print(error_msg)
        return False


def loop():
    global page0, info_step_label, info_label, status_label, i2c0, weight_i2c_0
    global current_step, adjusted_weights, calibration_data
    global last_encoder_change_time, encoder_speed_multiplier, encoder_last_direction, encoder_momentum_count
    
    M5.update()
    
    # Exit early if all steps are done
    if current_step >= len(CALIBRATION_POINTS):
        time.sleep_ms(100)
        return
    
    # Adjust phase: allow encoder to change weight with acceleration
    encoder_delta = rotary.get_rotary_value() if rotary else 0
    if rotary:
        rotary.reset_rotary_value()
    
    if encoder_delta != 0:
        current_time = time.ticks_ms()
        delta_time = time.ticks_diff(current_time, last_encoder_change_time)
        
        # Precision-first momentum system:
        # - Default: 1g (precision adjustments)
        # - Fast continuous rotation in same direction: builds up to 10g then 100g
        # - Slow rotation or direction change: back to 1g
        
        current_direction = 1 if encoder_delta > 0 else -1
        
        # Check if continuing in same direction quickly
        if delta_time < 500 and current_direction == encoder_last_direction:
            # Build momentum: max 3 fast clicks possible
            encoder_momentum_count += 1
            if encoder_momentum_count >= 3:
                encoder_speed_multiplier = 100  # 3rd fast click
            elif encoder_momentum_count >= 2:
                encoder_speed_multiplier = 10   # 2nd fast click
            else:
                encoder_speed_multiplier = 1    # 1st click
        else:
            # Gradual deceleration on pause or direction change
            if encoder_speed_multiplier == 100:
                encoder_speed_multiplier = 10
                encoder_momentum_count = 1  # Maintain at 10g level
            elif encoder_speed_multiplier == 10:
                encoder_speed_multiplier = 1
                encoder_momentum_count = 0
            else:
                encoder_speed_multiplier = 1
                encoder_momentum_count = 0
        
        encoder_last_direction = current_direction
        last_encoder_change_time = current_time
        
        # Apply change with momentum (1g → 10g → 100g)
        adjusted_weights[current_step] += encoder_delta * encoder_speed_multiplier
        
        # Clamp to reasonable bounds
        if adjusted_weights[current_step] < 0:
            adjusted_weights[current_step] = 0
        if adjusted_weights[current_step] > 50000:
            adjusted_weights[current_step] = 50000
        update_display()
    
    # Start calibration on button press
    if is_button_pressed():
        weight = adjusted_weights[current_step]
        
        # Read ADC for the duration and average
        average_adc = read_adc_average(CALIBRATION_DURATION)
        
        # Store average
        calibration_data[weight] = average_adc
        
        # Next step
        current_step += 1
        
        if current_step < len(CALIBRATION_POINTS):
            update_display()
            time.sleep_ms(500)  # Pause avant le point suivant
        else:
            # Final step: save
            update_display()
            if save_calibration_data():
                status_label.set_text("Calibration complete!\nData saved")
            time.sleep_ms(2000)
    
    time.sleep_ms(50)


if __name__ == '__main__':
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        try:
            m5ui.deinit()
            from utility import print_error_msg
            print_error_msg(e)
        except ImportError:
            print("please update to latest firmware")