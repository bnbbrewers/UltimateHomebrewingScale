"""
Internationalization (i18n) module for Ultimate Homebrewing Scale
Handles multi-language support with lightweight implementation for MicroPython
"""

class I18n:
    """Simple i18n manager optimized for MicroPython"""
    
    def __init__(self, lang='en'):
        """
        Initialize i18n with specified language
        
        Args:
            lang: Language code ('en', 'fr', etc.)
        """
        self.lang = lang
        self._translations = {}
        self._load_translations()
    
    def _load_translations(self):
        """Load translation module for current language"""
        try:
            # Import the language module (relative import since locales is in same package)
            if self.lang == 'en':
                from .locales.en import TRANSLATIONS
            elif self.lang == 'fr':
                from .locales.fr import TRANSLATIONS
            else:
                # Fallback to English
                from .locales.en import TRANSLATIONS
            
            self._translations = TRANSLATIONS
        except ImportError as e:
            print(f"Warning: Could not load translations for '{self.lang}': {e}")
            # Fallback to English
            try:
                from .locales.en import TRANSLATIONS
                self._translations = TRANSLATIONS
            except ImportError:
                print("Error: No translation files found!")
                self._translations = {}
    
    def t(self, key, *args, **kwargs):
        """
        Translate a key with optional format arguments
        
        Args:
            key: Translation key (e.g., 'scale.tare_ready')
            *args: Positional arguments for format()
            **kwargs: Keyword arguments for format()
        
        Returns:
            Translated string, or key if translation not found
        
        Examples:
            i18n.t('scale.tare_ready')
            i18n.t('grain.remaining', 150)
            i18n.t('keg.filling_progress', percent=75)
        """
        # Navigate nested keys (e.g., 'scale.tare_ready')
        keys = key.split('.')
        value = self._translations
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        
        # If not found, return the key itself
        if value is None:
            print(f"Warning: Translation key '{key}' not found for language '{self.lang}'")
            return key
        
        # Format with arguments if provided
        try:
            if args or kwargs:
                return value.format(*args, **kwargs)
            return value
        except (IndexError, KeyError) as e:
            print(f"Warning: Error formatting translation '{key}': {e}")
            return value
    
    def set_lang(self, lang):
        """
        Change language dynamically
        
        Args:
            lang: New language code
        
        Returns:
            True if successful, False otherwise
        """
        old_lang = self.lang
        self.lang = lang
        self._load_translations()
        
        # Check if translations were loaded
        if not self._translations:
            print(f"Warning: Failed to load language '{lang}', reverting to '{old_lang}'")
            self.lang = old_lang
            self._load_translations()
            return False
        
        return True
    
    def get_lang(self):
        """Get current language code"""
        return self.lang
    
    def get_available_languages(self):
        """
        Get list of available languages
        
        Returns:
            List of tuples (code, name) for each available language
        """
        # This could be made dynamic by scanning the locales directory
        # but for MicroPython, a static list is more efficient
        return [
            ('en', 'English'),
            ('fr', 'Français'),
        ]
