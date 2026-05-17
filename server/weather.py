"""Fetch Kfar Saba weather via Open-Meteo (no API key, no rate limits).

Returns the morning (07:00) and noon (12:00) temperatures + conditions, and a
short Hebrew cute-sentence advising what to wear / take.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

log = logging.getLogger(__name__)

LAT = 32.18
LON = 34.91
TZ_NAME = "Asia/Jerusalem"
TZ = ZoneInfo(TZ_NAME)
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes
HTTP_TIMEOUT_SECONDS = 10

API_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code → short Hebrew label.
WMO_LABELS: dict[int, str] = {
    0:  "בהיר",
    1:  "מעט עננים",
    2:  "מעונן חלקית",
    3:  "מעונן",
    45: "ערפל",
    48: "ערפל",
    51: "טפטוף",
    53: "טפטוף",
    55: "טפטוף חזק",
    61: "גשם",
    63: "גשם",
    65: "גשם חזק",
    71: "שלג",
    73: "שלג",
    75: "שלג חזק",
    80: "ממטרים",
    81: "ממטרים",
    82: "ממטרים חזקים",
    95: "סופת רעמים",
    96: "סופת רעמים",
    99: "סופת רעמים",
}

# WMO codes that mean precipitation.
RAIN_CODES = {51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99}
HEAVY_RAIN_CODES = {65, 82, 95, 96, 99}
SNOW_CODES = {71, 73, 75}

_cache: dict = {"data": None, "expires_at": 0.0}


def _label_for(code: int) -> str:
    return WMO_LABELS.get(code, "מזג אוויר")


def _icon_kind(morning_code: int, noon_code: int) -> str:
    """Pick the icon that best represents the day. Picks the most 'dramatic'
    of the two — rain trumps clouds trumps clear — so a partly-rainy day still
    shows the umbrella rather than the sun."""
    codes = (morning_code, noon_code)
    if any(c in SNOW_CODES for c in codes):
        return "snow"
    if any(c in (95, 96, 99) for c in codes):
        return "thunder"
    if any(c in HEAVY_RAIN_CODES for c in codes):
        return "heavy_rain"
    if any(c in RAIN_CODES for c in codes):
        return "rain"
    if any(c in (45, 48) for c in codes):
        return "fog"
    # Clear-ish codes 0-3; pick partly_cloudy if either is overcast/partly.
    if any(c in (2, 3) for c in codes):
        return "partly_cloudy"
    if any(c == 1 for c in codes):
        return "partly_cloudy"
    return "sun"


def _hour_index(times: list[str], hour: int) -> int | None:
    """Find the index in the hourly forecast for today's `hour`. The API
    returns timestamps as 'YYYY-MM-DDTHH:00' in Asia/Jerusalem."""
    today = datetime.now(TZ).strftime("%Y-%m-%dT")
    target = f"{today}{hour:02d}:00"
    try:
        return times.index(target)
    except ValueError:
        return None


def fetch_weather() -> dict | None:
    """Return today's Kfar Saba forecast or None on persistent failure.

    Dict shape:
      {
        "morning_temp": float, "morning_label": str,
        "noon_temp":    float, "noon_label":    str,
        "cute":         str,
      }
    """
    now = time.time()
    if _cache["data"] and _cache["expires_at"] > now:
        return _cache["data"]

    try:
        resp = requests.get(
            API_URL,
            params={
                "latitude":  LAT,
                "longitude": LON,
                "hourly":    "temperature_2m,weathercode",
                "timezone":  TZ_NAME,
                "forecast_days": 1,
            },
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        body = resp.json()
        hourly = body["hourly"]
        times = hourly["time"]
        temps = hourly["temperature_2m"]
        codes = hourly["weathercode"]

        m_idx = _hour_index(times, 7)
        n_idx = _hour_index(times, 12)
        if m_idx is None or n_idx is None:
            log.warning("Could not locate 07:00/12:00 in forecast")
            return _cache["data"]

        m_temp = float(temps[m_idx])
        n_temp = float(temps[n_idx])
        m_code = int(codes[m_idx])
        n_code = int(codes[n_idx])

        data = {
            "morning_temp":  m_temp,
            "morning_label": _label_for(m_code),
            "noon_temp":     n_temp,
            "noon_label":    _label_for(n_code),
            "icon_kind":     _icon_kind(m_code, n_code),
        }
        _cache["data"] = data
        _cache["expires_at"] = now + CACHE_TTL_SECONDS
        return data
    except Exception as e:
        log.warning("Weather fetch failed: %s", e)
        return _cache["data"]


def format_weather_text(data: dict) -> str:
    """Format the two weather rows (morning + noon) as a 2-line text block.

    The render path treats `\\n` as a forced line break, so this lays out as
    two centered lines. The icon is rendered separately, below the text.
    """
    return (
        f"בוקר {round(data['morning_temp'])}° - {data['morning_label']}\n"
        f"צהריים {round(data['noon_temp'])}° - {data['noon_label']}"
    )
