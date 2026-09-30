"""Pydantic request/response models."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    organization: str = Field(default="", max_length=120)
    role: str = Field(default="", max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OtpStartResponse(BaseModel):
    status: str = "otp_sent"
    email: str
    purpose: str
    expires_in_minutes: int
    delivery: str            # "email" or "dev"
    dev_otp: Optional[str] = None   # only populated in dev mode (no SMTP configured)


class RequestOtpRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    created_at: str
    organization: str = ""
    role: str = ""


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class AnalysisOut(BaseModel):
    id: str
    name: str
    created_at: str
    original_url: str
    segmentation_url: str
    detection_url: str
    land_cover: dict[str, float]
    objects: list[dict[str, Any]]
    object_counts: dict[str, int]
    confidence: float
    model_type: Optional[str] = None
    model_accuracy: Optional[float] = None
    width: int
    height: int
    location: Optional[dict[str, float]] = None
    report_url: Optional[str] = None


class ChangeOut(BaseModel):
    id: str
    name: str
    created_at: str
    before_url: str
    after_url: str
    change_map_url: str
    changed_percent: float
    class_deltas: dict[str, float]
    confidence: float
    model_type: Optional[str] = None
    model_accuracy: Optional[float] = None
    transitions: list[dict[str, Any]] = []
