"""Authentication routes.

Supports two flows, both issuing a JWT on success:
  * Password login          — POST /login         (email + password)
  * Email OTP (one-time PIN) — POST /register  -> emails a code, then
                               POST /verify-otp -> creates the account
                               POST /request-otp -> emails a login code, then
                               POST /verify-otp -> signs the user in

OTPs are 6-digit codes, hashed at rest, single-collection, expiring after
`OTP_EXPIRE_MINUTES`. Email delivery uses SMTP when configured; otherwise the
service runs in dev mode and returns the code in the response so the flow is
fully demo-able offline.
"""
from __future__ import annotations

import math
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import settings
from ..database import db
from ..deps import get_current_user
from ..schemas import (
    AuthResponse, LoginRequest, OtpStartResponse, RegisterRequest,
    RequestOtpRequest, UserOut, VerifyOtpRequest,
)
from ..security import create_access_token, hash_password, verify_password
from ..services import email_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _public(user: dict) -> dict:
    return {"id": user["id"], "name": user["name"],
            "email": user["email"], "created_at": user["created_at"],
            "organization": user.get("organization", ""), "role": user.get("role", "")}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue(user: dict) -> dict:
    token = create_access_token(user["id"], {"email": user["email"]})
    return {"token": token, "user": _public(user)}


def _start_otp(email: str, purpose: str, name: str = "", password_hash: str = "",
               organization: str = "", role: str = "") -> OtpStartResponse:
    """Generate + persist an OTP for `email`, email it, and return the start response.

    Rate-limited per address: a short resend cooldown and a hard cap on how many
    codes may be issued for one pending record — prevents using the endpoint to
    spam / email-bomb an inbox.
    """
    now = _now()
    existing = db.otps.find_one({"email": email})
    send_count = 0
    if existing:
        last = existing.get("last_sent_at")
        if last:
            elapsed = (now - datetime.fromisoformat(last)).total_seconds()
            if elapsed < settings.otp_resend_cooldown_seconds:
                wait = math.ceil(settings.otp_resend_cooldown_seconds - elapsed)
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                    f"Please wait {wait}s before requesting another code.")
        send_count = existing.get("send_count", 0)
        if send_count >= settings.otp_max_sends:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                                "Too many codes requested for this email. Try again later.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = (now + timedelta(minutes=settings.otp_expire_minutes)).isoformat()

    db.otps.delete_one({"email": email})           # one active OTP per email
    db.otps.insert_one({
        "email": email,
        "code_hash": hash_password(code),
        "purpose": purpose,
        "name": name,
        "password_hash": password_hash,
        "organization": organization,
        "role": role,
        "expires_at": expires,
        "attempts": 0,
        "send_count": send_count + 1,
        "last_sent_at": now.isoformat(),
    })

    sent = email_service.send_otp_email(email, code, purpose)
    # Expose the code in the response only when there's no real delivery (SMTP not
    # configured) or when the explicit OTP_DEV_MODE test switch is on. In normal
    # production (SMTP set, dev mode off) the code is never returned.
    expose = (not sent) or settings.otp_dev_mode
    return OtpStartResponse(
        status="otp_sent", email=email, purpose=purpose,
        expires_in_minutes=settings.otp_expire_minutes,
        delivery="email" if sent else "dev",
        dev_otp=code if expose else None,
    )


@router.post("/register", response_model=OtpStartResponse)
def register(body: RegisterRequest):
    """Step 1 of sign-up: validate, stash a pending record, email a verification code.
    The account is only created after the code is verified (POST /verify-otp)."""
    email = body.email.lower()
    if db.users.find_one({"email": email}):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return _start_otp(email, "register", name=body.name.strip(),
                      password_hash=hash_password(body.password),
                      organization=body.organization.strip(), role=body.role.strip())


@router.post("/request-otp", response_model=OtpStartResponse)
def request_otp(body: RequestOtpRequest):
    """Email a one-time sign-in code to an existing user."""
    email = body.email.lower()
    if not db.users.find_one({"email": email}):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No account for that email — create one first.")
    return _start_otp(email, "login")


@router.post("/verify-otp", response_model=AuthResponse)
def verify_otp(body: VerifyOtpRequest):
    """Step 2: verify the code and complete registration or sign-in."""
    email = body.email.lower()
    rec = db.otps.find_one({"email": email})
    if not rec:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "No pending code for this email. Request a new one.")

    if datetime.fromisoformat(rec["expires_at"]) < _now():
        db.otps.delete_one({"email": email})
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Code expired. Request a new one.")

    if rec.get("attempts", 0) >= settings.otp_max_attempts:
        db.otps.delete_one({"email": email})
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many attempts. Request a new code.")

    if not verify_password(body.code.strip(), rec["code_hash"]):
        db.otps.update_one({"email": email}, {"$set": {"attempts": rec.get("attempts", 0) + 1}})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect code.")

    # Code is valid — consume it
    db.otps.delete_one({"email": email})

    if rec["purpose"] == "register":
        if db.users.find_one({"email": email}):          # race / double-submit guard
            user = db.users.find_one({"email": email})
        else:
            user = {
                "id": uuid.uuid4().hex,
                "name": rec.get("name") or email.split("@")[0],
                "email": email,
                "password_hash": rec["password_hash"],
                "organization": rec.get("organization", ""),
                "role": rec.get("role", ""),
                "email_verified": True,
                "created_at": _now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
            db.users.insert_one(user)
    else:  # login
        user = db.users.find_one({"email": email})
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Account no longer exists.")

    return _issue(user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    user = db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _issue(user)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return _public(user)
