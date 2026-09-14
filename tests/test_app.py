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
    assert 'enctype="multipart/form-data"' in r.text


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


def test_index_has_the_calibration_and_links_to_the_help():
    r = client.get("/")
    assert 'name="scale_x"' in r.text
    assert 'name="scale_y"' in r.text
    assert 'id="calibrate"' in r.text
    assert 'href="/help#help-calibrate"' in r.text
    assert 'id="help-calibrate"' not in r.text
    assert "/static/calibrate.js" in r.text
    assert "/static/shrink.js" in r.text


def test_help_is_its_own_page():
    r = client.get("/help")
    assert r.status_code == 200
    assert 'id="help-calibrate"' in r.text
    assert 'id="setup"' not in r.text
    assert 'href="/"' in r.text


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


def test_pages_carry_the_tags_search_engines_and_link_previews_read():
    for path in ("/", "/help"):
        r = client.get(path)
        assert r.status_code == 200
        head = r.text.split("</head>")[0]
        assert '<html lang="en"' in head
        assert "<title>" in head and "Exactly Print" in head.split("</title>")[0]
        assert '<meta name="description" content="' in head
        assert f'<link rel="canonical" href="http://testserver{path}" />' in head
        assert '<meta name="robots" content="index, follow' in head
        assert f'<meta property="og:url" content="http://testserver{path}" />' in head
        assert '<meta property="og:image" content="http://testserver/static/og.png" />' in head
        assert '<meta name="twitter:card" content="summary_large_image" />' in head
        assert '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml" />' in head
        assert '<link rel="apple-touch-icon" href="/static/apple-touch-icon.png"' in head
        assert '<link rel="manifest" href="/static/manifest.webmanifest" />' in head
        assert 'type="application/ld+json"' in head


def test_each_page_has_its_own_title_and_description():
    home = client.get("/").text
    help_ = client.get("/help").text
    assert "<title>Exactly Print · Print an image at an exact size in mm or cm</title>" in home
    assert "<title>Why a print comes out the wrong size, and how to fix it · Exactly Print" in help_
    assert 'content="Upload an image, type its width or height in mm or cm' in home
    assert 'content="Why a printed image comes out a few percent too small or large' in help_
    assert '<meta property="og:type" content="website" />' in home
    assert '<meta property="og:type" content="article" />' in help_


def _structured_data(html: str) -> dict:
    import json

    start = html.index('<script type="application/ld+json">') + len(
        '<script type="application/ld+json">'
    )
    return json.loads(html[start : html.index("</script>", start)])


def test_structured_data_describes_the_app_and_the_help():
    home = _structured_data(client.get("/").text)
    types = {node["@type"] for node in home["@graph"]}
    assert types == {"WebSite", "Person", "WebApplication", "WebPage"}
    app_node = next(n for n in home["@graph"] if n["@type"] == "WebApplication")
    assert app_node["url"] == "http://testserver/"
    assert app_node["isAccessibleForFree"] is True
    assert app_node["softwareHelp"]["url"] == "http://testserver/help"

    help_ = _structured_data(client.get("/help").text)
    types = {node["@type"] for node in help_["@graph"]}
    assert {"HowTo", "FAQPage", "BreadcrumbList"} <= types
    howto = next(n for n in help_["@graph"] if n["@type"] == "HowTo")
    assert [s["position"] for s in howto["step"]] == [1, 2, 3, 4, 5]


def test_site_url_can_be_configured_for_a_proxy(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://exactly.example.com/")
    r = client.get("/help")
    assert '<link rel="canonical" href="https://exactly.example.com/help" />' in r.text
    assert 'content="https://exactly.example.com/static/og.png"' in r.text
    assert "Sitemap: https://exactly.example.com/sitemap.xml" in client.get("/robots.txt").text


def test_robots_sitemap_and_favicon_are_served():
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert robots.headers["content-type"].startswith("text/plain")
    assert "Disallow: /preview" in robots.text
    assert "Disallow: /pdf" in robots.text
    assert "Sitemap: http://testserver/sitemap.xml" in robots.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert "<loc>http://testserver/</loc>" in sitemap.text
    assert "<loc>http://testserver/help</loc>" in sitemap.text

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"] == "image/x-icon"
    assert favicon.content[:4] == b"\x00\x00\x01\x00"

    for path in ("/static/og.png", "/static/favicon.svg", "/static/manifest.webmanifest"):
        assert client.get(path).status_code == 200, path


def test_analytics_only_on_vercel(monkeypatch):
    tag = '<script defer src="/_vercel/insights/script.js"></script>'
    monkeypatch.delenv("VERCEL", raising=False)
    assert tag not in client.get("/").text
    monkeypatch.setenv("VERCEL", "1")
    for path in ("/", "/help"):
        assert tag in client.get(path).text.split("</head>")[0]


def test_the_api_docs_are_not_published():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
