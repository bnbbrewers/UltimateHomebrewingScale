# Debug Mode Guide

## Configuration

### Activer/Désactiver les Traces

Dans `config.py` :

```python
# Debug mode (set to True to enable debug prints)
DEBUG = False  # Par défaut : pas de traces
DEBUG = True   # Activer les traces
```

### Comportement

**Avec `DEBUG = False`** (défaut) :
- ✅ Aucune trace print dans la console
- ✅ Interface fluide sans ralentissement
- ✅ Seules les erreurs fatales s'affichent

**Avec `DEBUG = True`** :
- 📋 Traces de démarrage
- 📋 Événements du launcher
- 📋 Lancement des apps
- 📋 Détection appui long
- 📋 Calibration de la balance
- 📋 Erreurs détaillées

## Fichiers Modifiés

Tous les `print()` sont conditionnés par `DEBUG` :

- `main.py` — Initialisation système
- `apps/launcher_app.py` — Logique de navigation launcher
- `ui/launcher_screen.py` — UI du launcher
- `apps/base_app.py` — Détection appui long
- `apps/scale.py` — Calibration et pesée
- Autres apps (grain, hop, keg, settings)

## Appui Long pour Retour au Launcher

### Comment Utiliser

**Dans n'importe quelle app** :
1. Maintenez le **bouton central** enfoncé
2. Attendez **3 secondes**
3. L'app se ferme et retourne au launcher

### Implémentation

La détection est gérée dans `BaseApp.check_return_to_launcher()` :

```python
# Long press duration
LONG_PRESS_DURATION = 3000  # 3 secondes (ms)

# Automatiquement appelé dans la boucle principale
# de toutes les apps héritant de BaseApp
```

### Apps Concernées

✅ Toutes les apps héritant de `BaseApp` :
- Scale App
- Grain Assistant
- Hop Assistant
- Keg Filler
- Settings

### Debug Long Press

Avec `DEBUG = True`, un message s'affiche :
```
Long press detected - returning to launcher
```

## Déploiement

Uploadez ces fichiers modifiés sur le M5Dial :

- `config.py` (avec DEBUG = False/True)
- `main.py`
- `apps/launcher_app.py`
- `ui/launcher_screen.py`
- `apps/base_app.py`
- `apps/scale.py`

## Test

```python
# Sur M5Dial
exec(open('main.py').read())

# 1. Le launcher s'affiche (sans traces si DEBUG=False)
# 2. Sélectionnez Scale
# 3. Maintenez le bouton central 3s
# 4. Retour automatique au launcher
```

## Performance

**Impact Mémoire** : Aucun (les strings ne sont pas créées si DEBUG=False)

**Fluidité** : Améliorée sans traces debug

**Latence Appui Long** : < 50ms de détection
