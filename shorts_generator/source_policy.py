"""Shared canonical YouTube URL policy for CLI and web entry points."""

from __future__ import annotations

import ipaddress
from urllib.parse import parse_qs, urlparse, urlunparse

ALLOWED_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    }
)


def canonical_youtube_url(value: str) -> str:
    raw = value.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        raise ValueError("Only HTTPS YouTube URLs are supported.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL user information is not supported.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("The URL port is invalid.") from exc
    if port is not None:
        raise ValueError("Custom URL ports are not supported.")

    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    else:
        raise ValueError("IP-literal URLs are not supported.")
    if host not in ALLOWED_YOUTUBE_HOSTS:
        raise ValueError("Only canonical YouTube video URLs are supported.")

    path = parsed.path or "/"
    if host == "youtu.be":
        video_id = path.lstrip("/").split("/", 1)[0]
    elif path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    else:
        parts = path.strip("/").split("/")
        video_id = (
            parts[1]
            if len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}
            else ""
        )
    if not video_id or not all(ch.isalnum() or ch in "_-" for ch in video_id):
        raise ValueError(
            "Enter a supported YouTube watch, shorts, live, embed, or youtu.be URL."
        )

    normalized_host = "youtu.be" if host == "youtu.be" else "www.youtube.com"
    return urlunparse(("https", normalized_host, path, "", parsed.query, ""))
