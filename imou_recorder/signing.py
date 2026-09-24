"""IMOU OpenAPI request signing."""

from __future__ import annotations

import base64
import hashlib
import hmac


def signing_source(timestamp: int, nonce: str, app_secret: str) -> str:
    """Build the byte-for-byte signing source required by IMOU."""

    return f"time:{timestamp},nonce:{nonce},appSecret:{app_secret}"


def calculate_signature(
    timestamp: int,
    nonce: str,
    app_secret: str,
    algorithm: str = "hmac-sha256",
) -> str:
    """Calculate a current HMAC-SHA256 or explicitly selected legacy signature."""

    source = signing_source(timestamp, nonce, app_secret).encode("utf-8")
    if algorithm == "hmac-sha256":
        password = hashlib.sha256(app_secret.encode("utf-8")).hexdigest()
        digest = hmac.new(password.encode("utf-8"), source, hashlib.sha256).digest()
        return base64.b64encode(digest).decode("ascii")
    if algorithm == "md5":
        return hashlib.md5(source).hexdigest()  # noqa: S324 - protocol compatibility
    raise ValueError(f"Unsupported signing algorithm: {algorithm}")
