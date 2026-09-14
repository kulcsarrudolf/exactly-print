"""The web app: one page, a help page, one preview partial, one PDF endpoint,
and the few files crawlers and browsers ask for on their own.

Nothing is stored. The browser keeps the file in its file input and sends it
again with every preview and every download, so the server holds an image
only for the length of a request.
"""

import base64
import os
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps, UnidentifiedImageError

from . import seo
from .layout import MM_PER_UNIT, PAPERS, DoesNotFit, Layout, LayoutError, plan, to_mm
from .pdf import write_pdf
from .preview import render_preview

MAX_UPLOAD = 25 * 1024 * 1024

HERE = Path(__file__).parent
# No API docs: the form endpoints are not an API, and crawlers would index the pages.
app = FastAPI(title=seo.NAME, description=seo.TAGLINE, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals["seo"] = seo
# Vercel serves the analytics script itself at /_vercel/insights/, so the tag
# only belongs on pages served from there; anywhere else it would 404.
templates.env.globals["on_vercel"] = lambda: bool(os.environ.get("VERCEL"))

Image.MAX_IMAGE_PIXELS = 80_000_000


class RequestError(ValueError):
    """A problem with the upload, worded for the user."""


async def read_image(upload: UploadFile | None) -> Image.Image:
    if upload is None or not upload.filename:
        raise RequestError("Choose an image first.")
    data = await upload.read()
    if len(data) > MAX_UPLOAD:
        raise RequestError("The image is larger than 25 MB.")
    try:
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as e:
        raise RequestError("That file is not an image the server can read.") from e
    fmt = image.format
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        flat = Image.new("RGB", image.size, (255, 255, 255))
        flat.paste(image, mask=image.split()[-1])
        image = flat
    elif image.mode != "RGB":
        image = image.convert("RGB")
    image.format = fmt
    return image


def parse_length(raw: str, unit: str) -> float | None:
    raw = raw.strip().replace(",", ".")
    if not raw:
        return None
    try:
        return to_mm(float(raw), unit)
    except ValueError as e:
        raise RequestError(f"'{raw}' is not a number.") from e


def parse_scale(raw: str) -> float:
    """One of the printer's calibration factors, sent by the browser from the
    printer the user picked; an empty field means an uncalibrated printer."""
    raw = raw.strip().replace(",", ".")
    if not raw:
        return 1.0
    try:
        return float(raw)
    except ValueError as e:
        raise RequestError(f"'{raw}' is not a calibration factor.") from e


def build(
    image: Image.Image,
    width: str,
    height: str,
    unit: str,
    paper: str,
    orientation: str,
    scale_x: str = "",
    scale_y: str = "",
) -> Layout:
    if unit not in MM_PER_UNIT:
        raise RequestError("Pick mm or cm.")
    try:
        w, h = parse_length(width, unit), parse_length(height, unit)
        kx, ky = parse_scale(scale_x), parse_scale(scale_y)
        return plan(image.size, w, h, paper, orientation, kx, ky)
    except DoesNotFit as e:
        raise RequestError(e.message(unit)) from e
    except LayoutError as e:
        raise RequestError(str(e)) from e


def fmt_size(mm: float, unit: str) -> str:
    value = mm / MM_PER_UNIT[unit]
    return f"{value:.1f}".rstrip("0").rstrip(".")


def index_page(request: Request, error: str | None = None):
    page = seo.index_page(request)
    context = {
        "papers": list(PAPERS),
        "units": list(MM_PER_UNIT),
        "error": error,
        "page": page,
        "structured_data": seo.index_graph(page),
    }
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return index_page(request)


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    page = seo.help_page(request)
    context = {"page": page, "structured_data": seo.help_graph(page)}
    return templates.TemplateResponse(request, "help.html", context)


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots(request: Request):
    return seo.robots_txt(seo.site_url(request))


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request):
    return Response(seo.sitemap_xml(seo.site_url(request)), media_type="application/xml")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Browsers and crawlers ask for it at the root without reading the page.
    return FileResponse(HERE / "static" / "favicon.ico", media_type="image/x-icon")


@app.post("/preview", response_class=HTMLResponse)
async def preview(
    request: Request,
    image: UploadFile | None = File(None),
    width: str = Form(""),
    height: str = Form(""),
    unit: str = Form("mm"),
    paper: str = Form("A4"),
    orientation: str = Form("auto"),
    scale_x: str = Form(""),
    scale_y: str = Form(""),
    printer: str = Form(""),
):
    try:
        img = await read_image(image)
        layout = build(img, width, height, unit, paper, orientation, scale_x, scale_y)
    except RequestError as e:
        return templates.TemplateResponse(request, "_preview.html", {"error": str(e)})
    printer = printer.strip()
    png = render_preview(layout, img, layout.describe(unit, printer))
    return templates.TemplateResponse(
        request,
        "_preview.html",
        {
            "png": base64.b64encode(png).decode(),
            "layout": layout,
            "unit": unit,
            "printer": printer,
            "prints_at_x": f"{100 / layout.scale_x:.1f}",
            "prints_at_y": f"{100 / layout.scale_y:.1f}",
            # The size on paper, not the slightly scaled drawing of it.
            "trim_w": fmt_size(layout.trim.w / layout.scale_x, unit),
            "trim_h": fmt_size(layout.trim.h / layout.scale_y, unit),
            "page_w": fmt_size(layout.page_w, unit),
            "page_h": fmt_size(layout.page_h, unit),
            "dpi": round(layout.dpi),
        },
    )


@app.post("/pdf")
async def pdf(
    request: Request,
    image: UploadFile | None = File(None),
    width: str = Form(""),
    height: str = Form(""),
    unit: str = Form("mm"),
    paper: str = Form("A4"),
    orientation: str = Form("auto"),
    scale_x: str = Form(""),
    scale_y: str = Form(""),
    printer: str = Form(""),
    disposition: str = Form("attachment"),
):
    try:
        img = await read_image(image)
        layout = build(img, width, height, unit, paper, orientation, scale_x, scale_y)
    except RequestError as e:
        return index_page(request, str(e))
    data = write_pdf(layout, img, layout.describe(unit, printer.strip()))
    name = f"exactly-print-{layout.trim.w:.0f}x{layout.trim.h:.0f}mm-{layout.paper}.pdf"
    kind = "inline" if disposition == "inline" else "attachment"
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{kind}; filename="{name}"'},
    )
