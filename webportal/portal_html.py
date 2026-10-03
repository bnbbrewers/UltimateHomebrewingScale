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
    ("KEG_FILL_STALL_TIMEOUT_S", "Fill stall safety (s)", "number", ()),
    ("STANDBY_TIMEOUT_MIN", "Standby after (min, 0 = off)", "number", ()),
    ("BATTERY", "Battery powered", "checkbox", ()),
    ("DEBUG", "Debug mode", "checkbox", ()),
    ("UPDATE_CHANNEL", "Release channel", "select", ("stable", "prerelease")),
)

# Tabs of the page: (query key, i18n key, default title, cards), and each card
# is (i18n key, default title, dot colour class, fields). Every FIELDS key
# belongs to exactly one card. The kegs and the backup box are appended by
# _append_kegs and _append_maintenance.
TABS = (
    ("general", "portal.tabs.general", "General", (
        ("portal.sections.wifi", "Wi-Fi", "", ("LANGUAGE", "WIFI_SSID", "WIFI_PASSWORD")),
        ("portal.sections.device", "Device", "", ("STANDBY_TIMEOUT_MIN", "BATTERY", "DEBUG")),
    )),
    ("brewing", "portal.tabs.brewing", "Brewing", (
        ("portal.sections.brewfather", "Brewfather", "a", ("BREWING_SOFTWARE", "BREWFATHER_USER_ID", "BREWFATHER_API_KEY")),
        ("portal.sections.weighing", "Weighing", "g", ("GRAIN_WEIGHT_TOLERANCE", "HOP_WEIGHT_TOLERANCE")),
    )),
    ("kegs", "portal.tabs.kegs", "Kegs", (
        ("portal.sections.filling", "Filling", "s", ("KEG_SPUNDING_VALVE_INERTIA_ML", "KEG_FILL_STALL_TIMEOUT_S")),
    )),
    ("maintenance", "portal.tabs.maintenance", "Maintenance", (
        ("portal.sections.updates", "Updates", "", ("UPDATE_CHANNEL",)),
    )),
)

# The maintenance tab holds forms of its own (/update, /backup, /restore), so
# it sits outside the /save form; its settings join that form by id.
_SAVE_FORM = "s"
_OUTSIDE_TAB = len(TABS) - 1

# Inline on purpose: the Dial answers each request with one response held
# whole in RAM, so no stylesheet, font or image travels on its own.
# Colours follow docs/assets/css/uhs-docs.css. Tabs are radio buttons placed
# before the panels, so they switch without any script.
_CSS = (
    ":root{--bg:#F4F4F2;--cd:#fff;--ln:#E3E3DF;--tx:#14171B;--mu:#5A5E65;--in:#fff;"
    "--b:#0D0F12;--bf:#fff;--rd:#A8463F;--eb:#FDECEA;--ef:#8A1C12}"
    "@media(prefers-color-scheme:dark){:root{--bg:#0D0F12;--cd:#15181D;--ln:#2B313A;--tx:#EDEFF2;"
    "--mu:#A2A8B2;--in:#1D2128;--b:#EDEFF2;--bf:#0D0F12;--rd:#A84A43;--eb:#3A1512;--ef:#FFB4A9}}"
    "*{box-sizing:border-box}"
    "body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.4 system-ui,-apple-system,'Segoe UI',sans-serif}"
    "main{max-width:480px;margin:0 auto;padding:16px}"
    "header{display:flex;align-items:center;gap:12px;margin:8px 0 20px}"
    "header svg{width:44px;height:44px;flex:none;border-radius:11px;box-shadow:0 0 0 1px var(--ln)}"
    "h1{font-size:18px;margin:0}header p{margin:0;color:var(--mu);font-size:14px}"
    ".r{position:absolute;opacity:0;pointer-events:none}"
    "nav{position:sticky;top:8px;z-index:1;display:flex;gap:4px;padding:4px;margin:0 0 16px;background:var(--cd);"
    "border:1px solid var(--ln);border-radius:999px;box-shadow:0 4px 16px #0d0f1214}"
    "nav label{flex:auto;margin:0;padding:8px;border-radius:999px;text-align:center;white-space:nowrap;"
    "font-weight:600;cursor:pointer}"
    "#t0:checked~nav [for=t0],#t1:checked~nav [for=t1],#t2:checked~nav [for=t2],#t3:checked~nav [for=t3]"
    "{background:var(--b);color:var(--bf)}"
    ".p{display:none}"
    "#t0:checked~form #p0,#t1:checked~form #p1,#t2:checked~form #p2,#t3:checked~#p3{display:block}"
    "fieldset{background:var(--cd);border:1px solid var(--ln);border-radius:14px;padding:0 16px 16px;"
    "margin:0 0 16px;min-width:0;box-shadow:0 1px 2px #0d0f120a,0 8px 24px #0d0f120f}"
    "legend{float:left;width:100%;padding:16px 0 4px;font-weight:700;display:flex;align-items:center;gap:8px}"
    "legend:before{content:'';width:10px;height:10px;border-radius:50%;background:var(--d,var(--tx))}"
    ".a{--d:#FBB500}.g{--d:#13A923}.s{--d:#C9CED6}"
    "fieldset fieldset{background:var(--bg);box-shadow:none;border-radius:10px;padding:0 12px 12px;margin:12px 0 0}"
    "fieldset fieldset legend{padding-top:12px;font-size:15px}fieldset fieldset legend:before{display:none}"
    "label,form,p{display:block;clear:both;margin:12px 0 0}label{font-size:14px;color:var(--mu)}"
    "input,select{display:block;width:100%;margin-top:4px;padding:10px 12px;font:inherit;color:var(--tx);"
    "background:var(--in);border:1px solid var(--ln);border-radius:8px}"
    "input:focus,select:focus{outline:2px solid #13A923;outline-offset:1px}"
    ".c{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:16px;color:var(--tx)}"
    ".c input{appearance:none;-webkit-appearance:none;width:46px;height:28px;flex:none;margin:0;padding:0;"
    "border:0;border-radius:14px;background:var(--ln);position:relative;transition:.2s}"
    ".c input:after{content:'';position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;"
    "background:#fff;box-shadow:0 1px 3px #0004;transition:.2s}"
    ".c input:checked{background:#13A923}.c input:checked:after{left:21px}"
    ".u{display:grid;grid-template-columns:1fr 1fr;gap:0 12px}"
    "button,::file-selector-button{font:inherit;font-weight:600;border:0;border-radius:999px;"
    "background:var(--b);color:var(--bf);cursor:pointer}"
    "button{display:block;width:100%;margin-top:12px;padding:12px}"
    "::file-selector-button{padding:8px 14px;margin-right:12px}"
    "button.x{background:var(--rd);color:#fff}"
    ".bar{position:sticky;bottom:0;padding:4px 0 16px;background:linear-gradient(#0000,var(--bg) 40%)}"
    ".e,.k{border-radius:10px;padding:12px 16px;font-weight:600;margin:0 0 16px}"
    ".e{background:var(--eb);color:var(--ef)}.k{background:var(--cd);border:1px solid var(--ln)}"
    ".m{color:var(--mu)}.h{font-size:14px;margin-top:8px}"
)

# The one-line answer pages need only the frame: colours, header and notice.
# Answering /save with the whole sheet would cost RAM right before a reboot.
_MESSAGE_CSS = (
    _CSS[:_CSS.index("*{box-sizing")]
    + "body{margin:0;background:var(--bg);color:var(--tx);font:16px/1.4 system-ui,-apple-system,'Segoe UI',sans-serif}"
    "main{max-width:480px;margin:0 auto;padding:16px}"
    "header{display:flex;align-items:center;gap:12px;margin:8px 0 20px}"
    "header svg{width:44px;height:44px;flex:none;border-radius:11px;box-shadow:0 0 0 1px var(--ln)}"
    "h1{font-size:18px;margin:0}header p{margin:0;color:var(--mu);font-size:14px}"
    ".e,.k{border-radius:10px;padding:12px 16px;font-weight:600;margin:0 0 16px}"
    ".e{background:var(--eb);color:var(--ef)}.k{background:var(--cd);border:1px solid var(--ln)}"
)

# docs/assets/logo/uhs-logo-dark-small.svg without its metadata.
_LOGO = (
    "<svg viewBox='0 0 120 120' aria-hidden='true'><rect width='120' height='120' rx='30' fill='#0D0F12'/>"
    "<circle cx='60' cy='26' r='8' fill='#fff'/>"
    "<rect x='26' y='50' width='18' height='24' rx='9' fill='#13A923'/>"
    "<rect x='51' y='40' width='18' height='34' rx='9' fill='#FBB500'/>"
    "<rect x='76' y='46' width='18' height='28' rx='9' fill='#C9CED6'/>"
    "<rect x='18' y='78' width='84' height='12' rx='6' fill='#fff'/>"
    "<rect x='42' y='96' width='36' height='12' rx='6' fill='#fff' fill-opacity='.72'/></svg>"
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


def _page_start(parts, i18n, css=_CSS):
    # The stylesheet and the logo go in as their own parts, never formatted
    # into a larger string: that copy is what the Dial's heap cannot afford.
    parts.append("<!doctype html><html><head><meta charset='utf-8'>"
                 "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                 "<meta name='color-scheme' content='light dark'>")
    parts.append("<title>{}</title><style>".format(
        _escape(_t(i18n, "portal.title", "Ultimate Homebrewing Scale setup"))))
    parts.append(css)
    parts.append("</style></head><body><main><header>")
    parts.append(_LOGO)
    parts.append("<div><h1>Ultimate Homebrewing Scale</h1><p>{}</p></div></header>".format(
        _escape(_t(i18n, "portal.subtitle", "Setup"))))


def render_message_parts(text, i18n=None, error=False):
    """Branded page for the one-line answers of /save, /update and /restore."""
    parts = []
    _page_start(parts, i18n, _MESSAGE_CSS)
    parts.append("<p class='{}'>{}</p></main></body></html>".format("e" if error else "k", _escape(text)))
    return parts


def render_message_html(text, i18n=None, error=False):
    return "".join(render_message_parts(text, i18n=i18n, error=error))


def _append_field(parts, key, label, typ, choices, value, i18n, form_attr):
    text = _escape(_t(i18n, "portal.fields." + key, label))
    if typ == "checkbox":
        parts.append("<label class='c'>{}<input type='checkbox' name='{}' value='on'{}{}></label>".format(
            text, key, " checked" if bool(value) else "", form_attr))
        return
    parts.append("<label>{}".format(text))
    if typ == "select":
        parts.append("<select name='{}'{}>".format(key, form_attr))
        for choice in choices:
            label_choice = _t(i18n, "portal.choices.{}_{}".format(key.lower(), choice), choice)
            parts.append("<option value='{}'{}>{}</option>".format(choice, " selected" if str(value) == choice else "", label_choice))
        parts.append("</select>")
    elif typ == "number":
        parts.append("<input type='number' name='{}' value='{}' min='0' inputmode='decimal'{}>".format(key, _escape(value), form_attr))
    else:
        parts.append("<input type='{}' name='{}' value='{}' autocomplete='off'{}>".format(typ, key, _escape(value), form_attr))
    parts.append("</label>")


def _append_cards(parts, cards, fields, values, i18n, form_attr="", tail=None):
    """Render ``cards``; ``tail`` adds content at the end of the last one."""
    for idx, (title_key, title, dot, keys) in enumerate(cards):
        parts.append("<fieldset{}><legend>{}</legend>".format(
            " class='{}'".format(dot) if dot else "", _escape(_t(i18n, title_key, title))))
        for key in keys:
            _key, label, typ, choices = fields[key]
            _append_field(parts, key, label, typ, choices, values.get(key, ""), i18n, form_attr)
        if tail is not None and idx == len(cards) - 1:
            tail(parts, i18n)
        parts.append("</fieldset>")


def _append_kegs(parts, kegs, i18n):
    parts.append("<fieldset class='s'><legend>{}</legend>".format(_escape(_t(i18n, "portal.kegs", "Kegs"))))
    if not kegs:
        parts.append("<p class='m'>{}</p>".format(_escape(_t(i18n, "portal.no_kegs", "No saved keg"))))
    for idx, keg in enumerate(kegs):
        name = keg.get("name", "")
        parts.append("<fieldset><legend>{}</legend>".format(_escape(name)))
        parts.append("<label>{}<input type='text' name='keg_name_{}' value='{}' maxlength='32'></label>".format(_escape(_t(i18n, "portal.keg_name", "Keg name")), idx, _escape(name)))
        parts.append("<div class='u'><label>{} (g)<input type='number' name='keg_empty_weight_g_{}' value='{}' min='0.1' step='0.1' inputmode='decimal'></label>".format(_escape(_t(i18n, "portal.keg_empty_weight", "Empty weight")), idx, _escape(_number(keg.get("empty_weight_g", 0)))))
        parts.append("<label>{} (L)<input type='number' name='keg_max_volume_l_{}' value='{}' min='0.1' step='0.1' inputmode='decimal'></label></div>".format(_escape(_t(i18n, "portal.keg_max_volume", "Max volume")), idx, _escape(_number(keg.get("max_volume_l", 0)))))
        parts.append("<button class='x' type='submit' formaction='/kegs/delete' name='idx' value='{}'>{} {}</button></fieldset>".format(idx, _escape(_t(i18n, "portal.keg_delete", "Delete")), _escape(name)))
    parts.append("</fieldset>")


def _append_update(parts, i18n):
    parts.append("<p class='m h'>{}</p>".format(
        _escape(_t(i18n, "portal.channel_hint", "Changed the channel? Save and reboot first, then update."))))
    parts.append("<form method='post' action='/update'><button type='submit'>{}</button></form>".format(
        _escape(_t(i18n, "portal.update_app", "Update the app"))))


def _append_backup(parts, i18n):
    """One box holding both actions, each in its own standalone form.

    They must stay outside the /save form: nested there, the upload would ride
    along with every settings save and push the body past the request cap.
    """
    parts.append("<fieldset><legend>{}</legend>".format(
        _escape(_t(i18n, "portal.backup_title", "Configuration backup and restore"))))
    parts.append("<form method='get' action='/backup'><button type='submit'>{}</button></form>".format(
        _escape(_t(i18n, "portal.backup_download", "Back up"))))
    parts.append("<form method='post' action='/restore' enctype='multipart/form-data'><label>{}<input type='file' name='backup' accept='.txt'></label><button type='submit'>{}</button></form></fieldset>".format(
        _escape(_t(i18n, "portal.backup_file", "Backup file")),
        _escape(_t(i18n, "portal.backup_restore", "Restore")),
    ))


def render_form_html(values, kegs=None, include_kegs=False, error="", i18n=None, tab=""):
    return "".join(render_form_parts(values, kegs=kegs, include_kegs=include_kegs,
                                     error=error, i18n=i18n, tab=tab))


def render_form_parts(values, kegs=None, include_kegs=False, error="", i18n=None, tab=""):
    """The setup page as a list of strings; ``tab`` is the query key of the
    tab to open first.

    The Dial sends the parts one after the other: joined, the page is one
    9 KB block that its fragmented heap cannot allocate.
    """
    values = values or {}
    fields = {}
    for field in FIELDS:
        fields[field[0]] = field
    opened = 0
    for idx, item in enumerate(TABS):
        if item[0] == tab:
            opened = idx
    parts = []
    _page_start(parts, i18n)
    if error:
        parts.append("<p class='e'>{}</p>".format(_escape(_t(i18n, "portal.invalid_fields", "Invalid fields"))))
    # Radios outside every form: they only drive the CSS and are never sent.
    for idx in range(len(TABS)):
        parts.append("<input class='r' type='radio' name='tab' id='t{}'{}>".format(idx, " checked" if idx == opened else ""))
    parts.append("<nav>")
    for idx, item in enumerate(TABS):
        parts.append("<label for='t{}'>{}</label>".format(idx, _escape(_t(i18n, item[1], item[2]))))
    parts.append("</nav>")
    # novalidate: a browser check failing in a hidden tab would block the
    # submit without showing why. The Dial validates and reports instead.
    parts.append("<form id='{}' method='post' action='/save' novalidate>".format(_SAVE_FORM))
    for idx, item in enumerate(TABS):
        if idx == _OUTSIDE_TAB:
            continue
        parts.append("<div class='p' id='p{}'>".format(idx))
        _append_cards(parts, item[3], fields, values, i18n)
        if item[0] == "kegs" and include_kegs:
            _append_kegs(parts, kegs or [], i18n)
        parts.append("</div>")
    parts.append("</form><div class='p' id='p{}'>".format(_OUTSIDE_TAB))
    _append_cards(parts, TABS[_OUTSIDE_TAB][3], fields, values, i18n,
                  " form='{}'".format(_SAVE_FORM), tail=_append_update)
    _append_backup(parts, i18n)
    parts.append("</div><div class='bar'><button type='submit' form='{}'>{}</button></div>".format(
        _SAVE_FORM, _escape(_t(i18n, "portal.save_reboot", "Save and reboot"))))
    parts.append("</main></body></html>")
    return parts


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
