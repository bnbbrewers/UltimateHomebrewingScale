"""Settings screen with QR setup portal entrypoint."""

import m5ui
import lvgl as lv

from .ui_helper import UIHelper


class SettingsScreen:
    def __init__(self, i18n=None):
        self._i18n = i18n
        self.page = m5ui.M5Page(bg_c=0x000000)
        self._accent = 0x7E57C2

        self._title_bar, self._title = UIHelper.create_title(
            self.page,
            self._t("settings.title", "Settings"),
            self._accent,
        )

        self._qr_widget = None
        self._qr_ok = False
        self._qr_diag_printed = False

    def root(self):
        return self.page

    def configure(self, title, status, url, mode="sta", ap_ssid="", ap_password=""):
        # UX request: keep only the title text on screen.
        UIHelper.set_title(self._title, title or self._t("settings.title", "Settings"))
        self._qr_ok = self._render_qr(url)

    def _render_qr(self, payload):
        data = payload or ""
        try:
            self._print_qr_caps_once()
            if self._qr_widget is None:
                self._qr_widget = self._create_qr_widget(size=132)
                if self._qr_widget is None:
                    print("[QR] creation failed (no compatible API)")
                    return False
                self._qr_widget.set_pos(54, 62)

            ok = self._update_qr_data(self._qr_widget, data)
            if not ok:
                print("[QR] update failed for payload len={}".format(len(data)))
            return ok
        except Exception:
            return False

    def _create_qr_widget(self, size):
        dark = lv.color_hex(0x111111)
        light = lv.color_hex(0xFFFFFF)

        # Keep every QR widget in this screen's object tree. Falling back to
        # the active screen would make ScreenManager.root().delete() unable
        # to reclaim the widget reliably.
        parents = (self.page,)

        first_err = None

        # LVGL bindings vary a lot across firmware versions; try common signatures.
        for parent in parents:
            try:
                if hasattr(lv, "qrcode"):
                    return lv.qrcode(parent, size, dark, light)
            except Exception as e:
                if first_err is None:
                    first_err = e
            try:
                if hasattr(lv, "qrcode"):
                    return lv.qrcode(parent, size, 0x111111, 0xFFFFFF)
            except Exception as e:
                if first_err is None:
                    first_err = e
            try:
                if hasattr(lv, "qrcode"):
                    return lv.qrcode(parent, size)
            except Exception as e:
                if first_err is None:
                    first_err = e
            try:
                if hasattr(lv, "qrcode"):
                    return lv.qrcode(parent)
            except Exception as e:
                if first_err is None:
                    first_err = e

        # Fallback for bindings that expose qrcode_create(parent, size, dark, light).
        for parent in parents:
            try:
                if hasattr(lv, "qrcode_create"):
                    return lv.qrcode_create(parent, size, dark, light)
            except Exception as e:
                if first_err is None:
                    first_err = e

        if first_err is not None:
            try:
                print("[QR] create err: {}: {}".format(type(first_err).__name__, first_err))
            except Exception:
                pass
        return None

    @staticmethod
    def _update_qr_data(widget, payload):
        text = payload or ""
        b = text.encode("utf-8")
        try:
            if hasattr(lv, "qrcode_update"):
                # Binding-dependent: str or bytes are both attempted.
                try:
                    lv.qrcode_update(widget, text, len(text))
                except Exception:
                    lv.qrcode_update(widget, b, len(b))
                return True
        except Exception:
            pass
        try:
            widget.update(text, len(text))
            return True
        except Exception:
            pass
        try:
            widget.update(b, len(b))
            return True
        except Exception:
            pass
        try:
            widget.update(b)
            return True
        except Exception:
            pass
        try:
            widget.update(text)
            return True
        except Exception:
            pass
        return False

    def _print_qr_caps_once(self):
        if self._qr_diag_printed:
            return
        self._qr_diag_printed = True
        try:
            print(
                "[QR] caps qrcode={} qrcode_create={} qrcode_update={} qrcode_set_size={} scr_act={} screen_active={}".format(
                    hasattr(lv, "qrcode"),
                    hasattr(lv, "qrcode_create"),
                    hasattr(lv, "qrcode_update"),
                    hasattr(lv, "qrcode_set_size"),
                    hasattr(lv, "scr_act"),
                    hasattr(lv, "screen_active"),
                )
            )
        except Exception:
            pass

    def _t(self, key, fallback):
        if self._i18n is None:
            return fallback
        return self._i18n.t(key)
