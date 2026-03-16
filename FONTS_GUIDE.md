# Guide des Fonts sur M5Dial

## Fonts Disponibles dans UIFlow2

Les fonts Montserrat disponibles dans le firmware UIFlow2 sont :

### ✅ Tailles Disponibles
- `lv.font_montserrat_10`
- `lv.font_montserrat_12`
- `lv.font_montserrat_14`
- `lv.font_montserrat_16`
- `lv.font_montserrat_18`
- `lv.font_montserrat_20`
- `lv.font_montserrat_22`
- `lv.font_montserrat_24`
- `lv.font_montserrat_26`
- `lv.font_montserrat_28`

### ❌ Tailles NON Disponibles
- `lv.font_montserrat_32` ❌
- `lv.font_montserrat_48` ❌
- Tailles > 28 ❌

## Utilisation Recommandée

### Fonction de Fallback

Utilisez une fonction de fallback pour mapper les tailles non disponibles :

```python
def _get_font(preferred_size=16):
    """Get available LVGL font with fallbacks"""
    size_map = {
        48: 28,  # Large → Max disponible
        32: 24,  # Medium → 24
        24: 24,
        16: 16,
        14: 14,
        12: 12,
    }
    
    mapped_size = size_map.get(preferred_size, 16)
    font_name = f"font_montserrat_{mapped_size}"
    
    if hasattr(lv, font_name):
        return getattr(lv, font_name)
    
    # Fallback chain
    for size in [24, 20, 16, 14, 12]:
        font_name = f"font_montserrat_{size}"
        if hasattr(lv, font_name):
            return getattr(lv, font_name)
    
    return None
```

### Utilisation

```python
# Dans une app
label = m5ui.M5Label(
    "Mon Texte",
    x=10, y=10,
    font=_get_font(32),  # Demandera 32, obtiendra 24 ou 28
    parent=self.page
)
```

## Ajouter des Fonts Custom (Avancé)

⚠️ **Complexe** : Nécessite de recompiler le firmware UIFlow2

### Option 1 : LVGL Font Converter (Web)

1. **Préparer la font** :
   - Télécharger une font TrueType (.ttf)
   - Ex: [Google Fonts](https://fonts.google.com/)

2. **Convertir avec LVGL Online Converter** :
   - Aller sur : https://lvgl.io/tools/fontconverter
   - Uploader votre font .ttf
   - Sélectionner taille (ex: 32px)
   - Sélectionner format : **C array**
   - Sélectionner BPP : **4 bits** (bon compromis)
   - Sélectionner range : **Basic Latin** (ou personnalisé)
   - Cliquer **Convert**
   - Télécharger le fichier `.c`

3. **Intégrer dans UIFlow2** :
   ```c
   // Dans le firmware UIFlow2
   #include "my_font_32.c"
   
   // Enregistrer dans LVGL
   lv_font_t *my_font_32 = &lv_font_my_font_32;
   ```

4. **Recompiler UIFlow2** :
   - Compiler le firmware modifié
   - Flasher sur M5Dial
   - ⚠️ Processus complexe, documentation M5Stack requise

### Option 2 : Fonts Binary (MicroPython)

**Pas supporté directement** : LVGL MicroPython ne supporte pas facilement le chargement dynamique de fonts binaires.

### Option 3 : Utiliser des Images

Pour des textes très grands, créer des images PNG :

```python
# Créer des chiffres en images (0-9)
images = {
    '0': '/flash/assets/fonts/digit_0.png',
    '1': '/flash/assets/fonts/digit_1.png',
    # ...
}

# Afficher
for char in str(weight):
    img = m5ui.M5Image(images[char], x=x, y=y, parent=page)
    x += 30  # Espacement
```

**Avantages** :
- ✅ Très grande taille possible
- ✅ Styles personnalisés (couleurs, effets)

**Inconvénients** :
- ❌ Mémoire (1 image par caractère)
- ❌ Complexe à animer

## Recommandations

### Pour l'Ultimate Homebrewing Scale

1. **Utiliser les fonts disponibles** (10-28) avec fallback ✅
2. **Mapper 32 → 24 ou 28** (acceptable pour la lisibilité) ✅
3. **Ne pas recompiler le firmware** (trop complexe) ❌
4. **Alternative pour très gros texte** : Utiliser plusieurs labels ou images

### Exemple de Mapping dans le Projet

Le projet utilise déjà cette stratégie dans :
- `apps/scale.py` → `_get_font()`
- `ui/weight_screen.py` → fallback intégré

### Tailles Utilisées

| Usage | Taille Demandée | Taille Obtenue | Font |
|-------|-----------------|----------------|------|
| Titre | 16 | 16 | `lv.font_montserrat_16` |
| Poids principal | 32 | 24-28 | `lv.font_montserrat_24/28` |
| Statut | 14 | 14 | `lv.font_montserrat_14` |
| Petit texte | 12 | 12 | `lv.font_montserrat_12` |

## Test des Fonts Disponibles

Script pour lister toutes les fonts disponibles :

```python
import lvgl as lv

# Liste toutes les fonts Montserrat
for size in range(8, 60, 2):
    font_name = f"font_montserrat_{size}"
    if hasattr(lv, font_name):
        print(f"✅ {font_name}")
    else:
        print(f"❌ {font_name}")
```

## Liens Utiles

- **LVGL Font Converter** : https://lvgl.io/tools/fontconverter
- **LVGL Docs Fonts** : https://docs.lvgl.io/master/overview/font.html
- **Google Fonts** : https://fonts.google.com/
- **UIFlow2 Docs** : https://docs.m5stack.com/

## Résumé

Pour Ultimate Homebrewing Scale :
- ✅ **Utiliser fonts 10-28** avec fallback
- ✅ **Mapper 32+ vers 24-28**
- ❌ **Ne pas essayer d'ajouter des fonts custom**
- 💡 **Si vraiment nécessaire** : Utiliser images pour gros textes
