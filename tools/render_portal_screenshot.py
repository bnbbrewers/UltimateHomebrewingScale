"""Render the setup portal to a PNG used by the Software Installation Guide.

The screenshot is produced from ``webportal.portal_html.render_form_html`` so it
cannot drift from the real form: adding a field to ``FIELDS`` and rerunning this
script is enough to refresh the guide image.

Usage (from the repository root):

    python tools/render_portal_screenshot.py

It writes ``docs/SoftwareInstallationGuide/img/PortalPage.png``. Rendering needs
a Chrome or Edge binary; pass ``--browser`` when it lives outside the usual
install paths.
"""

import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUTPUT = os.path.join(ROOT, "docs", "SoftwareInstallationGuide", "img", "PortalPage.png")

# Viewport of a phone in portrait, which is how the portal is used. 510 is the
# narrowest width where the backup fieldset still fits: the portal ships no CSS,
# so that box is laid out at its min-content width and overflows below this.
WIDTH = 510
# Taller than the form on purpose; the blank tail is cropped after rendering.
HEIGHT = 1700

BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)

# Values shown in the screenshot. They are illustrative placeholders, never real
# credentials: the guide tells the reader to substitute their own.
SAMPLE_VALUES = {
    "LANGUAGE": "en",
    "WIFI_SSID": "MyBrewery",
    "WIFI_PASSWORD": "wifi-password",
    "BREWING_SOFTWARE": "brewfather",
    "BREWFATHER_USER_ID": "your_user_id_here",
    "BREWFATHER_API_KEY": "your_api_key_here",
    "GRAIN_WEIGHT_TOLERANCE": 10,
    "HOP_WEIGHT_TOLERANCE": 1,
    "KEG_SPUNDING_VALVE_INERTIA_ML": 200,
    "STANDBY_TIMEOUT_MIN": 30,
    "BATTERY": True,
    "DEBUG": False,
    "UPDATE_CHANNEL": "stable",
}


def find_browser(explicit=None):
    if explicit:
        if not os.path.exists(explicit):
            raise SystemExit("browser not found: %s" % explicit)
        return explicit
    for candidate in BROWSER_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    raise SystemExit(
        "no Chrome or Edge binary found; pass --browser with the path to one")


def build_page():
    """Wrap the portal's own HTML in a minimal phone frame."""
    from webportal.portal_html import render_form_html

    form = render_form_html(SAMPLE_VALUES)
    body = form[form.index("<body>") + len("<body>"):form.index("</body>")]
    return PAGE_TEMPLATE % {"body": body}


PAGE_TEMPLATE = """<!doctype html>
<html><head><meta charset='utf-8'>
<style>
  html, body { margin: 0; padding: 0; background: #ffffff; }
  .chrome {
    display: flex; align-items: center; gap: 10px;
    background: #202124; color: #e8eaed;
    padding: 10px 14px; font: 15px/1.2 system-ui, sans-serif;
  }
  .chrome .url {
    flex: 1; background: #303134; border-radius: 999px;
    padding: 7px 14px; color: #bdc1c6;
  }
  .page { padding: 12px 16px 28px; }
</style>
</head>
<body>
  <div class="chrome"><span class="url">192.168.4.1:8080</span></div>
  <div class="page">%(body)s</div>
</body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="path to a Chrome or Edge binary")
    parser.add_argument("--output", default=OUTPUT, help="PNG to write")
    parser.add_argument("--width", type=int, default=WIDTH,
                        help="viewport width in CSS pixels (default %d)" % WIDTH)
    args = parser.parse_args()

    browser = find_browser(args.browser)
    page = build_page()

    tmp_dir = tempfile.mkdtemp(prefix="uhs-portal-shot-")
    html_path = os.path.join(tmp_dir, "portal.html")
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(page)

    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            # The portal form is English-only, so keep browser-supplied widget
            # text (the file picker) English too whatever the host locale is.
            "--lang=en-US",
            "--accept-lang=en-US",
            "--screenshot=%s" % args.output,
            "--window-size=%d,%d" % (args.width, HEIGHT),
            "--user-data-dir=%s" % os.path.join(tmp_dir, "profile"),
            html_path,
        ],
        check=True,
        env=dict(os.environ, LANG="en_US.UTF-8", LANGUAGE="en_US"),
    )

    if not os.path.exists(args.output):
        raise SystemExit("the browser did not produce %s" % args.output)
    _trim_trailing_blank(args.output)
    print("wrote %s" % args.output)


def _trim_trailing_blank(path, margin=24):
    """Drop the empty page below the form, so the guide image stays compact.

    The window has to be taller than the form to avoid clipping it, which leaves
    blank pixels at the bottom. Skipped when Pillow is unavailable.
    """
    try:
        from PIL import Image
    except ImportError:
        print("Pillow missing: keeping the full-height screenshot")
        return

    image = Image.open(path).convert("RGB")
    width, height = image.size
    pixels = image.load()
    background = pixels[width - 1, height - 1]

    last_content = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y] != background:
                last_content = y
                break

    bottom = min(height, last_content + margin)
    if bottom < height:
        image.crop((0, 0, width, bottom)).save(path)
        print("trimmed %d blank pixels" % (height - bottom))


if __name__ == "__main__":
    main()
