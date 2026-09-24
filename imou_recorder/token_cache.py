"""Private, local cache for short-lived IMOU administrator tokens."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
import uuid

from .client import AccessToken


class TokenCacheError(RuntimeError):
    """Raised for an unsafe or unreadable token cache."""


class TokenCache:
    def __init__(self, path: str | Path, *, expiry_margin_seconds: int = 300) -> None:
        self.path = Path(path)
        self.expiry_margin_seconds = expiry_margin_seconds

    def load(self, *, now: int | None = None) -> AccessToken | None:
        current_time = int(time.time()) if now is None else now
        if not self.path.exists():
            return None
        try:
            mode = self.path.stat().st_mode & 0o777
            if mode & 0o077:
                raise TokenCacheError(
                    f"Token cache permissions are too broad ({mode:o}); expected 600"
                )
            data = json.loads(self.path.read_text(encoding="utf-8"))
            token = data["access_token"]
            expires_at = int(data["expires_at"])
        except TokenCacheError:
            raise
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TokenCacheError("Token cache is invalid or unreadable") from exc

        remaining = expires_at - current_time
        if not isinstance(token, str) or not token or remaining <= self.expiry_margin_seconds:
            return None
        return AccessToken(value=token, expires_in_seconds=remaining)

    def save(self, token: AccessToken, *, now: int | None = None) -> None:
        current_time = int(time.time()) if now is None else now
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(parent, 0o700)

        temporary = parent / f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        payload = json.dumps(
            {
                "access_token": token.value,
                "expires_at": current_time + token.expires_in_seconds,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        descriptor: int | None = None
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        except OSError as exc:
            raise TokenCacheError("Could not write the private token cache") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
