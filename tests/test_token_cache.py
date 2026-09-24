import os
from pathlib import Path
import tempfile
import unittest

from imou_recorder.client import AccessToken
from imou_recorder.token_cache import TokenCache


class TokenCacheTests(unittest.TestCase):
    def test_round_trip_uses_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "token.json"
            cache = TokenCache(path)
            cache.save(AccessToken("temporary-token", 1000), now=100)

            loaded = cache.load(now=200)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.value, "temporary-token")
            self.assertEqual(loaded.expires_in_seconds, 900)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_ignores_token_near_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "token.json"
            cache = TokenCache(path)
            cache.save(AccessToken("temporary-token", 500), now=100)
            self.assertIsNone(cache.load(now=350))


if __name__ == "__main__":
    unittest.main()
