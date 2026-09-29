import ast
import csv
import json
from pathlib import Path
import random
import unittest

from official_ground_truth_adapter import (
    VENDOR_ROOT, generate_author_records, label_author_scenario,
    load_author_modules, normalize_official_output, verify_author_source,
)


class AuthorIntegrationTests(unittest.TestCase):
    def test_all_100_published_records_match_author_aggregation(self):
        """A known author dataset is an independent reference, including wait/ranks."""
        path = next((VENDOR_ROOT / "extracted").glob("*/data/generated_dataset.csv"))
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 100)
        for index, row in enumerate(rows):
            with self.subTest(row=index):
                result = label_author_scenario(json.loads(row["scenario"]))
                self.assertEqual(result["is_conflict"], row["is_conflict"])
                self.assertEqual(result["number_of_conflicts"], int(row["number_of_conflicts"]))
                for key in ("places_of_conflicts", "conflict_vehicles", "decisions",
                            "priority_order", "waiting_times"):
                    self.assertEqual(result[key], ast.literal_eval(row[key]))

    def test_generator_seed_restoration_and_repeatability(self):
        state = random.getstate()
        first = generate_author_records(4, 4, True, 20260928)
        self.assertEqual(random.getstate(), state)
        self.assertEqual(first, generate_author_records(4, 4, True, 20260928))
        self.assertEqual(sum(r["is_conflict"] == "yes" for r in first), 2)

    def test_null_priorities_are_not_invented(self):
        raw = {
            "is_conflict": "no", "number_of_conflicts": 0, "places_of_conflicts": [],
            "conflict_vehicles": [], "decisions": [],
            "priority_order": {"A": None, "B": None}, "waiting_times": {"A": 0, "B": 0},
        }
        result = normalize_official_output(raw, ["A", "B"])
        self.assertEqual(result["priority_order"], [])
        self.assertEqual(result["unranked_vehicle_ids"], ["A", "B"])
        self.assertEqual(result["official_raw_output"], raw)

    def test_author_movement_semantics_preserved(self):
        conflict, _ = load_author_modules()
        vehicle = conflict.Vehicle("V1", "1", 40, 80, "north", "F",
                                   {"north": {"1": ["F", "H"]}})
        self.assertEqual(vehicle.movement_type, "right")
        # Deliberately different from our historical Figure-4 reconstruction.
        verify_author_source()


if __name__ == "__main__":
    unittest.main()
