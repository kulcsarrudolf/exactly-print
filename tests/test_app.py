from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from exactly_print.app import app

client = TestClient(app)


def png_bytes(size=(600, 850)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (180, 120, 120)).save(buf, "PNG")
    return buf.getvalue()


def test_index_renders_the_form():
    r = client.get("/")
    assert r.status_code == 200
    assert 'hx-post="/preview"' in r.text
    assert 'action="/pdf"' in r.text


def test_preview_returns_an_image_and_the_size():
    r = client.post(
        "/preview",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "12", "height": "17", "unit": "cm", "paper": "A4", "orientation": "auto"},
    )
    assert r.status_code == 200
    assert "data:image/png;base64," in r.text
    assert "12 × 17 cm" in r.text


def test_preview_without_a_size_explains():
    r = client.post("/preview", files={"image": ("a.png", png_bytes(), "image/png")})
    assert "Give a width, a height, or both." in r.text


def test_too_large_is_explained_in_the_typed_unit():
    r = client.post(
        "/preview",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "30", "height": "17", "unit": "cm", "paper": "A4"},
    )
    assert "30 × 17 cm does not fit on A4 (21 × 29.7 cm)" in r.text
    assert "18 × 26.1 cm" in r.text


def test_preview_without_an_image_explains():
    r = client.post("/preview", data={"width": "100"})
    assert "Choose an image first." in r.text


def test_preview_with_a_non_image_explains():
    r = client.post(
        "/preview", files={"image": ("a.txt", b"hello", "text/plain")}, data={"width": "10"}
    )
    assert "not an image" in r.text


def test_pdf_download():
    r = client.post(
        "/pdf",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "120", "height": "170", "unit": "mm", "disposition": "attachment"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    expected = 'attachment; filename="exactly-print-120x170mm-A4.pdf"'
    assert r.headers["content-disposition"] == expected
    assert b"(Image 120 \xd7 170 mm" in r.content
    assert r.content.startswith(b"%PDF")


def test_pdf_inline_for_printing():
    r = client.post(
        "/pdf",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "50", "disposition": "inline"},
    )
    assert r.headers["content-disposition"].startswith("inline;")


def test_index_has_the_calibration_and_the_help():
    r = client.get("/")
    assert 'name="scale_x"' in r.text
    assert 'name="scale_y"' in r.text
    assert 'id="calibrate"' in r.text
    assert 'id="help-calibrate"' in r.text
    assert "/static/calibrate.js" in r.text


def test_preview_with_a_calibrated_printer_says_so():
    r = client.post(
        "/preview",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={
            "width": "12",
            "unit": "cm",
            "scale_x": "1.020408",
            "scale_y": "1.010101",
            "printer": "HP LaserJet",
        },
    )
    assert r.status_code == 200
    assert "12 × 17 cm" in r.text
    assert "HP LaserJet: prints" in r.text
    assert "98.0 mm per 100 across and 99.0 down" in r.text
    assert "drawn at ×1.020 across, ×1.010 down" in r.text


def test_preview_with_one_factor_says_it_once():
    r = client.post(
        "/preview",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "12", "unit": "cm", "scale_x": "1.02", "scale_y": "1.02"},
    )
    assert "98.0 mm per 100," in r.text
    assert "across" not in r.text.split("<dt>Printer</dt>")[1]
    assert "drawn at ×1.020 to come out right" in r.text


def test_preview_without_a_printer_has_no_printer_row():
    r = client.post(
        "/preview",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "12", "unit": "cm", "scale_x": "", "scale_y": "", "printer": ""},
    )
    assert "<dt>Printer</dt>" not in r.text


def test_bad_calibration_is_explained():
    r = client.post(
        "/preview",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "12", "unit": "cm", "scale_x": "1", "scale_y": "1.5"},
    )
    assert "×1.500 down means the ruler measured 67 mm" in r.text
    r = client.post(
        "/preview",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "12", "unit": "cm", "scale_x": "abc"},
    )
    assert "is not a calibration factor." in r.text


def test_pdf_carries_the_printer_in_the_caption():
    r = client.post(
        "/pdf",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={
            "width": "120",
            "height": "170",
            "scale_x": "1.020408",
            "scale_y": "1.020408",
            "printer": "HP LaserJet",
        },
    )
    assert r.status_code == 200
    assert b"Calibrated for HP LaserJet, drawn at \xd71.020)" in r.content
