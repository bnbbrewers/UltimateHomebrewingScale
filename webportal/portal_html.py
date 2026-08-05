"""Small dependency-free setup form renderer."""

FIELDS = (
    ("LANGUAGE", "Language", "select", ("fr", "en")),
    ("WIFI_SSID", "Wi-Fi SSID", "text", ()),
    ("WIFI_PASSWORD", "Wi-Fi password", "password", ()),
    ("BREWING_SOFTWARE", "Brewing software", "select", ("brewfather",)),
    ("BREWFATHER_USER_ID", "Brewfather user id", "text", ()),
    ("BREWFATHER_API_KEY", "Brewfather API key", "password", ()),
    ("GRAIN_WEIGHT_TOLERANCE", "Grain tolerance (g)", "number", ()),
    ("HOP_WEIGHT_TOLERANCE", "Hop tolerance (g)", "number", ()),
    ("KEG_SPUNDING_VALVE_INERTIA_ML", "Spunding valve inertia (ml)", "number", ()),
    ("DEBUG", "Debug mode", "checkbox", ()),
    ("UPDATE_CHANNEL", "Release channel", "select", ("stable", "prerelease")),
)


def _escape(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def _number(value):
    try:
        number = float(value)
        return str(int(round(number))) if abs(number - round(number)) < 0.05 else "{:.1f}".format(number)
    except Exception:
        return str(value)


def _t(i18n, key, default):
    if i18n is not None:
        try:
            value = i18n._translations
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return default
                value = value[part]
            return i18n.t(key)
        except Exception:
            pass
    return default


def _append_kegs(parts, kegs, i18n):
    parts.append("<hr><h4>{}</h4>".format(_escape(_t(i18n, "portal.kegs", "Kegs"))))
    if not kegs:
        parts.append("<p>{}</p>".format(_escape(_t(i18n, "portal.no_kegs", "No saved keg"))))
        return
    for idx, keg in enumerate(kegs):
        name = keg.get("name", "")
        parts.append("<fieldset><legend>{}</legend>".format(_escape(name)))
        parts.append("<p>{}<br><input type='text' name='keg_name_{}' value='{}' maxlength='32'></p>".format(_escape(_t(i18n, "portal.keg_name", "Keg name")), idx, _escape(name)))
        parts.append("<p>{}<br><input type='number' name='keg_empty_weight_g_{}' value='{}' min='0.1' step='0.1'> g</p>".format(_escape(_t(i18n, "portal.keg_empty_weight", "Empty weight")), idx, _escape(_number(keg.get("empty_weight_g", 0)))))
        parts.append("<p>{}<br><input type='number' name='keg_max_volume_l_{}' value='{}' min='0.1' step='0.1'> L</p>".format(_escape(_t(i18n, "portal.keg_max_volume", "Max volume")), idx, _escape(_number(keg.get("max_volume_l", 0)))))
        parts.append("<p><button type='submit' formaction='/kegs/delete' name='idx' value='{}'>{} {}</button></p></fieldset>".format(idx, _escape(_t(i18n, "portal.keg_delete", "Delete")), _escape(name)))


def render_form_html(values, kegs=None, include_kegs=False, error="", i18n=None):
    values = values or {}
    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<title>{}</title></head><body>".format(_escape(_t(i18n, "portal.title", "Ultimate Homebrewing Scale setup"))),
             "<h3>{}</h3>".format(_escape(_t(i18n, "portal.title", "Ultimate Homebrewing Scale setup")))]
    if error:
        parts.append("<p><b>{}</b></p>".format(_escape(_t(i18n, "portal.invalid_fields", "Invalid fields"))))
    parts.append("<form method='post' action='/save'>")
    for key, label, typ, choices in FIELDS:
        value = values.get(key, "")
        parts.append("<p>{}<br>".format(_escape(_t(i18n, "portal.fields." + key, label))))
        if typ == "checkbox":
            parts.append("<input type='checkbox' name='{}' value='on'{}>".format(key, " checked" if bool(value) else ""))
        elif typ == "select":
            parts.append("<select name='{}'>".format(key))
            for choice in choices:
                label_choice = _t(i18n, "portal.choices.{}_{}".format(key.lower(), choice), choice)
                parts.append("<option value='{}'{}>{}</option>".format(choice, " selected" if str(value) == choice else "", label_choice))
            parts.append("</select>")
        elif typ == "number":
            parts.append("<input type='number' name='{}' value='{}' min='0'>".format(key, _escape(value)))
        else:
            parts.append("<input type='{}' name='{}' value='{}'>".format(typ, key, _escape(value)))
        parts.append("</p>")
    if include_kegs:
        _append_kegs(parts, kegs or [], i18n)
    parts.append("<p><button type='submit'>{}</button></p></form>".format(_escape(_t(i18n, "portal.save_reboot", "Save and reboot"))))
    parts.append("<form method='post' action='/update'><p><button type='submit'>{}</button></p></form>".format(_escape(_t(i18n, "portal.update_app", "UPDATE APP"))))
    parts.append("</body></html>")
    return "".join(parts)


def kegs_from_form(kegs, form):
    updated = list(kegs)
    changed = False
    for idx in range(len(kegs)):
        nk = "keg_name_{}".format(idx)
        wk = "keg_empty_weight_g_{}".format(idx)
        vk = "keg_max_volume_l_{}".format(idx)
        if nk not in form and wk not in form and vk not in form:
            continue
        name = str(form.get(nk, updated[idx].get("name", "")) or "").strip()
        try:
            weight = float(form.get(wk, updated[idx].get("empty_weight_g", 0)))
            volume = float(form.get(vk, updated[idx].get("max_volume_l", 0)))
        except Exception:
            return None
        if not name or weight <= 0 or volume <= 0:
            return None
        item = dict(updated[idx])
        item.update({"name": name, "empty_weight_g": weight, "max_volume_l": volume})
        changed = changed or item != updated[idx]
        updated[idx] = item
    return updated if changed else kegs
