"""Credit score gauge as inline SVG.

Geometry measured from the sample PDF: a half-ellipse (rx 61pt, ry 70pt) split into
red 300-500, orange 500-600, yellow 600-700 and light-green 700-900, with a thin
black needle and a white hub at the centre.
"""

from __future__ import annotations

import math

SCORE_MIN = 300
SCORE_MAX = 900

RX = 61.0
RY = 70.0
PAD = 1.0
CX = RX + PAD
CY = RY + PAD

BANDS = [
    (300, 500, "#ff0000"),
    (500, 600, "#ffa500"),
    (600, 700, "#ffff00"),
    (700, 900, "#90ee90"),
]

NEEDLE_COLOR = "#000000"
NEEDLE_LENGTH = 0.55  # fraction of the radius
NEEDLE_HALF_WIDTH = 1.4
HUB_RADIUS = 3.8


def score_to_angle(score: float) -> float:
    """Map a score to an angle in degrees: 300 -> 180 (left), 900 -> 0 (right)."""
    s = min(max(float(score), SCORE_MIN), SCORE_MAX)
    return 180.0 - (s - SCORE_MIN) / (SCORE_MAX - SCORE_MIN) * 180.0


def _point(angle_deg: float, scale: float = 1.0) -> tuple[float, float]:
    a = math.radians(angle_deg)
    return CX + RX * scale * math.cos(a), CY - RY * scale * math.sin(a)


def _wedge(start: float, end: float, color: str) -> str:
    a0, a1 = score_to_angle(start), score_to_angle(end)
    x0, y0 = _point(a0)
    x1, y1 = _point(a1)
    return (
        f'<path d="M{CX:.2f},{CY:.2f} L{x0:.2f},{y0:.2f} '
        f'A{RX:.2f},{RY:.2f} 0 0 1 {x1:.2f},{y1:.2f} Z" fill="{color}"/>'
    )


def _needle(score: float) -> str:
    angle = score_to_angle(score)
    tx, ty = _point(angle, NEEDLE_LENGTH)
    # base points perpendicular to the needle direction (in screen space)
    dx, dy = tx - CX, ty - CY
    length = math.hypot(dx, dy) or 1.0
    px, py = -dy / length * NEEDLE_HALF_WIDTH, dx / length * NEEDLE_HALF_WIDTH
    return (
        f'<path d="M{CX + px:.2f},{CY + py:.2f} L{tx:.2f},{ty:.2f} '
        f'L{CX - px:.2f},{CY - py:.2f} Z" fill="{NEEDLE_COLOR}"/>'
        f'<circle cx="{CX:.2f}" cy="{CY:.2f}" r="{HUB_RADIUS}" fill="#ffffff"/>'
    )


def gauge_svg(score: int | float | None) -> str:
    """Return an ``<svg>`` element. ``score=None`` draws the dial without a needle."""
    width = 2 * CX
    height = CY + HUB_RADIUS + PAD
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="gauge" width="{width:.0f}pt" '
        f'height="{height:.0f}pt" viewBox="0 0 {width:.2f} {height:.2f}">'
    ]
    parts += [_wedge(lo, hi, color) for lo, hi, color in BANDS]
    if score is not None:
        parts.append(_needle(score))
    parts.append("</svg>")
    return "".join(parts)
