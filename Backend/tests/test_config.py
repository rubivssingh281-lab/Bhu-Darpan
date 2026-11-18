"""Environment fallback regression coverage."""


def test_invalid_numeric_settings_use_defaults(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("PORT", "not-a-port")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "not-a-number")
    monkeypatch.setenv("AUTO_REFRESH_HOURS", "not-a-number")

    settings = Settings()

    assert settings.port == 8000
    assert settings.jwt_expire_minutes == 1440
    assert settings.auto_refresh_hours >= 0
