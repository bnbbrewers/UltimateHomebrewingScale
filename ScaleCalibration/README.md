# Scale Calibration Wizard

A calibration wizard for the M5 Dial weight scale using the Weight I2C Unit (HX711).

## Overview

This calibration wizard helps you calibrate your weight scale by measuring ADC (Analog-to-Digital Converter) values at different known weights. The wizard guides you through 4 calibration points with an intuitive rotary encoder interface.

## Hardware Requirements

- **M5 Dial** (ESP32-based device with rotary encoder)
- **Weight I2C Unit** (HX711-based, connected via I2C)
  - SCL: Pin 15
  - SDA: Pin 13
  - I2C Address: 0x26

## Configuration

Edit the following constants at the top of `ScaleCalibrationWizard.py`:

```python
CALIBRATION_POINTS = [0, 500, 5000, 20000]  # Calibration weights in grams
CALIBRATION_DURATION = 30  # Measurement duration in seconds
DEBUG_MODE = True  # Enable/disable serial debug logging
```

### Parameters

- **`CALIBRATION_POINTS`**: Array of calibration weights in grams
  - Default: `[0, 500, 5000, 20000]` (0g, 500g, 5kg, 20kg)
  - Adjust based on your available calibration weights

- **`CALIBRATION_DURATION`**: Duration for ADC averaging at each point
  - Default: `30` seconds
  - Longer duration = more stable average
  - Shorter duration = faster calibration

- **`DEBUG_MODE`**: Enable serial port logging
  - `True`: Log ADC values and debug info to serial port
  - `False`: Silent operation (production mode)

## User Interface

The wizard displays:
- **Title**: "Scale Calibration" (top)
- **Step Info**: Current step (e.g., "Step 2/4: 500g")
- **Instructions**: "Enc: adjust / Btn: start"
- **Status**: Current target and measurement progress
- **Progress Bar**: Visual feedback during measurement

### Display Layout (240px round screen)

```
┌─────────────────────┐
│  Scale Calibration  │  (y=30, gray)
│                     │
│   Step 2/4: 500g    │  (y=75, white)
│                     │
│  Enc: adjust        │  (y=105, gray, small)
│  Btn: start         │
│                     │
│   Target 500g       │  (y=150, white)
│                     │
│ ▓▓▓▓▓▓▓░░░░░░░░░░   │  (y=195, progress bar)
└─────────────────────┘
```

## Calibration Process

### Step-by-Step Guide

1. **Launch the wizard**
   ```
   execfile("/flash/apps/ScaleCalibrationWizard.py")
   ```

2. **For each calibration point** (4 steps):

   **a. Adjust the effective weight value**
   - Turn the rotary encoder to adjust the weight value
   - This allows you to match the **actual weight** of your calibration object
   - **Example**: If you don't have exactly 500g, but have a 498g weight, adjust to 498g
   - The display shows the current weight being adjusted
   - Default values are from `CALIBRATION_POINTS`, but you can adjust to any value
   
   **Encoder Acceleration:**
   - **Slow rotation** (> 500ms between clicks): **1g** increments (precision)
   - **2 fast clicks** (< 500ms): **10g** increments (medium)
   - **3 fast clicks** (< 500ms): **100g** increments (coarse)
   - **Pause**: Gradual deceleration (100g → 10g → 1g)
   
   **b. Place the weight on the scale**
   - Use a calibration weight matching the target
   - Or adjust to match your actual reference weight
   
   **c. Start measurement**
   - Press the center button to start
   - Wait while the wizard averages ADC readings
   - Progress bar shows measurement progress
   - **Debug mode**: Raw ADC values are logged to serial port every 100ms (see [Debugging](#debugging))
   
   **d. Repeat** for all 4 calibration points

3. **Completion**
   - The wizard saves calibration data automatically
   - Display shows "Calibration complete! Data saved"

## Rotary Encoder Controls

### Basic Operation

- **Turn slowly**: Adjust by 1g (fine precision)
- **Turn quickly**: Build momentum up to 100g per click
- **Press button**: Confirm and start measurement

### Momentum System

The encoder uses a momentum-based acceleration system:

```
1st click      →  1g   (fine adjustment)
2nd click      →  10g  (if < 500ms after 1st)
3rd click      →  100g (if < 500ms after 2nd)
Continuous     →  100g (stays at 100g)
Pause > 500ms  →  Gradual deceleration:
                  100g → 10g → 1g
```

**Tips:**
- For precise adjustments: Turn slowly, 1g at a time
- For large changes: Turn 3 times quickly to reach 100g/click
- To reset to 1g: Pause for ~1 second

## Output Format

The calibration data is saved to `/flash/scale_calibration.json` with the following structure:

```json
{
  "scale": {
    "CalibrationPoints": [
      {
        "step": 0,
        "calibration_point": 0,
        "weight": 0,
        "adc_average": 8388608.0
      },
      {
        "step": 1,
        "calibration_point": 500,
        "weight": 500,
        "adc_average": 8423456.5
      },
      {
        "step": 2,
        "calibration_point": 5000,
        "weight": 5000,
        "adc_average": 9123456.8
      },
      {
        "step": 3,
        "calibration_point": 20000,
        "weight": 20000,
        "adc_average": 12345678.2
      }
    ]
  }
}
```

### Fields Description

- **`step`**: Calibration step index (0-3)
- **`calibration_point`**: Reference weight from `CALIBRATION_POINTS` array
- **`weight`**: Actual weight used (adjusted with encoder if needed)
- **`adc_average`**: Average ADC value measured over the duration

## Debugging

### Serial Port Monitoring

When `DEBUG_MODE = True`, the wizard outputs debug information to the serial port (typically 115200 baud):

```
ADC: 8388615
ADC: 8388612
ADC: 8388619
...
Saving calibration data: {'scale': {'CalibrationPoints': [...]}}
Calibration data saved to /flash/scale_calibration.json
```

### Common Issues

**Error: "Save error: ..."**
- Check available flash memory
- Ensure `/flash/` is writable
- Check serial output for detailed error message

**ADC values not changing**
- Verify I2C connections (Pin 15/13)
- Check Weight Unit I2C address (0x26)
- Enable DEBUG_MODE to see raw ADC readings

**Encoder not responding**
- Verify rotary encoder is functioning
- Check `M5.Dial` hardware initialization
- Try turning more slowly or quickly

## Technical Details

### ADC Sampling

- **Sampling rate**: Every 100ms
- **Samples per point**: `CALIBRATION_DURATION * 10`
- **Example**: 30s duration = 300 samples averaged

### Data Processing

1. Collect raw ADC values during measurement window
2. Calculate arithmetic mean of all samples
3. Store as floating-point average
4. Build JSON structure with all calibration points
5. Save to flash memory

## License

Part of the Ultimate Homebrewing Scale (UHS) project.
See main project LICENSE for details.

## Support

For issues or questions:
- Check serial output with `DEBUG_MODE = True`
- Verify hardware connections
- Ensure UIFlow2 2.4+ firmware is installed
