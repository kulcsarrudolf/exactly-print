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
# The strip along the left edge kept for the vertical ruler: its numbers
# and the crop marks of the image must not run into each other.
SIDE_BAND = 20.0
RULER_LEN = 100.0
# The bottom ruler's baseline; the settings and the notes hang below it,
# the numbers sit above. The left ruler starts on the same line.
RULER_Y = 17.0
# The left ruler's line; its ticks and numbers sit to the right of it.
RULER_X = 7.0
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


class Incomplete(LayoutError):
    """Nothing is wrong yet: a field the layout needs is still empty. Worth
    telling apart from a mistake, so the page can ask rather than complain."""


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
            f"the rulers and the bleed is {s(self.max_w)} × {s(self.max_h)} {unit}."
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

    def scaled(self, kx: float, ky: float) -> "Box":
        return Box(self.x * kx, self.y * ky, self.w * kx, self.h * ky)


@dataclass(frozen=True)
class Layout:
    """Everything is in millimetres on the page as drawn. With a calibrated
    printer the drawing is `scale_x` times its real width and `scale_y` times
    its real height, so the printer's own scaling brings it back; `dpi` and
    `describe` still speak of the print."""

    paper: str
    page_w: float
    page_h: float
    trim: Box
    bleed: Box
    # Where the whole image is drawn. It covers the bleed box, and whatever
    # sticks out of the bleed box is clipped away.
    image: Box
    # The bottom ruler starts here and runs right; the left ruler starts at
    # (side_ruler_x, ruler_y) and runs up.
    ruler_x: float
    ruler_y: float
    side_ruler_x: float
    dpi: float
    scale_x: float = 1.0
    scale_y: float = 1.0

    @property
    def ruler_len(self) -> float:
        """The bottom ruler as drawn; it comes off the printer as RULER_LEN."""
        return RULER_LEN * self.scale_x

    @property
    def side_ruler_len(self) -> float:
        """The left ruler as drawn; it comes off the printer as RULER_LEN."""
        return RULER_LEN * self.scale_y

    @property
    def marks(self) -> list[tuple[float, float, float, float]]:
        """Two short lines at each trim corner, kept clear of the bleed."""
        kx, ky = self.scale_x, self.scale_y
        lines = []
        for cx, sx in ((self.trim.x, -1), (self.trim.right, 1)):
            for cy, sy in ((self.trim.y, -1), (self.trim.top, 1)):
                lines.append(
                    (cx + sx * MARK_GAP * kx, cy, cx + sx * (MARK_GAP + MARK_LEN) * kx, cy)
                )
                lines.append(
                    (cx, cy + sy * MARK_GAP * ky, cx, cy + sy * (MARK_GAP + MARK_LEN) * ky)
                )
        return lines

    @property
    def calibrated(self) -> bool:
        return self.scale_x != 1 or self.scale_y != 1

    def drawn_at(self) -> str:
        """The correction as text: one factor when both directions agree."""
        if self.scale_x == self.scale_y:
            return f"×{self.scale_x:.3f}"
        return f"×{self.scale_x:.3f} across, ×{self.scale_y:.3f} down"

    @property
    def soft(self) -> bool:
        return self.dpi < SOFT_DPI

    @property
    def orientation(self) -> str:
        return "landscape" if self.page_w > self.page_h else "portrait"

    def describe(self, unit: str = "mm", printer: str = "") -> str:
        """The settings in one line, printed under the ruler so a sheet
        found in a drawer still says what it was made for."""

        def s(mm: float) -> str:
            return f"{mm / MM_PER_UNIT[unit]:.1f}".rstrip("0").rstrip(".")

        text = (
            f"Image {s(self.trim.w / self.scale_x)} × {s(self.trim.h / self.scale_y)} {unit}  ·  "
            f"Paper {self.paper} {self.orientation}, {s(self.page_w)} × {s(self.page_h)} {unit}"
            f"  ·  Bleed {BLEED:g} mm  ·  {self.dpi:.0f} dpi"
        )
        if printer or self.calibrated:
            who = f" for {printer}" if printer else ""
            text += f"  ·  Calibrated{who}, drawn at {self.drawn_at()}"
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
        raise Incomplete("Give a width, a height, or both.")
    if (width_mm is not None and width_mm <= 0) or (height_mm is not None and height_mm <= 0):
        raise LayoutError("The size has to be larger than zero.")
    if width_mm is None:
        width_mm = height_mm * iw / ih
    elif height_mm is None:
        height_mm = width_mm * ih / iw
    return width_mm, height_mm


def _page(
    paper: str, orientation: str, trim_w: float, trim_h: float, kx: float = 1.0, ky: float = 1.0
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
    if _fits(short / kx, long / ky, trim_w, trim_h) or not _fits(
        long / kx, short / ky, trim_w, trim_h
    ):
        return short, long
    return long, short


def _fits(page_w: float, page_h: float, trim_w: float, trim_h: float) -> bool:
    return (
        trim_w + 2 * BLEED <= page_w - SIDE_BAND - MARGIN
        and trim_h + 2 * BLEED <= page_h - MARGIN - RULER_BAND
    )


def _check_scale(scale: float, direction: str) -> None:
    if not MIN_SCALE <= scale <= MAX_SCALE:
        raise LayoutError(
            f"A calibration of ×{scale:.3f} {direction} means the ruler measured "
            f"{100 / scale:.0f} mm. That far off is a print setting, not the printer: "
            f'print at 100% / "Actual size" and calibrate again.'
        )


def plan(
    image_px: tuple[int, int],
    width_mm: float | None,
    height_mm: float | None,
    paper: str = "A4",
    orientation: str = "auto",
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> Layout:
    """Lay the image out on the paper.

    `scale_x` and `scale_y` are the printer's calibration: a printer whose
    bottom ruler came out at 98 mm gets 100 / 98 across, and everything is
    drawn that much wider about the centre of the page so it comes off the
    printer at its real size. The left ruler does the same for the height.
    """
    _check_scale(scale_x, "across")
    _check_scale(scale_y, "down")
    trim_w, trim_h = target_size(image_px, width_mm, height_mm)
    page_w, page_h = _page(paper, orientation, trim_w, trim_h, scale_x, scale_y)
    # Lay the page out in printed millimetres on the sheet as the printer
    # will shrink or stretch it, then scale the drawing to the real sheet.
    sheet_w, sheet_h = page_w / scale_x, page_h / scale_y
    if not _fits(sheet_w, sheet_h, trim_w, trim_h):
        raise DoesNotFit(
            paper,
            trim_w,
            trim_h,
            page_w,
            page_h,
            max_w=sheet_w - SIDE_BAND - MARGIN - 2 * BLEED,
            max_h=sheet_h - MARGIN - RULER_BAND - 2 * BLEED,
        )

    # Centre the trim box in the space right of the side band and above
    # the ruler band.
    trim = Box(
        SIDE_BAND + (sheet_w - SIDE_BAND - MARGIN - trim_w) / 2,
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
        trim=trim.scaled(scale_x, scale_y),
        bleed=bleed.scaled(scale_x, scale_y),
        image=image.scaled(scale_x, scale_y),
        ruler_x=(sheet_w - RULER_LEN) / 2 * scale_x,
        ruler_y=RULER_Y * scale_y,
        side_ruler_x=RULER_X * scale_x,
        dpi=iw / (draw_w / 25.4),
        scale_x=scale_x,
        scale_y=scale_y,
    )
