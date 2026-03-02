"""
Test standalone du composant SelectableList.

Lancer depuis la console UIFlow2 :
    exec(open('test_selectable_list.py').read())
"""

import gc
import time

import M5
from M5 import *
import m5ui
import lvgl as lv
from hardware import Rotary

from ui.selectable_list import SelectableList

# ---------------------------------------------------------------------------
# Données de démo (sans accents - polices par défaut ASCII uniquement)
# ---------------------------------------------------------------------------
DEMO_SETS = [
    {
        "title": "Selectionner une recette",
        "color": 0xE67E22,
        "items": [
            "Pale Ale classique",
            "IPA houblonnee",
            "Stout irlandaise",
            "Blonde de printemps avec un libellé ultra ultra long",
            "Weizen bavaroise",
            "Porter fumee",
            "Saison belge",
            "Red Ale",
        ],
    },
    {
        "title": "Selectionner un malt",
        "color": 0x8B4513,
        "items": [
            "Pilsner 2-rangs",
            "Munich clair",
            "Vienna",
            "Crystal 20L",
            "Crystal 60L",
            "Chocolate",
            "Black Patent",
            "Carapils",
        ],
    },
    {
        "title": "Selectionner un houblon",
        "color": 0x27AE60,
        "items": [
            "Cascade",
            "Centennial",
            "Citra",
            "Mosaic",
            "Simcoe",
            "Saaz",
            "Hallertau",
            "Fuggles",
        ],
    },
]

# ---------------------------------------------------------------------------
# Init affichage
# ---------------------------------------------------------------------------
page = m5ui.M5Page(bg_c=0x000000)
page.screen_load()

# Encodeur rotatif
encoder = Rotary()
encoder.reset_rotary_value()

# ---------------------------------------------------------------------------
# Construction du composant
# ---------------------------------------------------------------------------
demo_idx = 0
d = DEMO_SETS[demo_idx]

lst = SelectableList(
    parent      = page,
    items       = d["items"],
    title       = d["title"],
    accent_color= d["color"],
)

print("SelectableList cree. Tourner l'encodeur pour naviguer, appuyer pour selectionner.")
print("Apres selection, la liste change de theme (recette -> malt -> houblon -> ...).")

# ---------------------------------------------------------------------------
# Boucle événements
# ---------------------------------------------------------------------------
while True:
    M5.update()

    # --- Encodeur ---
    delta = encoder.get_rotary_value()
    if delta != 0:
        encoder.reset_rotary_value()
        lst.handle_encoder(delta)

    # --- Bouton ---
    if M5.BtnA.isPressed():
        selected = lst.handle_button()
        print("Selection :", selected)

        # Passer au jeu de données suivant
        demo_idx = (demo_idx + 1) % len(DEMO_SETS)
        d = DEMO_SETS[demo_idx]

        lst.cleanup()
        gc.collect()

        lst = SelectableList(
            parent      = page,
            items       = d["items"],
            title       = d["title"],
            accent_color= d["color"],
        )
        encoder.reset_rotary_value()

    time.sleep_ms(20)
