"""Focused tests for weather news result limits."""
from app.services import weather_news


def test_headlines_caps_requested_limit(monkeypatch):
    seen = {}

    def fake_fetch(_key, limit):
        seen["limit"] = limit
        return []

    monkeypatch.setattr(weather_news.settings, "news_api_key", "test-key")
    monkeypatch.setattr(weather_news.settings, "news_provider", "newsapi")
    monkeypatch.setattr(weather_news, "_fetch_newsapi", fake_fetch)
    weather_news._cache.update(at=0.0, data=None)

    weather_news.headlines(limit=999)

    assert seen["limit"] == 20
