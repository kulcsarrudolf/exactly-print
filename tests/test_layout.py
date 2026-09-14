import pytest

from exactly_print.layout import (
    BLEED,
    MARGIN,
    SIDE_BAND,
    DoesNotFit,
    LayoutError,
    plan,
    target_size,
    to_mm,
)


def test_missing_side_follows_aspect_ratio():
    assert target_size((1000, 2000), 100, None) == (100, 200)
    assert target_size((1000, 2000), None, 200) == (100, 200)


def test_both_sides_are_kept_as_given():
    assert target_size((1000, 2000), 120, 170) == (120, 170)


def test_no_size_is_refused():
    with pytest.raises(LayoutError):
        target_size((1000, 2000), None, None)


def test_zero_is_refused():
    with pytest.raises(LayoutError):
        target_size((1000, 2000), 0, None)


def test_units():
    assert to_mm(12, "cm") == 120
    assert to_mm(12, "mm") == 12
    assert to_mm(None, "cm") is None
    with pytest.raises(LayoutError):
        to_mm(1, "in")


def test_invitation_on_a4():
    layout = plan((1488, 2078), 120, 170, "A4")
    assert (layout.page_w, layout.page_h) == (210, 297)
    assert (layout.trim.w, layout.trim.h) == (120, 170)
    # Centred between the side band and the margin, not on the sheet.
    assert layout.trim.x == pytest.approx(52)
    assert layout.bleed.w == 120 + 2 * BLEED
    # The image covers the bleed box: as tall as it, wider, centred.
    assert layout.image.h == pytest.approx(174)
    assert layout.image.w > layout.bleed.w
    assert layout.image.x < layout.bleed.x
    assert round(layout.dpi) == 303
    assert len(layout.marks) == 8


def test_too_large_is_refused_with_the_limit():
    with pytest.raises(DoesNotFit) as info:
        plan((100, 100), 200, 200, "A4")
    assert str(info.value) == (
        "200 × 200 mm does not fit on A4 (210 × 297 mm). "
        "The largest that fits with the rulers and the bleed is 180 × 261 mm."
    )
    assert info.value.message("cm") == (
        "20 × 20 cm does not fit on A4 (21 × 29.7 cm). "
        "The largest that fits with the rulers and the bleed is 18 × 26.1 cm."
    )


def test_describe_says_the_settings_in_the_unit():
    layout = plan((1488, 2078), 120, 170, "A4")
    assert layout.describe() == (
        "Image 120 × 170 mm  ·  Paper A4 portrait, 210 × 297 mm  ·  Bleed 2 mm  ·  303 dpi"
    )
    assert layout.describe("cm").startswith("Image 12 × 17 cm  ·  Paper A4 portrait, 21 × 29.7 cm")
    assert plan((3000, 2000), 240, None, "A4").orientation == "landscape"


def test_auto_orientation_goes_landscape_only_when_portrait_cannot_hold_it():
    layout = plan((3000, 2000), 240, None, "A4")
    assert (layout.page_w, layout.page_h) == (297, 210)


def test_auto_orientation_stays_portrait_for_a_small_wide_image():
    layout = plan((3000, 2000), 90, None, "A4")
    assert (layout.page_w, layout.page_h) == (210, 297)


def test_forced_portrait_refuses_what_only_fits_landscape():
    with pytest.raises(LayoutError):
        plan((3000, 2000), 240, None, "A4", "portrait")


def test_soft_flag():
    assert plan((300, 300), 100, None).soft
    assert not plan((3000, 3000), 100, None).soft


def test_the_two_rulers_share_a_corner():
    layout = plan((1488, 2078), 120, 170, "A4")
    assert layout.ruler_y == 17
    assert layout.side_ruler_x == 7
    assert layout.ruler_len == layout.side_ruler_len == 100
    # The left ruler's ticks stay left of the image's crop marks.
    assert layout.bleed.x - 8 > layout.side_ruler_x + 5


def test_calibration_draws_the_page_larger_but_reports_the_print():
    plain = plan((1488, 2078), 120, 170, "A4")
    layout = plan((1488, 2078), 120, 170, "A4", scale_x=1.02, scale_y=1.01)
    # The sheet is still the real A4; the drawing on it is larger, each way
    # by its own factor.
    assert (layout.page_w, layout.page_h) == (210, 297)
    assert layout.trim.w == pytest.approx(120 * 1.02)
    assert layout.trim.h == pytest.approx(170 * 1.01)
    assert layout.ruler_len == pytest.approx(102)
    assert layout.side_ruler_len == pytest.approx(101)
    assert layout.side_ruler_x == pytest.approx(7 * 1.02)
    assert layout.ruler_y == pytest.approx(17 * 1.01)
    # Still centred between the side band and the margin, both drawn scaled.
    centre = (SIDE_BAND * 1.02 + 210 - MARGIN * 1.02) / 2
    assert layout.trim.x + layout.trim.w / 2 == pytest.approx(centre)
    # The resolution is that of the print, which is what the eye sees.
    assert layout.dpi == pytest.approx(plain.dpi)
    assert layout.marks[0][2] - layout.marks[0][0] == pytest.approx(-7 * 1.02)
    assert layout.marks[1][3] - layout.marks[1][1] == pytest.approx(-7 * 1.01)


def test_calibration_leaves_less_room_on_the_sheet():
    plan((100, 100), 180, 100, "A4", "portrait")
    with pytest.raises(DoesNotFit) as info:
        plan((100, 100), 180, 100, "A4", "portrait", scale_x=1.05, scale_y=1.05)
    assert "does not fit on A4 (210 × 297 mm)" in str(info.value)
    assert "170 × 246.9 mm" in str(info.value)


def test_calibration_out_of_range_is_a_setting_not_a_printer():
    with pytest.raises(LayoutError) as info:
        plan((100, 100), 50, None, scale_x=1.5)
    assert "×1.500 across means the ruler measured 67 mm" in str(info.value)
    assert "print setting" in str(info.value)
    with pytest.raises(LayoutError) as info:
        plan((100, 100), 50, None, scale_y=0.7)
    assert "×0.700 down" in str(info.value)


def test_describe_names_the_printer_in_real_millimetres():
    layout = plan((1488, 2078), 120, 170, "A4", scale_x=100 / 98, scale_y=100 / 99)
    text = layout.describe("mm", "HP LaserJet")
    assert text.startswith("Image 120 × 170 mm  ·  Paper A4 portrait, 210 × 297 mm")
    assert text.endswith("Calibrated for HP LaserJet, drawn at ×1.020 across, ×1.010 down")
    assert plan((1488, 2078), 120, 170, "A4").describe("mm", "").endswith("dpi")
    same = plan((1488, 2078), 120, 170, "A4", scale_x=0.99, scale_y=0.99)
    assert same.describe().endswith("Calibrated, drawn at ×0.990")
