"""Draw the icons and the link-preview image into `src/exactly_print/static`.

Run with `uv run python scripts/icons.py`. The SVG favicon is the source of
the mark; this script repeats it in raster form for the platforms that need
one, and draws the 1200 × 630 Open Graph image: the logo, a sheet of paper
with an image at size, crop marks, the cut line and a ruler.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STATIC = Path(__file__).resolve().parents[1] / "src" / "exactly_print" / "static"

ACCENT = (0x7A, 0x2A, 0x3A)
PAPER = (0xFA, 0xFA, 0xF8)
INK = (0x1F, 0x1F, 0x1F)
MUTED = (0x6B, 0x6B, 0x6B)
LINE = (0xD9, 0xD9, 0xD9)
CUT = (0xE1, 0x1D, 0x2E)
WHITE = (0xFF, 0xFF, 0xFF)

FONTS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
BOLD_FONTS = [
    ("/System/Library/Fonts/Helvetica.ttc", 1),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 0),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = BOLD_FONTS if bold else [(path, 0) for path in FONTS]
    for path, index in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=index)
    raise SystemExit("No usable TrueType font found; add one to FONTS.")


def mark(
    size: int, *, padding: float = 0.0, rounded: bool = True, background: bool = True
) -> Image.Image:
    """The favicon at `size` pixels, drawn oversampled and shrunk for clean edges.

    The mark is an E whose arms are ruler ticks, long and short, in the accent
    on a sheet of paper. `padding` grows the background so a maskable icon
    keeps the letter inside the safe zone. Coordinates below are the SVG's
    64-unit grid.
    """
    over = 8
    px = size * over
    unit = px / (64 * (1 + 2 * padding))
    off = 64 * padding

    def s(v: float) -> float:
        return (v + off) * unit

    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if not background:
        pass
    elif rounded:
        d.rounded_rectangle((0, 0, px - 1, px - 1), radius=12 * unit, fill=PAPER)
    else:
        d.rectangle((0, 0, px - 1, px - 1), fill=PAPER)

    w = 6 * unit

    def stroke(x1: float, y1: float, x2: float, y2: float) -> None:
        """A line with round caps, like the SVG's stroke-linecap."""
        d.line((s(x1), s(y1), s(x2), s(y2)), fill=ACCENT, width=round(w))
        for x, y in ((x1, y1), (x2, y2)):
            d.ellipse((s(x) - w / 2, s(y) - w / 2, s(x) + w / 2, s(y) + w / 2), fill=ACCENT)

    stroke(16, 8, 16, 56)
    for i, y in enumerate((8, 20, 32, 44, 56)):
        stroke(16, y, 16 + (34 if i % 2 == 0 else 18), y)
    return img.resize((size, size), Image.LANCZOS)


def og_image() -> Image.Image:
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # A sheet of A4, portrait, on the right, with a shadow.
    sheet_w, sheet_h = 372, 526
    sx, sy = W - 80 - sheet_w, (H - sheet_h) // 2
    d.rounded_rectangle((sx + 6, sy + 8, sx + sheet_w + 6, sy + sheet_h + 8), 6, fill=LINE)
    d.rounded_rectangle((sx, sy, sx + sheet_w, sy + sheet_h), 6, fill=WHITE, outline=LINE)

    # The image at size: a block of colour with a lighter inner shape.
    ix1, iy1, ix2, iy2 = sx + 92, sy + 76, sx + 302, sy + 376
    d.rectangle((ix1 - 8, iy1 - 8, ix2 + 8, iy2 + 8), fill=(0x9A, 0x4A, 0x5A))  # bleed
    d.rectangle((ix1, iy1, ix2, iy2), fill=ACCENT)
    d.ellipse((ix1 + 40, iy1 + 60, ix2 - 40, iy2 - 60), fill=(0xB8, 0x6E, 0x7C))
    d.rectangle((ix1, iy1, ix2, iy2), outline=CUT, width=3)

    # Crop marks.
    gap, length = 14, 30
    for cx, cy, dx, dy in (
        (ix1, iy1, -1, -1), (ix2, iy1, 1, -1), (ix1, iy2, -1, 1), (ix2, iy2, 1, 1),
    ):  # fmt: skip
        d.line((cx, cy + dy * gap, cx, cy + dy * (gap + length)), fill=INK, width=3)
        d.line((cx + dx * gap, cy, cx + dx * (gap + length), cy), fill=INK, width=3)

    # A ruler along the bottom of the sheet.
    rx, ry, rlen = sx + 36, sy + sheet_h - 58, 300
    d.line((rx, ry, rx + rlen, ry), fill=INK, width=3)
    small = font(15)
    for i in range(0, 101, 2):
        x = rx + rlen * i / 100
        tick = 22 if i % 10 == 0 else (14 if i % 5 == 0 else 8)
        d.line((x, ry, x, ry - tick), fill=INK, width=2 if i % 10 == 0 else 1)
        if i % 20 == 0:
            d.text((x, ry - tick - 4), str(i), fill=INK, font=small, anchor="ms")
    d.text((rx + rlen + 12, ry - 2), "mm", fill=MUTED, font=small, anchor="ls")

    # The mark and the words.
    title = font(88, bold=True)
    body = font(34)
    x, y = 80, 150
    logo = mark(96, background=False)
    img.paste(logo, (x, y + 8), logo)
    d.text((x + 96 + 20, y), "Exactly Print", fill=INK, font=title)
    y += 128
    for line in (
        "Upload an image, pick a size,",
        "print it exactly that size.",
    ):
        d.text((x, y), line, fill=INK, font=body)
        y += 46
    y += 30
    for line in (
        "Millimetre-accurate PDF with crop marks, bleed",
        "and a 100 mm ruler to check the printer.",
    ):
        d.text((x, y), line, fill=MUTED, font=font(26))
        y += 36

    d.rectangle((0, H - 10, W, H), fill=ACCENT)
    return img


def main() -> None:
    STATIC.mkdir(exist_ok=True)
    mark(180).save(STATIC / "apple-touch-icon.png", optimize=True)
    mark(192).save(STATIC / "icon-192.png", optimize=True)
    mark(512).save(STATIC / "icon-512.png", optimize=True)
    mark(512, padding=0.15, rounded=False).save(STATIC / "icon-maskable-512.png", optimize=True)
    mark(48).save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    og_image().save(STATIC / "og.png", optimize=True)
    for name in sorted(p.name for p in STATIC.glob("*.png")) + ["favicon.ico"]:
        print(f"{name:24} {(STATIC / name).stat().st_size:>8} bytes")


if __name__ == "__main__":
    main()
