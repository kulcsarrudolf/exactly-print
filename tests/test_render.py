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
