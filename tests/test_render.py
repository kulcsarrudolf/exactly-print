import re
import zlib
from io import BytesIO

import pytest
from PIL import Image

from exactly_print.layout import plan
from exactly_print.pdf import PT, write_pdf
from exactly_print.preview import INK, PAPER, render_preview
from exactly_print.qr import encode

LINK = "https://exactly-print.puncto.live/"


def test_pdf_has_the_page_and_trim_box_in_points():
    image = Image.new("RGB", (600, 850), (200, 100, 100))
    layout = plan(image.size, 120, 170, "A4")
    pdf = write_pdf(layout, image)
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert f"/MediaBox [0 0 {210 * PT:.3f} {297 * PT:.3f}]".encode() in pdf
    m = re.search(rb"/TrimBox \[([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)\]", pdf)
    x0, y0, x1, y1 = (float(v) for v in m.groups())
    assert (x1 - x0) / PT == pytest.approx(120, abs=0.001)
    assert (y1 - y0) / PT == pytest.approx(170, abs=0.001)


def test_pdf_prints_the_caption_under_the_ruler():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4")
    pdf = write_pdf(layout, image, layout.describe("cm"))
    assert b"(Image 12 \xd7 17 cm" in pdf  # cp1252 multiplication sign


def test_jpeg_travels_as_jpeg_and_png_as_flate():
    image = Image.new("RGB", (100, 100))
    layout = plan(image.size, 50, None)
    assert b"/FlateDecode" in write_pdf(layout, image)
    image.format = "JPEG"
    assert b"/DCTDecode" in write_pdf(layout, image)


def test_png_travels_as_png_scanlines():
    image = Image.effect_noise((64, 48), 40).convert("RGB")
    layout = plan(image.size, 50, None)
    pdf = write_pdf(layout, image)
    m = re.search(
        rb"/Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns 64 >> /Length (\d+) >>\nstream\n",
        pdf,
    )
    assert m
    data = pdf[m.end() : m.end() + int(m.group(1))]

    # Wrapped back into a PNG, the stream must give the very same pixels:
    # that is what a reader's predictor does with it.
    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(kind + body).to_bytes(4, "big")
        return len(body).to_bytes(4, "big") + kind + body + crc

    ihdr = (64).to_bytes(4, "big") + (48).to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", data) + chunk(b"IEND", b"")
    assert Image.open(BytesIO(png)).convert("RGB").tobytes() == image.tobytes()


def test_preview_is_the_page_at_four_pixels_per_mm():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4")
    png = render_preview(layout, image)
    preview = Image.open(BytesIO(png))
    assert preview.size == (840, 1188)


def test_pdf_draws_both_rulers():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4")
    pdf = write_pdf(layout, image)
    rx, ry, sx = layout.ruler_x, layout.ruler_y, layout.side_ruler_x
    assert f"{rx * PT:.3f} {ry * PT:.3f} m {(rx + 100) * PT:.3f} {ry * PT:.3f} l S".encode() in pdf
    assert f"{sx * PT:.3f} {ry * PT:.3f} m {sx * PT:.3f} {(ry + 100) * PT:.3f} l S".encode() in pdf
    assert b"(Both rulers must measure exactly 100 mm." in pdf


def test_calibrated_pdf_draws_the_trim_box_scaled_on_the_real_sheet():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4", scale_x=1.02, scale_y=1.01)
    pdf = write_pdf(layout, image)
    assert f"/MediaBox [0 0 {210 * PT:.3f} {297 * PT:.3f}]".encode() in pdf
    m = re.search(rb"/TrimBox \[([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)\]", pdf)
    x0, y0, x1, y1 = (float(v) for v in m.groups())
    assert (x1 - x0) / PT == pytest.approx(120 * 1.02, abs=0.001)
    assert (y1 - y0) / PT == pytest.approx(170 * 1.01, abs=0.001)
    # The bottom ruler runs 102 mm with ticks 1.02 mm apart; the left one
    # runs 101 mm with ticks 1.01 mm apart.
    rx, ry, sx = layout.ruler_x, layout.ruler_y, layout.side_ruler_x
    assert f"{rx * PT:.3f} {ry * PT:.3f} m {(rx + 102) * PT:.3f}".encode() in pdf
    assert f"{(rx + 1.02) * PT:.3f} {ry * PT:.3f} m".encode() in pdf
    assert f"{sx * PT:.3f} {ry * PT:.3f} m {sx * PT:.3f} {(ry + 101) * PT:.3f}".encode() in pdf
    assert f"{sx * PT:.3f} {(ry + 1.01) * PT:.3f} m".encode() in pdf


def test_calibrated_preview_is_still_the_real_sheet():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4", scale_x=1.02, scale_y=1.01)
    preview = Image.open(BytesIO(render_preview(layout, image, layout.describe("mm", "HP"))))
    assert preview.size == (840, 1188)


def test_a_plain_page_is_only_the_image_and_its_crop_marks():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4", rulers=False, notes=False)
    pdf = write_pdf(layout, image, layout.describe("mm"), LINK)
    assert b" re\n" not in pdf  # no QR code
    assert b"Both rulers must measure" not in pdf
    assert b"Actual size" not in pdf
    assert b"(Image 120" not in pdf
    # Two lines at each of the four trim corners, and nothing else drawn.
    assert pdf.count(b" l S\n") == 8


def test_the_ruler_note_goes_with_the_rulers():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4", rulers=False)
    pdf = write_pdf(layout, image, layout.describe("mm"))
    assert b"(Image 120" in pdf
    assert b"Actual size" in pdf
    assert b"Both rulers must measure" not in pdf


def test_the_preview_draws_a_plain_page_too():
    image = Image.new("RGB", (600, 850), (200, 100, 100))
    layout = plan(image.size, 120, 170, "A4", rulers=False, notes=False)
    png = render_preview(layout, image, layout.describe("mm"), px_per_mm=2)
    assert Image.open(BytesIO(png)).size == (420, 594)


def test_the_pdf_draws_the_qr_code_inside_its_square():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4")
    pdf = write_pdf(layout, image, link=LINK)
    box = layout.qr
    rects = re.findall(rb"\n([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) re\n", pdf)
    assert rects
    module = box.w / len(encode(LINK)) * PT
    for raw in rects:
        x, y, w, h = (float(v) for v in raw)
        assert x >= box.x * PT - 0.001 and x + w <= box.right * PT + 0.001
        assert y >= box.y * PT - 0.001 and y + h <= box.top * PT + 0.001
        # Each rectangle is a row of dark modules, so it is one module tall.
        assert h == pytest.approx(module, abs=0.001)
        assert w == pytest.approx(round(w / module) * module, abs=0.001)
    # Runs, not one rectangle per module: the three finder patterns alone
    # would be far more than this.
    assert len(rects) < len(encode(LINK)) ** 2


def test_the_pdf_puts_the_top_left_module_of_the_code_at_the_top_left():
    image = Image.new("RGB", (600, 850))
    layout = plan(image.size, 120, 170, "A4")
    pdf = write_pdf(layout, image, link=LINK)
    box = layout.qr
    module = box.w / len(encode(LINK))
    # The first row of a finder pattern is seven dark modules wide, and it
    # belongs at the top of the square, not the bottom.
    top_row = f"{box.x * PT:.3f} {(box.top - module) * PT:.3f} {7 * module * PT:.3f}"
    assert top_row.encode() in pdf


def test_the_preview_draws_the_code_in_the_top_right_corner():
    image = Image.new("RGB", (600, 850), (255, 255, 255))
    layout = plan(image.size, 120, 170, "A4")
    page = Image.open(BytesIO(render_preview(layout, image, link=LINK)))
    box = layout.qr
    s = 4  # the preview's pixels per millimetre
    left, top = round(box.x * s), round((layout.page_h - box.top) * s)
    code = page.crop((left, top, left + round(box.w * s), top + round(box.h * s)))
    assert code.getpixel((0, 0)) == INK  # the corner of the first finder
    colours = {colour: count for count, colour in code.getcolors()}
    assert set(colours) == {INK, PAPER}  # squares, not a smudge
    assert 0.3 < colours[INK] / (code.width * code.height) < 0.7
    # Nothing of the code spills onto the paper kept clear around it.
    assert page.getpixel((left - 1, top + 2)) == PAPER
    assert page.getpixel((left + 2, top + code.height + 1)) == PAPER


def test_the_preview_leaves_the_code_off_a_clean_sheet():
    image = Image.new("RGB", (600, 850), (255, 255, 255))
    layout = plan(image.size, 120, 170, "A4", rulers=False, notes=False)
    page = Image.open(BytesIO(render_preview(layout, image, link=LINK)))
    corner = page.crop((page.width - 80, 0, page.width, 80))
    assert corner.getcolors() == [(80 * 80, PAPER)]
