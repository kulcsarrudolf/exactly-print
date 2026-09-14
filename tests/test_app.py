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
    assert "19.4 × 26.5 cm" in r.text


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
    assert r.content.startswith(b"%PDF")


def test_pdf_inline_for_printing():
    r = client.post(
        "/pdf",
        files={"image": ("a.png", png_bytes(), "image/png")},
        data={"width": "50", "disposition": "inline"},
    )
    assert r.headers["content-disposition"].startswith("inline;")
