import unittest
import tempfile
import sys
import types
from unittest import mock

from i18n import I18n
from storage import config_registry
from webportal.config_keys import EDITABLE_KEYS, EDITABLE_ORDER
from webportal.setup_portal import SetupPortalService, render_form_html


class _FakeNVS:
    stores = {}
    fail_write = False

    def __init__(self, namespace):
        self._namespace = namespace
        _FakeNVS.stores.setdefault(namespace, {})

    def get_str(self, key):
        return _FakeNVS.stores[self._namespace].get(key, "")

    def set_str(self, key, value):
        if _FakeNVS.fail_write:
            raise OSError("nvs full")
        _FakeNVS.stores[self._namespace][key] = value

    def commit(self):
        if _FakeNVS.fail_write:
            raise OSError("nvs full")


class _FakeEsp32(types.SimpleNamespace):
    pass


class WebPortalKegTests(unittest.TestCase):
    def setUp(self):
        self._previous_esp32 = sys.modules.get("esp32")
        _FakeNVS.stores = {}
        _FakeNVS.fail_write = False
        sys.modules["esp32"] = _FakeEsp32(NVS=_FakeNVS)

    def tearDown(self):
        if self._previous_esp32 is None:
            sys.modules.pop("esp32", None)
        else:
            sys.modules["esp32"] = self._previous_esp32

    def test_hop_tolerance_defaults_to_one_when_missing_from_config(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write('LANGUAGE = "en"\nGRAIN_WEIGHT_TOLERANCE = 10\n')
            path = f.name

        try:
            values = config_registry.load_current_values(config_path=path)
        finally:
            import os

            os.remove(path)

        self.assertEqual(values["HOP_WEIGHT_TOLERANCE"], 1)

    def test_render_form_includes_hop_tolerance_after_grain_tolerance(self):
        html = render_form_html({"LANGUAGE": "fr"}, i18n=I18n("fr"))

        self.assertIn("Tolerance houblon (g)", html)
        self.assertLess(html.index("Tolerance malt (g)"), html.index("Tolerance houblon (g)"))
        self.assertLess(
            EDITABLE_ORDER.index("GRAIN_WEIGHT_TOLERANCE"),
            EDITABLE_ORDER.index("HOP_WEIGHT_TOLERANCE"),
        )
        self.assertEqual(EDITABLE_KEYS["HOP_WEIGHT_TOLERANCE"]["default"], 1)

    def test_keg_spunding_valve_inertia_defaults_to_200_when_missing_from_config(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write('LANGUAGE = "en"\n')
            path = f.name

        try:
            values = config_registry.load_current_values(config_path=path)
        finally:
            import os

            os.remove(path)

        self.assertEqual(values["KEG_SPUNDING_VALVE_INERTIA_ML"], 200)

    def test_load_current_values_migrates_wifi_from_config_to_nvs_and_removes_config_lines(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(
                'LANGUAGE = "en"\n'
                'WIFI_SSID = "sweet_home"\n'
                'WIFI_PASSWORD = "secret"\n'
                'DEBUG = False\n'
            )
            path = f.name

        try:
            values = config_registry.load_current_values(config_path=path)
            with open(path, "r") as f:
                updated = f.read()
        finally:
            import os

            os.remove(path)

        self.assertEqual(values["WIFI_SSID"], "sweet_home")
        self.assertEqual(values["WIFI_PASSWORD"], "secret")
        self.assertEqual(_FakeNVS.stores["uiflow"]["ssid0"], "sweet_home")
        self.assertEqual(_FakeNVS.stores["uiflow"]["pswd0"], "secret")
        self.assertNotIn("WIFI_SSID", updated)
        self.assertNotIn("WIFI_PASSWORD", updated)
        self.assertIn('LANGUAGE = "en"', updated)
        self.assertIn("DEBUG = False", updated)

    def test_load_current_values_keeps_wifi_config_lines_when_nvs_migration_fails(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            original = (
                'LANGUAGE = "en"\n'
                'WIFI_SSID = "sweet_home"\n'
                'WIFI_PASSWORD = "secret"\n'
            )
            f.write(original)
            path = f.name

        try:
            _FakeNVS.fail_write = True
            values = config_registry.load_current_values(config_path=path)
            with open(path, "r") as f:
                updated = f.read()
        finally:
            import os

            os.remove(path)

        self.assertEqual(values["WIFI_SSID"], "sweet_home")
        self.assertEqual(values["WIFI_PASSWORD"], "secret")
        self.assertEqual(updated, original)

    def test_load_current_values_prefers_existing_nvs_over_config_wifi(self):
        _FakeNVS.stores["uiflow"] = {"ssid0": "old_wifi", "pswd0": "old_secret"}
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            original = (
                'LANGUAGE = "en"\n'
                'WIFI_SSID = "sweet_home"\n'
                'WIFI_PASSWORD = "secret"\n'
            )
            f.write(original)
            path = f.name

        try:
            _FakeNVS.fail_write = True
            values = config_registry.load_current_values(config_path=path)
            with open(path, "r") as f:
                updated = f.read()
        finally:
            import os

            os.remove(path)

        self.assertEqual(values["WIFI_SSID"], "old_wifi")
        self.assertEqual(values["WIFI_PASSWORD"], "old_secret")
        self.assertEqual(updated, original)

    def test_save_updates_removes_wifi_lines_after_writing_nvs(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(
                'LANGUAGE = "en"\n'
                'WIFI_SSID = "old_wifi"\n'
                'WIFI_PASSWORD = "old_secret"\n'
                'DEBUG = False\n'
            )
            path = f.name

        try:
            ok, errors = config_registry.save_updates(
                {"WIFI_SSID": "sweet_home", "WIFI_PASSWORD": "secret"},
                config_path=path,
            )
            with open(path, "r") as f:
                updated = f.read()
        finally:
            import os

            os.remove(path)

        self.assertTrue(ok)
        self.assertEqual(errors, {})
        self.assertEqual(_FakeNVS.stores["uiflow"]["ssid0"], "sweet_home")
        self.assertEqual(_FakeNVS.stores["uiflow"]["pswd0"], "secret")
        self.assertNotIn("WIFI_SSID", updated)
        self.assertNotIn("WIFI_PASSWORD", updated)
        self.assertIn('LANGUAGE = "en"', updated)
        self.assertIn("DEBUG = False", updated)

    def test_render_form_includes_keg_spunding_valve_inertia_after_hop_tolerance(self):
        html = render_form_html({"LANGUAGE": "fr"}, i18n=I18n("fr"))

        self.assertIn("Inertie spunding valve (ml)", html)
        self.assertLess(html.index("Tolerance houblon (g)"), html.index("Inertie spunding valve (ml)"))
        self.assertLess(
            EDITABLE_ORDER.index("HOP_WEIGHT_TOLERANCE"),
            EDITABLE_ORDER.index("KEG_SPUNDING_VALVE_INERTIA_ML"),
        )
        self.assertEqual(EDITABLE_KEYS["KEG_SPUNDING_VALVE_INERTIA_ML"]["default"], 200)

    def test_render_form_includes_edit_and_delete_controls_for_kegs(self):
        html = render_form_html(
            {"LANGUAGE": "en"},
            token="abc",
            i18n=I18n("en"),
            kegs=[{"name": "keg0", "empty_weight_g": 4200.0, "max_volume_l": 18.0}],
        )

        self.assertIn("<h4>Kegs</h4>", html)
        self.assertNotIn("action='/kegs/save'", html)
        self.assertIn("name='keg_name_0' value='keg0'", html)
        self.assertIn("name='keg_empty_weight_g_0' value='4200'", html)
        self.assertIn("name='keg_max_volume_l_0' value='18'", html)
        self.assertIn("action='/kegs/delete'", html)
        self.assertIn("name='idx' value='0'", html)
        self.assertIn(">Delete keg0</button>", html)
        self.assertIn("name='k' value='abc'", html)
        self.assertLess(html.index("<h4>Kegs</h4>"), html.index(">Save and reboot</button>"))
        self.assertLess(html.index(">Save and reboot</button>"), html.index(">UPDATE APP</button>"))

    def test_save_updates_keg_edit_fields_before_reboot_response(self):
        service = SetupPortalService(i18n=I18n("en"))
        body = (
            "LANGUAGE=en&"
            "keg_name_0=Corny&"
            "keg_empty_weight_g_0=4210.5&"
            "keg_max_volume_l_0=19.5"
        )
        sent = []

        def capture_send(_client, status_code=200, content_type="text/plain; charset=utf-8", body="", headers=None):
            sent.append((status_code, content_type, body, headers))

        with mock.patch.object(service, "_read_request", return_value=("POST", "/save", {}, body)), mock.patch.object(
            service, "_send", side_effect=capture_send
        ), mock.patch("webportal.setup_portal.config_registry.save_updates", return_value=(True, {})), mock.patch(
            "webportal.setup_portal.keg_registry.load_kegs",
            return_value=[{"name": "keg0", "empty_weight_g": 4200.0, "max_volume_l": 18.0}],
        ), mock.patch("webportal.setup_portal.keg_registry.save_kegs", return_value=True) as save_kegs:
            service._handle_client(object())

        save_kegs.assert_called_once_with(
            "kegs.json",
            [{"name": "Corny", "empty_weight_g": 4210.5, "max_volume_l": 19.5}],
        )
        self.assertEqual(sent[-1][2], "Saved. Please reboot manually.")

    def test_update_channel_replaces_update_branch_in_schema(self):
        self.assertIn("UPDATE_CHANNEL", EDITABLE_KEYS)
        self.assertNotIn("UPDATE_BRANCH", EDITABLE_KEYS)
        self.assertEqual(EDITABLE_KEYS["UPDATE_CHANNEL"]["type"], "enum")
        self.assertEqual(EDITABLE_KEYS["UPDATE_CHANNEL"]["choices"], ["stable", "prerelease"])
        self.assertEqual(EDITABLE_KEYS["UPDATE_CHANNEL"]["default"], "stable")
        self.assertIn("UPDATE_CHANNEL", EDITABLE_ORDER)
        self.assertNotIn("UPDATE_BRANCH", EDITABLE_ORDER)

    def test_render_form_includes_release_channel_selector(self):
        html = render_form_html({"LANGUAGE": "en", "UPDATE_CHANNEL": "prerelease"}, i18n=I18n("en"))

        self.assertIn("Release channel", html)
        self.assertIn("name='UPDATE_CHANNEL'", html)
        self.assertIn("<option value='stable'>Stable</option>", html)
        self.assertIn("<option value='prerelease' selected>Pre-release</option>", html)
        self.assertNotIn("Update branch", html)


if __name__ == "__main__":
    unittest.main()
