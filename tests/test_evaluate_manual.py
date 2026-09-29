import json
import tempfile
import unittest
from pathlib import Path

from evaluate_manual import evaluate, parse_prediction, write_results


class ManualEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.gt_dir = self.root / "gt"
        self.pred_dir = self.root / "pred"
        self.gt_dir.mkdir()
        self.pred_dir.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def truth(self, name, value):
        (self.gt_dir / f"{name}_gt.json").write_text(json.dumps({
            "is_conflict": value, "ground_truth_backend": "official",
            "ground_truth_method": "author_code",
        }), encoding="utf-8")

    def answer(self, name, content, extension="txt"):
        path = self.pred_dir / f"{name}.{extension}"
        path.write_text(content, encoding="utf-8")
        return path

    def test_strict_binary_parser_and_legacy_json(self):
        self.assertFalse(parse_prediction(self.answer("negative", '{"is_conflict": " NO "}', "json")))
        self.assertFalse(parse_prediction(self.answer("boolean", '{"is_conflict": false}', "json")))
        self.assertTrue(parse_prediction(self.answer("positive", "  YES\n")))
        fence = chr(96) * 3
        self.assertFalse(parse_prediction(self.answer("fence", fence + "text\nno\n" + fence)))
        self.assertTrue(parse_prediction(self.answer("legacy", '{"is_conflict":true,"waiting_times":{"V1":0}}', "json")))
        for content in ('{"is_conflict":"false"}', '{"is_conflict":0}', '{"is_conflict":null}', '[]', '{broken'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                parse_prediction(self.answer("invalid", content, "json"))
        with self.assertRaises(ValueError):
            parse_prediction(self.answer("explanation", "Yes, because paths cross."))

    def test_confusion_counts_and_fingerprints(self):
        for name, truth, answer in [("tp", True, "yes"), ("tn", False, "no"), ("fp", False, "yes"), ("fn", True, "no")]:
            self.truth(name, truth)
            self.answer(name, answer)
        rows, summary = evaluate(self.gt_dir, self.pred_dir)
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["coverage"], 1)
        for field in ("TP", "TN", "FP", "FN"):
            self.assertEqual(summary[field], 1)
        for field in ("accuracy", "precision", "recall", "f1"):
            self.assertEqual(summary[field], 0.5)
        self.assertTrue(all(row["status"] == "evaluated" for row in rows))
        self.assertEqual(len(summary["prediction_files"]), 4)
        self.assertTrue(all(len(record["sha256"]) == 64 for record in summary["prediction_files"]))
        self.assertEqual(summary["ground_truth_provenance"]["backend_counts"], {"official": 4})

    def test_missing_invalid_ambiguous_extra_do_not_inflate_coverage(self):
        for name in ("good", "missing", "invalid", "duplicate"):
            self.truth(name, True)
        self.answer("good", "yes")
        self.answer("invalid", "not JSON", "json")
        self.answer("duplicate", "yes")
        self.answer("duplicate", '{"is_conflict":true}', "json")
        self.answer("unknown", "no")
        rows, summary = evaluate(self.gt_dir, self.pred_dir)
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["n_evaluated"], 1)
        self.assertEqual(summary["coverage"], 0.25)
        self.assertEqual(summary["n_missing_predictions"], 1)
        self.assertEqual(summary["n_invalid_predictions"], 1)
        self.assertEqual(summary["n_ambiguous_predictions"], 1)
        self.assertEqual(summary["n_extra_prediction_files"], 1)
        self.assertEqual(summary["TP"], 1)
        self.assertEqual(summary["FN"], 0)
        self.assertEqual(len(rows), 4)

    def test_pending_has_null_metrics_and_csv_includes_scenario(self):
        self.truth("waiting", False)
        rows, summary = evaluate(self.gt_dir, self.pred_dir)
        self.assertEqual(summary["status"], "pending")
        self.assertEqual(summary["coverage"], 0)
        self.assertEqual(summary["n_scenarios"], 0)
        for metric in ("accuracy", "precision", "recall", "f1"):
            self.assertIsNone(summary[metric])
        csv_path, summary_path = write_results(rows, summary, self.root / "report")
        self.assertIn("missing_prediction", csv_path.read_text(encoding="utf-8-sig"))
        self.assertNotIn("NaN", summary_path.read_text(encoding="utf-8"))

    def test_no_positive_cases_keeps_accuracy_but_undefined_positive_metrics(self):
        self.truth("negative", False)
        self.answer("negative", "no")
        _, summary = evaluate(self.gt_dir, self.pred_dir)
        self.assertEqual(summary["accuracy"], 1)
        for metric in ("precision", "recall", "f1"):
            self.assertIsNone(summary[metric])

    def test_invalid_ground_truth_does_not_discard_other_cases(self):
        self.truth("valid", True)
        self.answer("valid", "yes")
        (self.gt_dir / "broken_gt.json").write_text("broken", encoding="utf-8")
        _, summary = evaluate(self.gt_dir, self.pred_dir)
        self.assertEqual(summary["n_invalid_ground_truth"], 1)
        self.assertEqual(summary["n_evaluated"], 1)
        self.assertEqual(summary["coverage"], 0.5)

    def test_metadata_is_recorded_but_not_scored_as_extra_answer(self):
        self.truth("case", True)
        self.answer("case", "yes")
        metadata = self.answer("run_metadata", '{"model":"manually recorded GPT"}', "json")
        _, summary = evaluate(self.gt_dir, self.pred_dir, metadata)
        self.assertEqual(summary["n_extra_prediction_files"], 0)
        self.assertEqual(summary["run_metadata"]["model"], "manually recorded GPT")
        self.assertEqual(len(summary["run_metadata_file"]["sha256"]), 64)

    def test_manifest_groups_keep_partial_coverage_and_original_cases_separate(self):
        for name, truth in [("four_yes", True), ("four_pending", False), ("eight_no", False), ("mixed_wrong", True), ("original", False)]:
            self.truth(name, truth)
        self.answer("four_yes", "yes")
        self.answer("eight_no", "no")
        self.answer("mixed_wrong", "no")
        self.answer("original", "no")
        manifest = self.root / "generation_manifest.json"
        manifest.write_text(json.dumps({"scenarios": [
            {"scenario_id": "four_yes", "source_group": "four_vehicle"},
            {"scenario_id": "four_pending", "source_group": "four_vehicle"},
            {"scenario_id": "eight_no", "source_group": "eight_vehicle"},
            {"scenario_id": "mixed_wrong", "source_group": "mixed_vehicle"},
            {"scenario_id": "not_in_gt", "source_group": "mixed_vehicle"},
        ]}), encoding="utf-8")
        _, summary = evaluate(self.gt_dir, self.pred_dir, scenario_manifest_path=manifest)
        groups = summary["by_group"]
        self.assertEqual(groups["four_vehicle"]["expected"], 2)
        self.assertEqual(groups["four_vehicle"]["evaluated"], 1)
        self.assertEqual(groups["four_vehicle"]["coverage"], 0.5)
        self.assertEqual(groups["four_vehicle"]["TP"], 1)
        self.assertEqual(groups["mixed_vehicle"]["expected"], 1)
        self.assertEqual(groups["mixed_vehicle"]["FN"], 1)
        self.assertEqual(groups["mixed_vehicle"]["f1"], 0)
        self.assertIsNone(groups["eight_vehicle"]["recall"])
        self.assertEqual(groups["original_or_unassigned"]["TN"], 1)
        self.assertEqual(len(summary["scenario_manifest_file"]["sha256"]), 64)
        self.assertEqual(summary["n_evaluated"], 4)
        self.assertEqual(summary["coverage"], 0.8)


if __name__ == "__main__":
    unittest.main()
