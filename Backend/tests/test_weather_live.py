"""Focused tests for live weather response validation."""
import pytest

from app.services import weather_live


def test_current_rejects_partial_station_payload(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [{}]

    monkeypatch.setattr(weather_live.requests, "get", lambda *args, **kwargs: Response())

    with pytest.raises(RuntimeError, match="locations"):
        weather_live.current()


def test_finite_number_rejects_invalid_upstream_values():
    assert weather_live._finite_number("12.5") == 12.5
    assert weather_live._finite_number("not-a-number") is None
