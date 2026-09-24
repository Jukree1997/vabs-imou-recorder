"""Configuration loading for the IMOU OpenAPI backend."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re


OFFICIAL_API_HOSTS = frozenset(
    {
        "openapi-sg.easy4ip.com",
        "openapi-fk.easy4ip.com",
        "openapi-or.easy4ip.com",
    }
)
SUPPORTED_SIGNING_ALGORITHMS = frozenset({"hmac-sha256", "md5"})


class ConfigurationError(ValueError):
    """Raised when local configuration is incomplete or unsafe."""


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Configuration file not found: {path}") from exc
    except OSError as exc:
        raise ConfigurationError(f"Could not read configuration file: {path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(
                f"Invalid assignment in {path} at line {line_number}"
            )
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigurationError(f"Invalid key in {path} at line {line_number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def _required(values: dict[str, str], key: str) -> str:
    value = values.get(key, "").strip()
    if not value:
        raise ConfigurationError(f"{key} is missing or empty")
    return value


@dataclass(frozen=True)
class ImouConfig:
    """Validated settings required for signed IMOU OpenAPI requests."""

    app_id: str
    app_secret: str
    api_host: str
    signing_algorithm: str = "hmac-sha256"
    timeout_seconds: float = 20.0
    camera_name: str | None = None
    device_code: str | None = None
    vabs_project: str | None = None
    vabs_branch: str | None = None
    video_root: Path | None = None
    time_zone: str = "Asia/Bangkok"

    @classmethod
    def from_env_file(cls, path: str | Path = ".env") -> "ImouConfig":
        values = _parse_env_file(Path(path))
        for key in (
            "IMOU_APP_ID",
            "IMOU_APP_SECRET",
            "IMOU_API_HOST",
            "IMOU_SIGNING_ALGORITHM",
            "IMOU_DEVICE_CODE",
            "VABS_PROJECT",
            "VABS_BRANCH",
            "VABS_CAMERA_NAME",
            "VABS_VIDEO_ROOT",
            "VABS_TIME_ZONE",
        ):
            if key in os.environ:
                values[key] = os.environ[key]

        host = _required(values, "IMOU_API_HOST").lower().rstrip(".")
        if host not in OFFICIAL_API_HOSTS:
            allowed = ", ".join(sorted(OFFICIAL_API_HOSTS))
            raise ConfigurationError(
                "IMOU_API_HOST must be a hostname assigned by IMOU; "
                f"expected one of: {allowed}"
            )

        algorithm = values.get("IMOU_SIGNING_ALGORITHM", "hmac-sha256").strip().lower()
        if algorithm not in SUPPORTED_SIGNING_ALGORITHMS:
            raise ConfigurationError(
                "IMOU_SIGNING_ALGORITHM must be hmac-sha256 or md5"
            )

        video_root_text = values.get("VABS_VIDEO_ROOT", "").strip()
        return cls(
            app_id=_required(values, "IMOU_APP_ID"),
            app_secret=_required(values, "IMOU_APP_SECRET"),
            api_host=host,
            signing_algorithm=algorithm,
            camera_name=values.get("VABS_CAMERA_NAME", "").strip() or None,
            device_code=values.get("IMOU_DEVICE_CODE", "").strip() or None,
            vabs_project=values.get("VABS_PROJECT", "").strip() or None,
            vabs_branch=values.get("VABS_BRANCH", "").strip() or None,
            video_root=Path(video_root_text).expanduser() if video_root_text else None,
            time_zone=values.get("VABS_TIME_ZONE", "Asia/Bangkok").strip()
            or "Asia/Bangkok",
        )
