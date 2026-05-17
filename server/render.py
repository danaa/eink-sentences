"""Render a Hebrew sentence to an 800x480 1-bit PNG."""
from __future__ import annotations

import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features
from bidi.algorithm import get_display

FONT_PATH = Path(__file__).parent / "fonts" / "FrankRuhlLibre-VF.ttf"
# Frank Ruhl Libre is a variable font with a single Weight axis (300-900).
# 500 (Medium) reads well on monochrome e-ink: thicker than Regular for
# contrast, lighter than Bold so the nikud stays legible.
FONT_WEIGHT = 500

PANEL_W = 800
PANEL_H = 480
H_MARGIN = 20
V_MARGIN = 20
USABLE_W = PANEL_W - 2 * H_MARGIN

# Decorative heart drawn just below the text. Sized to feel like a small
# flourish, not a billboard.
HEART_HALF_HEIGHT = 18
HEART_GAP_ABOVE = 18  # gap between last text line and heart
# Total vertical space the heart occupies (above+below center).
HEART_BLOCK_H = HEART_HALF_HEIGHT * 2 + HEART_GAP_ABOVE
USABLE_H = PANEL_H - 2 * V_MARGIN - HEART_BLOCK_H

MAX_FONT_PT = 84
MIN_FONT_PT = 26
FONT_STEP = 4
LINE_HEIGHT_FACTOR = 1.25

# Raqm engine uses HarfBuzz to shape combining marks (nikud dagesh, sin/shin
# dot, etc.) at the correct positions. Linux Pillow wheels bundle libraqm;
# Windows wheels don't — when unavailable, Pillow silently falls back to
# basic layout (still correct letters, but nikud placement may be off).
_RAQM_AVAILABLE = features.check("raqm")
_LAYOUT_ENGINE = (
    ImageFont.Layout.RAQM if _RAQM_AVAILABLE else ImageFont.Layout.BASIC
)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(
        str(FONT_PATH), size=size, layout_engine=_LAYOUT_ENGINE
    )
    try:
        font.set_variation_by_axes([FONT_WEIGHT])
    except Exception:
        # Static-font fallback: ignore if axes can't be set (e.g. local test
        # systems running an older Pillow).
        pass
    return font


def _to_visual(text: str) -> str:
    """RAQM does BiDi internally via HarfBuzz; only manually reorder when
    falling back to the BASIC layout engine."""
    if _RAQM_AVAILABLE:
        return text
    return get_display(text)


def _wrap_logical(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word-wrap of logical-order Hebrew text. Returns logical-order lines.
    Widths are measured on the visual form (post-BiDi)."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        visual = _to_visual(candidate)
        w = font.getlength(visual)
        if w <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def _fit_font(text: str) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Largest font + wrapped lines that fit in the usable area."""
    for size in range(MAX_FONT_PT, MIN_FONT_PT - 1, -FONT_STEP):
        font = _load_font(size)
        lines = _wrap_logical(text, font, USABLE_W)
        line_h = int(size * LINE_HEIGHT_FACTOR)
        block_h = line_h * len(lines)
        if block_h <= USABLE_H:
            return font, lines
    font = _load_font(MIN_FONT_PT)
    lines = _wrap_logical(text, font, USABLE_W)
    return font, lines


def _draw_heart(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                size: float = 1.6) -> None:
    """Draw a filled black heart using the classic parametric cardioid curve.

    The shape is x = 16·sin³(t), y = 13·cos(t) − 5·cos(2t) − 2·cos(3t) − cos(4t),
    sampled around a full circle and rendered as a filled polygon. This is the
    canonical "math heart" used widely in print/web — clean, symmetric, with
    proper bumps and a pointed tip.

    `size` is a multiplier on the raw curve units (one unit ≈ one pixel of the
    raw 32-px-wide heart). A size of 1.6 gives roughly a 50×46 pixel heart.
    """
    pts = []
    n = 100
    for i in range(n):
        t = (i / n) * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        # Negate y so the heart points downward in image coordinates.
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t)
              - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((cx + x * size, cy + y * size))
    draw.polygon(pts, fill=0)


def render_sentence(text: str) -> bytes:
    """Render a Hebrew sentence to a 1-bit 800x480 PNG. Returns PNG bytes.

    Renders text + heart in 8-bit grayscale so PIL applies proper subpixel
    antialiasing along curves, then converts to 1-bit using Floyd-Steinberg
    error-diffusion dithering. The dither pattern softens edges that would
    otherwise look stair-stepped, while keeping the output as 1-bit (so the
    firmware's PNG-to-framebuffer path is unchanged).
    """
    # 8-bit grayscale canvas, 255 = white.
    img = Image.new("L", (PANEL_W, PANEL_H), 255)
    draw = ImageDraw.Draw(img)

    font, lines = _fit_font(text)
    line_h = int(font.size * LINE_HEIGHT_FACTOR)
    text_h = line_h * len(lines)

    composition_h = text_h + HEART_BLOCK_H
    top = (PANEL_H - composition_h) // 2

    y = top
    for line in lines:
        visual = _to_visual(line)
        line_w = font.getlength(visual)
        x = (PANEL_W - line_w) // 2
        draw.text((x, y), visual, font=font, fill=0)
        y += line_h

    heart_cy = y + HEART_GAP_ABOVE + HEART_HALF_HEIGHT
    _draw_heart(draw, cx=PANEL_W // 2, cy=heart_cy)

    # Convert to 1-bit with Floyd-Steinberg dithering.
    img_1bit = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

    buf = io.BytesIO()
    img_1bit.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
