from __future__ import annotations

import unittest

from pipeline.ingest.slicer import compute_window_boxes


class WindowSlicerTests(unittest.TestCase):
    def test_compute_window_boxes_with_overlap(self) -> None:
        boxes = compute_window_boxes(width=100, height=120, window_height=50, overlap=10)
        self.assertEqual(boxes, [(0, 0, 100, 50), (0, 40, 100, 90), (0, 80, 100, 120)])

    def test_overlap_must_be_smaller_than_window_height(self) -> None:
        with self.assertRaises(ValueError):
            compute_window_boxes(width=100, height=120, window_height=50, overlap=50)

    def test_short_image_still_creates_one_window(self) -> None:
        boxes = compute_window_boxes(width=100, height=40, window_height=120, overlap=20)
        self.assertEqual(boxes, [(0, 0, 100, 40)])


if __name__ == "__main__":
    unittest.main()
