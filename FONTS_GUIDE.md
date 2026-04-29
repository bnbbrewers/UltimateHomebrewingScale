# M5Dial Font Guide

## Fonts Available in UIFlow2

The Montserrat fonts available in our UIFlow2 firmware are:

### Available Sizes
- `lv.font_montserrat_14`
- `lv.font_montserrat_16`
- `lv.font_montserrat_24`

### Imported Custom Font
- `S:/flash/assets/montserrat_40.bin` via `lv.binfont_create(...)`
- Used for the main weight value in `ui/weight_screen.py`
- Partial font: do not use it as a general-purpose UI font

### Unavailable Sizes
- `lv.font_montserrat_10`
- `lv.font_montserrat_12`
- `lv.font_montserrat_18`
- `lv.font_montserrat_20`
- `lv.font_montserrat_22`
- `lv.font_montserrat_26`
- `lv.font_montserrat_28`
- `lv.font_montserrat_32`
- `lv.font_montserrat_48`
- Any size other than 14, 16, and 24

## Recommended Usage

Use the firmware fonts directly. There is no dynamic detection: we control the
firmware and reference existing fonts explicitly.

```python
label = m5ui.M5Label(
    "My Text",
    x=10, y=10,
    font=lv.font_montserrat_24,
    parent=self.page,
)
```

## Adding Custom Fonts

This is complex and requires rebuilding the UIFlow2 firmware.

### Option 1: LVGL Font Converter

1. Prepare the font:
   - Download a TrueType font (`.ttf`)
   - Example source: Google Fonts

2. Convert it with the LVGL online converter:
   - Open `https://lvgl.io/tools/fontconverter`
   - Upload the `.ttf` file
   - Select the target size, for example `32px`
   - Select format: `C array`
   - Select BPP: `4 bits`
   - Select range: `Basic Latin` or a custom range
   - Convert and download the `.c` file

3. Integrate it into UIFlow2:

```c
// In the UIFlow2 firmware
#include "my_font_32.c"

// Register it in LVGL
lv_font_t *my_font_32 = &lv_font_my_font_32;
```

4. Rebuild and flash the modified firmware.

### Option 2: Binary Fonts from MicroPython

This project supports one targeted binary font use case: `ui/weight_screen.py`
loads `S:/flash/assets/montserrat_40.bin` with `lv.binfont_create(...)`.

That font is partial and reserved for the main weight value. For labels, titles,
and status text, use the firmware fonts `14`, `16`, and `24`.

### Option 3: Images

For very large text, create PNG images:

```python
# Create digit images (0-9)
images = {
    "0": "/flash/assets/fonts/digit_0.png",
    "1": "/flash/assets/fonts/digit_1.png",
    # ...
}

# Display them
for char in str(weight):
    img = m5ui.M5Image(images[char], x=x, y=y, parent=page)
    x += 30
```

Advantages:
- Very large sizes are possible
- Fully custom styling

Drawbacks:
- Higher memory usage
- More work to animate

## Project Recommendations

1. Use the firmware fonts directly: `14`, `16`, and `24`.
2. Use `24` explicitly for larger standard text.
3. Do not rebuild the firmware unless strictly needed.
4. Use the imported partial 40px font only for the main weight value.
5. For very large non-weight text, consider images or multiple labels.

## Project Usage

The project references these fonts directly:
- `lv.font_montserrat_14`
- `lv.font_montserrat_16`
- `lv.font_montserrat_24`
- `S:/flash/assets/montserrat_40.bin` in `ui/weight_screen.py`

## Font Usage Table

| Usage | Requested Size | Actual Size | Font |
|-------|----------------|-------------|------|
| Title | 16 | 16 | `lv.font_montserrat_16` |
| Main weight | 40 | partial 40 | `S:/flash/assets/montserrat_40.bin` |
| Large standard text | 24 | 24 | `lv.font_montserrat_24` |
| Status | 14 | 14 | `lv.font_montserrat_14` |
| Small text | 14 | 14 | `lv.font_montserrat_14` |

## Useful Links

- LVGL Font Converter: `https://lvgl.io/tools/fontconverter`
- LVGL Fonts documentation: `https://docs.lvgl.io/master/overview/font.html`
- Google Fonts: `https://fonts.google.com/`
- UIFlow2 documentation: `https://docs.m5stack.com/`

## Summary

For Ultimate Homebrewing Scale:
- Use firmware fonts `14`, `16`, and `24` directly.
- Use the partial custom 40px font only for the main weight value.
- Use `24` for large standard text.
- Do not add general-purpose custom fonts unless the firmware is rebuilt.
- Use images for very large text when needed.
