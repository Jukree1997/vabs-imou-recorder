import unittest

from imou_recorder.cli import capability_names, mask_identifier, select_target_channel


class CliTests(unittest.TestCase):
    def test_masks_device_identifier(self) -> None:
        masked = mask_identifier("ABCDEF123456")
        self.assertEqual(masked, "********3456")
        self.assertNotIn("ABCDEF", masked)

    def test_collects_device_and_channel_capabilities(self) -> None:
        names = capability_names(
            {
                "ability": "LocalStorage,Auth",
                "channels": [{"ability": "PlaybackByFilename,PBSV1"}],
            }
        )
        self.assertEqual(
            names,
            {"LocalStorage", "Auth", "PlaybackByFilename", "PBSV1"},
        )

    def test_selects_configured_camera_name(self) -> None:
        selected = select_target_channel(
            [
                {
                    "deviceId": "device-1",
                    "channels": [{"channelId": "0", "channelName": "BKS_IMOU_01"}],
                }
            ],
            "BKS_IMOU_01",
        )
        self.assertEqual(selected, ("device-1", "0"))


if __name__ == "__main__":
    unittest.main()
