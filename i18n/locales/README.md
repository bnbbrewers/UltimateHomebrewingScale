# Locales - Translation Files

This directory contains translation files for the Ultimate Homebrewing Scale application.

## Structure

Each language has its own Python file (e.g., `en.py`, `fr.py`) containing a `TRANSLATIONS` dictionary with all translated strings organized by feature.

## Available Languages

- **en.py** - English (default)
- **fr.py** - Français (French)

## Adding a New Language

To add a new language:

1. **Create a new file** in this directory named `{language_code}.py` (e.g., `de.py` for German, `es.py` for Spanish)

2. **Copy the structure** from `en.py` and translate all strings:

```python
"""
German translations for Ultimate Homebrewing Scale
"""

TRANSLATIONS = {
    'common': {
        'ready': 'Bereit',
        'error': 'Fehler',
        # ... etc
    },
    # ... rest of translations
}
```

3. **Update `i18n.py`** to include the new language:

```python
# In the _load_translations() method, add:
elif self.lang == 'de':
    from locales.de import TRANSLATIONS

# In the get_available_languages() method, add:
('de', 'Deutsch'),
```

4. **Test** your translations by setting `LANGUAGE = 'de'` in `config.py`

## Translation Key Structure

Translations are organized hierarchically by feature:

```
{feature}.{component}.{string_name}
```

Examples:
- `scale.tare_ready` - "Press to tare" button in scale mode
- `grain.remaining` - "Remaining: Xg" text in grain assistant
- `common.error` - Generic error message used everywhere

## Format Strings

Use Python format syntax for dynamic values:

```python
'target': 'Target: {0}g',              # Positional argument
'filling_progress': 'Filled: {percent}%',  # Named argument
```

Usage in code:
```python
i18n.t('grain.target', 500)                    # "Target: 500g"
i18n.t('keg.filling_progress', percent=75)     # "Filled: 75%"
```

## Best Practices

1. **Keep keys consistent** across all language files
2. **Use descriptive key names** that indicate where the string is used
3. **Test text length** - some languages are longer than English
4. **Consider context** - the same English word might translate differently depending on usage
5. **Keep formatting consistent** - maintain the same format placeholders across languages

## Text Length Considerations

When translating, be aware that:
- German and French translations are typically 20-30% longer than English
- UI labels should be tested to ensure they fit in the allocated space
- Consider using abbreviations if necessary for very small displays

## Contributing Translations

If you'd like to contribute a translation:

1. Fork the repository
2. Add your language file following the structure above
3. Test it on actual hardware if possible
4. Submit a pull request with your translation

Thank you for helping make this project accessible to more brewers worldwide! 🍺
