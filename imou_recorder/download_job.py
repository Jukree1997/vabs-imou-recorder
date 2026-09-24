"""Create a private, single-clip job for the Android OpenSDK companion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import ConfigurationError, ImouConfig


JOB_SCHEMA_VERSION = 1
_SAFE_PATH_SEGMENT = re.compile(r"^[^/\\\x00]+$")


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ConfigurationError(f"{name} is missing from the IMOU response")
    return text


def _safe_segment(value: str | None, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ConfigurationError(f"{name} is missing or empty")
    if text in {".", ".."} or not _SAFE_PATH_SEGMENT.fullmatch(text):
        raise ConfigurationError(f"{name} must be one safe folder-name segment")
    return text


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _record_time(value: Any, name: str, time_zone: str) -> datetime:
    try:
        zone = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigurationError(f"VABS_TIME_ZONE is not recognized: {time_zone}") from exc
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ConfigurationError(f"{name} is not a valid IMOU timestamp") from exc
    return parsed.replace(tzinfo=zone)


def _lookup_device_details(
    device_id: str,
    devices: list[dict[str, Any]],
    details: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    device = next(
        (entry for entry in devices if str(entry.get("deviceId") or "") == device_id),
        {},
    )
    detail = next(
        (entry for entry in details if str(entry.get("deviceId") or "") == device_id),
        {},
    )
    return device, detail


@dataclass(frozen=True)
class AndroidDownloadJob:
    """Secrets and metadata needed by one native OpenSDK download."""

    payload: dict[str, Any]
    destination: Path

    def write_private(self, path: Path) -> None:
        """Atomically write the job with owner-only permissions."""

        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        data = json.dumps(self.payload, separators=(",", ":"), sort_keys=True)
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            path.chmod(0o600)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def build_android_download_job(
    config: ImouConfig,
    *,
    access_token: str,
    device_id: str,
    channel_id: str,
    record: dict[str, Any],
    devices: list[dict[str, Any]],
    details: list[dict[str, Any]],
    download_speed: int = 2,
) -> AndroidDownloadJob:
    """Build one job without exposing sensitive values in terminal output."""

    if not config.device_code:
        raise ConfigurationError(
            "IMOU_DEVICE_CODE is required to decrypt/download SD-card recordings"
        )
    if config.video_root is None:
        raise ConfigurationError("VABS_VIDEO_ROOT is missing or empty")

    project = _safe_segment(config.vabs_project, "VABS_PROJECT")
    branch = _safe_segment(config.vabs_branch, "VABS_BRANCH")
    camera = _safe_segment(config.camera_name, "VABS_CAMERA_NAME")
    device, detail = _lookup_device_details(device_id, devices, details)

    play_token = _required_text(
        detail.get("playToken") or device.get("playToken"),
        "playToken",
    )
    record_id = _required_text(record.get("recordId"), "recordId")
    begin = _record_time(record.get("beginTime"), "beginTime", config.time_zone)
    end = _record_time(record.get("endTime"), "endTime", config.time_zone)
    if end <= begin:
        raise ConfigurationError("record endTime must be later than beginTime")

    try:
        channel_number = int(channel_id)
    except ValueError as exc:
        raise ConfigurationError("channelId must be an integer for Android OpenSDK") from exc

    output_name = f"{begin:%H%M}-{end:%H%M}.mp4"
    destination = (
        config.video_root
        / project
        / branch
        / camera
        / begin.strftime("%Y-%m")
        / begin.strftime("%d")
        / output_name
    )
    try:
        expected_bytes = int(record.get("fileLength") or 0)
    except (TypeError, ValueError):
        expected_bytes = 0

    product_id = str(
        record.get("productId")
        or detail.get("productId")
        or device.get("productId")
        or ""
    )
    tls_enable = _parse_bool(
        detail.get("tlsEnable", device.get("tlsEnable", False))
    )

    return AndroidDownloadJob(
        payload={
            "schemaVersion": JOB_SCHEMA_VERSION,
            "apiHost": f"{config.api_host}:443",
            "accessToken": access_token,
            "playToken": play_token,
            "deviceId": device_id,
            "channelId": channel_number,
            "recordId": record_id,
            "deviceCode": config.device_code,
            "beginTimeMillis": int(begin.timestamp() * 1000),
            "endTimeMillis": int(end.timestamp() * 1000),
            "recordType": 1,
            "speed": download_speed,
            "productId": product_id,
            "tlsEnable": tls_enable,
            "expectedBytes": max(expected_bytes, 0),
            "outputName": output_name,
            # The Android app ignores this field. The Linux bridge validates it
            # against VABS_VIDEO_ROOT before publishing the pulled MP4.
            "linuxDestination": str(destination),
        },
        destination=destination,
    )
