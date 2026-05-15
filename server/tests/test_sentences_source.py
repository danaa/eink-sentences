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
    src._cache["sentences"] = []
    src._cache["expires_at"] = 0.0


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
    with patch("server.sentences_source.requests.get",
               return_value=_make_response("שלום\n")):
        src.fetch_sentences()
    src._cache["expires_at"] = 0
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
