"""The web app: one page, one preview partial, one PDF endpoint.

Nothing is stored. The browser keeps the file in its file input and sends it
again with every preview and every download, so the server holds an image
only for the length of a request.
"""

import base64
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps, UnidentifiedImageError

from .layout import MM_PER_UNIT, PAPERS, DoesNotFit, Layout, LayoutError, plan, to_mm
from .pdf import write_pdf
from .preview import render_preview

MAX_UPLOAD = 25 * 1024 * 1024

HERE = Path(__file__).parent
app = FastAPI(title="Exactly Print")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

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


def build(
    image: Image.Image, width: str, height: str, unit: str, paper: str, orientation: str
) -> Layout:
    if unit not in MM_PER_UNIT:
        raise RequestError("Pick mm or cm.")
    try:
        w, h = parse_length(width, unit), parse_length(height, unit)
        return plan(image.size, w, h, paper, orientation)
    except DoesNotFit as e:
        raise RequestError(e.message(unit)) from e
    except LayoutError as e:
        raise RequestError(str(e)) from e


def fmt_size(mm: float, unit: str) -> str:
    value = mm / MM_PER_UNIT[unit]
    return f"{value:.1f}".rstrip("0").rstrip(".")


def index_page(request: Request, error: str | None = None):
    context = {"papers": list(PAPERS), "units": list(MM_PER_UNIT), "error": error}
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return index_page(request)


@app.post("/preview", response_class=HTMLResponse)
async def preview(
    request: Request,
    image: UploadFile | None = File(None),
    width: str = Form(""),
    height: str = Form(""),
    unit: str = Form("mm"),
    paper: str = Form("A4"),
    orientation: str = Form("auto"),
):
    try:
        img = await read_image(image)
        layout = build(img, width, height, unit, paper, orientation)
    except RequestError as e:
        return templates.TemplateResponse(request, "_preview.html", {"error": str(e)})
    png = render_preview(layout, img)
    return templates.TemplateResponse(
        request,
        "_preview.html",
        {
            "png": base64.b64encode(png).decode(),
            "layout": layout,
            "unit": unit,
            "trim_w": fmt_size(layout.trim.w, unit),
            "trim_h": fmt_size(layout.trim.h, unit),
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
    disposition: str = Form("attachment"),
):
    try:
        img = await read_image(image)
        layout = build(img, width, height, unit, paper, orientation)
    except RequestError as e:
        return index_page(request, str(e))
    data = write_pdf(layout, img)
    name = f"exactly-print-{layout.trim.w:.0f}x{layout.trim.h:.0f}mm-{layout.paper}.pdf"
    kind = "inline" if disposition == "inline" else "attachment"
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{kind}; filename="{name}"'},
    )
