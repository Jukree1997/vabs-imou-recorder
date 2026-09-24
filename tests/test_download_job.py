import json
from pathlib import Path
import stat
import tempfile
import unittest

from imou_recorder.config import ConfigurationError, ImouConfig
from imou_recorder.download_job import build_android_download_job


class DownloadJobTests(unittest.TestCase):
    def _config(self, root: Path, **overrides) -> ImouConfig:
        values = {
            "app_id": "app-id",
            "app_secret": "app-secret",
            "api_host": "openapi-sg.easy4ip.com",
            "camera_name": "BKS_IMOU_01",
            "device_code": "device-code",
            "vabs_project": "VABS",
            "vabs_branch": "BKS",
            "video_root": root,
            "time_zone": "Asia/Bangkok",
        }
        values.update(overrides)
        return ImouConfig(**values)

    def test_builds_job_and_expected_vabs_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = build_android_download_job(
                self._config(root),
                access_token="temporary-token",
                device_id="device-1",
                channel_id="0",
                record={
                    "recordId": "internal-file-name",
                    "beginTime": "2026-09-22 00:00:00",
                    "endTime": "2026-09-22 00:05:00",
                    "fileLength": "1234",
                },
                devices=[{"deviceId": "device-1"}],
                details=[
                    {
                        "deviceId": "device-1",
                        "playToken": "play-token",
                        "tlsEnable": True,
                    }
                ],
            )

            self.assertEqual(job.payload["schemaVersion"], 1)
            self.assertEqual(job.payload["channelId"], 0)
            self.assertEqual(job.payload["expectedBytes"], 1234)
            self.assertEqual(job.payload["speed"], 2)
            self.assertEqual(job.payload["outputName"], "0000-0005.mp4")
            self.assertEqual(
                job.destination,
                root
                / "VABS"
                / "BKS"
                / "BKS_IMOU_01"
                / "2026-09"
                / "22"
                / "0000-0005.mp4",
            )

    def test_writes_job_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = build_android_download_job(
                self._config(root),
                access_token="temporary-token",
                device_id="device-1",
                channel_id="0",
                record={
                    "recordId": "record-1",
                    "beginTime": "2026-09-22 00:00:00",
                    "endTime": "2026-09-22 00:05:00",
                },
                devices=[{"deviceId": "device-1", "playToken": "play-token"}],
                details=[],
            )
            path = root / "state" / "job.json"
            job.write_private(path)

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["accessToken"], "temporary-token")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_requires_device_security_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ConfigurationError, "IMOU_DEVICE_CODE"):
                build_android_download_job(
                    self._config(Path(directory), device_code=None),
                    access_token="temporary-token",
                    device_id="device-1",
                    channel_id="0",
                    record={},
                    devices=[],
                    details=[],
                )


if __name__ == "__main__":
    unittest.main()
