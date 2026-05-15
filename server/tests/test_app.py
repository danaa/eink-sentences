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
    assert resp.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_healthcheck():
    app = create_app()
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
