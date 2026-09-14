# Exactly Print

Upload an image, pick a size, print it exactly that size.

Printing an image at a real-world size is harder than it should be: the print dialog quietly scales the page, the image has no physical size of its own, and a hand cut needs something to run along. Exactly Print lays the image out on a sheet of paper as a PDF, with:

- the image at the size you asked for, placed by physical millimetres, not pixels;
- a 2 mm bleed past the cut line, so a slightly imprecise cut still shows image, not paper;
- crop marks in the four corners;
- two 100 mm rulers, one along the bottom and one up the left edge, so a test print tells you whether the printer scaled the page, and by how much in each direction;
- a per-printer calibration, so a printer that always comes out a little small or large can be corrected once and forgotten.

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

When the site is served behind a proxy or on a domain of its own, set `SITE_URL` to its public origin, for example `SITE_URL=https://print.example.com`. It is what the canonical links, the link-preview tags, `robots.txt` and `sitemap.xml` name; without it the app uses the address each request arrived at.

## Use it

1. Choose an image.
2. Type a width, a height, or both, in mm or cm. With one side given, the other is filled in from the image's proportions and marked *auto* until you type over it; with both, the image is scaled to cover the size and cropped evenly on the longer side.
3. Pick the paper size. Orientation is automatic unless you set it.
4. The preview updates as you type. The red line is where you cut.
5. **Download PDF**, or **Open to print** and print from the browser.
6. Print at **100% / "Actual size"** on the paper size the page names. Never "Fit to page". Measure the rulers on the first print: if both are 100 mm, the image is the size you asked for.

## Calibrate a printer

Print dialogs and drivers like to scale the page a few percent, and even at 100% the rollers and the heat of a printer stretch or shrink the sheet by a fraction, usually more along the direction the paper travels than across it. If the rulers on every print from one printer are off by the same amount, that printer can be calibrated:

1. Under **Printer**, leave the calibration on **None** and print a page at 100%.
2. Measure both rulers from the 0 to the 100 mark.
3. Click **Calibrate…**, name the printer and type what the bottom and the left ruler measured.

From then on, with that printer chosen, the whole page is drawn 100 ÷ measured times its real size, across and down separately, so the printer's own scaling brings both rulers back to 100 mm. A second round stacks on the first: choose the printer under *The page was printed with* and enter the new measurements. Printers are saved in the browser's local storage, on that device only; the server receives just the factor and the name along with each request. The **Help** section on the page explains the causes in more detail.

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
  seo.py        titles, descriptions, schema.org data, robots.txt, sitemap.xml
  templates/    index.html, help.html and the htmx partial
  static/       stylesheet, the calibration script, a vendored htmx, icons
scripts/
  icons.py      redraws the icons and the link-preview image in static/
```

## Develop

```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat(layout): add A3`.

## License

MIT.
