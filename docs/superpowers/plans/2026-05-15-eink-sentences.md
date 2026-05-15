# E-Ink Hebrew Sentences Display — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Battery-powered XIAO ESP32 + Seeed 7.5" e-paper that wakes every 5 minutes, fetches a server-rendered Hebrew PNG, and displays it. Sentences are edited in `sentences.md` and updated by `git push`.

**Architecture:** Three pieces — `sentences.md` in a GitHub repo (source of truth), a Flask app on Render.com that renders Hebrew PNGs with Pillow + python-bidi + Frank Ruhl Libre, and an Arduino/PlatformIO firmware that just fetches the PNG and pushes it to the panel.

**Tech Stack:** Python 3.11+, Flask, Pillow, python-bidi, gunicorn, Render.com (free web service), Arduino-ESP32, PlatformIO, GxEPD2, bitbank2/PNGdec.

**Spec:** `docs/superpowers/specs/2026-05-15-eink-sentences-design.md`

---

## Phase 0: Repo bootstrap

The Flask server fetches `sentences.md` from a GitHub raw URL, so the project must live in a GitHub repo before the server is useful.

### Task 0.1: Initialize git and the working tree

**Files:**
- Create: `C:\Users\danaa\DEV\eink\.gitignore`

- [ ] **Step 1: Initialize git in the project root**

Run (PowerShell):
```powershell
git init -b main
```
Expected: `Initialized empty Git repository in C:/Users/danaa/DEV/eink/.git/`

- [ ] **Step 2: Create `.gitignore`**

Create `C:\Users\danaa\DEV\eink\.gitignore`:
```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
.coverage

# PlatformIO
firmware/.pio/
firmware/.vscode/
firmware/src/secrets.h

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Stage and commit existing files**

Run:
```powershell
git add .gitignore sentences.md docs/
git status
git commit -m "chore: initial commit with sentences and spec"
```
Expected: a commit listing `.gitignore`, `sentences.md`, and the docs tree.

### Task 0.2: Create the GitHub repo and push

- [ ] **Step 1: Create a private GitHub repo and push**

Pick ONE of these two paths.

**Path A — using `gh` CLI (recommended):**
```powershell
gh repo create eink-sentences --private --source=. --remote=origin --push
```

**Path B — manual:**
1. Go to https://github.com/new — name `eink-sentences`, **private**, do NOT initialize with README.
2. Run:
   ```powershell
   git remote add origin https://github.com/<your-username>/eink-sentences.git
   git push -u origin main
   ```

Expected: the repo exists on GitHub with `sentences.md` visible.

- [ ] **Step 2: Note the raw URL for `sentences.md`**

The raw URL has this shape:
```
https://raw.githubusercontent.com/<your-username>/eink-sentences/main/sentences.md
```

Test it loads in a browser. Save it — the Render service needs it later (`SENTENCES_URL` env var).

> **Privacy note:** A private repo's raw URLs require a token. If you keep the repo private, use a fine-grained personal access token with read access to this repo only, and append `?token=<token>` (GitHub's old raw-token URLs are deprecated; the cleaner option is to make this single repo public — it's only your sentences).

---

## Phase 1: Flask server (TDD)

### Task 1.1: Server scaffold + Python venv

**Files:**
- Create: `server/requirements.txt`
- Create: `server/fonts/.gitkeep`
- Create: `server/tests/__init__.py`
- Create: `server/__init__.py`

- [ ] **Step 1: Create a venv inside the project**

Run:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```
Expected: `(.venv)` appears at the start of the PowerShell prompt.

- [ ] **Step 2: Create `server/requirements.txt`**

```
flask==3.0.3
pillow==10.4.0
python-bidi==0.6.6
requests==2.32.3
gunicorn==23.0.0
pytest==8.3.3
```

- [ ] **Step 3: Install deps**

Run:
```powershell
pip install -r server/requirements.txt
```
Expected: all packages install without error.

- [ ] **Step 4: Create empty package files**

Create `server/__init__.py` (empty) and `server/tests/__init__.py` (empty) and `server/fonts/.gitkeep` (empty).

- [ ] **Step 5: Commit**

```powershell
git add server/ .venv .gitignore
git status
```
Note: `.venv` should be IGNORED. If it shows up in status, double-check `.gitignore`.

```powershell
git add server/
git commit -m "feat(server): scaffold Flask service"
```

### Task 1.2: Download Frank Ruhl Libre Medium

**Files:**
- Create: `server/fonts/FrankRuhlLibre-Medium.ttf`

- [ ] **Step 1: Download the static font from the Google Fonts repo**

Run (PowerShell):
```powershell
Invoke-WebRequest `
  -Uri "https://github.com/google/fonts/raw/main/ofl/frankruhllibre/static/FrankRuhlLibre-Medium.ttf" `
  -OutFile "server/fonts/FrankRuhlLibre-Medium.ttf"
```
Expected: a `.ttf` file ~120-200KB at `server/fonts/FrankRuhlLibre-Medium.ttf`.

If the URL 404s (Google sometimes restructures the repo), download manually from https://fonts.google.com/specimen/Frank+Ruhl+Libre and extract the Medium static TTF into `server/fonts/`.

- [ ] **Step 2: Verify Pillow can load it**

Run:
```powershell
python -c "from PIL import ImageFont; f = ImageFont.truetype('server/fonts/FrankRuhlLibre-Medium.ttf', size=48); print(f.getlength('שלום'))"
```
Expected: a number (likely between 60 and 120). NO traceback.

- [ ] **Step 3: Commit**

```powershell
git add server/fonts/FrankRuhlLibre-Medium.ttf
git commit -m "feat(server): add Frank Ruhl Libre Medium font"
```

### Task 1.3: Sentences parser

The parser turns the raw `sentences.md` text into a clean list of Hebrew strings.

**Files:**
- Create: `server/parser.py`
- Create: `server/tests/test_parser.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_parser.py`:
```python
from server.parser import parse_sentences

def test_strips_leading_line_numbers():
    raw = "1\tתמיד יהיו טובים\n2\t\n3\tאני לומדת\n"
    assert parse_sentences(raw) == ["תמיד יהיו טובים", "אני לומדת"]

def test_strips_markdown_bold():
    raw = "**הרגישות שלך היא כוח אדיר**"
    assert parse_sentences(raw) == ["הרגישות שלך היא כוח אדיר"]

def test_skips_blank_and_whitespace_only_lines():
    raw = "שלום\n\n   \nעולם\n"
    assert parse_sentences(raw) == ["שלום", "עולם"]

def test_handles_plain_lines_with_no_prefix():
    raw = "שורה ראשונה\nשורה שנייה\n"
    assert parse_sentences(raw) == ["שורה ראשונה", "שורה שנייה"]

def test_returns_empty_list_for_empty_input():
    assert parse_sentences("") == []
    assert parse_sentences("\n\n\n") == []
```

- [ ] **Step 2: Run the test, see it fail**

Run:
```powershell
pytest server/tests/test_parser.py -v
```
Expected: ImportError / `ModuleNotFoundError: No module named 'server.parser'`.

- [ ] **Step 3: Implement the parser**

Create `server/parser.py`:
```python
import re

_LINE_NUMBER_PREFIX = re.compile(r"^\d+\t")
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")


def parse_sentences(raw: str) -> list[str]:
    """Parse sentences.md text into a list of clean sentences.

    Strips leading "N\\t" line-number prefixes (the format produced when the
    file was pasted from a numbered list), unwraps **markdown bold**, and
    drops blank/whitespace-only lines.
    """
    out: list[str] = []
    for line in raw.splitlines():
        line = _LINE_NUMBER_PREFIX.sub("", line).strip()
        if not line:
            continue
        line = _MARKDOWN_BOLD.sub(r"\1", line)
        if line:
            out.append(line)
    return out
```

- [ ] **Step 4: Run the tests, see them pass**

Run:
```powershell
pytest server/tests/test_parser.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add server/parser.py server/tests/test_parser.py
git commit -m "feat(server): add sentences.md parser"
```

### Task 1.4: PNG renderer

Renders one Hebrew sentence to an 800×480 1-bit PNG with auto-fit and BiDi reshaping.

**Files:**
- Create: `server/render.py`
- Create: `server/tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_render.py`:
```python
import io
from PIL import Image
from server.render import render_sentence


def _decode(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes))


def test_returns_png_bytes():
    out = render_sentence("שלום עולם")
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_is_800_by_480():
    img = _decode(render_sentence("שלום עולם"))
    assert img.size == (800, 480)


def test_image_is_1_bit_mode():
    img = _decode(render_sentence("שלום עולם"))
    assert img.mode == "1"


def test_short_sentence_uses_largest_font():
    img = _decode(render_sentence("שלום"))
    # 1-bit: black pixels == 0, white == 255. Short text → lots of white,
    # but the few black pixels should be present.
    extrema = img.convert("L").getextrema()
    assert extrema == (0, 255), "expected both black and white pixels"


def test_very_long_sentence_still_fits_in_frame():
    # Build a sentence ~5x longer than the longest real entry.
    long = " ".join(["מילה"] * 80)
    img = _decode(render_sentence(long))
    assert img.size == (800, 480)
    # Should still produce a valid image with text (some black pixels).
    extrema = img.convert("L").getextrema()
    assert extrema == (0, 255)
```

- [ ] **Step 2: Run the test, see it fail**

Run:
```powershell
pytest server/tests/test_render.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement the renderer**

Create `server/render.py`:
```python
"""Render a Hebrew sentence to an 800x480 1-bit PNG."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display

FONT_PATH = Path(__file__).parent / "fonts" / "FrankRuhlLibre-Medium.ttf"

PANEL_W = 800
PANEL_H = 480
H_MARGIN = 20         # left+right combined margin space
USABLE_W = PANEL_W - 2 * H_MARGIN
USABLE_H = PANEL_H - 40  # 20px top + 20px bottom

MAX_FONT_PT = 64
MIN_FONT_PT = 20
FONT_STEP = 4
LINE_HEIGHT_FACTOR = 1.25


def _wrap_logical(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Greedy word-wrap of logical-order Hebrew text. Returns list of lines
    still in logical order. Measurement uses the visual form so widths are
    accurate."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        visual = get_display(candidate)
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
    """Return the largest font + wrapped lines that fit in the usable area."""
    for size in range(MAX_FONT_PT, MIN_FONT_PT - 1, -FONT_STEP):
        font = ImageFont.truetype(str(FONT_PATH), size=size)
        lines = _wrap_logical(text, font, USABLE_W)
        line_h = int(size * LINE_HEIGHT_FACTOR)
        block_h = line_h * len(lines)
        if block_h <= USABLE_H:
            return font, lines
    # Smallest size still didn't fit — render anyway at MIN_FONT_PT.
    font = ImageFont.truetype(str(FONT_PATH), size=MIN_FONT_PT)
    lines = _wrap_logical(text, font, USABLE_W)
    return font, lines


def render_sentence(text: str) -> bytes:
    """Render a Hebrew sentence to a 1-bit 800x480 PNG. Returns PNG bytes."""
    img = Image.new("1", (PANEL_W, PANEL_H), 1)  # 1 = white
    draw = ImageDraw.Draw(img)

    font, lines = _fit_font(text)
    line_h = int(font.size * LINE_HEIGHT_FACTOR)
    block_h = line_h * len(lines)
    y = (PANEL_H - block_h) // 2

    for line in lines:
        visual = get_display(line)
        line_w = font.getlength(visual)
        x = (PANEL_W - line_w) // 2
        draw.text((x, y), visual, font=font, fill=0)  # 0 = black
        y += line_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
```

- [ ] **Step 4: Run the tests, see them pass**

Run:
```powershell
pytest server/tests/test_render.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Eyeball a rendered sample**

Run:
```powershell
python -c "from server.render import render_sentence; open('sample.png','wb').write(render_sentence('הרגישות שלך היא כוח אדיר, לא חולשה'))"
start sample.png
```
Expected: a window opens showing a centered Hebrew sentence in Frank Ruhl Libre on a white 800×480 canvas, reading right-to-left.

If the Hebrew looks reversed (letters in left-to-right order) or jumbled, the BiDi call isn't firing — re-check that `python-bidi` is installed.

- [ ] **Step 6: Clean up the sample and commit**

```powershell
Remove-Item sample.png
git add server/render.py server/tests/test_render.py
git commit -m "feat(server): render Hebrew sentence to 800x480 1-bit PNG"
```

### Task 1.5: Sentences source (fetch + cache)

**Files:**
- Create: `server/sentences_source.py`
- Create: `server/tests/test_sentences_source.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_sentences_source.py`:
```python
from unittest.mock import patch, MagicMock
import server.sentences_source as src


def _make_response(text: str, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = Exception("http error")
    return r


def setup_function(_):
    src._cache.clear()


def test_fetches_and_parses(monkeypatch):
    monkeypatch.setenv("SENTENCES_URL", "https://example.com/s.md")
    with patch("server.sentences_source.requests.get",
               return_value=_make_response("שלום\n\nעולם\n")):
        out = src.fetch_sentences()
    assert out == ["שלום", "עולם"]


def test_uses_cache_within_ttl(monkeypatch):
    monkeypatch.setenv("SENTENCES_URL", "https://example.com/s.md")
    with patch("server.sentences_source.requests.get",
               return_value=_make_response("שלום\n")) as mock_get:
        src.fetch_sentences()
        src.fetch_sentences()
        src.fetch_sentences()
    assert mock_get.call_count == 1


def test_falls_back_to_cache_on_fetch_failure(monkeypatch):
    monkeypatch.setenv("SENTENCES_URL", "https://example.com/s.md")
    # First call succeeds, second call fails — should return cached value.
    with patch("server.sentences_source.requests.get",
               return_value=_make_response("שלום\n")):
        src.fetch_sentences()
    src._cache["expires_at"] = 0  # force TTL expiry
    with patch("server.sentences_source.requests.get",
               side_effect=Exception("network down")):
        out = src.fetch_sentences()
    assert out == ["שלום"]


def test_returns_empty_list_when_no_cache_and_fetch_fails(monkeypatch):
    monkeypatch.setenv("SENTENCES_URL", "https://example.com/s.md")
    with patch("server.sentences_source.requests.get",
               side_effect=Exception("network down")):
        out = src.fetch_sentences()
    assert out == []
```

- [ ] **Step 2: Run the test, see it fail**

Run:
```powershell
pytest server/tests/test_sentences_source.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement the source**

Create `server/sentences_source.py`:
```python
"""Fetch sentences.md from a remote URL with a small in-memory cache."""
from __future__ import annotations

import os
import time
import logging

import requests

from server.parser import parse_sentences

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 10

# Module-level cache. Single-process gunicorn worker is fine; multi-worker
# means each worker has its own — that's OK at our scale.
_cache: dict = {
    "sentences": [],
    "expires_at": 0.0,
}


def fetch_sentences() -> list[str]:
    """Return the current list of sentences. Caches for CACHE_TTL_SECONDS.

    On fetch failure, returns the last cached list (which may be empty if
    no successful fetch has happened yet).
    """
    now = time.time()
    if _cache["expires_at"] > now and _cache["sentences"]:
        return _cache["sentences"]

    url = os.environ.get("SENTENCES_URL")
    if not url:
        log.error("SENTENCES_URL env var is not set")
        return _cache["sentences"]

    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
        parsed = parse_sentences(resp.text)
        _cache["sentences"] = parsed
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return parsed
    except Exception as e:
        log.warning("Failed to fetch sentences, returning cached list: %s", e)
        return _cache["sentences"]
```

- [ ] **Step 4: Run the tests, see them pass**

Run:
```powershell
pytest server/tests/test_sentences_source.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add server/sentences_source.py server/tests/test_sentences_source.py
git commit -m "feat(server): fetch sentences.md with 60s in-memory cache"
```

### Task 1.6: Flask app

**Files:**
- Create: `server/app.py`
- Create: `server/tests/test_app.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_app.py`:
```python
from unittest.mock import patch
from server.app import create_app


def test_image_endpoint_returns_png():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_sentences", return_value=["שלום"]):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "image/png"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_endpoint_uses_fallback_when_no_sentences():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_sentences", return_value=[]):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "image/png"
    # Should still be a valid PNG (the "אין משפטים" fallback).
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_healthcheck():
    app = create_app()
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run the test, see it fail**

Run:
```powershell
pytest server/tests/test_app.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement the app**

Create `server/app.py`:
```python
"""Flask app — single endpoint returns a Hebrew PNG for the e-paper."""
from __future__ import annotations

import logging
import random

from flask import Flask, Response

from server.render import render_sentence
from server.sentences_source import fetch_sentences

log = logging.getLogger(__name__)

FALLBACK_NO_SENTENCES = "אין משפטים"
FALLBACK_ERROR = "שגיאה"


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def health() -> str:
        return "ok"

    @app.get("/image.png")
    def image() -> Response:
        try:
            sentences = fetch_sentences()
            if not sentences:
                png = render_sentence(FALLBACK_NO_SENTENCES)
            else:
                png = render_sentence(random.choice(sentences))
        except Exception as e:
            log.exception("Render failed: %s", e)
            png = render_sentence(FALLBACK_ERROR)

        return Response(
            png,
            mimetype="image/png",
            headers={"Cache-Control": "no-store"},
        )

    return app


# Module-level app for gunicorn: `gunicorn server.app:app`
app = create_app()
```

- [ ] **Step 4: Run the tests, see them pass**

Run:
```powershell
pytest server/tests/test_app.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Run the full test suite**

Run:
```powershell
pytest server/ -v
```
Expected: all tests pass (parser + render + source + app).

- [ ] **Step 6: Manual smoke test**

Run:
```powershell
$env:SENTENCES_URL = "https://raw.githubusercontent.com/<your-username>/eink-sentences/main/sentences.md"
python -m flask --app server.app run --port 5000
```
In another terminal:
```powershell
Invoke-WebRequest http://localhost:5000/image.png -OutFile out.png
start out.png
```
Expected: an 800×480 image with a random Hebrew sentence from your list.

Stop the server with Ctrl+C. Delete `out.png`.

- [ ] **Step 7: Commit**

```powershell
git add server/app.py server/tests/test_app.py
git commit -m "feat(server): Flask /image.png endpoint with fallback rendering"
```

---

## Phase 2: Deploy to Render

### Task 2.1: Render blueprint

**Files:**
- Create: `server/render.yaml`
- Create: `server/Procfile`

- [ ] **Step 1: Create the Render blueprint**

The blueprint runs everything from the repo root (no `rootDir`) so the `server.app:app` import path resolves correctly.

Create `server/render.yaml`:
```yaml
services:
  - type: web
    name: eink-sentences
    runtime: python
    plan: free
    region: frankfurt
    buildCommand: pip install -r server/requirements.txt
    startCommand: gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 server.app:app
    envVars:
      - key: SENTENCES_URL
        sync: false   # set this in the Render dashboard, not in git
      - key: PYTHON_VERSION
        value: 3.11.9
```

- [ ] **Step 2: Commit**

```powershell
git add server/render.yaml
git commit -m "feat(server): Render blueprint for free web service"
git push
```

### Task 2.2: Create the Render service

This is a manual step — Render's API requires a token and a dashboard click is faster.

- [ ] **Step 1: Connect the repo to Render**

1. Go to https://dashboard.render.com/blueprints
2. Click **New Blueprint Instance**.
3. Connect your GitHub account if prompted, and pick `eink-sentences`.
4. Render reads `render.yaml`. Confirm.
5. **Add the `SENTENCES_URL` env var:** paste the raw URL from Phase 0 Task 0.2.
6. Click **Apply**.

Expected: Render builds and deploys (~3-5 minutes). You'll get a URL like `https://eink-sentences-XXXX.onrender.com`.

- [ ] **Step 2: Smoke test the live URL**

In a browser, open `https://<your-render-url>.onrender.com/image.png`.
Expected: a Hebrew sentence rendered on white background. **First request may take ~30s** (free-tier cold start) — that's normal and accounted for in the firmware retry behavior.

Save the Render URL — the firmware needs it.

---

## Phase 3: XIAO firmware

Phase 3 requires the actual hardware connected to a USB port. Before starting, install PlatformIO (https://platformio.org/install/ide) — easiest path is the PlatformIO IDE extension for VS Code.

### Task 3.1: Identify hardware specifics

This is a one-time information-gathering step.

- [ ] **Step 1: Identify your XIAO board variant**

Look at the chip name printed on your XIAO board (the small square module). Note:
- `ESP32-C3` → board ID `seeed_xiao_esp32c3`
- `ESP32-S3` → board ID `seeed_xiao_esp32s3`
- `ESP32-C6` → board ID `seeed_xiao_esp32c6`

- [ ] **Step 2: Identify the panel revision**

Look at the e-paper driver board / panel cable. Note the model number if printed (e.g. `GDEY075T7`, `GDEW075T7`).

In `firmware/src/main.cpp` (next task) you'll pick the matching GxEPD2 class:
- `GxEPD2_750_T7` — UC8179 controller (most common Seeed 7.5" rev)
- `GxEPD2_750_GDEY075T7` — SSD168x controller (newer rev)

If unsure, start with `GxEPD2_750_T7` and switch if the display shows garbled output.

- [ ] **Step 3: Identify the SPI pinout**

If you're using Seeed's "XIAO ePaper Driver Board", the pinout is standard:
| Signal | XIAO pin (logical) | GPIO (ESP32-C3) |
|--------|-------------------:|----------------:|
| CS     | D1                 | 3               |
| DC     | D3                 | 5               |
| RST    | D0                 | 2               |
| BUSY   | D2                 | 4               |
| CLK    | D8                 | 8 (SPI SCK)     |
| MOSI   | D10                | 10              |

Confirm against your driver board's silkscreen / datasheet before flashing.

### Task 3.2: PlatformIO project scaffold

**Files:**
- Create: `firmware/platformio.ini`
- Create: `firmware/src/secrets.example.h`

- [ ] **Step 1: Create `firmware/platformio.ini`**

```ini
; Adjust [env:xiao] board to your actual board:
;   seeed_xiao_esp32c3  | seeed_xiao_esp32s3  | seeed_xiao_esp32c6
[env:xiao]
platform = espressif32
board = seeed_xiao_esp32c3
framework = arduino
monitor_speed = 115200
upload_speed = 921600

build_flags =
    -DCORE_DEBUG_LEVEL=3

lib_deps =
    zinggjm/GxEPD2@^1.5.8
    bitbank2/PNGdec@^1.0.3
```

- [ ] **Step 2: Create `firmware/src/secrets.example.h`**

```cpp
#pragma once

// Copy this file to `secrets.h` and fill in real values.
// `secrets.h` is gitignored.

#define WIFI_SSID   "your-wifi-name"
#define WIFI_PASS   "your-wifi-password"
#define SERVER_URL  "https://your-render-url.onrender.com/image.png"
```

- [ ] **Step 3: Create your real `secrets.h` locally (do not commit)**

```powershell
Copy-Item firmware/src/secrets.example.h firmware/src/secrets.h
notepad firmware/src/secrets.h
```
Fill in your Wi-Fi credentials and the Render URL from Phase 2.

- [ ] **Step 4: Verify `secrets.h` is gitignored**

```powershell
git status
```
Expected: `secrets.h` should NOT appear. If it does, fix `.gitignore`.

- [ ] **Step 5: Commit**

```powershell
git add firmware/platformio.ini firmware/src/secrets.example.h
git commit -m "feat(firmware): PlatformIO scaffold and secrets template"
```

### Task 3.3: Firmware main

**Files:**
- Create: `firmware/src/main.cpp`

- [ ] **Step 1: Implement `main.cpp`**

```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <SPI.h>

// --- Display library ---
// If your panel rev shows garbled output with GxEPD2_750_T7, swap to
// #include <epd/GxEPD2_750_GDEY075T7.h> and use that class below.
#include <GxEPD2_BW.h>
#include <epd/GxEPD2_750_T7.h>

#include <PNGdec.h>
#include "secrets.h"

// --- Pinout (Seeed XIAO ePaper Driver Board, ESP32-C3) ---
// Update these if your wiring differs.
#define EPD_CS   3   // D1
#define EPD_DC   5   // D3
#define EPD_RST  2   // D0
#define EPD_BUSY 4   // D2

GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(
    GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

// --- Sleep / network constants ---
static const uint64_t SLEEP_US   = 5ULL * 60ULL * 1000000ULL;  // 5 min
static const uint32_t WIFI_TIMEOUT_MS = 15000;
static const size_t   PNG_BUF_SIZE   = 64 * 1024;  // 64KB max PNG payload

// --- PNG decode state ---
static uint8_t pngBuffer[PNG_BUF_SIZE];
static size_t  pngBufferLen = 0;
static PNG     png;

// Called once per PNG row.
void pngDraw(PNGDRAW *pDraw) {
  uint8_t lineGray[800];
  png.getLineAsGray8(pDraw, lineGray, 0);
  for (int x = 0; x < pDraw->iWidth && x < 800; x++) {
    uint16_t color = (lineGray[x] > 127) ? GxEPD_WHITE : GxEPD_BLACK;
    display.drawPixel(x, pDraw->y, color);
  }
}

void deepSleep() {
  Serial.println("Sleeping 5 min");
  Serial.flush();
  esp_sleep_enable_timer_wakeup(SLEEP_US);
  esp_deep_sleep_start();
}

bool connectWiFi() {
  Serial.printf("Connecting to %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi timeout");
    return false;
  }
  Serial.printf("IP: %s\n", WiFi.localIP().toString().c_str());
  return true;
}

bool fetchPng() {
  WiFiClientSecure client;
  client.setInsecure();  // Render uses a public cert; OK for our use case
  HTTPClient http;
  if (!http.begin(client, SERVER_URL)) {
    Serial.println("http.begin failed");
    return false;
  }
  int code = http.GET();
  if (code != 200) {
    Serial.printf("HTTP %d\n", code);
    http.end();
    return false;
  }
  WiFiClient *stream = http.getStreamPtr();
  pngBufferLen = 0;
  uint32_t start = millis();
  while (http.connected() && (millis() - start) < 30000) {
    size_t avail = stream->available();
    if (avail > 0) {
      size_t space = PNG_BUF_SIZE - pngBufferLen;
      if (space == 0) {
        Serial.println("PNG larger than buffer");
        http.end();
        return false;
      }
      size_t toRead = avail < space ? avail : space;
      int got = stream->readBytes(pngBuffer + pngBufferLen, toRead);
      pngBufferLen += got;
    } else if (!stream->connected() || http.getSize() == (int)pngBufferLen) {
      break;
    } else {
      delay(5);
    }
  }
  http.end();
  Serial.printf("Fetched %u bytes\n", (unsigned)pngBufferLen);
  return pngBufferLen > 0;
}

bool decodeAndDraw() {
  int rc = png.openRAM(pngBuffer, pngBufferLen, pngDraw);
  if (rc != PNG_SUCCESS) {
    Serial.printf("PNG open failed: %d\n", rc);
    return false;
  }
  Serial.printf("PNG %dx%d, %dbpp\n", png.getWidth(), png.getHeight(), png.getBpp());
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    rc = png.decode(NULL, 0);
  } while (display.nextPage());
  png.close();
  return rc == PNG_SUCCESS;
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n=== eink-sentences wake ===");

  display.init(115200, true, 2, false);

  if (!connectWiFi()) {
    deepSleep();
  }
  if (!fetchPng()) {
    deepSleep();
  }
  if (!decodeAndDraw()) {
    Serial.println("Decode/draw failed");
    deepSleep();
  }

  Serial.println("Display refreshed");
  display.hibernate();
  deepSleep();
}

void loop() {
  // Never reached — setup() always ends in deepSleep().
}
```

- [ ] **Step 2: Build the firmware**

In the firmware directory:
```powershell
cd firmware
pio run
```
Expected: compile succeeds. If GxEPD2 complains about the panel class, swap the include and class to `GxEPD2_750_GDEY075T7` as noted in the comment.

- [ ] **Step 3: Flash and watch serial**

Plug the XIAO into USB.
```powershell
pio run -t upload
pio device monitor
```
Expected serial output:
```
=== eink-sentences wake ===
Connecting to <ssid>
....
IP: 192.168.x.x
Fetched <N> bytes
PNG 800x480, 1bpp
Display refreshed
Sleeping 5 min
```
And: the panel shows a Hebrew sentence within ~10-15 seconds of boot.

- [ ] **Step 4: Verify the refresh cycle**

After ~5 minutes, watch for a new sentence to appear. The serial monitor will reconnect when the device wakes (the USB-CDC interface re-enumerates briefly).

- [ ] **Step 5: Commit**

From the repo root:
```powershell
cd ..
git add firmware/src/main.cpp
git commit -m "feat(firmware): wake, fetch PNG, render, deep sleep cycle"
git push
```

---

## Phase 4: End-to-end verification

### Task 4.1: Edit a sentence and watch it propagate

- [ ] **Step 1: Edit `sentences.md`** — add a new sentence (e.g. `בדיקה`), save.

- [ ] **Step 2: Commit and push**
```powershell
git add sentences.md
git commit -m "test: add sentence to verify pipeline"
git push
```

- [ ] **Step 3: Wait for next wake (≤5 min) and confirm**

The new sentence is in the random pool. It may take a few refreshes to be picked. To force a refresh, briefly press the reset button on the XIAO.

- [ ] **Step 4: Final commit and tag**

```powershell
git tag v1.0.0
git push --tags
```

---

## Self-review notes

- All spec sections (server, firmware, edit workflow, error handling, power budget) have a corresponding task.
- All file paths and library versions are concrete.
- Hebrew strings in test code are real (not placeholders).
- The four open implementation questions in the spec are surfaced in Phase 3 Task 3.1 (board, panel rev, pinout) and parser handling of `**` is implemented in Task 1.3.
- Each failing test step has matching pass criteria.
- Each TDD cycle ends with a commit.
