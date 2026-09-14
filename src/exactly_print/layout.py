"""Where everything sits on the page, in millimetres.

The PDF writer and the preview renderer both draw from a `Layout`, so the
printed page and the preview can never disagree. Coordinates follow PDF:
the origin is the bottom-left corner of the page and y grows upwards.
"""

from dataclasses import dataclass

PAPERS: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
}

MM_PER_UNIT: dict[str, float] = {"mm": 1.0, "cm": 10.0}

# The image runs this far past the trim line so an imprecise cut never shows
# white paper.
BLEED = 2.0
# Nothing is drawn closer to the paper edge than this; home printers cannot
# reach it.
MARGIN = 6.0
# The strip along the bottom edge kept for the ruler and the notes.
RULER_BAND = 26.0
RULER_LEN = 100.0
# The ruler's baseline; the settings and the notes hang below it, the
# numbers sit above.
RULER_Y = 17.0
# Crop marks start this far outside the trim corner and run this long.
MARK_GAP = 3.0
MARK_LEN = 7.0
# Below this the print starts to look soft at reading distance.
SOFT_DPI = 150
# A calibrated printer may scale the page by this much either way (a ruler
# measuring 80 to 125 mm). Anything beyond that is a print setting, not the
# printer.
MIN_SCALE = 0.8
MAX_SCALE = 1.25


class LayoutError(ValueError):
    """The request cannot be laid out; the message is shown to the user."""


@dataclass
class DoesNotFit(LayoutError):
    """The trim box is too large for the page. Sizes are in millimetres;
    `message` says them in whatever unit the user typed."""

    paper: str
    trim_w: float
    trim_h: float
    page_w: float
    page_h: float
    max_w: float
    max_h: float

    def message(self, unit: str = "mm") -> str:
        def s(mm: float) -> str:
            return f"{mm / MM_PER_UNIT[unit]:.1f}".rstrip("0").rstrip(".")

        return (
            f"{s(self.trim_w)} × {s(self.trim_h)} {unit} does not fit on {self.paper} "
            f"({s(self.page_w)} × {s(self.page_h)} {unit}). The largest that fits with "
            f"the ruler and the bleed is {s(self.max_w)} × {s(self.max_h)} {unit}."
        )

    def __str__(self) -> str:
        return self.message()


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y + self.h

    def scaled(self, k: float) -> "Box":
        return Box(self.x * k, self.y * k, self.w * k, self.h * k)


@dataclass(frozen=True)
class Layout:
    """Everything is in millimetres on the page as drawn. With a calibrated
    printer the drawing is `scale` times its real size, so the printer's own
    scaling brings it back; `dpi` and `describe` still speak of the print."""

    paper: str
    page_w: float
    page_h: float
    trim: Box
    bleed: Box
    # Where the whole image is drawn. It covers the bleed box, and whatever
    # sticks out of the bleed box is clipped away.
    image: Box
    ruler_x: float
    ruler_y: float
    dpi: float
    scale: float = 1.0

    @property
    def ruler_len(self) -> float:
        """The ruler as drawn; it comes off the printer as RULER_LEN."""
        return RULER_LEN * self.scale

    @property
    def marks(self) -> list[tuple[float, float, float, float]]:
        """Two short lines at each trim corner, kept clear of the bleed."""
        gap, end = MARK_GAP * self.scale, (MARK_GAP + MARK_LEN) * self.scale
        lines = []
        for cx, sx in ((self.trim.x, -1), (self.trim.right, 1)):
            for cy, sy in ((self.trim.y, -1), (self.trim.top, 1)):
                lines.append((cx + sx * gap, cy, cx + sx * end, cy))
                lines.append((cx, cy + sy * gap, cx, cy + sy * end))
        return lines

    @property
    def soft(self) -> bool:
        return self.dpi < SOFT_DPI

    @property
    def orientation(self) -> str:
        return "landscape" if self.page_w > self.page_h else "portrait"

    def describe(self, unit: str = "mm", printer: str = "") -> str:
        """The settings in one line, printed under the ruler so a sheet
        found in a drawer still says what it was made for."""
        k = self.scale

        def s(mm: float) -> str:
            return f"{mm / k / MM_PER_UNIT[unit]:.1f}".rstrip("0").rstrip(".")

        text = (
            f"Image {s(self.trim.w)} × {s(self.trim.h)} {unit}  ·  "
            f"Paper {self.paper} {self.orientation}, {s(self.page_w * k)} × {s(self.page_h * k)} "
            f"{unit}  ·  Bleed {BLEED:g} mm  ·  {self.dpi:.0f} dpi"
        )
        if printer or k != 1:
            who = f" for {printer}" if printer else ""
            text += f"  ·  Calibrated{who}, drawn at ×{k:.3f}"
        return text


def to_mm(value: float | None, unit: str) -> float | None:
    if unit not in MM_PER_UNIT:
        raise LayoutError(f"Unknown unit: {unit}")
    return None if value is None else value * MM_PER_UNIT[unit]


def target_size(
    image_px: tuple[int, int], width_mm: float | None, height_mm: float | None
) -> tuple[float, float]:
    """The trim size. A missing side follows the image's aspect ratio."""
    iw, ih = image_px
    if width_mm is None and height_mm is None:
        raise LayoutError("Give a width, a height, or both.")
    if (width_mm is not None and width_mm <= 0) or (height_mm is not None and height_mm <= 0):
        raise LayoutError("The size has to be larger than zero.")
    if width_mm is None:
        width_mm = height_mm * iw / ih
    elif height_mm is None:
        height_mm = width_mm * ih / iw
    return width_mm, height_mm


def _page(
    paper: str, orientation: str, trim_w: float, trim_h: float, scale: float = 1.0
) -> tuple[float, float]:
    if paper not in PAPERS:
        raise LayoutError(f"Unknown paper size: {paper}")
    short, long = PAPERS[paper]
    if orientation == "portrait":
        return short, long
    if orientation == "landscape":
        return long, short
    if orientation != "auto":
        raise LayoutError(f"Unknown orientation: {orientation}")
    # Auto: portrait, the way paper sits in the tray, unless only landscape
    # fits. The print is cut out anyway, so its own orientation does not matter.
    if _fits(short / scale, long / scale, trim_w, trim_h) or not _fits(
        long / scale, short / scale, trim_w, trim_h
    ):
        return short, long
    return long, short


def _fits(page_w: float, page_h: float, trim_w: float, trim_h: float) -> bool:
    return (
        trim_w + 2 * BLEED <= page_w - 2 * MARGIN
        and trim_h + 2 * BLEED <= page_h - MARGIN - RULER_BAND
    )


def plan(
    image_px: tuple[int, int],
    width_mm: float | None,
    height_mm: float | None,
    paper: str = "A4",
    orientation: str = "auto",
    scale: float = 1.0,
) -> Layout:
    """Lay the image out on the paper.

    `scale` is the printer's calibration: a printer whose ruler came out at
    98 mm gets 100 / 98, and everything is drawn that much larger about the
    centre of the page so it comes off the printer at its real size.
    """
    if not MIN_SCALE <= scale <= MAX_SCALE:
        raise LayoutError(
            f"A calibration of ×{scale:.3f} means the ruler measured {100 / scale:.0f} mm. "
            f"That far off is a print setting, not the printer: print at 100% / "
            f'"Actual size" and calibrate again.'
        )
    trim_w, trim_h = target_size(image_px, width_mm, height_mm)
    page_w, page_h = _page(paper, orientation, trim_w, trim_h, scale)
    # Lay the page out in printed millimetres on the sheet as the printer
    # will shrink or stretch it, then scale the drawing to the real sheet.
    sheet_w, sheet_h = page_w / scale, page_h / scale
    if not _fits(sheet_w, sheet_h, trim_w, trim_h):
        raise DoesNotFit(
            paper,
            trim_w,
            trim_h,
            page_w,
            page_h,
            max_w=sheet_w - 2 * MARGIN - 2 * BLEED,
            max_h=sheet_h - MARGIN - RULER_BAND - 2 * BLEED,
        )

    # Centre the trim box in the space above the ruler band.
    trim = Box(
        (sheet_w - trim_w) / 2,
        RULER_BAND + (sheet_h - RULER_BAND - MARGIN - trim_h) / 2,
        trim_w,
        trim_h,
    )
    bleed = Box(trim.x - BLEED, trim.y - BLEED, trim_w + 2 * BLEED, trim_h + 2 * BLEED)

    # Scale the image to cover the bleed box without distortion; the overflow
    # on the longer side is clipped evenly from both ends.
    iw, ih = image_px
    fit = max(bleed.w / iw, bleed.h / ih)
    draw_w, draw_h = iw * fit, ih * fit
    image = Box(bleed.x + (bleed.w - draw_w) / 2, bleed.y + (bleed.h - draw_h) / 2, draw_w, draw_h)

    return Layout(
        paper=paper,
        page_w=page_w,
        page_h=page_h,
        trim=trim.scaled(scale),
        bleed=bleed.scaled(scale),
        image=image.scaled(scale),
        ruler_x=(sheet_w - RULER_LEN) / 2 * scale,
        ruler_y=RULER_Y * scale,
        dpi=iw / (draw_w / 25.4),
        scale=scale,
    )
