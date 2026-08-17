from __future__ import annotations

import unittest

from owner_gateway.annotations import region


class AnnotationValidationTests(unittest.TestCase):
    def test_normalized_regions(self) -> None:
        self.assertEqual("pin", region({"id": "1", "kind": "pin", "x": .2, "y": .8, "comment": "CTA"})["kind"])
        self.assertEqual(.4, region({"id": "2", "kind": "rectangle", "x": .1, "y": .2, "width": .4, "height": .3, "comment": "Crop"})["width"])
        self.assertEqual(2, len(region({"id": "3", "kind": "freehand", "points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}], "comment": "Line"})["points"]))

    def test_out_of_bounds_or_empty_annotations_are_rejected(self) -> None:
        invalid = [
            {"id": "1", "kind": "pin", "x": 1.1, "y": .2, "comment": "bad"},
            {"id": "2", "kind": "rectangle", "x": .8, "y": .1, "width": .5, "height": .2, "comment": "bad"},
            {"id": "3", "kind": "freehand", "points": [{"x": 0, "y": 0}], "comment": "bad"},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                region(value)
