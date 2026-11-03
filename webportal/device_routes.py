"""Settings-only Wi-Fi diagnostics and live simulated-scale controls."""
import json


def handle(service, client, method, path, query, body, portal):
    if not path.startswith(('/wifi/', '/simulation/')):
        return False
    form = portal.parse_form_urlencoded(body) if method == 'POST' else {}
    def answer(status, data):
        service._send(client, status, 'application/json', json.dumps(data))
    if not service._token_ok(query, form):
        answer(403, {'error': 'Forbidden'})
        return True
    try:
        if method == 'GET' and path == '/wifi/status':
            from netcore.wifi_setup import station, link_status
            data = service._wifi_test.status() if service._wifi_test else link_status(station())
            data['hostname'] = portal._current_values().get('HOSTNAME', 'uhs-scale')
            answer(200, data)
        elif method == 'POST' and path == '/wifi/scan':
            if service._wifi_test and service._wifi_test.running:
                answer(409, {'error': 'Wait until the connection test finishes'})
            else:
                import runtime_watchdog
                from netcore.wifi_setup import scan_networks
                runtime_watchdog.feed()
                networks = scan_networks()
                runtime_watchdog.feed()
                answer(200, {'networks': networks})
        elif method == 'POST' and path == '/wifi/test':
            if service._wifi_test and service._wifi_test.running:
                answer(409, {'error': 'A connection test is already running'})
                return True
            from storage.config_registry import validate_payload
            updates = {key: form.get(key, '') for key in ('WIFI_SSID', 'WIFI_PASSWORD')}
            ok, values, errors = validate_payload(updates)
            if not ok or not values.get('WIFI_SSID'):
                answer(400, {'error': errors or 'Enter an SSID'})
                return True
            from netcore.wifi_setup import station, ConnectionTest
            current = portal._current_values()
            # Bring up recovery access before disconnecting the current STA link.
            ap_ip = service._ensure_ap()
            if service._ap is None or not service._ap.active():
                answer(503, {"error": "Recovery access point unavailable; connection test was not started"})
                return True
            service._wifi_test = ConnectionTest(station(),
                (current.get('WIFI_SSID', ''), current.get('WIFI_PASSWORD', '')), service._wifi)
            service._wifi_test.start(values['WIFI_SSID'], values['WIFI_PASSWORD'])
            answer(200, {'testing': service._wifi_test.running, 'setupSsid': service._cfg.get('ap_ssid'),
                         'setupUrl': portal.build_portal_url(ap_ip=ap_ip, port=portal.PORTAL_HTTP_PORT),
                         'message': 'Test started; credentials are not saved. Use Save after success.'})
        elif method == 'GET' and path == '/simulation/status':
            scale = service._scale
            enabled = bool(getattr(scale, 'simulated', False))
            answer(200, {'enabled': enabled,
                         'weightG': scale.read_weight_filtered() if enabled else None,
                         'targetG': scale.target if enabled else None,
                         'stable': scale.is_stable() if enabled else False})
        elif method == 'POST' and path == '/simulation/weight':
            scale = service._scale
            if not getattr(scale, 'simulated', False):
                answer(400, {'error': 'Enable simulation, save and restart first'})
                return True
            if form.get('action') == 'tare':
                scale.tare()
            elif form.get('action') == 'target':
                scale.set_target(form.get('weight', ''))
            else:
                scale.set_weight(form.get('weight', ''))
            answer(200, {'ok': True, 'weightG': scale.read_weight_filtered()})
        else:
            answer(404, {'error': 'Unknown settings endpoint'})
    except ValueError:
        answer(400, {'error': 'Invalid simulation value or connection test already running'})
    except Exception:
        # Never return raw Wi-Fi driver errors containing the supplied password.
        answer(500, {'error': 'Device operation failed; check Wi-Fi availability and retry'})
    return True
