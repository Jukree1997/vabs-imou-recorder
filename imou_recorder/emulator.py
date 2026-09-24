"""ADB bridge for one prepared Android OpenSDK download job."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from .config import ConfigurationError, ImouConfig


PACKAGE = "com.vabs.imourecorder"
ACTIVITY = f"{PACKAGE}/.MainActivity"
REMOTE_ROOT = "files"
_SAFE_OUTPUT = re.compile(
    r"^(?:[0-9]{4}-[0-9]{4}|[0-9]{6}-[0-9]{6}-[0-9]{4})\.mp4$"
)


class EmulatorError(RuntimeError):
    """A safe-to-display emulator, ADB, or media-validation error."""


def find_adb(explicit: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        root = os.environ.get(variable)
        if root:
            candidates.append(Path(root) / "platform-tools" / "adb")
    candidates.append(Path(".tools/android-sdk/platform-tools/adb"))
    system_adb = shutil.which("adb")
    if system_adb:
        candidates.append(Path(system_adb))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise EmulatorError(
        "adb was not found; install the local Android toolchain described in "
        "android-downloader/README.md"
    )


def _run(
    command: list[str | Path],
    *,
    check: bool = True,
    timeout: float = 60,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            [str(part) for part in command],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            input=input_text,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EmulatorError(f"Command could not run: {type(exc).__name__}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        last_line = detail[-1] if detail else "unknown error"
        raise EmulatorError(f"Command failed: {last_line}")
    return result


def _write_app_file(adb: Path, source: Path, destination: str) -> None:
    """Stream a private text file into debug-app internal storage."""

    try:
        content = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise EmulatorError("Could not read the prepared Android job") from exc
    _run(
        [
            adb,
            "shell",
            "run-as",
            PACKAGE,
            "dd",
            f"of={destination}",
        ],
        input_text=content,
    )


def _read_app_file(adb: Path, source: str) -> subprocess.CompletedProcess[str]:
    return _run(
        [adb, "exec-out", "run-as", PACKAGE, "cat", source],
        check=False,
        timeout=30,
    )


def _pull_app_file(adb: Path, source: str, destination: Path) -> None:
    try:
        with destination.open("wb") as handle:
            result = subprocess.run(
                [str(adb), "exec-out", "run-as", PACKAGE, "cat", source],
                stdout=handle,
                stderr=subprocess.PIPE,
                timeout=300,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EmulatorError(f"Could not pull Android output: {type(exc).__name__}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip().splitlines()
        last_line = detail[-1] if detail else "unknown error"
        raise EmulatorError(f"Could not pull Android output: {last_line}")


def _load_job(path: Path, config: ImouConfig) -> tuple[dict[str, Any], Path]:
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EmulatorError(f"Prepared job not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise EmulatorError("Prepared Android job is unreadable or invalid") from exc
    if not isinstance(job, dict) or job.get("schemaVersion") != 1:
        raise EmulatorError("Prepared Android job has an unsupported schema")
    output_name = str(job.get("outputName") or "")
    if not _SAFE_OUTPUT.fullmatch(output_name):
        raise EmulatorError("Prepared Android job has an unsafe output filename")
    if config.video_root is None:
        raise ConfigurationError("VABS_VIDEO_ROOT is missing or empty")
    destination = Path(str(job.get("linuxDestination") or ""))
    if not destination.is_absolute():
        raise EmulatorError("Prepared Android job has no absolute Linux destination")
    root = config.video_root.resolve()
    resolved_destination = destination.resolve()
    if not resolved_destination.is_relative_to(root):
        raise EmulatorError("Prepared job destination is outside VABS_VIDEO_ROOT")
    return job, resolved_destination


def _require_one_device(adb: Path) -> None:
    output = _run([adb, "devices"]).stdout.splitlines()
    devices = [
        line.split("\t", 1)[0]
        for line in output
        if "\tdevice" in line
    ]
    if len(devices) != 1:
        raise EmulatorError(
            f"Expected one running Android emulator, found {len(devices)}"
        )


def validate_mp4(
    path: Path,
    *,
    expected_duration_seconds: float | None = None,
) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise EmulatorError("ffprobe is required to validate the downloaded MP4")
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ]
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise EmulatorError("ffprobe found no valid MP4 duration") from exc
    if duration <= 0:
        raise EmulatorError("Downloaded MP4 duration is not positive")
    if (
        expected_duration_seconds is not None
        and expected_duration_seconds > 0
        and duration < expected_duration_seconds * 0.8
    ):
        raise EmulatorError(
            f"Downloaded MP4 is truncated ({duration:.1f}s; expected about "
            f"{expected_duration_seconds:.1f}s)"
        )
    return duration


def run_prepared_job(
    config: ImouConfig,
    job_path: Path,
    *,
    adb_path: Path | None = None,
    timeout_seconds: int = 900,
) -> tuple[Path, float]:
    """Push, execute, pull, validate, and publish one prepared job."""

    if timeout_seconds < 30:
        raise EmulatorError("Download timeout must be at least 30 seconds")
    job, destination = _load_job(job_path, config)
    if destination.exists():
        raise EmulatorError(f"Destination already exists: {destination}")
    adb = find_adb(adb_path)
    _require_one_device(adb)

    output_name = str(job["outputName"])
    remote_job = f"{REMOTE_ROOT}/job.json"
    remote_result = f"{REMOTE_ROOT}/result.json"
    remote_output = f"{REMOTE_ROOT}/Movies/{output_name}"

    _run([adb, "shell", "am", "force-stop", PACKAGE])
    _run([adb, "shell", "run-as", PACKAGE, "mkdir", "-p", f"{REMOTE_ROOT}/Movies"])
    _run(
        [
            adb,
            "shell",
            "run-as",
            PACKAGE,
            "rm",
            "-f",
            remote_job,
            remote_result,
            remote_output,
        ]
    )
    _write_app_file(adb, job_path, remote_job)
    _run([adb, "shell", "am", "start", "-W", "-n", ACTIVITY])

    pull_root = Path(".state/android-pulls")
    pull_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="result-", dir=pull_root) as result_dir:
        local_result = Path(result_dir) / "result.json"
        deadline = time.monotonic() + timeout_seconds
        result_data: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            pulled = _read_app_file(adb, remote_result)
            if pulled.returncode == 0:
                try:
                    local_result.write_text(pulled.stdout, encoding="utf-8")
                    parsed = json.loads(pulled.stdout)
                except (OSError, json.JSONDecodeError):
                    parsed = None
                if isinstance(parsed, dict) and parsed.get("status") in {
                    "complete",
                    "failed",
                }:
                    result_data = parsed
                    break
            time.sleep(2)
        if result_data is None:
            raise EmulatorError("Timed out waiting for the Android download result")
        if result_data.get("status") != "complete":
            code = str(result_data.get("code") or "unknown")
            raise EmulatorError(f"Android OpenSDK download failed with state {code}")

    local_pull = pull_root / output_name
    _pull_app_file(adb, remote_output, local_pull)
    expected_duration = (
        int(job.get("endTimeMillis") or 0) - int(job.get("beginTimeMillis") or 0)
    ) / 1000
    try:
        duration = validate_mp4(
            local_pull,
            expected_duration_seconds=expected_duration,
        )
    except EmulatorError:
        local_pull.unlink(missing_ok=True)
        raise
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(local_pull, destination)

    _run(
        [
            adb,
            "shell",
            "run-as",
            PACKAGE,
            "rm",
            "-f",
            remote_job,
            remote_result,
            remote_output,
        ],
        check=False,
    )
    job_path.unlink(missing_ok=True)
    return destination, duration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one prepared IMOU job through the local Android emulator."
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--job-file",
        type=Path,
        default=Path(".state/android-job.json"),
    )
    parser.add_argument("--adb", type=Path, help="Explicit adb executable")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds to wait")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = ImouConfig.from_env_file(args.env_file)
        destination, duration = run_prepared_job(
            config,
            args.job_file,
            adb_path=args.adb,
            timeout_seconds=args.timeout,
        )
        print(f"Validated and published MP4 ({duration:.1f} seconds): {destination}")
        return 0
    except (ConfigurationError, EmulatorError) as exc:
        print(f"Android emulator download failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
