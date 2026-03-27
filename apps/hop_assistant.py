"""
Memory-safe hop assistant app (business logic only).
"""

import gc

import config

from .base_app import BaseApp
from ui import screen_ids

_STATE_RECIPE = 1
_STATE_PREP_ACK = 2
_STATE_SELECT_HOP = 3
_STATE_SELECT_STEP = 4
_STATE_WEIGHT = 5
_STATE_HOP_DONE_ACK = 6
_STATE_ALL_DONE_ACK = 7
_COLOR_HOP = 0x388E3C


class HopAssistantApp(BaseApp):
    APP_ID = "hop_assistant"

    def __init__(self, screen_manager, hardware, apis, i18n=None):
        super().__init__(screen_manager, hardware, apis, i18n=i18n)
        self._api = self.apis.get("brewing")
        self._rotary = self.hardware.rotary
        self._scale = self.hardware.scale

        self._select_screen = self.screen_manager.get(screen_ids.SELECT_ITEM)
        self._message_screen = self.screen_manager.get(screen_ids.SIMPLE_MESSAGE)
        self._weigh_screen = self.screen_manager.get(screen_ids.WEIGHT)

        self._state = _STATE_RECIPE
        self._batches = []
        self._batch_idx = 0
        self._batch_id = None
        self._prep_flow_active = False
        self._hop_sessions = []
        self._current_hop_idx = 0
        self._step_idx = 0
        self._target_g = 0
        self._last_in_range = None

    def on_exit(self):
        super().on_exit()
        if config.DEBUG:
            gc.collect()
            print("[MEM] hop.on_exit before_cleanup free={}".format(gc.mem_free()))
        self._batches = []
        self._hop_sessions = []
        self._batch_id = None
        self._prep_flow_active = False
        self._select_screen.set_items([])

    def on_enter(self):
        super().on_enter()
        try:
            import lvgl as lv

            lv.image_cache_drop(None)
        except Exception:
            pass
        gc.collect()
        self._load_batches()

    def tick(self):
        if self._check_return_to_launcher():
            return "launcher"

        if self._state == _STATE_RECIPE:
            self._tick_recipe()
        elif self._state == _STATE_PREP_ACK:
            return self._tick_prep_ack()
        elif self._state == _STATE_SELECT_HOP:
            self._tick_select_hop()
        elif self._state == _STATE_SELECT_STEP:
            self._tick_select_step()
        elif self._state == _STATE_WEIGHT:
            return self._tick_weight()
        elif self._state == _STATE_HOP_DONE_ACK:
            return self._tick_hop_done_ack()
        elif self._state == _STATE_ALL_DONE_ACK:
            return self._tick_all_done_ack()
        return None

    def _flush_lvgl(self):
        try:
            import lvgl as lv

            lv.task_handler()
        except Exception:
            pass

    def _show_loading_message(self, message_key, bar_color=_COLOR_HOP):
        if self._message_screen:
            self._message_screen.configure(
                title=self.t("hop.title"),
                message=self.t(message_key),
                title_bg_color=bar_color,
            )
            self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
            self._flush_lvgl()

    def _show_prepare_ack(self, recipient_count, bar_color=_COLOR_HOP):
        if not self._message_screen:
            return False
        self._message_screen.configure(
            title=self.t("hop.title"),
            message=self.t("hop.prepare_recipients", recipient_count),
            title_bg_color=bar_color,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._flush_lvgl()
        self._prep_flow_active = True
        self._state = _STATE_PREP_ACK
        return True

    def _show_no_hops_ack(self):
        if not self._message_screen:
            return False
        self._message_screen.configure(
            title=self.t("hop.title"),
            message=self.t("hop.no_hops"),
            title_bg_color=_COLOR_HOP,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._flush_lvgl()
        self._prep_flow_active = False
        self._state = _STATE_PREP_ACK
        return True

    def _tick_prep_ack(self):
        if self.hardware.button.wasPressed():
            if self._prep_flow_active and self._batch_id and self._api:
                self._prep_flow_active = False
                self._enter_hop_weighing_flow()
            else:
                return "launcher"
        return None

    def _enter_hop_weighing_flow(self):
        if not self._hop_sessions:
            if self._show_no_hops_ack():
                pass
            else:
                self._state = _STATE_RECIPE
            return
        self._show_hop_select()
        if self._rotary:
            self._rotary.reset_rotary_value()
        if config.DEBUG:
            gc.collect()
            print("[MEM] hop.sessions_ready hops={} free={}".format(
                len(self._hop_sessions), gc.mem_free()))

    def _reload_hop_sessions(self):
        self._hop_sessions = []
        hops = self._api.get_hops(self._batch_id) if self._api else []
        for h in hops:
            steps = []
            for s in h.steps:
                steps.append((s.step_name, float(s.step_amount)))
            if steps:
                self._hop_sessions.append({"name": h.hop_name, "steps": steps})
        hops = []
        gc.collect()

    @staticmethod
    def _format_step_amount_g(amount):
        a = float(amount)
        if abs(a - round(a)) < 0.05:
            return str(int(round(a)))
        t = "{:.1f}".format(a)
        if t.endswith(".0"):
            return t[:-2]
        return t

    def _step_display_line(self, step_name, amount):
        return self.t(
            "hop.step_line",
            step_name,
            self._format_step_amount_g(amount),
        )

    @staticmethod
    def _hop_amount_to_target_g(amount):
        a = float(amount)
        g = int(round(a))
        if g == 0 and a > 0:
            g = int(round(a * 1000))
        return max(0, g)

    def _show_hop_select(self):
        names = []
        for s in self._hop_sessions:
            names.append(s["name"])
        self._current_hop_idx = min(self._current_hop_idx, max(0, len(names) - 1))
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        self._select_screen.configure(
            title=self.t("hop.select_hop"),
            items=names,
            accent_color=_COLOR_HOP,
            selected_index=self._current_hop_idx,
        )
        if self._rotary:
            self._rotary.reset_rotary_value()
        self._state = _STATE_SELECT_HOP

    def _show_step_select(self):
        hop = self._hop_sessions[self._current_hop_idx]
        lines = []
        for sn, amt in hop["steps"]:
            lines.append(self._step_display_line(sn, amt))
        self._step_idx = min(self._step_idx, max(0, len(lines) - 1))
        self.screen_manager.show(screen_ids.SELECT_ITEM)
        self._select_screen.configure(
            title=hop["name"],
            items=lines,
            accent_color=_COLOR_HOP,
            selected_index=self._step_idx,
        )
        if self._rotary:
            self._rotary.reset_rotary_value()
        self._state = _STATE_SELECT_STEP

    def _show_hop_done_ack(self, hop_name):
        if not self._message_screen:
            return False
        self._message_screen.configure(
            title=self.t("hop.title"),
            message=self.t("hop.hop_weighed", hop_name),
            title_bg_color=_COLOR_HOP,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._flush_lvgl()
        self._state = _STATE_HOP_DONE_ACK
        return True

    def _show_all_done_ack(self):
        if not self._message_screen:
            return False
        self._message_screen.configure(
            title=self.t("hop.title"),
            message=self.t("hop.all_hops_weighed"),
            title_bg_color=_COLOR_HOP,
            show_ok_button=True,
        )
        self.screen_manager.show(screen_ids.SIMPLE_MESSAGE)
        self._flush_lvgl()
        self._state = _STATE_ALL_DONE_ACK
        return True

    def _tick_hop_done_ack(self):
        if self.hardware.button.wasPressed():
            if not self._hop_sessions:
                if not self._show_all_done_ack():
                    return "launcher"
            else:
                self._current_hop_idx = 0
                self._step_idx = 0
                self._show_hop_select()
        return None

    def _tick_all_done_ack(self):
        if self.hardware.button.wasPressed():
            return "launcher"
        return None

    def _tick_select_hop(self):
        n = len(self._hop_sessions)
        if not n:
            return
        if self._rotary:
            delta = self._rotary.get_rotary_value()
            if delta:
                self._rotary.reset_rotary_value()
                if delta > 0:
                    self._current_hop_idx += 1
                else:
                    self._current_hop_idx -= 1
                if self._current_hop_idx < 0:
                    self._current_hop_idx = 0
                if self._current_hop_idx >= n:
                    self._current_hop_idx = n - 1
                self._select_screen.set_selected_index(self._current_hop_idx)
        if self.hardware.button.wasPressed():
            self._step_idx = 0
            self._show_step_select()

    def _tick_select_step(self):
        hop = self._hop_sessions[self._current_hop_idx]
        steps = hop["steps"]
        if not steps:
            return
        if self._rotary:
            delta = self._rotary.get_rotary_value()
            if delta:
                self._rotary.reset_rotary_value()
                if delta > 0:
                    self._step_idx += 1
                else:
                    self._step_idx -= 1
                if self._step_idx < 0:
                    self._step_idx = 0
                if self._step_idx >= len(steps):
                    self._step_idx = len(steps) - 1
                self._select_screen.set_selected_index(self._step_idx)
        if self.hardware.button.wasPressed():
            self._start_weighing()

    def _start_weighing(self):
        hop = self._hop_sessions[self._current_hop_idx]
        step = hop["steps"][self._step_idx]
        self._target_g = self._hop_amount_to_target_g(step[1])
        self.screen_manager.show(screen_ids.WEIGHT)
        self._weigh_screen.configure(
            title=hop["name"],
            mode="countdown_g",
            target=self._target_g,
            title_bg_color=_COLOR_HOP,
            tolerance=config.GRAIN_WEIGHT_TOLERANCE,
        )
        self._weigh_screen.set_status(self.t("scale.tare_ready"))
        self._last_in_range = None
        if self._scale:
            self._scale.tare()
        self._state = _STATE_WEIGHT
        if config.DEBUG:
            gc.collect()
            print("[MEM] hop.start_weigh hop={} target={}g free={}".format(
                hop["name"], self._target_g, gc.mem_free()))

    def _tick_weight(self):
        if self._scale is None:
            self._weigh_screen.set_status("Scale not found")
            return
        weight = self._scale.read_weight()
        if weight is None:
            return
        self._weigh_screen.update_from_weight(weight)
        remaining = self._target_g - weight
        tol = config.GRAIN_WEIGHT_TOLERANCE
        in_range = abs(remaining) <= tol
        if in_range != self._last_in_range:
            self._last_in_range = in_range
            if in_range:
                self._weigh_screen.set_status(self.t("common.ok"))
            else:
                self._weigh_screen.set_status("")

        if (in_range or config.DEBUG) and self.hardware.button.wasPressed():
            return self._complete_current_step()
        return None

    def _complete_current_step(self):
        hop = self._hop_sessions[self._current_hop_idx]
        hop_name = hop["name"]
        hop["steps"].pop(self._step_idx)
        gc.collect()
        if config.DEBUG:
            print("[MEM] hop.step_done hop={} remaining_steps={} free={}".format(
                hop_name, len(hop["steps"]), gc.mem_free()))

        if hop["steps"]:
            if self._step_idx >= len(hop["steps"]):
                self._step_idx = len(hop["steps"]) - 1
            self._show_step_select()
            return None

        del self._hop_sessions[self._current_hop_idx]
        if self._current_hop_idx >= len(self._hop_sessions):
            self._current_hop_idx = max(0, len(self._hop_sessions) - 1)
        self._step_idx = 0

        if not self._show_hop_done_ack(hop_name):
            if not self._hop_sessions:
                return "launcher"
            self._current_hop_idx = 0
            self._show_hop_select()
        return None

    def _load_batches(self):
        self._show_loading_message("recipe.loading_recipes")

        self._batches = self._api.get_batches() if self._api else []
        names = []
        for batch in self._batches:
            names.append(batch.name)
        self._batch_idx = 0

        self.screen_manager.show(screen_ids.SELECT_ITEM)
        if names:
            self._select_screen.configure(
                title=self.t("recipe.select_recipe"),
                items=names,
                accent_color=_COLOR_HOP,
                selected_index=0,
            )
        else:
            self._select_screen.configure(
                title=self.t("recipe.no_recipe"),
                items=[],
                accent_color=_COLOR_HOP,
                selected_index=0,
            )

        if self._rotary:
            self._rotary.reset_rotary_value()
        self._state = _STATE_RECIPE
        gc.collect()
        if config.DEBUG:
            print("[MEM] hop.batches_loaded free={}".format(gc.mem_free()))

    def _tick_recipe(self):
        if not self._batches:
            return
        if self._rotary:
            delta = self._rotary.get_rotary_value()
            if delta:
                self._rotary.reset_rotary_value()
                if delta > 0:
                    self._batch_idx += 1
                else:
                    self._batch_idx -= 1
                if self._batch_idx < 0:
                    self._batch_idx = 0
                if self._batch_idx >= len(self._batches):
                    self._batch_idx = len(self._batches) - 1
                self._select_screen.set_selected_index(self._batch_idx)
        if self.hardware.button.wasPressed():
            self._load_hops()

    def _load_hops(self):
        self._show_loading_message("hop.loading_hops")

        self._batch_id = self._batches[self._batch_idx].batch_id
        self._batches = []
        gc.collect()

        if self._api:
            hops = self._api.get_hops(self._batch_id)
        else:
            hops = []

        self._hop_sessions = []
        recipient_count = 0
        for h in hops:
            steps = []
            for s in h.steps:
                steps.append((s.step_name, float(s.step_amount)))
                recipient_count += 1
            if steps:
                self._hop_sessions.append({"name": h.hop_name, "steps": steps})
        hops = []
        gc.collect()

        if recipient_count > 0:
            if not self._show_prepare_ack(recipient_count):
                self.screen_manager.show(screen_ids.SELECT_ITEM)
                self._select_screen.configure(
                    title=self.t("hop.prepare_recipients", recipient_count),
                    items=[],
                    accent_color=_COLOR_HOP,
                    selected_index=0,
                )
                self._state = _STATE_RECIPE
        elif self._show_no_hops_ack():
            pass
        else:
            self.screen_manager.show(screen_ids.SELECT_ITEM)
            self._select_screen.configure(
                title=self.t("hop.no_hops"),
                items=[],
                accent_color=_COLOR_HOP,
                selected_index=0,
            )
            self._state = _STATE_RECIPE

        if self._rotary:
            self._rotary.reset_rotary_value()
        if config.DEBUG:
            gc.collect()
            print("[MEM] hop.hops_loaded recipients={} free={}".format(
                recipient_count, gc.mem_free()))
