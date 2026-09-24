import json
from pathlib import Path
import tempfile
import unittest

from imou_recorder.config import ImouConfig
from imou_recorder.emulator import EmulatorError, _load_job


class EmulatorBridgeTests(unittest.TestCase):
    def _config(self, video_root: Path) -> ImouConfig:
        return ImouConfig(
            app_id="app-id",
            app_secret="app-secret",
            api_host="openapi-sg.easy4ip.com",
            video_root=video_root,
        )

    def _write_job(self, path: Path, destination: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "outputName": "0000-0005.mp4",
                    "linuxDestination": str(destination),
                }
            ),
            encoding="utf-8",
        )

    def test_accepts_destination_below_video_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "recordings"
            job_path = Path(directory) / "job.json"
            destination = root / "VABS" / "clip.mp4"
            self._write_job(job_path, destination)

            _, loaded_destination = _load_job(job_path, self._config(root))

            self.assertEqual(loaded_destination, destination)

    def test_rejects_destination_outside_video_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "recordings"
            job_path = Path(directory) / "job.json"
            self._write_job(job_path, Path(directory) / "outside.mp4")

            with self.assertRaisesRegex(EmulatorError, "outside VABS_VIDEO_ROOT"):
                _load_job(job_path, self._config(root))


if __name__ == "__main__":
    unittest.main()
