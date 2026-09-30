"""J&K weather news headlines — a live news feed for the twin's Insights page.

Fetches recent weather-related headlines for Jammu & Kashmir from a third-party news
API (NewsAPI or GNews — whichever key is configured). The API key is read from the
environment (never hard-coded); with no key the panel degrades to a friendly notice.

Results are cached for 30 minutes to conserve the free-tier request quota. Headlines
are treated purely as data for display — never as instructions.
"""
from __future__ import annotations

import time

import requests

from ..config import settings

_TTL = 1800  # 30 minutes — news changes slowly and free tiers cap at ~100 req/day
_cache: dict = {"at": 0.0, "data": None}

# Focused query: a J&K place AND a weather term, so we don't pull unrelated regional news.
# Kept compact — GNews caps the query at 200 characters.
_PLACES = "Kashmir OR Jammu OR Ladakh OR Srinagar"
_TOPICS = "weather OR rain OR snow OR flood OR avalanche OR heatwave OR forecast OR IMD OR monsoon"
_QUERY = f"({_PLACES}) AND ({_TOPICS})"


def _fetch_newsapi(key: str, limit: int) -> list[dict]:
    r = requests.get("https://newsapi.org/v2/everything", timeout=25, params={
        "q": _QUERY, "language": "en", "sortBy": "publishedAt",
        "pageSize": limit, "apiKey": key,
    })
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok":
        raise RuntimeError(data.get("message", "NewsAPI error"))
    out = []
    for a in data.get("articles", []):
        out.append({"title": a.get("title"), "summary": a.get("description"),
                    "url": a.get("url"), "image": a.get("urlToImage"),
                    "source": (a.get("source") or {}).get("name"),
                    "published_at": a.get("publishedAt")})
    return out


def _fetch_gnews(key: str, limit: int) -> list[dict]:
    r = requests.get("https://gnews.io/api/v4/search", timeout=25, params={
        "q": _QUERY, "lang": "en", "country": "in", "max": limit, "apikey": key,
    })
    r.raise_for_status()
    data = r.json()
    out = []
    for a in data.get("articles", []):
        out.append({"title": a.get("title"), "summary": a.get("description"),
                    "url": a.get("url"), "image": a.get("image"),
                    "source": (a.get("source") or {}).get("name"),
                    "published_at": a.get("publishedAt")})
    return out


def headlines(region: str = "jk", limit: int = 8) -> dict:
    if not settings.news_configured:
        return {"configured": False, "provider": settings.news_provider, "articles": [],
                "hint": "Set NEWS_API_KEY in Backend/.env (NewsAPI or GNews) to enable "
                        "live weather headlines."}

    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < _TTL:
        return _cache["data"]

    provider = settings.news_provider
    fetch = _fetch_gnews if provider == "gnews" else _fetch_newsapi
    articles = fetch(settings.news_api_key, limit)

    # keep only well-formed, de-duplicated items
    seen, clean = set(), []
    for a in articles:
        t = (a.get("title") or "").strip()
        if not t or not a.get("url") or t.lower() in seen:
            continue
        seen.add(t.lower())
        clean.append(a)

    out = {"configured": True, "provider": provider, "region": "Jammu & Kashmir",
           "count": len(clean), "articles": clean}
    _cache.update(at=now, data=out)
    return out
