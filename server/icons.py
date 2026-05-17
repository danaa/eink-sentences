"""Line-art weather icons drawn with PIL primitives.

Each public draw function takes (draw, cx, cy, size) and renders an outlined
silhouette centered at (cx, cy) fitting roughly in a `size`-pixel-wide
square. All icons use thin uniform strokes for a sleek "line drawing" look.

Implementation note: for shapes built from overlapping primitives (the cloud)
we use a "fill then inset-fill-white" trick — draw the full silhouette black,
then draw the same silhouette `STROKE` pixels smaller in white, leaving a
clean outline of uniform thickness. This avoids the intersection-line
artifacts you'd get from drawing each component as a ring.
"""
from __future__ import annotations

import math

from PIL import ImageDraw

# Line weight. 3px reads cleanly on the e-paper after Floyd-Steinberg
# dithering; thinner (1-2px) tends to look faded.
STROKE = 3


# ---------- low-level helpers ----------

def _circle(draw, cx, cy, r, fill):
    if r <= 0:
        return
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _ring(draw, cx, cy, r, stroke=STROKE):
    """Circle outline (ring)."""
    if r <= 0:
        return
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=stroke)


def _cloud_filled(draw, cx, cy, w, fill, inset=0):
    """Fill a cloud silhouette with `fill`. `inset` shrinks the shape uniformly
    from its boundary (used to leave an outline of width `inset`)."""
    r_main = w * 0.28
    r_left = w * 0.22
    r_right = w * 0.20
    base_h = r_main * 0.7

    # Bump centers (constant — geometry stays the same regardless of inset).
    main_c = (cx, cy - r_main * 0.10)
    left_c = (cx - w * 0.22, cy + r_main * 0.10)
    right_c = (cx + w * 0.24, cy + r_main * 0.10)

    _circle(draw, *main_c,  max(0, r_main  - inset), fill)
    _circle(draw, *left_c,  max(0, r_left  - inset), fill)
    _circle(draw, *right_c, max(0, r_right - inset), fill)

    base_left   = cx - w * 0.42 + inset
    base_right  = cx + w * 0.42 - inset
    base_top    = cy + r_main * 0.10 + inset
    base_bottom = (cy + r_main * 0.10) + base_h - inset
    if base_right > base_left and base_bottom > base_top:
        draw.rectangle([base_left, base_top, base_right, base_bottom],
                       fill=fill)

    rc = (base_h - 2 * inset) / 2
    if rc > 0:
        _circle(draw, base_left + rc,  base_bottom - rc, rc, fill)
        _circle(draw, base_right - rc, base_bottom - rc, rc, fill)


def _cloud(draw, cx, cy, w):
    """Outlined cloud: filled black, then inner white inset by STROKE."""
    _cloud_filled(draw, cx, cy, w, fill=0)
    _cloud_filled(draw, cx, cy, w, fill=255, inset=STROKE)


def _sun(draw, cx, cy, w, rays=8):
    """Line-art sun: ring + radial line rays with a clean gap between."""
    body_r   = w * 0.20
    ray_in   = w * 0.27   # ray inner endpoint (outside the body, leaves a gap)
    ray_out  = w * 0.46
    _ring(draw, cx, cy, body_r, stroke=STROKE)
    for i in range(rays):
        a = (2 * math.pi / rays) * i
        x0, y0 = cx + math.cos(a) * ray_in,  cy + math.sin(a) * ray_in
        x1, y1 = cx + math.cos(a) * ray_out, cy + math.sin(a) * ray_out
        draw.line([(x0, y0), (x1, y1)], fill=0, width=STROKE)


def _raindrops(draw, cx, top_y, w, n=4, length_factor=0.16):
    """Thin diagonal rain streaks below a cloud base."""
    streak_len = w * length_factor
    spacing    = w * 0.16
    start_x    = cx - spacing * (n - 1) / 2
    for i in range(n):
        x = start_x + spacing * i
        draw.line(
            [(x, top_y), (x - streak_len * 0.4, top_y + streak_len)],
            fill=0, width=STROKE,
        )


def _lightning(draw, cx, top_y, w):
    """Outlined lightning bolt — connected line segments along the bolt path."""
    s = w * 0.22
    pts = [
        (cx - s * 0.10, top_y),
        (cx + s * 0.45, top_y),
        (cx + s * 0.05, top_y + s * 0.55),
        (cx + s * 0.40, top_y + s * 0.55),
        (cx - s * 0.30, top_y + s * 1.30),
        (cx + s * 0.05, top_y + s * 0.75),
        (cx - s * 0.30, top_y + s * 0.75),
        (cx - s * 0.10, top_y),  # close the path
    ]
    draw.line(pts, fill=0, width=STROKE, joint="curve")


def _snowflake(draw, cx, cy, r):
    """Six-pointed line-art snowflake (three crossed segments)."""
    for angle_deg in (0, 60, 120):
        a = math.radians(angle_deg)
        dx = math.cos(a) * r
        dy = math.sin(a) * r
        draw.line([(cx - dx, cy - dy), (cx + dx, cy + dy)],
                  fill=0, width=STROKE)


# ---------- public icons ----------

def draw_sun(draw, cx, cy, size):
    _sun(draw, cx, cy, size)


def draw_cloud(draw, cx, cy, size):
    _cloud(draw, cx, cy, size)


def draw_partly_cloudy(draw, cx, cy, size):
    """Sun behind a cloud. Sun drawn first; cloud overlays and erases the
    portion of the sun behind it (because cloud's inner fills white)."""
    sun_size   = size * 0.75
    _sun(draw, cx - size * 0.18, cy - size * 0.20, sun_size)
    _cloud(draw, cx + size * 0.10, cy + size * 0.12, size * 0.85)


def draw_rain(draw, cx, cy, size):
    _cloud(draw, cx, cy - size * 0.12, size)
    _raindrops(draw, cx, cy + size * 0.20, size, n=4, length_factor=0.16)


def draw_heavy_rain(draw, cx, cy, size):
    _cloud(draw, cx, cy - size * 0.14, size)
    _raindrops(draw, cx, cy + size * 0.20, size, n=6, length_factor=0.20)


def draw_drizzle(draw, cx, cy, size):
    """Cloud with small dotted rain instead of streaks."""
    _cloud(draw, cx, cy - size * 0.12, size)
    dot_r = max(2, int(size * 0.022))
    rain_top = cy + size * 0.22
    spacing = size * 0.16
    for i in range(5):
        x = cx + (i - 2) * spacing
        _circle(draw, x, rain_top, dot_r, fill=0)
        _circle(draw, x + spacing * 0.4, rain_top + size * 0.10, dot_r, fill=0)


def draw_thunder(draw, cx, cy, size):
    _cloud(draw, cx, cy - size * 0.15, size)
    _lightning(draw, cx, cy + size * 0.18, size)


def draw_fog(draw, cx, cy, size):
    """Three wavy horizontal lines suggesting drifting mist."""
    spacing    = size * 0.18
    widths     = [0.62, 0.78, 0.54]
    amplitude  = size * 0.035       # wave height
    wavelength = size * 0.22        # one full sine cycle
    phases     = [0, math.pi * 0.6, math.pi * 1.2]  # stagger so waves don't line up
    n_points   = 60
    for i, frac in enumerate(widths):
        y_center = cy - spacing + i * spacing
        w = size * frac
        x_start = cx - w / 2
        pts = []
        for j in range(n_points):
            t = j / (n_points - 1)
            x = x_start + t * w
            phase = 2 * math.pi * (x - x_start) / wavelength + phases[i]
            y = y_center + amplitude * math.sin(phase)
            pts.append((x, y))
        draw.line(pts, fill=0, width=STROKE, joint="curve")


def draw_snow(draw, cx, cy, size):
    _cloud(draw, cx, cy - size * 0.14, size)
    flake_r = size * 0.07
    spacing = size * 0.22
    base_y = cy + size * 0.28
    for i in (-1, 0, 1):
        _snowflake(draw, cx + i * spacing, base_y, flake_r)


_ICONS = {
    "sun":           draw_sun,
    "cloud":         draw_cloud,
    "partly_cloudy": draw_partly_cloudy,
    "rain":          draw_rain,
    "heavy_rain":    draw_heavy_rain,
    "drizzle":       draw_drizzle,
    "thunder":       draw_thunder,
    "fog":           draw_fog,
    "snow":          draw_snow,
}


def draw_weather_icon(draw: ImageDraw.ImageDraw, kind: str,
                      cx: int, cy: int, size: int) -> None:
    """Dispatch to the right icon. Unknown kinds fall back to sun."""
    _ICONS.get(kind, draw_sun)(draw, cx, cy, size)
