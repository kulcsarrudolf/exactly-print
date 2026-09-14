"""The page as a PNG, drawn from the same layout the PDF uses."""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .layout import RULER_LEN, Layout

PX_PER_MM = 4
PAPER = (255, 255, 255)
INK = (40, 40, 40)
GUIDE = (200, 120, 120)


def render_preview(
    layout: Layout, image: Image.Image, caption: str = "", px_per_mm: int = PX_PER_MM
) -> bytes:
    s = px_per_mm
    page_w, page_h = round(layout.page_w * s), round(layout.page_h * s)

    def pt(x_mm: float, y_mm: float) -> tuple[int, int]:
        # Flip from PDF's bottom-left origin to the raster's top-left one.
        return round(x_mm * s), round(page_h - y_mm * s)

    page = Image.new("RGB", (page_w, page_h), PAPER)
    im = layout.image
    scaled = image.resize((max(1, round(im.w * s)), max(1, round(im.h * s))), Image.LANCZOS)
    left, top = pt(im.x, im.top)
    # Paste through a mask the size of the bleed box so the overflow is clipped.
    b = layout.bleed
    bl, bt = pt(b.x, b.top)
    clipped = Image.new("RGB", (page_w, page_h), PAPER)
    clipped.paste(scaled, (left, top))
    page.paste(clipped.crop((bl, bt, bl + round(b.w * s), bt + round(b.h * s))), (bl, bt))

    draw = ImageDraw.Draw(page)
    for x1, y1, x2, y2 in layout.marks:
        draw.line([pt(x1, y1), pt(x2, y2)], fill=INK, width=1)

    # The trim line is drawn on the preview only, so the user can see what
    # the bleed will lose; the PDF has just the crop marks.
    t = layout.trim
    draw.rectangle([pt(t.x, t.top), pt(t.right, t.y)], outline=GUIDE, width=1)

    rx, ry = layout.ruler_x, layout.ruler_y
    draw.line([pt(rx, ry), pt(rx + RULER_LEN, ry)], fill=INK, width=1)
    for mm in range(int(RULER_LEN) + 1):
        tick = 5 if mm % 10 == 0 else 3 if mm % 5 == 0 else 1.5
        draw.line([pt(rx + mm, ry), pt(rx + mm, ry + tick)], fill=INK, width=1)
    for mm in range(0, int(RULER_LEN) + 1, 10):
        draw.text(pt(rx + mm, ry + 9), str(mm), fill=INK, anchor="mm")
    if caption:
        # Pillow's bundled font has no multiplication sign; the PDF keeps it.
        font = ImageFont.load_default(size=3 * s)
        text = caption.replace("×", "x")
        draw.text(pt(layout.page_w / 2, ry - 5), text, fill=INK, anchor="mm", font=font)

    out = BytesIO()
    page.save(out, "PNG", optimize=True)
    return out.getvalue()
