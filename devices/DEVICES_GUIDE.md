# Devices Module Guide

## Overview

Les modules de gestion des périphériques hardware ont été extraits dans `devices/`.

**Devices disponibles** :
- **Scale** : Balance calibrée avec tare (`devices/scale.py`)
- **Button** : Gestion centralisée appui court / appui long (`devices/button.py`)
- **Relay** : Contrôle de relais (à venir)

## Architecture

```
devices/
├── __init__.py           # Exports CalibratedScale, etc.
├── button.py             # ButtonDevice (short/long press)
├── scale.py              # CalibratedScale class
└── relay.py              # RelayController class (futur)
```

## Utilisation

### Import

```python
from devices.scale import CalibratedScale

# Ou (via __init__.py)
from devices import CalibratedScale
```

### Initialisation

```python
# Basic usage
scale = CalibratedScale()

# With custom calibration file
scale = CalibratedScale(calibration_file="custom_cal.json")
```

### Lecture du Poids

```python
# Read weight with moving average
weight = scale.read_weight()  # Returns weight in grams (float)

if weight is not None:
    print(f"Current weight: {weight:.1f}g")
```

### Tare (Mise à Zéro)

```python
# Tare the scale
success = scale.tare()

if success:
    print("Tare completed")
```

### Vérifier la Stabilité

```python
# Check if reading is stable
if scale.is_stable(threshold=5.0, samples=5):
    print("Weight is stable")
```

### Informations de Calibration

```python
info = scale.get_calibration_info()
print(f"Points: {info['num_points']}")
print(f"Range: {info['min_weight']}g - {info['max_weight']}g")
print(f"Tare: {info['tare_offset']}g")
```

## API Reference

### CalibratedScale Class

#### Methods

**`__init__(calibration_file=None)`**
- Initialise la balance avec calibration
- `calibration_file` : Chemin vers fichier JSON (optionnel)

**`read_weight() -> float | None`**
- Lit le poids actuel avec moyenne mobile
- Retourne poids en grammes, ou `None` en cas d'erreur

**`read_raw_adc() -> int | None`**
- Lit la valeur ADC brute du capteur
- Retourne valeur ADC, ou `None` en cas d'erreur

**`tare() -> bool`**
- Effectue la mise à zéro (tare)
- Retourne `True` si succès, `False` sinon

**`is_stable(threshold=5.0, samples=5) -> bool`**
- Vérifie si la lecture est stable
- `threshold` : Variation maximale tolérée (grammes)
- `samples` : Nombre d'échantillons à vérifier

**`get_calibration_info() -> dict`**
- Retourne infos sur la calibration
- Dict : `num_points`, `min_weight`, `max_weight`, `tare_offset`

## Apps Utilisant CalibratedScale

### ✅ Scale App (apps/scale_app.py)
Affichage simple du poids avec tare

### ✅ Grain Assistant (apps/malt_app.py)
Pesée de malt avec comparaison à un poids cible

### ✅ Hop Assistant (apps/hop_app.py)
Pesée de houblon avec comparaison à un poids cible

### ✅ Keg Filler (apps/keg_filler_app.py)
Remplissage de fût avec conversion poids → volume

## Configuration

### Fichier: `scale_calibration.json`

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

### Constantes (devices/scale.py)

```python
CALIBRATION_FILE = "scale_calibration.json"
I2C_ADDRESS = 0x26
SCL_PIN = 15
SDA_PIN = 13
MOVING_AVERAGE_SIZE = 10  # Samples for smoothing
```

## Exemple Complet

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
    weight = scale.read_weight()
    
    if weight is not None:
        print(f"Weight: {weight:.1f}g")
        
        # Check stability
        if scale.is_stable():
            print("  (stable)")
    
    time.sleep(0.5)
```

## Avantages de la Séparation

1. **✅ Réutilisabilité** : Même code dans toutes les apps
2. **✅ Maintenabilité** : Un seul endroit pour les corrections
3. **✅ Testabilité** : Module hardware isolé
4. **✅ Clarté** : Séparation UI / logique métier
5. **✅ Performance** : Une seule instance partageable

## Debug Mode

Le mode DEBUG de `config.py` s'applique aussi à `CalibratedScale` :

```python
# config.py
DEBUG = True  # Active les traces de la balance
```

Traces affichées :
- Initialisation du capteur
- Chargement de la calibration
- Lecture ADC/poids (throttled)
- Opérations de tare

## Déploiement

Uploadez ces fichiers sur le M5Dial :

```
devices/
├── __init__.py
└── scale.py

apps/
├── scale.py          (modifié)
├── malt_app.py (modifié)
├── hop_app.py  (modifié)
└── keg_filler_app.py (modifié)
```

## Test

```python
# Sur M5Dial
exec(open('main.py').read())

# 1. Sélectionnez Scale App → fonctionne
# 2. Sélectionnez Grain Assistant → utilise même balance
# 3. Retour launcher (appui long 3s)
# 4. Sélectionnez Hop Assistant → balance déjà initialisée
```

## Performance

- **Mémoire** : Classe partagée entre apps
- **CPU** : Moyenne mobile optimisée
- **Latence** : ~50ms par lecture
- **Précision** : Interpolation linéaire multi-points

## Troubleshooting

**Erreur "Weight Unit initialization failed"** :
- Vérifier câblage I2C
- Vérifier pins SCL/SDA (15/13)
- Vérifier adresse I2C (0x26)

**Erreur "Calibration file not found"** :
- Uploader `scale_calibration.json`
- Ou lancer `ScaleCalibration/ScaleCalibrationWizard.py`

**Poids instable** :
- Augmenter `MOVING_AVERAGE_SIZE`
- Utiliser `is_stable()` avant lecture
- Éviter vibrations

**Poids incorrect** :
- Re-calibrer avec wizard
- Vérifier points de calibration
- Tester avec poids connus
