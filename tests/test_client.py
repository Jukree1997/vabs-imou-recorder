import unittest

from imou_recorder.client import ImouClient
from imou_recorder.config import ImouConfig


class PagingClient(ImouClient):
    def __init__(self) -> None:
        super().__init__(
            ImouConfig(
                app_id="test-id",
                app_secret="test-secret",
                api_host="openapi-sg.easy4ip.com",
            )
        )
        self.begin_times: list[str] = []

    def _request(self, method, params):  # type: ignore[override]
        self.assert_method(method)
        if params["queryRange"] != "1-30":
            raise AssertionError(f"unexpected query range: {params['queryRange']}")
        begin_time = params["beginTime"]
        self.begin_times.append(begin_time)
        first_page = begin_time.endswith("00:00:00")
        count = 30 if first_page else 2
        start = 1 if first_page else 31
        return {
            "records": [
                {
                    "recordId": f"record-{number}",
                    "endTime": (
                        "2026-09-24 02:30:00"
                        if first_page
                        else "2026-09-24 02:40:00"
                    ),
                }
                for number in range(start, start + count)
            ]
        }

    @staticmethod
    def assert_method(method: str) -> None:
        if method != "queryLocalRecords":
            raise AssertionError(f"unexpected method: {method}")


class ClientTests(unittest.TestCase):
    def test_paginates_local_records_in_thirty_item_pages(self) -> None:
        client = PagingClient()
        records = client.query_all_local_records(
            "token",
            "device",
            "0",
            "2026-09-24",
        )
        self.assertEqual(len(records), 32)
        self.assertEqual(
            client.begin_times,
            ["2026-09-24 00:00:00", "2026-09-24 02:30:00"],
        )


if __name__ == "__main__":
    unittest.main()
