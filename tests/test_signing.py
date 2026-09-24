import unittest

from imou_recorder.signing import calculate_signature, signing_source


class SigningTests(unittest.TestCase):
    TIMESTAMP = 1706511734
    NONCE = "f5a1ae2d-c09c-4d39-a744-83a5c2c653c2"
    SECRET = "test123456789test123456789"

    def test_source_matches_documented_order(self) -> None:
        self.assertEqual(
            signing_source(self.TIMESTAMP, self.NONCE, self.SECRET),
            "time:1706511734,nonce:f5a1ae2d-c09c-4d39-a744-83a5c2c653c2,"
            "appSecret:test123456789test123456789",
        )

    def test_current_hmac_sha256_vector(self) -> None:
        self.assertEqual(
            calculate_signature(self.TIMESTAMP, self.NONCE, self.SECRET),
            "xjhCQBoJ9hRDsCjyDcHjtDNzRZ3ZJezcawsfWeiaoxU=",
        )

    def test_legacy_md5_vector(self) -> None:
        self.assertEqual(
            calculate_signature(
                self.TIMESTAMP,
                self.NONCE,
                self.SECRET,
                algorithm="md5",
            ),
            "fd37b62889e4757c58b8f3bf05fb9976",
        )


if __name__ == "__main__":
    unittest.main()
