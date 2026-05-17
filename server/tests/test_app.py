from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from server.app import create_app, _is_morning_window


IL = ZoneInfo("Asia/Jerusalem")


def test_image_endpoint_returns_png():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_sentences", return_value=["שלום"]), \
         patch("server.app._is_morning_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "image/png"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_endpoint_uses_fallback_when_no_sentences():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_sentences", return_value=[]), \
         patch("server.app._is_morning_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_endpoint_uses_morning_pool_in_window():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_morning_sentences",
               return_value=["ציחצחתי שיניים?"]) as morning_mock, \
         patch("server.app.fetch_sentences") as regular_mock, \
         patch("server.app._is_morning_window", return_value=True):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    morning_mock.assert_called_once()
    regular_mock.assert_not_called()


def test_image_endpoint_uses_regular_pool_outside_window():
    app = create_app()
    client = app.test_client()
    with patch("server.app.fetch_morning_sentences") as morning_mock, \
         patch("server.app.fetch_sentences", return_value=["שלום"]) as regular_mock, \
         patch("server.app._is_morning_window", return_value=False):
        resp = client.get("/image.png")
    assert resp.status_code == 200
    regular_mock.assert_called_once()
    morning_mock.assert_not_called()


def test_morning_window_boundaries():
    # 6:29 -> not morning
    assert _is_morning_window(datetime(2026, 5, 17, 6, 29, tzinfo=IL)) is False
    # 6:30 -> morning (inclusive start)
    assert _is_morning_window(datetime(2026, 5, 17, 6, 30, tzinfo=IL)) is True
    # 7:00 -> morning
    assert _is_morning_window(datetime(2026, 5, 17, 7, 0, tzinfo=IL)) is True
    # 7:30 -> still morning (end is 08:00)
    assert _is_morning_window(datetime(2026, 5, 17, 7, 30, tzinfo=IL)) is True
    # 7:59 -> morning
    assert _is_morning_window(datetime(2026, 5, 17, 7, 59, tzinfo=IL)) is True
    # 8:00 -> not morning (exclusive end)
    assert _is_morning_window(datetime(2026, 5, 17, 8, 0, tzinfo=IL)) is False
    # 12:00 -> not morning
    assert _is_morning_window(datetime(2026, 5, 17, 12, 0, tzinfo=IL)) is False
    # 2:00 AM -> not morning (per "from 6:30")
    assert _is_morning_window(datetime(2026, 5, 17, 2, 0, tzinfo=IL)) is False


def test_healthcheck():
    app = create_app()
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
