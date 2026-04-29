# 🌍 i18n - Localization System

Lightweight localization system optimized for MicroPython.

**Current support:** 🇬🇧 English • 🇫🇷 French • (~120 keys each)

---

## 📁 Structure

```
i18n/
├── __init__.py              # Main module (I18n class)
├── locales/                 # Translations
│   ├── en.py               # 🇬🇧 English
│   ├── fr.py               # 🇫🇷 French
│   └── README.md           # Guide to add languages
├── example_usage.py         # Examples (basic + complete)
└── README.md               # This file
```

---

## 🚀 Quick Start (3 steps)

### 1. Configuration

In `config.py` (project root):

```python
LANGUAGE = "en"  # or "fr"
```

### 2. Import and Initialization

```python
from i18n import I18n
import config

# In your class __init__
self.i18n = I18n(config.LANGUAGE)
```

### 3. Usage

```python
# Simple
self.label.set_text(self.i18n.t('scale.tare_ready'))

# With positional argument
self.label.set_text(self.i18n.t('grain.target', 500))
# → "Target: 500g"

# With named argument
self.label.set_text(self.i18n.t('keg.filling_progress', percent=75))
# → "Filled: 75%"
```

---

## 🔧 Migrating Existing scale.py

### Required Changes

**1. Add imports** (at top of file):

```python
from i18n import I18n
import config
```

**2. Initialize i18n** (in `ScaleApp.__init__`):

```python
def __init__(self):
    M5.begin()
    m5ui.init()
    
    # ✨ Add this line
    self.i18n = I18n(config.LANGUAGE)
    
    # ... rest of code
```

**3. Replace hardcoded strings**:

| Before | After |
|-------|-------|
| `"Press to tare"` | `self.i18n.t('scale.tare_ready')` |
| `"Taring..."` | `self.i18n.t('scale.taring')` |
| `"Tare done!"` | `self.i18n.t('scale.tare_done')` |
| `"Tare error"` | `self.i18n.t('scale.tare_error')` |
| `"Initial tare..."` | `self.i18n.t('scale.initial_tare')` |
| `"Ready"` | `self.i18n.t('common.ready')` |

**Complete example:** See `i18n/example_usage.py --full`

---

## 🗂️ Available Translation Keys

### Scale Mode (`scale.*`)
- `scale.title` - Scale screen title
- `scale.tare_ready` - Prompt shown when the scale can be tared
- `scale.taring` - Tare operation in progress
- `scale.tare_done` - Tare operation completed
- `scale.tare_error` - Tare operation failed
- `scale.initial_tare` - Initial tare operation

### Common (`common.*`)
- `common.ready` - Generic ready state
- `common.error` - Generic error state
- `common.ok` - "OK"
- `common.cancel` - Generic cancel action
- `common.loading` - Generic loading state

### Grain Assistant (`grain.*`)
- `grain.title` - Grain assistant title
- `grain.target` - Target grain weight
- `grain.remaining` - Remaining grain weight
- `grain.complete` - Grain step completion message
- `grain.all_done` - All grains weighed message

### Hop Assistant (`hop.*`)
- `hop.title` - Hop assistant title
- `hop.target` - Target hop weight
- `hop.remaining` - Remaining hop weight
- `hop.addition_time` - Hop addition time

### Keg Filler (`keg.*`)
- `keg.title` - Keg filler title
- `keg.filling` - Filling in progress
- `keg.complete` - Filling complete
- `keg.filling_progress` - Filling progress percentage
- `keg.valve_open` - Valve open state
- `keg.valve_closed` - Valve closed state

### Menu & Settings (`menu.*`, `settings.*`)
- `menu.title` - "Menu"
- `menu.scale_mode` - Scale mode menu item
- `menu.grain_assistant` - Grain assistant menu item
- `menu.hop_assistant` - Hop assistant menu item
- `menu.keg_filler` - Keg filler menu item
- `settings.title` - Settings screen title
- `settings.language` - Language setting label
- `settings.wifi` - "Wi-Fi"

**Complete list:** See `i18n/locales/en.py` and `i18n/locales/fr.py`

---

## 🌍 Adding a New Language

### 1. Create Translation File

Copy `locales/en.py` to `locales/{code}.py` (e.g., `de.py` for German):

```python
"""
German translations for Ultimate Homebrewing Scale
"""

TRANSLATIONS = {
    'common': {
        'ready': 'Translated ready text',
        'error': 'Translated error text',
        # ... translate all keys
    },
    'scale': {
        'tare_ready': 'Translated tare prompt',
        # ...
    },
    # ... all groups
}
```

### 2. Update `i18n/__init__.py`

Add in `_load_translations()` method:

```python
elif self.lang == 'de':
    from .locales.de import TRANSLATIONS
```

And in `get_available_languages()`:

```python
return [
    ('en', 'English'),
    ('fr', 'French'),
    ('de', 'German'),  # Add this
]
```

### 3. Test

```python
# In config.py
LANGUAGE = "de"
```

See `i18n/locales/README.md` for more details.

---

## 📚 API Reference

### `I18n` Class

```python
from i18n import I18n

# Initialization
i18n = I18n('en')  # or 'fr'

# Simple translation
text = i18n.t('scale.tare_ready')

# With positional arguments
text = i18n.t('grain.target', 500)
# → "Target: 500g"

# With named arguments
text = i18n.t('keg.filling_progress', percent=75)
# → "Filled: 75%"

# Change language
i18n.set_lang('fr')  # Returns True if successful

# Get current language
lang = i18n.get_lang()  # → 'en'

# List available languages
langs = i18n.get_available_languages()
# → [('en', 'English'), ('fr', 'French')]
```

---

## 🧪 Testing

### Quick Test (Terminal)

```bash
# From project root

# Basic examples (quick, no hardware needed)
python i18n/example_usage.py

# Complete examples with ScaleApp (requires M5Stack)
python i18n/example_usage.py --full
```

### Unit Tests

```python
from i18n import I18n

# Test EN
i18n = I18n('en')
assert i18n.t('scale.tare_ready') == 'Press to tare'

# Test FR; expected value depends on the French locale file
i18n = I18n('fr')
assert isinstance(i18n.t('scale.tare_ready'), str)

# Test with arguments
assert isinstance(i18n.t('grain.target', 500), str)
assert isinstance(i18n.t('keg.filling_progress', percent=75), str)
```

---

## 🎨 UI Considerations

### Text Length

Translations can be longer:

| Language | Text | Length |
|--------|-------|----------|
| 🇬🇧 EN | "Press to tare" | 14 chars |
| FR | French translation | Typically longer |
| DE | German translation | Typically longer |

**Recommendation:** Allow 30-40% extra space in labels.

### Fonts

M5Stack Montserrat fonts support:
- French accented characters
- German accented characters
- Spanish accented characters

---

## 🐛 Troubleshooting

### "Translation key not found"

**Cause:** Missing key in translation file

**Solution:** Add the key to `i18n/locales/{lang}.py`

### "Could not load translations"

**Cause:** Missing language file or syntax error

**Solution:** 
1. Verify `i18n/locales/{lang}.py` exists
2. Check Python syntax
3. Ensure `TRANSLATIONS` is defined

### Accented characters display incorrectly

**Cause:** Font doesn't support UTF-8

**Solution:** Use M5Stack Montserrat fonts

### Text cut off in UI

**Cause:** Label too small for translation

**Solution:** Increase label size or reduce font size

---

## ⚡ Performance

System optimized for MicroPython:

- ✅ **No I/O** - Direct Python imports (no file reading)
- ✅ **Fast lookups** - Native Python dictionaries
- ✅ **Memory efficient** - Only one language loaded at a time
- ✅ **No dependencies** - Vanilla Python code

**Memory footprint:** ~5-10 KB (one language loaded)

---

## 📊 Statistics

- **Supported languages:** 2 (EN, FR)
- **Translations:** ~120 keys per language
- **Features covered:** 100%
- **Files:** 4 (module + 2 languages + README)
- **Total size:** ~15 KB

---

## 🤝 Contributing

To add a translation:

1. Fork the project
2. Create `i18n/locales/{code}.py` with all translations
3. Update `i18n/__init__.py`
4. Test on real hardware if possible
5. Submit a Pull Request

Translations are welcome! 🌍

---

---

**Version:** 1.0  
**License:** Same as project (see LICENSE)  
**Ready for:** 🇩🇪 DE • 🇪🇸 ES • 🇮🇹 IT • 🇵🇹 PT • ...

🍺 **Happy multilingual brewing!** 🌍
