"""Authentication and security module tests."""
from app.routers.auth import _normalize_email, _normalize_otp, _parse_utc
from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hashing():
    raw = "secureSecretPass123"
    hashed = hash_password(raw)
    assert verify_password(raw, hashed)
    assert not verify_password("wrongSecret", hashed)


def test_token_encoding_decoding():
    payload = {"sub": "user_test_01", "role": "researcher"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded.get("sub") == "user_test_01"
    assert decoded.get("role") == "researcher"


def test_email_normalization():
    assert _normalize_email("  User@Example.COM ") == "user@example.com"


def test_utc_timestamp_parsing_supports_z_and_naive_values():
    from datetime import timezone

    assert _parse_utc("2026-11-20T10:15:30Z").tzinfo == timezone.utc
    assert _parse_utc("2026-11-20T10:15:30").tzinfo == timezone.utc


def test_otp_normalization_removes_copy_formatting():
    assert _normalize_otp(" 12 34 56 ") == "123456"
