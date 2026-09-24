"""Resumable time-range ingestion through the Android OpenSDK companion."""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from .cli import parse_date, select_target_channel
from .client import ImouApiError, ImouClient
from .config import ConfigurationError, ImouConfig
from .download_job import AndroidDownloadJob, build_android_download_job
from .emulator import EmulatorError, run_prepared_job, validate_mp4
from .token_cache import TokenCache, TokenCacheError


class BatchError(RuntimeError):
    """A safe-to-display batch planning or execution error."""


def parse_clock(value: str) -> str:
    """Validate and normalize a local wall-clock value."""

    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("time must use HH:MM (00:00-23:59)") from exc


def select_overlapping_records(
    records: list[dict[str, Any]],
    date_text: str,
    start_clock: str,
    end_clock: str,
) -> list[dict[str, Any]]:
    """Return source clips overlapping the half-open local range [start, end)."""

    start = datetime.strptime(f"{date_text} {start_clock}:00", "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(f"{date_text} {end_clock}:00", "%Y-%m-%d %H:%M:%S")
    if end <= start:
        raise BatchError("--end must be later than --start on the selected date")

    selected: list[dict[str, Any]] = []
    for record in records:
        try:
            begin = datetime.strptime(str(record.get("beginTime")), "%Y-%m-%d %H:%M:%S")
            finish = datetime.strptime(str(record.get("endTime")), "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise BatchError("IMOU returned a recording with an invalid timestamp") from exc
        if begin < end and finish > start:
            selected.append(record)
    return sorted(
        selected,
        key=lambda item: (
            str(item.get("beginTime") or ""),
            str(item.get("endTime") or ""),
            str(item.get("recordId") or ""),
        ),
    )


def recorded_bytes(records: list[dict[str, Any]]) -> int:
    total = 0
    for record in records:
        try:
            total += max(0, int(record.get("fileLength") or 0))
        except (TypeError, ValueError):
            continue
    return total


def build_staging_jobs(
    jobs: list[AndroidDownloadJob],
    records: list[dict[str, Any]],
    video_root: Path,
) -> list[AndroidDownloadJob]:
    """Give every source clip a unique, private staging destination."""

    staged: list[AndroidDownloadJob] = []
    for index, (job, record) in enumerate(zip(jobs, records, strict=True), start=1):
        begin = datetime.strptime(str(record.get("beginTime")), "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(str(record.get("endTime")), "%Y-%m-%d %H:%M:%S")
        output_name = f"{begin:%H%M%S}-{end:%H%M%S}-{index:04d}.mp4"
        relative_parent = job.destination.parent.relative_to(video_root)
        destination = video_root / ".staging" / relative_parent / output_name
        payload = dict(job.payload)
        payload["outputName"] = output_name
        payload["linuxDestination"] = str(destination)
        staged.append(AndroidDownloadJob(payload=payload, destination=destination))
    return staged


def continuity_deltas(records: list[dict[str, Any]]) -> tuple[int, int, float, float]:
    """Return gap/overlap counts and total seconds between chronological clips."""

    gaps = overlaps = 0
    gap_seconds = overlap_seconds = 0.0
    for previous, current in zip(records, records[1:]):
        previous_end = datetime.strptime(
            str(previous.get("endTime")), "%Y-%m-%d %H:%M:%S"
        )
        current_begin = datetime.strptime(
            str(current.get("beginTime")), "%Y-%m-%d %H:%M:%S"
        )
        delta = (current_begin - previous_end).total_seconds()
        if delta > 0:
            gaps += 1
            gap_seconds += delta
        elif delta < 0:
            overlaps += 1
            overlap_seconds += -delta
    return gaps, overlaps, gap_seconds, overlap_seconds


def concatenate_mp4s(inputs: list[Path], destination: Path) -> float:
    """Losslessly concatenate validated source clips and atomically publish them."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise BatchError("ffmpeg is required to merge the downloaded source clips")
    if not inputs:
        raise BatchError("No source clips were available to merge")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.part.mp4")
    state_root = Path(".state/concat")
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="batch-", dir=state_root) as directory:
            manifest = Path(directory) / "inputs.txt"
            lines = []
            for source in inputs:
                escaped = str(source.resolve()).replace("'", "'\\''")
                lines.append(f"file '{escaped}'")
            manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(manifest),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(temporary),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1800,
                check=False,
            )
        if result.returncode != 0:
            details = result.stderr.strip().splitlines()
            message = details[-1] if details else "unknown ffmpeg error"
            raise BatchError(f"ffmpeg could not merge the source clips: {message}")
        duration = validate_mp4(temporary)
        os.replace(temporary, destination)
        return duration
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BatchError(f"Could not merge source clips: {type(exc).__name__}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download a resumable IMOU SD-card time range through the emulator."
    )
    parser.add_argument("--date", required=True, type=parse_date, help="YYYY-MM-DD")
    parser.add_argument("--start", required=True, type=parse_clock, help="HH:MM local time")
    parser.add_argument("--end", required=True, type=parse_clock, help="HH:MM local time")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--job-file", type=Path, default=Path(".state/android-job.json")
    )
    parser.add_argument(
        "--token-cache", type=Path, default=Path(".state/access_token.json")
    )
    parser.add_argument("--adb", type=Path, help="Explicit adb executable")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds per clip")
    parser.add_argument(
        "--speed",
        type=int,
        choices=(1, 2, 4, 8, 16),
        default=4,
        help="OpenSDK device-download speed (default: verified 4x)",
    )
    parser.add_argument(
        "--attempts", type=int, default=2, help="Maximum attempts per clip (default: 2)"
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=3,
        help="Stop after this many clips fail consecutively (default: 3)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Plan the range without downloading"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.attempts < 1:
            raise BatchError("--attempts must be at least 1")
        if args.max_consecutive_failures < 1:
            raise BatchError("--max-consecutive-failures must be at least 1")

        config = ImouConfig.from_env_file(args.env_file)
        client = ImouClient(config)
        cache = TokenCache(args.token_cache)
        token = cache.load()
        auth_source = "cached token"
        if token is None:
            token = client.get_access_token()
            cache.save(token)
            auth_source = "new token"
        print(f"Authentication: successful ({auth_source}; token not displayed)", flush=True)

        devices = client.list_imou_life_devices(token.value)
        if not devices:
            raise BatchError("No authorized Imou Life devices are visible")
        details = client.list_imou_life_device_details(token.value, devices)
        device_id, channel_id = select_target_channel(devices, config.camera_name)
        all_records = client.query_all_local_records(
            token.value, device_id, channel_id, args.date
        )
        selected = select_overlapping_records(
            all_records, args.date, args.start, args.end
        )
        if not selected:
            raise BatchError("No SD-card recordings overlap the requested time range")

        source_jobs = [
            build_android_download_job(
                config,
                access_token=token.value,
                device_id=device_id,
                channel_id=channel_id,
                record=record,
                devices=devices,
                details=details,
                download_speed=args.speed,
            )
            for record in selected
        ]
        if config.video_root is None:
            raise BatchError("VABS_VIDEO_ROOT is missing")
        jobs = build_staging_jobs(source_jobs, selected, config.video_root)
        first_begin = str(selected[0].get("beginTime") or "?")
        last_end = max(str(record.get("endTime") or "?") for record in selected)
        total_mib = recorded_bytes(selected) / (1024 * 1024)
        gaps, overlaps, gap_seconds, overlap_seconds = continuity_deltas(selected)
        final_destination = source_jobs[0].destination.parent / (
            f"{args.start.replace(':', '')}-{args.end.replace(':', '')}.mp4"
        )
        print(
            f"Plan: {len(selected)} source clips, {total_mib:.1f} MiB, "
            f"covering {first_begin} to {last_end}",
            flush=True,
        )
        print(
            f"Continuity: gaps={gaps} ({gap_seconds:.1f}s), "
            f"overlaps={overlaps} ({overlap_seconds:.1f}s)",
            flush=True,
        )
        print(f"Final destination: {final_destination}", flush=True)
        if overlaps:
            raise BatchError(
                "overlapping source recordings cannot be safely concatenated without "
                "duplicating timeline content"
            )
        if args.dry_run:
            print("Dry run complete; no video was downloaded.", flush=True)
            return 0

        if final_destination.exists():
            duration = validate_mp4(final_destination)
            print(
                f"Range is already complete ({duration:.1f}s): {final_destination}",
                flush=True,
            )
            return 0

        downloaded = 0
        skipped = 0
        failed = 0
        consecutive_failures = 0
        for index, job in enumerate(jobs, start=1):
            label = job.destination.name
            if job.destination.exists():
                expected_duration = (
                    int(job.payload["endTimeMillis"])
                    - int(job.payload["beginTimeMillis"])
                ) / 1000
                try:
                    duration = validate_mp4(
                        job.destination,
                        expected_duration_seconds=expected_duration,
                    )
                except EmulatorError as exc:
                    print(
                        f"[{index}/{len(jobs)}] replacing invalid staging file: {exc}",
                        flush=True,
                    )
                    job.destination.unlink(missing_ok=True)
                else:
                    skipped += 1
                    consecutive_failures = 0
                    print(
                        f"[{index}/{len(jobs)}] already valid "
                        f"({duration:.1f}s): {label}",
                        flush=True,
                    )
                    continue

            clip_error: EmulatorError | None = None
            for attempt in range(1, args.attempts + 1):
                print(
                    f"[{index}/{len(jobs)}] downloading {label} "
                    f"(attempt {attempt}/{args.attempts})",
                    flush=True,
                )
                job.write_private(args.job_file)
                try:
                    destination, duration = run_prepared_job(
                        config,
                        args.job_file,
                        adb_path=args.adb,
                        timeout_seconds=args.timeout,
                    )
                    downloaded += 1
                    consecutive_failures = 0
                    print(
                        f"[{index}/{len(jobs)}] saved {duration:.1f}s: {destination}",
                        flush=True,
                    )
                    clip_error = None
                    break
                except EmulatorError as exc:
                    clip_error = exc
                    print(
                        f"[{index}/{len(jobs)}] attempt failed: {exc}", flush=True
                    )
            if clip_error is not None:
                failed += 1
                consecutive_failures += 1
                if consecutive_failures >= args.max_consecutive_failures:
                    raise BatchError(
                        f"stopped after {consecutive_failures} consecutive clip failures; "
                        "rerun the same command to resume"
                    )

        print(
            f"Source download complete: downloaded={downloaded}, "
            f"already_valid={skipped}, failed={failed}",
            flush=True,
        )
        if failed:
            print("Merge deferred until every source clip is valid.", flush=True)
            return 1

        print(f"Merging {len(jobs)} clips into {final_destination.name}", flush=True)
        duration = concatenate_mp4s(
            [job.destination for job in jobs], final_destination
        )
        for job in jobs:
            job.destination.unlink(missing_ok=True)
        staging_day = jobs[0].destination.parent
        try:
            staging_day.rmdir()
        except OSError:
            pass
        print(
            f"Batch complete: validated {duration:.1f}s MP4: {final_destination}",
            flush=True,
        )
        return 0
    except KeyboardInterrupt:
        print("Batch interrupted; rerun the same command to resume.", flush=True)
        return 130
    except (BatchError, ConfigurationError, EmulatorError, ImouApiError, TokenCacheError) as exc:
        print(f"Batch failed: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
