import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from generate_ground_truth import generate_labels


class GroundTruthExportTests(unittest.TestCase):
    def test_subset_cannot_shrink_existing_experiment_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            manifest = out / "ground_truth_manifest.json"
            original = json.dumps({"scenarios": [{"scenario_id": "a"}, {"scenario_id": "b"}]})
            manifest.write_text(original, encoding="utf-8")
            summary = out / "ground_truth_summary.csv"
            summary.write_text("previous complete summary", encoding="utf-8")
            with patch("generate_ground_truth.load_scenario", side_effect=AssertionError("should fail in preflight")):
                with self.assertRaisesRegex(ValueError, "different scenario scope"):
                    generate_labels([Path("a.json")], out)
            self.assertEqual(manifest.read_text(encoding="utf-8"), original)
            self.assertEqual(summary.read_text(encoding="utf-8"), "previous complete summary")


if __name__ == "__main__":
    unittest.main()
