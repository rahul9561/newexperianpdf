import math
import re

import pytest

from experian_pdf.gauge import CX, CY, NEEDLE_LENGTH, RX, RY, gauge_svg, score_to_angle


@pytest.mark.parametrize("score,angle", [(300, 180), (450, 135), (600, 90), (750, 45), (900, 0)])
def test_needle_angle(score, angle):
    assert score_to_angle(score) == pytest.approx(angle)


@pytest.mark.parametrize("score,angle", [(0, 180), (299, 180), (-50, 180), (901, 0), (1000, 0)])
def test_out_of_range_scores_clamp(score, angle):
    assert score_to_angle(score) == pytest.approx(angle)


def _needle_tip(svg: str) -> tuple[float, float]:
    # needle path: M base1 L tip L base2 Z (the 5th <path>, after the four bands)
    d = re.findall(r'<path d="([^"]+)"', svg)[4]
    tip = re.findall(r"L([\d.]+),([\d.]+)", d)[0]
    return float(tip[0]), float(tip[1])


@pytest.mark.parametrize("score", [300, 450, 600, 804, 900])
def test_needle_drawn_at_computed_angle(score):
    x, y = _needle_tip(gauge_svg(score))
    a = math.radians(score_to_angle(score))
    assert x == pytest.approx(CX + RX * NEEDLE_LENGTH * math.cos(a), abs=0.01)
    assert y == pytest.approx(CY - RY * NEEDLE_LENGTH * math.sin(a), abs=0.01)


def test_clamped_needle_matches_bounds():
    assert _needle_tip(gauge_svg(100)) == _needle_tip(gauge_svg(300))
    assert _needle_tip(gauge_svg(2000)) == _needle_tip(gauge_svg(900))


def test_no_score_draws_dial_only():
    svg = gauge_svg(None)
    assert svg.count("<path") == 4 and "<circle" not in svg
    assert gauge_svg(627) != gauge_svg(804)


def test_band_colours():
    svg = gauge_svg(700)
    for colour in ("#ff0000", "#ffa500", "#ffff00", "#90ee90"):
        assert colour in svg
