# Exactly Print

Upload an image, pick a size, print it exactly that size.

Printing an image at a real-world size is harder than it should be: the print dialog quietly scales the page, the image has no physical size of its own, and a hand cut needs something to run along. Exactly Print lays the image out on a sheet of paper as a PDF, with:

- the image at the size you asked for, placed by physical millimetres, not pixels;
- a 2 mm bleed past the cut line, so a slightly imprecise cut still shows image, not paper;
- crop marks in the four corners;
- a 100 mm ruler along the bottom, so one measurement on a test print tells you whether the printer scaled the page.

Nothing is stored: the browser sends the image with every preview and every download, and the server holds it only for the length of the request.

## Run it

```bash
docker compose up
```

Then open <http://localhost:8000>.

Without Docker, with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run uvicorn exactly_print.app:app --reload
```

## Use it

1. Choose an image.
2. Type a width, a height, or both, in mm or cm. With one side given, the other follows the image's proportions; with both, the image is scaled to cover the size and cropped evenly on the longer side.
3. Pick the paper size. Orientation is automatic unless you set it.
4. The preview updates as you type. The red line is where you cut.
5. **Download PDF**, or **Open to print** and print from the browser.
6. Print at **100% / "Actual size"** on the paper size the page names. Never "Fit to page". Measure the ruler on the first print: if it is 100 mm, the image is the size you asked for.

## How it is built

- [FastAPI](https://fastapi.tiangolo.com/) serves one page, an [htmx](https://htmx.org/) preview partial and the PDF.
- [Pillow](https://python-imaging.github.io/) reads the upload and draws the preview.
- The PDF is written by hand in `pdf.py`: one page, one image, a few lines and a bit of Helvetica. JPEG uploads travel inside the PDF as JPEG; everything else is deflated losslessly.
- `layout.py` is the single source of the geometry. The PDF and the preview both draw from it, so they cannot disagree.

```
src/exactly_print/
  app.py        routes and form parsing
  layout.py     paper sizes, units, where everything sits (pure, tested)
  pdf.py        the PDF writer
  preview.py    the page as a PNG
  templates/    index.html and the htmx partial
  static/       stylesheet and a vendored htmx
```

## Develop

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat(layout): add A3`.

## License

MIT.
