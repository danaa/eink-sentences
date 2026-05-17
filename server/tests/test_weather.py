from unittest.mock import patch, MagicMock
import server.weather as weather


def setup_function(_):
    weather._cache["data"] = None
    weather._cache["expires_at"] = 0.0


def _fake_api(times, temps, codes):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"hourly": {
        "time": times, "temperature_2m": temps, "weathercode": codes,
    }}
    r.raise_for_status = MagicMock()
    return r


def _times_for_today():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d")
    return [f"{today}T{h:02d}:00" for h in range(24)]


def test_icon_kind_rain_wins_over_clear():
    assert weather._icon_kind(0, 61) == "rain"
    assert weather._icon_kind(61, 0) == "rain"


def test_icon_kind_thunder_wins_over_rain():
    assert weather._icon_kind(95, 61) == "thunder"


def test_icon_kind_heavy_rain():
    assert weather._icon_kind(65, 0) == "heavy_rain"


def test_icon_kind_partly_cloudy_for_codes_1_to_3():
    assert weather._icon_kind(0, 2) == "partly_cloudy"
    assert weather._icon_kind(1, 0) == "partly_cloudy"


def test_icon_kind_pure_sun_only_when_code_zero_both():
    assert weather._icon_kind(0, 0) == "sun"


def test_icon_kind_fog():
    assert weather._icon_kind(45, 0) == "fog"


def test_icon_kind_snow():
    assert weather._icon_kind(73, 0) == "snow"


def test_fetch_weather_parses_open_meteo_response():
    times = _times_for_today()
    temps = [10.0] * 24
    codes = [0] * 24
    temps[7] = 16.4
    temps[12] = 28.0
    codes[7] = 1
    codes[12] = 3
    with patch("server.weather.requests.get",
               return_value=_fake_api(times, temps, codes)):
        data = weather.fetch_weather()
    assert data is not None
    assert round(data["morning_temp"]) == 16
    assert round(data["noon_temp"]) == 28
    assert data["morning_label"]
    assert data["noon_label"]
    assert data["icon_kind"] in {
        "sun", "cloud", "partly_cloudy", "rain", "heavy_rain", "drizzle",
        "thunder", "fog", "snow",
    }


def test_fetch_weather_falls_back_to_cache_on_failure():
    # First call succeeds
    times = _times_for_today()
    temps = [10.0] * 24
    codes = [0] * 24
    temps[7] = 12.0
    temps[12] = 13.0
    with patch("server.weather.requests.get",
               return_value=_fake_api(times, temps, codes)):
        first = weather.fetch_weather()
    weather._cache["expires_at"] = 0  # force TTL expiry
    with patch("server.weather.requests.get",
               side_effect=Exception("network down")):
        second = weather.fetch_weather()
    assert first == second


def test_format_weather_text_is_two_lines():
    data = {
        "morning_temp": 16.4,
        "morning_label": "בהיר",
        "noon_temp": 28.7,
        "noon_label": "בהיר",
        "icon_kind": "sun",
    }
    text = weather.format_weather_text(data)
    lines = text.split("\n")
    assert len(lines) == 2
    assert "16" in lines[0]
    assert "29" in lines[1]
