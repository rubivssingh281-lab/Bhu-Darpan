"""Real-time weather for Jammu & Kashmir — a live 'weather desk' for the twin.

Pulls current conditions and today's outlook for the major J&K stations from the
Open-Meteo forecast API (keyless, free, ERA5/ICON-based — the same provider the twin
already assimilates). Results are cached briefly so the dashboard can poll cheaply.

https://open-meteo.com/en/docs
"""
from __future__ import annotations

import time

import requests

_FORECAST = "https://api.open-meteo.com/v1/forecast"
_TTL = 600  # seconds — cache a pull for 10 minutes
_cache: dict = {"at": 0.0, "data": None}

# Representative J&K stations across the valley, plains, high Himalaya and Ladakh.
STATIONS = [
    ("Srinagar", 34.08, 74.80),
    ("Jammu", 32.73, 74.87),
    ("Gulmarg", 34.05, 74.38),
    ("Pahalgam", 34.01, 75.31),
    ("Leh (Ladakh)", 34.16, 77.58),
    ("Kupwara", 34.53, 74.26),
]

# WMO weather-interpretation codes → (label, emoji)
_WMO = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "\U0001f324️"), 2: ("Partly cloudy", "⛅"), 3: ("Overcast", "☁️"),
    45: ("Fog", "\U0001f32b️"), 48: ("Rime fog", "\U0001f32b️"),
    51: ("Light drizzle", "\U0001f327️"), 53: ("Drizzle", "\U0001f327️"), 55: ("Heavy drizzle", "\U0001f327️"),
    56: ("Freezing drizzle", "\U0001f327️"), 57: ("Freezing drizzle", "\U0001f327️"),
    61: ("Light rain", "\U0001f326️"), 63: ("Rain", "\U0001f327️"), 65: ("Heavy rain", "\U0001f327️"),
    66: ("Freezing rain", "\U0001f327️"), 67: ("Freezing rain", "\U0001f327️"),
    71: ("Light snow", "\U0001f328️"), 73: ("Snow", "\U0001f328️"), 75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "\U0001f328️"),
    80: ("Rain showers", "\U0001f326️"), 81: ("Rain showers", "\U0001f327️"), 82: ("Violent showers", "⛈️"),
    85: ("Snow showers", "\U0001f328️"), 86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Storm w/ hail", "⛈️"), 99: ("Storm w/ hail", "⛈️"),
}


def _describe(code):
    return _WMO.get(int(code) if code is not None else -1, ("—", "\U0001f321️"))


def current(region: str = "jk") -> dict:
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < _TTL:
        return _cache["data"]

    lat = ",".join(f"{s[1]:.4f}" for s in STATIONS)
    lon = ",".join(f"{s[2]:.4f}" for s in STATIONS)
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,precipitation_probability_max",
        "timezone": "Asia/Kolkata", "forecast_days": 1,
    }
    r = requests.get(_FORECAST, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    locs = payload if isinstance(payload, list) else [payload]

    stations = []
    for (name, la, lo), loc in zip(STATIONS, locs):
        cur = loc.get("current", {})
        day = loc.get("daily", {})
        label, emoji = _describe(cur.get("weather_code"))
        stations.append({
            "name": name, "lat": la, "lon": lo,
            "temp_c": cur.get("temperature_2m"),
            "feels_c": cur.get("apparent_temperature"),
            "humidity_pct": cur.get("relative_humidity_2m"),
            "precip_mm": cur.get("precipitation"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "condition": label, "icon": emoji,
            "high_c": (day.get("temperature_2m_max") or [None])[0],
            "low_c": (day.get("temperature_2m_min") or [None])[0],
            "rain_chance_pct": (day.get("precipitation_probability_max") or [None])[0],
            "observed_at": cur.get("time"),
        })

    out = {
        "region": "Jammu & Kashmir",
        "source": "Open-Meteo (live forecast API)",
        "updated_at": stations[0]["observed_at"] if stations else None,
        "stations": stations,
    }
    _cache.update(at=now, data=out)
    return out
