# Devices Module Guide

## Overview

Hardware device management modules have been extracted into `devices/`.

Available devices:
- **Scale**: calibrated scale with tare support (`devices/scale.py`)
- **Button**: centralized short-press and long-press handling (`devices/button.py`)
- **Relay**: relay control, planned for later

## Architecture

```text
devices/
├── __init__.py           # Exports CalibratedScale, etc.
├── button.py             # ButtonDevice (short/long press)
├── scale.py              # CalibratedScale class
└── relay.py              # RelayController class, future
```

## Usage

### Import

```python
from devices.scale import CalibratedScale

# Or via __init__.py
from devices import CalibratedScale
```

### Initialization

```python
# Basic usage
scale = CalibratedScale()

# With a custom calibration file
scale = CalibratedScale(calibration_file="custom_cal.json")
```

### Reading Weight

```python
# Read weight with moving average
weight = scale.read_weight_filtered()  # Returns weight in grams as a float

if weight is not None:
    print(f"Current weight: {weight:.1f}g")
```

### Tare

```python
# Tare the scale
success = scale.tare()

if success:
    print("Tare completed")
```

### Checking Stability

```python
# Check whether the reading is stable
if scale.is_stable(threshold=5.0, samples=5):
    print("Weight is stable")
```

### Calibration Information

```python
info = scale.get_calibration_info()
print(f"Points: {info['num_points']}")
print(f"Range: {info['min_weight']}g - {info['max_weight']}g")
print(f"Tare: {info['tare_offset']}g")
```

## API Reference

### `CalibratedScale`

#### `__init__(calibration_file=None)`
- Initializes the scale with calibration data.
- `calibration_file`: optional path to a JSON calibration file.

#### `read_weight_filtered() -> float | None`
- Reads the current weight using a moving average.
- Returns the weight in grams, or `None` on error.

#### `read_raw_adc() -> int | None`
- Reads the raw ADC value from the sensor.
- Returns the ADC value, or `None` on error.

#### `tare() -> bool`
- Performs tare.
- Returns `True` on success, `False` otherwise.

#### `is_stable(threshold=5.0, samples=5) -> bool`
- Checks whether the reading is stable.
- `threshold`: maximum tolerated variation in grams.
- `samples`: number of samples to check.

#### `get_calibration_info() -> dict`
- Returns calibration metadata.
- Keys: `num_points`, `min_weight`, `max_weight`, `tare_offset`.

## Apps Using `CalibratedScale`

### Scale App (`apps/scale_app.py`)

Simple weight display with tare.

### Grain Assistant (`apps/malt_app.py`)

Malt weighing with comparison against a target weight.

### Hop Assistant (`apps/hop_app.py`)

Hop weighing with comparison against a target weight.

### Keg Filler (`apps/keg_filler_app.py`)

Keg filling with weight-to-volume conversion.

## Configuration

### File: `scale_calibration.json`

```json
{
  "scale": {
    "CalibrationPoints": [
      {
        "step": 1,
        "weight": 0,
        "adc_average": 8388608
      },
      {
        "step": 2,
        "weight": 100,
        "adc_average": 8423456
      }
    ]
  }
}
```

### Constants in `devices/scale.py`

```python
CALIBRATION_FILE = "scale_calibration.json"
I2C_ADDRESS = 0x26
SCL_PIN = 15
SDA_PIN = 13
MOVING_AVERAGE_SIZE = 10  # Samples for smoothing
```

## Complete Example

```python
from devices.scale import CalibratedScale
import time

# Initialize scale
scale = CalibratedScale()

# Tare
print("Place nothing on scale, then tare...")
time.sleep(2)
scale.tare()

# Read weight continuously
print("Add weight...")
while True:
    weight = scale.read_weight_filtered()

    if weight is not None:
        print(f"Weight: {weight:.1f}g")

        # Check stability
        if scale.is_stable():
            print("  (stable)")

    time.sleep(0.5)
```

## Benefits of Separation

1. Reusability: the same code is shared by every app.
2. Maintainability: fixes live in one place.
3. Hardware isolation: hardware behavior is kept out of the UI layer.
4. Clarity: UI and business logic stay separated.
5. Performance: a single instance can be shared.

## Debug Mode

The `DEBUG` setting from `config.py` also applies to `CalibratedScale`:

```python
# config.py
DEBUG = True  # Enables scale traces
```

Displayed traces:
- Sensor initialization
- Calibration loading
- ADC and weight reads, throttled
- Tare operations

## Deployment

Upload these files to the M5Dial:

```text
devices/
├── __init__.py
└── scale.py

apps/
├── scale.py          (modified)
├── malt_app.py       (modified)
├── hop_app.py        (modified)
└── keg_filler_app.py (modified)
```

## Manual Check

```python
# On the M5Dial
exec(open("main.py").read())

# 1. Select Scale App. It works.
# 2. Select Grain Assistant. It uses the same scale.
# 3. Return to the launcher with a 3-second long press.
# 4. Select Hop Assistant. The scale is already initialized.
```

## Performance

- Memory: shared class across apps
- CPU: optimized moving average
- Latency: around 50 ms per read
- Precision: multi-point linear interpolation

## Troubleshooting

### Error: `Weight Unit initialization failed`

- Check I2C wiring.
- Check SCL/SDA pins: 15/13.
- Check I2C address: `0x26`.

### Error: `Calibration file not found`

- Upload `scale_calibration.json`.
- Or run the scale calibration wizard.

### Unstable Weight

- Increase `MOVING_AVERAGE_SIZE`.
- Use `is_stable()` before reading.
- Avoid vibrations.

### Incorrect Weight

- Recalibrate with the wizard.
- Check calibration points.
- Test with known weights.
