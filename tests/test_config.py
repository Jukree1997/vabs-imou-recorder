from pathlib import Path
import tempfile
import unittest

from imou_recorder.config import ConfigurationError, ImouConfig


class ImouConfigTests(unittest.TestCase):
    def _write_env(self, content: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / ".env"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_valid_config(self) -> None:
        path = self._write_env(
            "IMOU_APP_ID=test-id\n"
            "IMOU_APP_SECRET='test-secret'\n"
            "IMOU_API_HOST=openapi-sg.easy4ip.com\n"
            "IMOU_DEVICE_CODE=device-code\n"
            "VABS_PROJECT=VABS\n"
            "VABS_BRANCH=BKS\n"
            "VABS_CAMERA_NAME=BKS_IMOU_01\n"
            "VABS_VIDEO_ROOT=/tmp/videos\n"
        )
        config = ImouConfig.from_env_file(path)
        self.assertEqual(config.app_id, "test-id")
        self.assertEqual(config.app_secret, "test-secret")
        self.assertEqual(config.signing_algorithm, "hmac-sha256")
        self.assertEqual(config.device_code, "device-code")
        self.assertEqual(config.vabs_project, "VABS")
        self.assertEqual(config.video_root, Path("/tmp/videos"))

    def test_rejects_non_imou_host(self) -> None:
        path = self._write_env(
            "IMOU_APP_ID=test-id\n"
            "IMOU_APP_SECRET=test-secret\n"
            "IMOU_API_HOST=example.com\n"
        )
        with self.assertRaises(ConfigurationError):
            ImouConfig.from_env_file(path)


if __name__ == "__main__":
    unittest.main()
