# Guide des Fonts sur M5Dial

## Fonts Disponibles dans UIFlow2

Les fonts Montserrat disponibles dans notre firmware UIFlow2 sont :

### ✅ Tailles Disponibles
- `lv.font_montserrat_14`
- `lv.font_montserrat_16`
- `lv.font_montserrat_24`

### ✅ Font custom importée
- `S:/flash/assets/montserrat_40.bin` via `lv.binfont_create(...)`
- Utilisée pour le poids principal dans `ui/weight_screen.py`
- Font partielle : ne pas l'utiliser comme police générale

### ❌ Tailles NON Disponibles
- `lv.font_montserrat_10` ❌
- `lv.font_montserrat_12` ❌
- `lv.font_montserrat_18` ❌
- `lv.font_montserrat_20` ❌
- `lv.font_montserrat_22` ❌
- `lv.font_montserrat_26` ❌
- `lv.font_montserrat_28` ❌
- `lv.font_montserrat_32` ❌
- `lv.font_montserrat_48` ❌
- Tailles autres que 14, 16 et 24 ❌

## Utilisation Recommandée

### Fonction de Fallback

Utilisez une fonction de fallback pour mapper les tailles non disponibles :

```python
def _get_font(preferred_size=16):
    """Get available LVGL font with fallbacks"""
    size_map = {
        48: 24,  # Large -> max firmware disponible
        32: 24,  # Medium -> 24
        24: 24,
        16: 16,
        14: 14,
        12: 14,
        10: 14,
    }
    
    mapped_size = size_map.get(preferred_size, 16)
    font_name = f"font_montserrat_{mapped_size}"
    
    if hasattr(lv, font_name):
        return getattr(lv, font_name)
    
    # Fallback chain
    for size in [24, 16, 14]:
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
    font=_get_font(32),  # Demandera 32, obtiendra 24
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

**Supporté dans ce projet pour un cas ciblé** : `ui/weight_screen.py` charge
`S:/flash/assets/montserrat_40.bin` avec `lv.binfont_create(...)`.

Cette font est partielle et réservée au poids principal. Pour les libellés,
titres et statuts, rester sur les fonts firmware `14`, `16` et `24`.

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

1. **Utiliser les fonts firmware disponibles** (14, 16, 24) avec fallback ✅
2. **Mapper 32+ → 24** pour les textes standards ✅
3. **Ne pas recompiler le firmware** (trop complexe) ❌
4. **Pour le poids principal** : utiliser la font custom partielle 40 déjà importée
5. **Alternative pour très gros texte hors poids** : Utiliser plusieurs labels ou images

### Exemple de Mapping dans le Projet

Le projet utilise déjà cette stratégie dans :
- `apps/scale_app.py` → `_get_font()`
- `ui/weight_screen.py` → fallback intégré

### Tailles Utilisées

| Usage | Taille Demandée | Taille Obtenue | Font |
|-------|-----------------|----------------|------|
| Titre | 16 | 16 | `lv.font_montserrat_16` |
| Poids principal | 40 | 40 partielle | `S:/flash/assets/montserrat_40.bin` |
| Grand texte standard | 32 | 24 | `lv.font_montserrat_24` |
| Statut | 14 | 14 | `lv.font_montserrat_14` |
| Petit texte | 12 | 14 | `lv.font_montserrat_14` |

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
- ✅ **Utiliser fonts firmware 14, 16 et 24** avec fallback
- ✅ **Utiliser la font custom partielle 40 uniquement pour le poids principal**
- ✅ **Mapper 32+ vers 24** pour les textes standards
- ❌ **Ne pas essayer d'ajouter des fonts custom générales**
- 💡 **Si vraiment nécessaire** : Utiliser images pour gros textes
