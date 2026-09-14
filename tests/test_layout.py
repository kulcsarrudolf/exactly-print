import pytest

from exactly_print.layout import BLEED, DoesNotFit, LayoutError, plan, target_size, to_mm


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
    assert layout.trim.x == pytest.approx(45)
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
        "The largest that fits with the ruler and the bleed is 194 × 261 mm."
    )
    assert info.value.message("cm") == (
        "20 × 20 cm does not fit on A4 (21 × 29.7 cm). "
        "The largest that fits with the ruler and the bleed is 19.4 × 26.1 cm."
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
