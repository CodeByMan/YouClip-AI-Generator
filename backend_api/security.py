"""Authentication and source-policy helpers for the web adapter."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os

from fastapi import HTTPException, Request
from shorts_generator.source_policy import canonical_youtube_url

MIN_HOSTED_ACCESS_KEY_LENGTH = 32
PLACEHOLDER_ACCESS_KEY_TOKENS = (
    "changeme",
    "example",
    "placeholder",
    "replace_",
    "sample",
    "secret",
    "test",
    "your_",
)


def access_mode() -> str:
    mode = os.getenv("WEB_ACCESS_MODE", "local").strip().lower()
    if mode not in {"local", "hosted"}:
        raise RuntimeError("WEB_ACCESS_MODE must be either 'local' or 'hosted'.")
    return mode


def configured_access_key() -> str:
    return os.getenv("YOUCLIP_ACCESS_KEY", "").strip()


def validate_hosted_access_key(value: str) -> str:
    cleaned = (value or "").strip()
    lowered = cleaned.lower()
    if (
        len(cleaned) < MIN_HOSTED_ACCESS_KEY_LENGTH
        or any(token in lowered for token in PLACEHOLDER_ACCESS_KEY_TOKENS)
    ):
        raise HTTPException(
            status_code=500,
            detail="Hosted access key is not safely configured.",
        )
    return cleaned


def require_access(request: Request) -> str:
    """Return a non-secret owner id after enforcing hosted access."""
    if access_mode() == "local":
        client_host = request.client.host if request.client else ""
        try:
            loopback = ipaddress.ip_address(client_host).is_loopback
        except ValueError:
            loopback = client_host == "localhost"
        if not loopback:
            raise HTTPException(
                status_code=403,
                detail="Local mode accepts requests only from the loopback interface.",
            )
        return "local"

    expected = validate_hosted_access_key(configured_access_key())
    supplied = request.headers.get("X-YouClip-Key", "")
    if not hmac.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="A valid YouClip access key is required.")
    return hashlib.sha256(supplied.encode("utf-8")).hexdigest()



__all__ = [
    "access_mode",
    "canonical_youtube_url",
    "configured_access_key",
    "require_access",
    "validate_hosted_access_key",
]
