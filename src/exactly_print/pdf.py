"""A one-page PDF written by hand: an image, crop marks, a ruler, three notes.

Everything is placed in points converted from the layout's millimetres, so
printing at 100% puts the trim box on paper at exactly the requested size.
"""

import zlib
from io import BytesIO

from PIL import Image

from .layout import RULER_LEN, Layout

PT = 72 / 25.4  # points per millimetre

NOTE_RULER = "This ruler must measure exactly 100 mm. Cut along the crop marks in the corners."
NOTE_PRINT = 'Print at 100% / "Actual size", never "Fit to page".'


def _n(mm: float) -> str:
    return f"{mm * PT:.3f}"


def _text(x_mm: float, y_mm: float, size: float, s: str, center: bool = False) -> bytes:
    raw = s.encode("cp1252")
    if center:
        x_mm -= len(raw) * size * 0.5 / PT / 2  # Helvetica averages half an em per glyph
    esc = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    x, y = _n(x_mm).encode(), _n(y_mm).encode()
    return b"BT /F1 %.1f Tf %s %s Td (%s) Tj ET\n" % (size, x, y, esc)


def _image_stream(image: Image.Image) -> tuple[bytes, bytes]:
    """The image object's dictionary entries and its encoded bytes.

    Photographs travel as JPEG so a 12-megapixel upload does not become a
    40 MB PDF; everything else is losslessly deflated.
    """
    if image.format == "JPEG":
        buf = BytesIO()
        image.save(buf, "JPEG", quality=92, subsampling=0)
        return b"/Filter /DCTDecode", buf.getvalue()
    return b"/Filter /FlateDecode", zlib.compress(image.tobytes(), 9)


def _content(layout: Layout, caption: str) -> bytes:
    ops: list[bytes] = []
    b, im = layout.bleed, layout.image
    ops.append(
        f"q {_n(b.x)} {_n(b.y)} {_n(b.w)} {_n(b.h)} re W n "
        f"{_n(im.w)} 0 0 {_n(im.h)} {_n(im.x)} {_n(im.y)} cm /Im1 Do Q\n".encode()
    )

    ops.append(b"q 0 G 0.3 w\n")
    for x1, y1, x2, y2 in layout.marks:
        ops.append(f"{_n(x1)} {_n(y1)} m {_n(x2)} {_n(y2)} l S\n".encode())

    rx, ry = layout.ruler_x, layout.ruler_y
    ops.append(f"{_n(rx)} {_n(ry)} m {_n(rx + RULER_LEN)} {_n(ry)} l S\n".encode())
    for mm in range(int(RULER_LEN) + 1):
        tick = 5 if mm % 10 == 0 else 3 if mm % 5 == 0 else 1.5
        ops.append(f"{_n(rx + mm)} {_n(ry)} m {_n(rx + mm)} {_n(ry + tick)} l S\n".encode())
    ops.append(b"Q 0 g\n")

    for mm in range(0, int(RULER_LEN) + 1, 10):
        ops.append(_text(rx + mm, ry + 6.5, 6, str(mm), center=True))
    # The settings first, then the notes; all of it stays above the 6 mm
    # margin a home printer cannot reach.
    cx = layout.page_w / 2
    ops.append(_text(cx, ry - 4, 7, caption, center=True))
    ops.append(_text(cx, ry - 7.5, 6, NOTE_RULER, center=True))
    ops.append(_text(cx, ry - 11, 6, NOTE_PRINT, center=True))
    return b"".join(ops)


def write_pdf(layout: Layout, image: Image.Image, caption: str = "") -> bytes:
    if image.mode != "RGB":
        raise ValueError("write_pdf wants an RGB image")
    iw, ih = image.size
    img_filter, img_data = _image_stream(image)
    content = _content(layout, caption)
    t, b = layout.trim, layout.bleed

    def box(bx) -> str:
        return f"[{_n(bx.x)} {_n(bx.y)} {_n(bx.right)} {_n(bx.top)}]"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {_n(layout.page_w)} {_n(layout.page_h)}] "
            f"/BleedBox {box(b)} /TrimBox {box(t)} "
            f"/Resources << /XObject << /Im1 4 0 R >> /Font << /F1 6 0 R >> >> "
            f"/Contents 5 0 R >>"
        ).encode(),
        (
            f"<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
        ).encode()
        + img_filter
        + f" /Length {len(img_data)} >>\nstream\n".encode()
        + img_data
        + b"\nendstream",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)
