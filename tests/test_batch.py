from pathlib import Path
import unittest

from imou_recorder.batch import (
    BatchError,
    build_staging_jobs,
    continuity_deltas,
    recorded_bytes,
    select_overlapping_records,
)
from imou_recorder.download_job import AndroidDownloadJob


class BatchTests(unittest.TestCase):
    def test_selects_records_that_overlap_half_open_range(self) -> None:
        records = [
            {"recordId": "before", "beginTime": "2026-09-23 07:50:00", "endTime": "2026-09-23 08:00:00"},
            {"recordId": "crosses", "beginTime": "2026-09-23 07:59:30", "endTime": "2026-09-23 08:01:00"},
            {"recordId": "inside", "beginTime": "2026-09-23 12:00:00", "endTime": "2026-09-23 12:05:00"},
            {"recordId": "at-end", "beginTime": "2026-09-23 20:00:00", "endTime": "2026-09-23 20:05:00"},
        ]

        selected = select_overlapping_records(records, "2026-09-23", "08:00", "20:00")

        self.assertEqual([record["recordId"] for record in selected], ["crosses", "inside"])

    def test_rejects_reversed_range(self) -> None:
        with self.assertRaisesRegex(BatchError, "later than"):
            select_overlapping_records([], "2026-09-23", "20:00", "08:00")

    def test_builds_unique_private_staging_destinations(self) -> None:
        root = Path("/videos")
        destination = Path("/tmp/0800-0805.mp4")
        base = [
            AndroidDownloadJob(
                payload={"outputName": "0800-0805.mp4"},
                destination=root / "VABS/BKS/CAM/2026-09/23/0800-0805.mp4",
            ),
            AndroidDownloadJob(
                payload={"outputName": "0800-0805.mp4"},
                destination=root / "VABS/BKS/CAM/2026-09/23/0800-0805.mp4",
            ),
        ]
        records = [
            {"beginTime": "2026-09-23 08:00:00", "endTime": "2026-09-23 08:00:20"},
            {"beginTime": "2026-09-23 08:00:20", "endTime": "2026-09-23 08:00:40"},
        ]

        jobs = build_staging_jobs(base, records, root)

        self.assertNotEqual(jobs[0].destination, jobs[1].destination)
        self.assertEqual(jobs[0].destination.name, "080000-080020-0001.mp4")
        self.assertIn("/.staging/", str(jobs[0].destination))
        self.assertEqual(recorded_bytes([{"fileLength": "10"}, {"fileLength": "bad"}]), 10)

    def test_reports_timeline_gaps_and_overlaps(self) -> None:
        records = [
            {"beginTime": "2026-09-23 08:00:00", "endTime": "2026-09-23 08:01:00"},
            {"beginTime": "2026-09-23 08:01:05", "endTime": "2026-09-23 08:02:00"},
            {"beginTime": "2026-09-23 08:01:58", "endTime": "2026-09-23 08:03:00"},
        ]

        self.assertEqual(continuity_deltas(records), (1, 1, 5.0, 2.0))


if __name__ == "__main__":
    unittest.main()
