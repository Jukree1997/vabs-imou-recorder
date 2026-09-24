"""Command-line read-only connectivity probe."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from .client import ImouApiError, ImouClient
from .config import ConfigurationError, ImouConfig
from .token_cache import TokenCache, TokenCacheError


def mask_identifier(value: object) -> str:
    """Mask device identifiers while keeping enough suffix for local recognition."""

    text = str(value or "")
    if not text:
        return "(missing ID)"
    suffix_length = min(4, len(text))
    return f"{'*' * max(4, len(text) - suffix_length)}{text[-suffix_length:]}"


def parse_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def capability_names(entry: dict[str, Any]) -> set[str]:
    names = {
        name.strip()
        for name in str(entry.get("ability") or "").split(",")
        if name.strip()
    }
    channels = entry.get("channels", [])
    if isinstance(channels, list):
        for channel in channels:
            if not isinstance(channel, dict):
                continue
            names.update(
                name.strip()
                for name in str(
                    channel.get("channelAbility") or channel.get("ability") or ""
                ).split(",")
                if name.strip()
            )
    return names


def select_target_channel(
    devices: list[dict[str, Any]],
    camera_name: str | None,
) -> tuple[str, str]:
    candidates: list[tuple[str, str, str]] = []
    for device in devices:
        device_id = device.get("deviceId")
        channels = device.get("channels", [])
        if not isinstance(device_id, str) or not isinstance(channels, list):
            continue
        for channel in channels:
            if not isinstance(channel, dict) or channel.get("channelId") is None:
                continue
            candidates.append(
                (
                    device_id,
                    str(channel["channelId"]),
                    str(channel.get("channelName") or ""),
                )
            )

    if camera_name:
        matches = [candidate for candidate in candidates if candidate[2] == camera_name]
        if len(matches) == 1:
            return matches[0][0], matches[0][1]
        if not matches:
            raise ImouApiError(
                f"No visible channel matched VABS_CAMERA_NAME={camera_name}"
            )
        raise ImouApiError(f"More than one channel matched VABS_CAMERA_NAME={camera_name}")
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1]
    raise ImouApiError(
        "Could not select one channel; set VABS_CAMERA_NAME to an exact channel name"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only IMOU authentication and Imou Life device-list probe."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Configuration file path (default: .env)",
    )
    parser.add_argument(
        "--records-date",
        type=parse_date,
        help="Also query all SD-card clip metadata for YYYY-MM-DD",
    )
    parser.add_argument(
        "--token-cache",
        type=Path,
        default=Path(".state/access_token.json"),
        help="Private token cache path (default: .state/access_token.json)",
    )
    parser.add_argument(
        "--no-token-cache",
        action="store_true",
        help="Do not read or write the local administrator-token cache",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = ImouConfig.from_env_file(args.env_file)
        print(f"Configuration: valid ({config.api_host}, {config.signing_algorithm})")

        client = ImouClient(config)
        token = None
        cache = None if args.no_token_cache else TokenCache(args.token_cache)
        if cache is not None:
            token = cache.load()
        if token is None:
            token = client.get_access_token()
            if cache is not None:
                cache.save(token)
            auth_source = "new token"
        else:
            auth_source = "cached token"
        print(
            f"Authentication: successful ({auth_source}, expires in "
            f"{token.expires_in_seconds} seconds; not displayed)"
        )

        devices = client.list_imou_life_devices(token.value)
        print(f"Visible Imou Life devices: {len(devices)}")
        for device in devices:
            channels = device.get("channels", [])
            channel_names = []
            if isinstance(channels, list):
                channel_names = [
                    str(channel.get("channelName") or channel.get("channelId") or "unnamed")
                    for channel in channels
                    if isinstance(channel, dict)
                ]
            channel_summary = ", ".join(channel_names) if channel_names else "no channels"
            print(f"- {mask_identifier(device.get('deviceId'))}: {channel_summary}")

        if not devices:
            print(
                "No devices were visible. Do not rebind the camera yet; first verify that "
                "the Open Platform and Imou Life accounts use the same login or sharing."
            )
            return 0

        abilities = client.list_imou_life_device_details(token.value, devices)
        relevant = ("LocalStorage", "PlaybackByFilename", "LocalRecord", "PBSV1")
        for entry in abilities:
            names = capability_names(entry)
            summary = ", ".join(
                f"{name}={'yes' if name in names else 'no'}" for name in relevant
            )
            print(f"Capabilities {mask_identifier(entry.get('deviceId'))}: {summary}")

        if args.records_date:
            device_id, channel_id = select_target_channel(devices, config.camera_name)
            records = client.query_all_local_records(
                token.value,
                device_id,
                channel_id,
                args.records_date,
            )
            total_bytes = sum(
                int(record.get("fileLength") or 0)
                for record in records
                if str(record.get("fileLength") or "0").isdigit()
            )
            print(
                f"Local records on {args.records_date}: {len(records)} "
                f"({total_bytes / (1024 * 1024):.1f} MiB recorded-file total)"
            )
            preview = records[:3]
            if len(records) > 6:
                preview += records[-3:]
            elif len(records) > 3:
                preview += records[3:]
            for index, record in enumerate(preview):
                if len(records) > 6 and index == 3:
                    print(f"  ... {len(records) - 6} additional clips ...")
                print(
                    f"- {record.get('beginTime', '?')} to {record.get('endTime', '?')} "
                    f"({record.get('type', 'unknown')})"
                )
        return 0
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 2
    except ImouApiError as exc:
        code_suffix = f" [code {exc.code}]" if exc.code else ""
        print(f"OpenAPI probe failed: {exc}{code_suffix}")
        return 1
    except TokenCacheError as exc:
        print(f"Token cache error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
