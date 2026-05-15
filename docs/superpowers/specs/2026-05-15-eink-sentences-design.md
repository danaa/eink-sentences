# E-Ink Hebrew Sentences Display — Design

**Date:** 2026-05-15
**Owner:** Dana
**Hardware:** Seeed Studio XIAO ESP32 + Seeed 7.5" e-paper panel, LiPo battery

## Goal

A battery-powered wall-mounted 7.5" e-ink display that shows one Hebrew inspirational sentence at a time, rotating every 5 minutes by fetching from a small remote server. The sentence list is edited as a plain text file in this repo (`sentences.md`) and updated by `git push`.

## Architecture

```
┌────────────────────────┐  git push   ┌────────────────────────────┐  HTTP   ┌─────────────────────┐
│  Dana edits sentences  │────────────▶│  GitHub                    │◀────────│  Render.com (Python)│
│  sentences.md (this    │             │  raw.githubusercontent.com │  fetch  │  Flask + Pillow     │
│  repo)                 │             │  /…/sentences.md           │  (60s   │  GET /image.png     │
└────────────────────────┘             └────────────────────────────┘  cache) └──────────┬──────────┘
                                                                                         │ PNG 800×480
                                                                                         │ 1-bit mono
                                                                                         ▼
                                                                              ┌─────────────────────┐
                                                                              │ XIAO ESP32 + 7.5"   │
                                                                              │ e-paper (battery)   │
                                                                              │ wake → fetch → draw │
                                                                              │ → deep sleep 5 min  │
                                                                              └─────────────────────┘
```

Three independently testable pieces:

1. **`sentences.md`** — already exists. Source of truth.
2. **Flask service on Render.com** — fetches the list, picks one at random, renders a Hebrew PNG.
3. **XIAO firmware** — fetches the PNG and pushes it to the panel.

## Component 1: Flask server

**Endpoint:** `GET /image.png` → `Content-Type: image/png`, 800×480, 1-bit grayscale, `Cache-Control: no-store`.

**Request flow:**
1. Fetch the sentences file from `SENTENCES_URL` (env var set in Render dashboard, e.g. `https://raw.githubusercontent.com/<user>/<repo>/main/sentences.md`). 60s in-memory cache to avoid hammering GitHub.
2. Parse: split on blank lines; strip leading line numbers, markdown `**` wrappers, trailing whitespace; drop empties.
3. `random.choice()` over the list.
4. Reshape with `python-bidi` (logical → visual order for RTL rendering).
5. Word-wrap to panel width (with a small horizontal margin, target ~760px of usable width).
6. Auto-fit font size: start at 64pt; shrink in 4pt steps until the wrapped block fits inside 800×440 (leaving vertical margin). This keeps short sentences large and centered while long ones remain readable.
7. Render to a 1-bit `PIL.Image`, center the text block vertically and horizontally.
8. Return as PNG bytes.

**Font:** Frank Ruhl Libre Medium (`FrankRuhlLibre-Medium.ttf`). Classic Hebrew book typeface from 1908. Committed to the repo under `server/fonts/`.

**Files (`server/` directory):**

| File | Purpose |
|------|---------|
| `app.py` | Flask app, single `/image.png` route. |
| `render.py` | `render_sentence(text: str) -> bytes` — pure function, unit-testable. |
| `sentences_source.py` | `fetch_sentences() -> list[str]` with 60s cache. |
| `requirements.txt` | `flask`, `pillow`, `python-bidi`, `requests`, `gunicorn`. |
| `fonts/FrankRuhlLibre-Medium.ttf` | The font. |
| `render.yaml` | Render blueprint: free web service, `gunicorn app:app`, declares `SENTENCES_URL` env var. |
| `tests/test_render.py` | Snapshot tests for short/medium/long Hebrew strings. |

**Error handling — server never returns HTTP error to the device:**

| Failure | Response |
|---------|----------|
| GitHub fetch fails, cache still warm | Use cached list. |
| GitHub fetch fails, cache empty | Render fallback image "אין חיבור לשרת" (no server connection). |
| Empty sentence list | Render fallback "אין משפטים" (no sentences). |
| `render_sentence` raises | Render a plain "שגיאה" image and log. |

The device's behavior is "fetch a PNG and show it" — any errors handled here mean the display never goes blank or shows an HTTP error code.

## Component 2: XIAO firmware

**Lifecycle (every wake = full main):**
1. Boot from deep sleep.
2. Init the 7.5" panel (GxEPD2).
3. Connect Wi-Fi (15s timeout).
4. `HTTP GET <SERVER_URL>/image.png` into a memory buffer.
5. Decode PNG with PNGdec, stream rows into the panel framebuffer.
6. `display.display()` — full refresh (~3s).
7. `esp_deep_sleep_start()` with a 5-minute timer wake.

**Files (`firmware/` PlatformIO project):**

| File | Purpose |
|------|---------|
| `platformio.ini` | Board: `seeed_xiao_esp32c3` (or `_s3` — confirm during plan); framework: arduino; libs: `GxEPD2`, `bitbank2/PNGdec`. |
| `src/main.cpp` | Lifecycle above. |
| `src/secrets.h` | Wi-Fi SSID/password, server URL. **Gitignored.** |
| `src/secrets.example.h` | Template, committed. |
| `.gitignore` | Ignores `src/secrets.h`, build artifacts. |

**Libraries:**
- **GxEPD2** — supports Seeed 7.5" (UC8179 controller; exact class `GxEPD2_750_T7` or `GxEPD2_750_GDEY075T7` confirmed during implementation against the actual panel revision).
- **bitbank2/PNGdec** — row-streaming PNG decoder, ~5KB working memory.
- **HTTPClient / WiFiClientSecure** — Arduino-ESP32 built-ins.

**Error handling — each failure does ONE thing then sleeps:**

| Failure | Action |
|---------|--------|
| Wi-Fi connect timeout | Skip refresh, deep sleep 5 min. |
| HTTP non-200 | Skip refresh, deep sleep 5 min. |
| PNG decode error | Skip refresh, deep sleep 5 min. |

The panel retains the last image during these no-ops (free with e-ink), so failed refreshes are silent — the user keeps seeing the previous sentence until the next successful poll.

## Edit workflow

1. Open `sentences.md` locally, add/remove/edit lines.
2. `git push`.
3. Within ~60 seconds (server cache TTL) the next poll picks up the new list.
4. Within ~5 minutes (device poll interval) the screen reflects it.

No admin UI, no auth, no database. Sentences live in git history.

## Power budget

Battery: 2000mAh LiPo (representative).

| Phase | Duration / interval | Current (avg) |
|-------|---------------------|---------------|
| Deep sleep | ~5 min between wakes | ~20-50µA |
| Wi-Fi + HTTP + render | ~6-10s per wake | ~80mA |

Estimate: ~3-4 weeks per charge at 5-minute polling. The Wi-Fi connect cycle dominates; longer poll intervals scale roughly linearly.

## Non-goals (explicitly out of scope)

- No web admin UI for editing sentences (git is the editor).
- No per-device targeting (every device sees the same `/image.png`; the server is stateless w.r.t. clients).
- No scheduling logic (no "morning sentence vs evening sentence").
- No OTA firmware updates.
- No analytics / display-history tracking.
- No multi-color rendering (panel is monochrome).

## Open implementation questions (resolved during plan)

1. Exact XIAO model: ESP32-C3 vs S3 vs C6 (Dana to confirm from the actual board).
2. Exact panel revision: which Seeed 7.5" SKU (controller + GxEPD2 class).
3. Panel orientation: landscape (800×480) vs portrait (480×800).
4. Whether to include the "**" emphasis from `sentences.md` as bold styling, or strip it as markdown noise. Default: strip.
