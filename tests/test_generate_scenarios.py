import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate_scenarios as generator


def payload(n, speed=40.12345678901234, distance=123.45678901234567):
    return {"vehicles_scenario": [
        {
            "vehicle_id": f"V{i}", "lane": "1", "speed": speed + i,
            "distance_to_intersection": distance + i,
            "direction": "north", "destination": "F",
        }
        for i in range(n)
    ]}


def fake_records(*, count, num_vehicles, fixed_vehicle_count, seed):
    return [
        {
            "scenario": json.dumps(payload(num_vehicles if fixed_vehicle_count else 2 + i, distance=100.12345678901234 + seed + i)),
            "is_conflict": "yes" if i < count // 2 else "no",
        }
        for i in range(count)
    ]


class AuthorScenarioGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "scenarios"
        self.manifest = self.root / "manifest.json"
        self.output.mkdir()

    def run_generation(self, **kwargs):
        with patch.object(generator.author_adapter, "official_source_provenance", return_value={"version": "v1.0.0"}):
            return generator.generate_scenario_batch(
                per_group=kwargs.pop("per_group", 2), seed=23,
                output_dir=self.output, manifest_path=self.manifest, **kwargs,
            )

    def test_three_author_groups_append_without_mutating_original_and_preserve_precision(self):
        original = self.output / "scenario_024.json"
        original_bytes = json.dumps(payload(2)).encode("utf-8")
        original.write_bytes(original_bytes)
        with patch.object(generator.author_adapter, "generate_author_records", side_effect=fake_records) as call:
            manifest = self.run_generation()
        self.assertEqual(original.read_bytes(), original_bytes)
        self.assertEqual(call.call_count, 3)
        self.assertEqual(call.call_args_list[0].kwargs, dict(count=2, num_vehicles=4, fixed_vehicle_count=True, seed=23))
        self.assertEqual(call.call_args_list[1].kwargs, dict(count=2, num_vehicles=8, fixed_vehicle_count=True, seed=24))
        self.assertEqual(call.call_args_list[2].kwargs, dict(count=2, num_vehicles=8, fixed_vehicle_count=False, seed=25))
        self.assertEqual(manifest["new_scenario_count"], 6)
        self.assertEqual(manifest["scenarios"][0]["scenario_id"], "scenario_025")
        self.assertEqual(manifest["scenarios"][-1]["scenario_id"], "scenario_030")
        self.assertTrue(manifest["not_original_paper_dataset"])
        for entry in manifest["scenarios"]:
            content = Path(entry["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
            self.assertEqual(json.loads(content)["vehicles_scenario"][0]["speed"], 40.12345678901234)
        for group in manifest["groups"]:
            self.assertEqual((group["conflict_count"], group["no_conflict_count"]), (1, 1))

    def test_manifest_guard_prevents_accidental_repeated_batch(self):
        self.manifest.write_text("{}", encoding="utf-8")
        with patch.object(generator.author_adapter, "generate_author_records") as call:
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                self.run_generation()
            call.assert_not_called()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_odd_or_nonpositive_group_count_is_rejected_before_generation(self):
        with patch.object(generator.author_adapter, "generate_author_records") as call:
            for n in [0, -2, 3]:
                with self.subTest(n=n), self.assertRaisesRegex(ValueError, "positive even"):
                    self.run_generation(per_group=n)
            call.assert_not_called()

    def test_duplicate_state_with_changed_ids_and_order_is_rejected_before_any_writes(self):
        duplicate = payload(4)
        (self.output / "scenario_001.json").write_text(json.dumps(duplicate), encoding="utf-8")
        renamed = copy.deepcopy(duplicate)
        renamed["vehicles_scenario"].reverse()
        for i, vehicle in enumerate(renamed["vehicles_scenario"]):
            vehicle["vehicle_id"] = f"NEW_{i}"
        self.assertEqual(generator.scenario_state_sha256(duplicate), generator.scenario_state_sha256(renamed))
        with patch.object(generator.author_adapter, "generate_author_records", return_value=[
            {"scenario": json.dumps(renamed), "is_conflict": "yes"},
            {"scenario": json.dumps(payload(4, distance=300)), "is_conflict": "no"},
        ]):
            with self.assertRaisesRegex(ValueError, "Duplicate scenario state"):
                self.run_generation()
        self.assertEqual(len(list(self.output.glob("*.json"))), 1)
        self.assertFalse(self.manifest.exists())

    def test_unbalanced_author_group_does_not_write_partial_batch(self):
        def unbalanced(**kwargs):
            records = fake_records(**kwargs)
            records[1]["is_conflict"] = "yes"
            return records
        with patch.object(generator.author_adapter, "generate_author_records", side_effect=unbalanced):
            with self.assertRaisesRegex(ValueError, "not balanced"):
                self.run_generation()
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertFalse(self.manifest.exists())


if __name__ == "__main__":
    unittest.main()
