from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from server.app import create_app, _is_morning_window, _is_evening_window


IL = ZoneInfo("Asia/Jerusalem")


def test_image_endpoint_returns_png():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_sentences", return_value=["שלום"]), \
         patch("server.app._is_morning_window", return_value=False), \
         patch("server.app._is_evening_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "image/png"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_endpoint_uses_fallback_when_no_sentences():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_sentences", return_value=[]), \
         patch("server.app._is_morning_window", return_value=False), \
         patch("server.app._is_evening_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_endpoint_uses_morning_pool_in_window():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_morning_sentences",
               return_value=["ציחצחתי שיניים?"]) as morning_mock, \
         patch("server.app.fetch_sentences") as regular_mock, \
         patch("server.app.fetch_evening_sentences") as evening_mock, \
         patch("server.app.fetch_weather", return_value=None), \
         patch("server.app._is_morning_window", return_value=True), \
         patch("server.app._is_evening_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    morning_mock.assert_called_once()
    regular_mock.assert_not_called()
    evening_mock.assert_not_called()


def test_image_endpoint_includes_weather_card_in_morning_pool():
    """When weather fetch succeeds, the card is mixed into the morning pool."""
    app = create_app()
    client = app.test_client()
    fake_weather = {
        "morning_temp": 16.0, "morning_label": "בהיר",
        "noon_temp": 28.0, "noon_label": "בהיר",
        "icon_kind": "sun",
    }
    with patch("server.app.fetch_morning_sentences",
               return_value=["ציחצחתי שיניים?"]), \
         patch("server.app.fetch_weather", return_value=fake_weather) as w, \
         patch("server.app._is_morning_window", return_value=True), \
         patch("server.app._is_evening_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    w.assert_called_once()


def test_image_endpoint_uses_evening_pool_in_window():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_morning_sentences") as morning_mock, \
         patch("server.app.fetch_sentences") as regular_mock, \
         patch("server.app.fetch_evening_sentences",
               return_value=["אכלתי ארוחת ערב?"]) as evening_mock, \
         patch("server.app._is_morning_window", return_value=False), \
         patch("server.app._is_evening_window", return_value=True):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    evening_mock.assert_called_once()
    morning_mock.assert_not_called()
    regular_mock.assert_not_called()


def test_image_endpoint_uses_regular_pool_outside_windows():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_morning_sentences") as morning_mock, \
         patch("server.app.fetch_sentences", return_value=["שלום"]) as regular_mock, \
         patch("server.app.fetch_evening_sentences") as evening_mock, \
         patch("server.app._is_morning_window", return_value=False), \
         patch("server.app._is_evening_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    regular_mock.assert_called_once()
    morning_mock.assert_not_called()
    evening_mock.assert_not_called()


def test_morning_window_boundaries():
    assert _is_morning_window(datetime(2026, 5, 17, 6, 29, tzinfo=IL)) is False
    assert _is_morning_window(datetime(2026, 5, 17, 6, 30, tzinfo=IL)) is True
    assert _is_morning_window(datetime(2026, 5, 17, 7, 0, tzinfo=IL)) is True
    assert _is_morning_window(datetime(2026, 5, 17, 9, 0, tzinfo=IL)) is True
    assert _is_morning_window(datetime(2026, 5, 17, 9, 29, tzinfo=IL)) is True
    assert _is_morning_window(datetime(2026, 5, 17, 9, 30, tzinfo=IL)) is False
    assert _is_morning_window(datetime(2026, 5, 17, 12, 0, tzinfo=IL)) is False
    assert _is_morning_window(datetime(2026, 5, 17, 2, 0, tzinfo=IL)) is False


def test_evening_window_boundaries():
    # 18:44 -> not evening
    assert _is_evening_window(datetime(2026, 5, 17, 18, 44, tzinfo=IL)) is False
    # 18:45 -> evening (inclusive start)
    assert _is_evening_window(datetime(2026, 5, 17, 18, 45, tzinfo=IL)) is True
    # 19:30 -> evening
    assert _is_evening_window(datetime(2026, 5, 17, 19, 30, tzinfo=IL)) is True
    # 20:44 -> evening
    assert _is_evening_window(datetime(2026, 5, 17, 20, 44, tzinfo=IL)) is True
    # 20:45 -> not evening (exclusive end)
    assert _is_evening_window(datetime(2026, 5, 17, 20, 45, tzinfo=IL)) is False
    # 12:00 -> not evening
    assert _is_evening_window(datetime(2026, 5, 17, 12, 0, tzinfo=IL)) is False


def test_healthcheck():
    app = create_app()
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
