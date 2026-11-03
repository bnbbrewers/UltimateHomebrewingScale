"""Small setup fallback independent of LVGL and the full settings renderer."""


def escape(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')


def page(values=None, token='', message='', saved=False):
    values = values or {}
    parts = ["<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             "<title>UHS recovery setup</title><style>body{max-width:30em;margin:24px auto;padding:16px;font:16px system-ui}"
             "label,input,button{display:block;margin:12px 0}input:not([type=checkbox]){box-sizing:border-box;width:100%;padding:10px}"
             "button{padding:12px;width:100%}</style></head><body><h1>UHS recovery setup</h1>"]
    if message:
        parts.append('<p>' + escape(message) + '</p>')
    if saved:
        parts.append('<p>Settings saved. UHS is restarting.</p></body></html>')
        return parts
    parts.append("<p>Minimal setup. Other settings are preserved.</p><form method='post' action='/recovery/save'>")
    if token:
        parts.append("<input type='hidden' name='k' value='{}'>".format(escape(token)))
    for key, label, kind in (('HOSTNAME', 'Hostname', 'text'), ('WIFI_SSID', 'Wi-Fi SSID', 'text'),
                             ('WIFI_PASSWORD', 'Wi-Fi password (empty for open Wi-Fi)', 'password')):
        parts.append("<label>{}<input type='{}' name='{}' value='{}'></label>".format(
            label, kind, key, escape(values.get(key, 'uhs-scale' if key == 'HOSTNAME' else ''))))
    parts.append("<label>Simulate scale (physical relay disabled)<input type='checkbox' name='SIMULATION_ENABLED'{}></label>".format(
        ' checked' if values.get('SIMULATION_ENABLED') else ''))
    parts.append("<button type='submit'>Save and restart</button></form><p><a href='/'>Full settings</a></p></body></html>")
    return parts


def handle(service, client, method, path, query, body, portal):
    form = portal.parse_form_urlencoded(body) if method == 'POST' else {}
    if not service._token_ok(query, form):
        service._send(client, 403, body='Forbidden')
        return
    token = service._token if service._cfg.get('require_token') else ''
    values = portal._current_values()
    status = 200
    if method == 'POST' and path == '/recovery/save':
        from storage import config_registry
        updates = {key: form[key] for key in ('HOSTNAME', 'WIFI_SSID', 'WIFI_PASSWORD') if key in form}
        updates['SIMULATION_ENABLED'] = form.get('SIMULATION_ENABLED', '').lower() in ('on', 'true', '1')
        ok, errors = config_registry.save_updates(updates)
        if ok:
            service._send(client, 200, 'text/html; charset=utf-8', page(saved=True))
            service.reboot_after_response()
            return
        values.update(updates)
        result = page(values, token, str(errors))
        status = 400
    elif method == 'GET' and path == '/recovery':
        result = page(values, token)
    else:
        service._send(client, 404, body='Not found')
        return
    service._send(client, status, 'text/html; charset=utf-8', result)
