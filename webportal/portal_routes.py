"""HTTP routes for the setup portal.

This module is deliberately imported only after the Settings screen has been
released.  Keeping request handling out of setup_portal_service reduces the
allocation required while entering Settings on MicroPython.
"""


def handle_request(service, client, method, target, body):
    # Import lazily: this file must not be loaded while Settings is starting.
    import webportal.setup_portal_service as portal

    path, query = portal._split_target(target)
    send = service._send

    if path == "/health":
        send(client, 200, "application/json", '{"ok":true}')
        return

    if method == "GET" and path == "/diag":
        try:
            size = int(query.get("bytes", "0") or "0")
        except Exception:
            size = 0
        if size > 0:
            send(client, 200, "text/plain; charset=utf-8", "D" * min(size, 4096))
            return
        try:
            html_size = int(query.get("html", "0") or "0")
        except Exception:
            html_size = 0
        if html_size > 0:
            html_size = min(html_size, 4096)
            prefix = "<!doctype html><html><body><pre>"
            suffix = "</pre></body></html>"
            fill_len = max(0, html_size - len(prefix) - len(suffix))
            send(client, 200, "text/html; charset=utf-8", prefix + ("H" * fill_len) + suffix)
            return
        if query.get("formtext") == "1":
            send(client, 200, "text/plain; charset=utf-8", portal.render_minimal_form_html(portal._current_values(), i18n=service._i18n))
            return
        send(client, 200, "text/html; charset=utf-8", "<!doctype html><html><body>UHS diag OK</body></html>")
        return

    if method == "GET" and path == "/favicon.ico":
        send(client, 404, body="")
        return

    if method == "GET" and path == "/kegs":
        send(client, 200, "text/html; charset=utf-8", portal.render_kegs_html(portal._load_kegs(), i18n=service._i18n))
        return

    if method == "GET" and path == "/":
        if not service._token_ok(query, {}):
            send(client, 403, body="Forbidden")
            return
        send(
            client,
            200,
            "text/html; charset=utf-8",
            portal.render_minimal_form_html(
                portal._current_values(),
                kegs=portal._load_kegs(),
                i18n=service._i18n,
            ),
        )
        return

    if method == "POST" and path == "/save":
        form = portal.parse_form_urlencoded(body)
        if not service._token_ok(query, form):
            send(client, 403, body="Forbidden")
            return
        updates = {}
        for key, _label, typ, _choices in portal._EDITABLE_FIELDS:
            if typ == "checkbox":
                updates[key] = key in form and str(form.get(key, "")).lower() in ("1", "true", "on", "yes")
            elif key in form:
                updates[key] = form.get(key)
        kegs = portal._load_kegs()
        updated_kegs = portal._kegs_from_form(kegs, form)
        if updated_kegs is None:
            send(client, 400, "text/html; charset=utf-8", portal.render_minimal_form_html(dict(portal._current_values(), **updates), error="Invalid fields", kegs=kegs, i18n=service._i18n))
            return
        try:
            from storage import config_registry
            ok, errors = config_registry.save_updates(updates)
        except Exception as e:
            ok, errors = False, str(e)
        if not ok:
            send(client, 400, "text/html; charset=utf-8", portal.render_minimal_form_html(dict(portal._current_values(), **updates), error=errors, kegs=updated_kegs, i18n=service._i18n))
            return
        if updated_kegs is not kegs:
            try:
                from storage import keg_registry
                kegs_saved = keg_registry.save_kegs(keg_registry.KEG_FILE, updated_kegs)
            except Exception:
                kegs_saved = False
            if not kegs_saved:
                send(client, 500, "text/html; charset=utf-8", "Keg save error")
                return
        send(client, 200, "text/html; charset=utf-8", "Saved. Rebooting...")
        try:
            import machine
            portal.time.sleep_ms(200)
            machine.reset()
        except Exception:
            pass
        return

    if method == "POST" and path == "/kegs/delete":
        form = portal.parse_form_urlencoded(body)
        if not service._token_ok(query, form):
            send(client, 403, body="Forbidden")
            return
        try:
            from storage import keg_registry
            kegs = keg_registry.load_kegs()
            updated = keg_registry.delete_keg(kegs, form.get("idx"))
            if updated is None:
                send(client, 400, "text/html; charset=utf-8", "Invalid fields")
                return
            if not keg_registry.save_kegs(keg_registry.KEG_FILE, updated):
                send(client, 500, "text/html; charset=utf-8", "Keg save error")
                return
        except Exception as e:
            send(client, 500, "text/html; charset=utf-8", "Keg save error: {}".format(e))
            return
        location = "/?saved=1"
        if service._cfg.get("require_token"):
            location = "/?saved=1&k={}".format(service._token)
        send(client, 303, "text/plain; charset=utf-8", "", headers={"Location": location})
        return

    if method == "POST" and path == "/update":
        form = portal.parse_form_urlencoded(body)
        if not service._token_ok(query, form):
            send(client, 403, body="Forbidden")
            return
        try:
            from storage import config_registry
            ok, error = config_registry.set_update_requested(True)
        except Exception as e:
            ok, error = False, str(e)
        if not ok:
            send(client, 500, "text/html; charset=utf-8", "Update request failed: {}".format(error))
            return
        send(client, 200, "text/html; charset=utf-8", "Update requested. Rebooting...")
        try:
            import machine
            portal.time.sleep_ms(200)
            machine.reset()
        except Exception:
            pass
        return

    send(client, 404, body="Not found")
