"""
Liquid unit conversions shared by the keg flow and the weight screen.

Dependency-light on purpose: apps must not import ui.weight_screen, which
pulls in lvgl/m5ui at module level and is evicted from sys.modules between
apps. This module imports nothing and is never evicted.
"""

# Beer at pitching temperature. One value, used both to compute the fill
# target in grams and to render that weight back as litres.
LIQUID_DENSITY = 1.005


def volume_l_to_weight_g(volume_l):
    return float(volume_l) * 1000.0 * LIQUID_DENSITY
