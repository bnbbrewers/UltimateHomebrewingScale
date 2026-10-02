"""Render the setup portal tabs to the PNGs used by the user guides.

The screenshots are produced from ``webportal.portal_html.render_form_html`` so
they cannot drift from the real form: changing ``FIELDS`` or ``TABS`` and
rerunning this script is enough to refresh the guide images.

Usage (from the repository root):

    python tools/render_portal_screenshot.py

It writes one ``docs/SoftwareInstallationGuide/img/PortalPage-<tab>.png`` per
tab. Rendering needs a Chrome or Edge binary; pass ``--browser`` when it lives
outside the usual install paths.
"""

import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUTPUT_DIR = os.path.join(ROOT, "docs", "SoftwareInstallationGuide", "img")

# Width of a phone in portrait, which is how the portal is used. Headless
# Chrome on Windows will not lay out a window below about 500 px (it renders
# wider and crops), so the page is laid out in an iframe of this width and the
# shot is cropped to it.
WIDTH = 360
# Taller than any tab on purpose; the blank tail is cropped after rendering.
HEIGHT = 1400
WINDOW_WIDTH = 520
SCALE = 2

BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)

# Values shown in the screenshots. They are illustrative placeholders, never
# real credentials: the guide tells the reader to substitute their own.
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
    "KEG_FILL_STALL_TIMEOUT_S": 10,
    "STANDBY_TIMEOUT_MIN": 30,
    "BATTERY": True,
    "DEBUG": False,
    "UPDATE_CHANNEL": "stable",
}

# One keg, so the guide shows the keg editor of the Kegs tab.
SAMPLE_KEGS = [{"name": "Corny 19L", "empty_weight_g": 4200, "max_volume_l": 19}]

# Matches the portal's light background, so the trimmed tail blends in.
BACKGROUND = "#F4F4F2"


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


def build_page(tab):
    """The portal's own page on ``tab``, in its light theme, under a URL bar.

    The dark-theme block is dropped so the image does not follow the theme of
    the machine that renders it. English, as on a first setup, which is what
    the guides describe; the Dial always passes its i18n, so the choices read
    "English" and "Stable" rather than their raw values.
    """
    from i18n import I18n
    from webportal.portal_html import render_form_html

    page = render_form_html(SAMPLE_VALUES, kegs=SAMPLE_KEGS, include_kegs=True,
                            i18n=I18n("en"), tab=tab)
    dark = page.index("@media(prefers-color-scheme:dark){")
    page = page[:dark] + page[page.index("}}", dark) + 2:]
    page = page.replace("content='light dark'", "content='light'")
    page = page.replace("</style>", URL_BAR_CSS + "</style>", 1)
    return page.replace("<body>", "<body>" + URL_BAR, 1)


URL_BAR_CSS = (
    ".chrome{display:flex;background:#202124;padding:10px 14px;font:15px/1.2 system-ui,sans-serif}"
    ".chrome span{flex:1;background:#303134;border-radius:999px;padding:7px 14px;color:#bdc1c6}"
)
URL_BAR = "<div class='chrome'><span>192.168.4.1:8080</span></div>"

FRAME_PAGE = (
    "<!doctype html><html><body style='margin:0;background:%(bg)s'>"
    "<iframe src='%(src)s' style='display:block;border:0;width:%(w)dpx;height:%(h)dpx'></iframe>"
    "</body></html>"
)


def render_tab(browser, tab, output, tmp_dir):
    page_path = os.path.join(tmp_dir, "portal-%s.html" % tab)
    with open(page_path, "w", encoding="utf-8") as handle:
        handle.write(build_page(tab))
    frame_path = os.path.join(tmp_dir, "frame-%s.html" % tab)
    with open(frame_path, "w", encoding="utf-8") as handle:
        handle.write(FRAME_PAGE % {"bg": BACKGROUND, "src": os.path.basename(page_path),
                                   "w": WIDTH, "h": HEIGHT})

    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=%d" % SCALE,
            # The page is rendered in English, so keep browser-supplied widget
            # text (the file picker) English too whatever the host locale is.
            "--lang=en-US",
            "--accept-lang=en-US",
            # The iframe loads a sibling file:// page.
            "--allow-file-access-from-files",
            "--virtual-time-budget=3000",
            "--screenshot=%s" % output,
            "--window-size=%d,%d" % (WINDOW_WIDTH, HEIGHT),
            "--user-data-dir=%s" % os.path.join(tmp_dir, "profile-%s" % tab),
            frame_path,
        ],
        check=True,
        env=dict(os.environ, LANG="en_US.UTF-8", LANGUAGE="en_US"),
    )
    if not os.path.exists(output):
        raise SystemExit("the browser did not produce %s" % output)
    _crop(output)


def main():
    from webportal.portal_html import TABS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="path to a Chrome or Edge binary")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="folder of the PNGs")
    args = parser.parse_args()

    browser = find_browser(args.browser)
    tmp_dir = tempfile.mkdtemp(prefix="uhs-portal-shot-")
    for tab in TABS:
        output = os.path.join(args.output_dir, "PortalPage-%s.png" % tab[0])
        render_tab(browser, tab[0], output, tmp_dir)
        print("wrote %s" % output)


def _crop(path, margin=24):
    """Keep the iframe's width and drop the empty page below the last card.

    The window has to be wider and taller than the phone frame, which leaves
    blank pixels on the right and at the bottom. Skipped when Pillow is
    unavailable.
    """
    try:
        from PIL import Image
    except ImportError:
        print("Pillow missing: keeping the full-size screenshot")
        return

    image = Image.open(path).convert("RGB")
    width = min(image.size[0], WIDTH * SCALE)
    image = image.crop((0, 0, width, image.size[1]))
    pixels = image.load()
    background = pixels[width - 1, image.size[1] - 1]

    last_content = 0
    for y in range(image.size[1]):
        for x in range(width):
            if pixels[x, y] != background:
                last_content = y
                break

    bottom = min(image.size[1], last_content + margin)
    image.crop((0, 0, width, bottom)).save(path)


if __name__ == "__main__":
    main()
