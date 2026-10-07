"""Structural stream URL validation; no remote URL is fetched by the bot."""

import ipaddress
import re
from urllib.parse import urlsplit


def validate_stream_url(value):
    value = value.strip()
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid stream URL.") from None
    host = host.rstrip(".").lower() if host else host
    invalid = (
        parsed.scheme not in ("http", "https")
        or not host
        or "." not in host
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 80, 443)
        or len(value) > 512
        or any(c.isspace() or ord(c) < 32 for c in value)
        or any(c in value for c in ("\\", "<", ">", "`"))
    )
    if not invalid:
        try:
            ipaddress.ip_address(host)
            invalid = True  # Link buttons must use public DNS names, not IP literals.
        except ValueError:
            labels = host.rstrip(".").split(".")
            invalid = (
                len(host) > 253
                or len(labels) < 2
                or labels[-1].isdigit()
                or host.endswith(
                    (".local", ".localhost", ".internal", ".test", ".lan", ".home", ".invalid")
                )
                or any(
                    not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                    for label in labels
                )
            )
    if invalid:
        raise ValueError(
            "Use a valid public http(s) stream URL without credentials (max 512 characters)."
        )
    return value
