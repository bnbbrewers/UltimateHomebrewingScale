"""Draw assets/icons/Update.png, the launcher's update-available icon.

Same style as the other launcher icons: a full solid disc on an opaque black
square, with a near-white filled glyph -- here a down arrow into a tray. It is
drawn 8x larger and downscaled, so the edges are anti-aliased like the
hand-exported icons.

    python tools/make_update_icon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 38
SUPERSAMPLE = 8
DISC = (211, 47, 47, 255)  # 0xD32F2F, the update prompt's accent
GLYPH = (250, 249, 248, 255)
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "icons" / "Update.png"


def _points(scale, *coords):
    return [(x * scale, y * scale) for x, y in zip(coords[::2], coords[1::2])]


def draw():
    s = SUPERSAMPLE
    n = SIZE * s
    image = Image.new("RGBA", (n, n), (0, 0, 0, 255))
    d = ImageDraw.Draw(image)
    d.ellipse((0, 0, n - 1, n - 1), fill=DISC)
    # Arrow shaft and head.
    d.rectangle((17 * s, 8 * s, 21 * s, 20 * s), fill=GLYPH)
    d.polygon(_points(s, 11.5, 17.5, 26.5, 17.5, 19, 25.5), fill=GLYPH)
    # Tray, with rounded ends.
    width = int(3.2 * s)
    d.line(_points(s, 10, 23, 10, 28.5, 28, 28.5, 28, 23), fill=GLYPH, width=width, joint="curve")
    radius = width / 2
    for x, y in ((10, 23), (28, 23), (10, 28.5), (28, 28.5)):
        d.ellipse((x * s - radius, y * s - radius, x * s + radius, y * s + radius), fill=GLYPH)
    return image.resize((SIZE, SIZE), Image.LANCZOS)


if __name__ == "__main__":
    draw().save(OUTPUT)
    print("wrote", OUTPUT)
