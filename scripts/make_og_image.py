"""Generate og-image.png — the preview card shown when the site URL is shared
on Slack, Twitter, LinkedIn, Discord. Run once (or after design changes):

    uv run scripts/make_og_image.py

Outputs ./assets/og-image.png."""

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (21, 22, 26)
ACCENT = (255, 138, 76)
ACCENT_DIM = (74, 41, 22)
FG = (236, 236, 236)
MUTED = (154, 154, 154)
BORDER = (42, 44, 51)

ROOT = pathlib.Path(__file__).resolve().parent.parent

FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    print("[warn] no system font found; using default", file=sys.stderr)
    return ImageFont.load_default()


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([(0, 0), (W, 10)], fill=ACCENT)
    d.rectangle([(60, 60), (W - 60, H - 60)], outline=BORDER, width=1)

    pad = 90
    d.text((pad, 110), "REDDIT  +  GITHUB", font=font(36), fill=ACCENT)

    d.text((pad, 175), "Tech Trends", font=font(120), fill=FG)

    badges = ["Python", "AI Agents", "Claude", "MCP", "RAG", "ML"]
    x = pad
    y = 330
    for b in badges:
        bbox = d.textbbox((0, 0), b, font=font(26))
        w = bbox[2] - bbox[0]
        pad_x, pad_y = 18, 9
        box = [x, y, x + w + pad_x * 2, y + 26 + pad_y * 2]
        d.rounded_rectangle(box, radius=8, fill=ACCENT_DIM, outline=ACCENT, width=1)
        d.text((x + pad_x, y + pad_y - 2), b, font=font(26), fill=ACCENT)
        x = box[2] + 12

    d.text((pad, 440), "What your peers are talking about and shipping —", font=font(30), fill=MUTED)
    d.text((pad, 480), "weekly snapshot, ranked by combined Reddit + GitHub signal.", font=font(30), fill=MUTED)

    d.text((pad, H - 110), "Made by Peter", font=font(22), fill=FG)
    d.text((pad, H - 80), "maiphong0411.github.io/reddit-trend", font=font(22), fill=MUTED)

    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    out = assets / "og-image.png"
    img.save(out, optimize=True)
    print(f"Wrote {out} ({W}x{H})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
