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
# → "Target: 500g" / "Cible : 500g"

# With named argument
self.label.set_text(self.i18n.t('keg.filling_progress', percent=75))
# → "Filled: 75%" / "Rempli : 75%"
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
- `scale.title` - "Scale" / "Balance"
- `scale.tare_ready` - "Press to tare" / "Appuyer pour tarer"
- `scale.taring` - "Taring..." / "Tarage..."
- `scale.tare_done` - "Tare done!" / "Tarage effectué !"
- `scale.tare_error` - "Tare error" / "Erreur de tarage"
- `scale.initial_tare` - "Initial tare..." / "Tarage initial..."

### Common (`common.*`)
- `common.ready` - "Ready" / "Prêt"
- `common.error` - "Error" / "Erreur"
- `common.ok` - "OK"
- `common.cancel` - "Cancel" / "Annuler"
- `common.loading` - "Loading..." / "Chargement..."

### Grain Assistant (`grain.*`)
- `grain.title` - "Grain Assistant" / "Assistant Malts"
- `grain.target` - "Target: {0}g" / "Cible : {0}g"
- `grain.remaining` - "Remaining: {0}g" / "Restant : {0}g"
- `grain.complete` - "Complete!" / "Terminé !"
- `grain.all_done` - "All grains weighed!" / "Tous les malts pesés !"

### Hop Assistant (`hop.*`)
- `hop.title` - "Hop Assistant" / "Assistant Houblons"
- `hop.target` - "Target: {0}g" / "Cible : {0}g"
- `hop.remaining` - "Remaining: {0}g" / "Restant : {0}g"
- `hop.addition_time` - "Addition: {0} min" / "Ajout : {0} min"

### Keg Filler (`keg.*`)
- `keg.title` - "Keg Filler" / "Remplisseur de Fûts"
- `keg.filling` - "Filling..." / "Remplissage..."
- `keg.complete` - "Filling complete!" / "Remplissage terminé !"
- `keg.filling_progress` - "Filled: {percent}%" / "Rempli : {percent}%"
- `keg.valve_open` - "Valve: OPEN" / "Vanne : OUVERTE"
- `keg.valve_closed` - "Valve: CLOSED" / "Vanne : FERMÉE"

### Menu & Settings (`menu.*`, `settings.*`)
- `menu.title` - "Menu"
- `menu.scale_mode` - "Scale" / "Balance"
- `menu.grain_assistant` - "Grain Assistant" / "Assistant Malts"
- `menu.hop_assistant` - "Hop Assistant" / "Assistant Houblons"
- `menu.keg_filler` - "Keg Filler" / "Remplisseur de Fûts"
- `settings.title` - "Settings" / "Paramètres"
- `settings.language` - "Language" / "Langue"
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
        'ready': 'Bereit',
        'error': 'Fehler',
        # ... translate all keys
    },
    'scale': {
        'tare_ready': 'Zum Tarieren drücken',
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
    ('fr', 'Français'),
    ('de', 'Deutsch'),  # ← Add this
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
# → [('en', 'English'), ('fr', 'Français')]
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

# Test FR
i18n = I18n('fr')
assert i18n.t('scale.tare_ready') == 'Appuyer pour tarer'

# Test with arguments
assert i18n.t('grain.target', 500) == 'Cible : 500g'
assert i18n.t('keg.filling_progress', percent=75) == 'Rempli : 75%'
```

---

## 🎨 UI Considerations

### Text Length

Translations can be longer:

| Language | Text | Length |
|--------|-------|----------|
| 🇬🇧 EN | "Press to tare" | 14 chars |
| 🇫🇷 FR | "Appuyer pour tarer" | 18 chars (+28%) |
| 🇩🇪 DE | "Zum Tarieren drücken" | 20 chars (+43%) |

**Recommendation:** Allow 30-40% extra space in labels.

### Fonts

M5Stack Montserrat fonts support:
- ✅ French accents (é, è, ê, à, ç, ô)
- ✅ German characters (ä, ö, ü, ß)
- ✅ Spanish characters (ñ, á, í, ó, ú, ¿, ¡)

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
