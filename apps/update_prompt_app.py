"""
Hidden app: confirm the update the launcher announced.

The launcher opens it from its Update entry, which only exists once
updater.update_notice found a newer release. "Yes" reuses the boot update
the web portal starts: raise the NVS flag and reboot, so the install runs on
the fresh heap it was sized for.
"""

from apps.base_app import BaseApp
from ui import screen_ids

PROMPT_COLOR = 0xD32F2F
_YES = 0
_CHOICES = 2


class UpdatePromptApp(BaseApp):
    APP_ID = "update_prompt_app"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._select_screen = None
        self._index = _YES

    def on_enter(self):
        super().on_enter()
        self._index = _YES
        self._select_screen = self.screen_manager.get(screen_ids.SELECT_ITEM)
        self._select_screen.configure(
            title=self.t("update_prompt.title"),
            items=[self.t("update_prompt.yes"), self.t("update_prompt.no")],
            accent_color=PROMPT_COLOR,
            selected_index=self._index,
        )
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        rotary = self.hardware.rotary
        if rotary:
            rotary.reset()

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"
        index, changed = self._rotary_navigate(self._index, _CHOICES)
        if changed:
            self._index = index
            self._select_screen.set_selected_index(index)
        button = self.hardware.button
        if button and button.was_short_pressed():
            if self._index == _YES:
                return self._start_update()
            return "launcher"
        return None

    def _start_update(self):
        try:
            from updater.boot import set_update_requested

            set_update_requested(True)
        except Exception as e:
            print("[update_prompt] update flag write failed:", e)
            return "launcher"
        import machine

        machine.reset()
        return None
