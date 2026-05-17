"""Flask app — single endpoint returns a Hebrew PNG for the e-paper."""
from __future__ import annotations

import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify
from PIL import features, __version__ as pil_version

from server.render import render_sentence, render_weather, _LAYOUT_ENGINE
from server.sentences_source import (
    fetch_sentences,
    fetch_morning_sentences,
    fetch_evening_sentences,
)
from server.weather import fetch_weather, format_weather_text

log = logging.getLogger(__name__)

FALLBACK_NO_SENTENCES = "אין משפטים"
FALLBACK_ERROR = "שגיאה"

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")
MORNING_START_MIN = 6 * 60 + 30   # 06:30
MORNING_END_MIN   = 9 * 60 + 30   # 09:30
EVENING_START_MIN = 18 * 60 + 45  # 18:45
EVENING_END_MIN   = 20 * 60 + 45  # 20:45


def _now_israel() -> datetime:
    """Indirection point so tests can inject a fixed time."""
    return datetime.now(ISRAEL_TZ)


def _minutes_of_day(now: datetime) -> int:
    return now.hour * 60 + now.minute


def _is_morning_window(now: datetime) -> bool:
    return MORNING_START_MIN <= _minutes_of_day(now) < MORNING_END_MIN


def _is_evening_window(now: datetime) -> bool:
    return EVENING_START_MIN <= _minutes_of_day(now) < EVENING_END_MIN


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def health() -> str:
        return "ok"

    @app.get("/diag")
    def diag():
        now = _now_israel()
        return jsonify({
            "pillow": pil_version,
            "freetype": features.version("freetype2"),
            "raqm_available": features.check("raqm"),
            "libimagequant": features.check("libimagequant"),
            "layout_engine": str(_LAYOUT_ENGINE),
            "israel_time": now.isoformat(),
            "morning_window": _is_morning_window(now),
            "evening_window": _is_evening_window(now),
        })

    @app.get("/image.png")
    def image() -> Response:
        try:
            now = _now_israel()
            if _is_morning_window(now):
                # Mix today's forecast card into the morning rotation. Each
                # refresh picks from (routine prompts + 1 weather card)
                # uniformly, so over a ~1-hour window with 5-min refreshes
                # (~12 wakes) the weather appears a handful of times alongside
                # the checklist.
                pool: list = list(fetch_morning_sentences())
                weather = fetch_weather()
                if weather:
                    pool.append({"weather": weather})  # marker dict
            elif _is_evening_window(now):
                pool = list(fetch_evening_sentences())
            else:
                pool = list(fetch_sentences())

            if not pool:
                png = render_sentence(FALLBACK_NO_SENTENCES)
            else:
                choice = random.choice(pool)
                if isinstance(choice, dict) and "weather" in choice:
                    w = choice["weather"]
                    png = render_weather(format_weather_text(w),
                                         w["icon_kind"])
                else:
                    # Checklist prompts get the current time above the question
                    # so it doubles as a time display. Regular inspirational
                    # sentences (outside both windows) render as-is.
                    if _is_morning_window(now) or _is_evening_window(now):
                        text = f"{now.strftime('%H:%M')}\n{choice}"
                    else:
                        text = choice
                    png = render_sentence(text)
        except Exception as e:
            log.exception("Render failed: %s", e)
            png = render_sentence(FALLBACK_ERROR)

        return Response(
            png,
            mimetype="image/png",
            headers={"Cache-Control": "no-store"},
        )

    return app


app = create_app()
