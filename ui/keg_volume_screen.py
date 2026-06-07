"""
Keg filler volume confirmation screen.
"""

import m5ui
import lvgl as lv

from .ui_helper import UIHelper

try:
    import config
    _DEBUG = getattr(config, "DEBUG", False)
except Exception:
    _DEBUG = False

if _DEBUG:
    from memory_debug import snapshot as mem_snapshot
else:
    def mem_snapshot(*args, **kwargs):
        return None


class KegVolumeScreen:
    def __init__(self, i18n=None):
        mem_snapshot("keg_volume.init.start", enabled=_DEBUG, collect=True)
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=0x000000)

        self._title_bar, self._title_label = UIHelper.create_title(
            self.page,
            "",
            0x607D8B,
        )

        self._volume_label = m5ui.M5Label(
            "0.0 L",
            x=0,
            y=86,
            text_c=0xFFFFFF,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_24,
            parent=self.page,
        )
        self._volume_label.set_width(240)
        self._volume_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._hint_label = m5ui.M5Label(
            "",
            x=20,
            y=150,
            text_c=0xC7D2FE,
            bg_c=0x000000,
            bg_opa=0,
            font=lv.font_montserrat_14,
            parent=self.page,
        )
        self._hint_label.set_width(200)
        self._hint_label.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)

        self._ok_bg, self._ok_label = UIHelper.create_action_button(self.page)
        mem_snapshot("keg_volume.init.done", enabled=_DEBUG, collect=True)

    def root(self):
        return self.page

    def _t(self, key):
        if self._i18n:
            return self._i18n.t(key)
        return key

    def configure(self, title, volume_l, title_bg_color=0x607D8B):
        UIHelper.set_title(self._title_label, title)
        UIHelper.set_title_color(self._title_bar, title_bg_color)
        self._hint_label.set_text(self._t("keg.volume_hint"))
        UIHelper.set_action_button_visible(
            self._ok_bg,
            self._ok_label,
            True,
            self._t("common.ok"),
        )
        self.set_volume(volume_l)

    def set_volume(self, volume_l):
        self._volume_label.set_text("{:.1f} L".format(volume_l))
