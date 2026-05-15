"""Render a Hebrew sentence to an 800x480 1-bit PNG."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features
from bidi.algorithm import get_display

FONT_PATH = Path(__file__).parent / "fonts" / "LibertinusSerif-Regular.ttf"

PANEL_W = 800
PANEL_H = 480
H_MARGIN = 20
USABLE_W = PANEL_W - 2 * H_MARGIN
USABLE_H = PANEL_H - 40

MAX_FONT_PT = 64
MIN_FONT_PT = 20
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
    return ImageFont.truetype(
        str(FONT_PATH), size=size, layout_engine=_LAYOUT_ENGINE
    )


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


def render_sentence(text: str) -> bytes:
    """Render a Hebrew sentence to a 1-bit 800x480 PNG. Returns PNG bytes."""
    img = Image.new("1", (PANEL_W, PANEL_H), 1)
    draw = ImageDraw.Draw(img)

    font, lines = _fit_font(text)
    line_h = int(font.size * LINE_HEIGHT_FACTOR)
    block_h = line_h * len(lines)
    y = (PANEL_H - block_h) // 2

    for line in lines:
        visual = _to_visual(line)
        line_w = font.getlength(visual)
        x = (PANEL_W - line_w) // 2
        draw.text((x, y), visual, font=font, fill=0)
        y += line_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
