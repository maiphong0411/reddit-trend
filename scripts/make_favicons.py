"""Generate PNG favicon fallbacks (for older browsers + iOS home screen).
Re-run only if the design changes:

    uv run scripts/make_favicons.py

Outputs (in ./assets/):
  favicon-32x32.png     small browser fallback for clients that don't support SVG favicons
  apple-touch-icon.png  iOS home-screen icon (180x180, no SVG support)
"""

import pathlib
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent

BG = (21, 22, 26, 255)
BAR = (255, 138, 76, 255)


def make_icon(size: int, out: pathlib.Path) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = max(2, int(size * 0.20))
    d.rounded_rectangle([(0, 0), (size, size)], radius=radius, fill=BG)

    bar_w = size * 0.16
    gap = size * 0.04
    base_y = size * 0.82
    heights = [size * 0.30, size * 0.48, size * 0.65]
    x_start = (size - (3 * bar_w + 2 * gap)) / 2
    for i, h in enumerate(heights):
        x = x_start + i * (bar_w + gap)
        y = base_y - h
        d.rounded_rectangle(
            [(x, y), (x + bar_w, base_y)],
            radius=max(1, int(bar_w * 0.2)),
            fill=BAR,
        )

    img.save(out, optimize=True)
    print(f"Wrote {out} ({size}x{size})")


def main() -> int:
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    make_icon(32, assets / "favicon-32x32.png")
    make_icon(180, assets / "apple-touch-icon.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
