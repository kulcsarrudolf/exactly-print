import re
from io import BytesIO

import pytest
from PIL import Image

from exactly_print.layout import plan
from exactly_print.pdf import PT, write_pdf
from exactly_print.preview import render_preview


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
