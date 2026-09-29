"""Checks for input fidelity and answer leakage in the manual workflow."""

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from export_manual_prompts import export_prompts
from parser import load_scenario
from prompt_builder import SYSTEM_PROMPT, build_manual_prompt, scenario_to_text
from vehicle import Vehicle


class ManualPromptTests(unittest.TestCase):
    def setUp(self):
        self.vehicles = [
            Vehicle("CHECK_A", "2", 40.125, 66.678, "north", "D"),
            Vehicle("CHECK_B", "3", 36.0, 100.0, "east", "H"),
        ]

    def test_preserves_all_six_input_fields_in_author_template(self):
        self.assertEqual(
            scenario_to_text(self.vehicles),
            "Vehicle CHECK_A is in lane 2, moving north at a speed of 40.12 km/h, "
            "and is 66.68 meters away from the intersection, heading towards D. "
            "Vehicle CHECK_B is in lane 3, moving east at a speed of 36.00 km/h, "
            "and is 100.00 meters away from the intersection, heading towards H.",
        )

    def test_no_derived_state_or_answer_example(self):
        with patch.object(Vehicle, "to_structured_state", side_effect=AssertionError("derived state accessed")), \
             patch.object(Vehicle, "movement", side_effect=AssertionError("movement accessed")), \
             patch.object(Vehicle, "time_to_intersection", side_effect=AssertionError("TTI accessed")):
            prompt = build_manual_prompt(self.vehicles)
        for forbidden in ("is_conflict", "ground_truth", "time_to_intersection", "movement", "waiting_times", "V101", "V102"):
            self.assertNotIn(forbidden, prompt)
        self.assertIn(SYSTEM_PROMPT, prompt)
        self.assertIn("Respond only with 'yes' or 'no'", prompt)

    def test_export_hashes_and_refuses_to_replace_different_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            source_dir, output_dir = Path(temp) / "inputs", Path(temp) / "prompts"
            source_dir.mkdir()
            source = source_dir / "case.json"
            source.write_text(json.dumps({"vehicles_scenario": [vars(v) for v in self.vehicles]}), encoding="utf-8")
            manifest = export_prompts(source_dir, output_dir)
            record = manifest["prompts"][0]
            self.assertEqual(record["scenario_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            prompt_path = output_dir / "case.txt"
            self.assertEqual(record["prompt_sha256"], hashlib.sha256(prompt_path.read_bytes()).hexdigest())
            self.assertEqual(manifest["expected_output"], "yes_or_no")
            prompt_path.write_text("existing experiment", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_prompts(source_dir, output_dir)
            self.assertEqual(prompt_path.read_text(encoding="utf-8"), "existing experiment")

    def test_matches_installed_author_converter_for_existing_scenarios(self):
        project = Path(__file__).resolve().parents[1]
        vendor_roots = list((project / "vendor/zenodo_14171745/extracted").glob("*/run_evaluation.py"))
        if len(vendor_roots) != 1:
            self.skipTest("Install the pinned author archive before testing author parity")
        vendor = vendor_roots[0].parent
        system_ast = ast.parse((vendor / "run_evaluation.py").read_text(encoding="utf-8"))
        author_system = next(
            ast.literal_eval(node.value)
            for node in system_ast.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "system_instruction" for target in node.targets)
        )
        self.assertEqual(SYSTEM_PROMPT, author_system.strip())

        # Extract only the inspected, pure text converter. Do not import the
        # upstream module, which would unnecessarily require pandas or API code.
        source = vendor / "gpt_finetuning/prepare_data.py"
        converter_ast = ast.parse(source.read_text(encoding="utf-8"))
        converter = next(
            node for node in converter_ast.body
            if isinstance(node, ast.FunctionDef) and node.name == "parse_scenario_to_string"
        )
        namespace = {"json": json}
        module = ast.Module(body=[converter], type_ignores=[])
        exec(compile(module, str(source), "exec"), namespace)
        scenarios = sorted((project / "data/scenarios").glob("*.json"))
        self.assertTrue(scenarios)
        for scenario in scenarios:
            with self.subTest(scenario=scenario.name):
                self.assertEqual(
                    scenario_to_text(load_scenario(str(scenario))),
                    namespace["parse_scenario_to_string"](scenario.read_text(encoding="utf-8")),
                )


if __name__ == "__main__":
    unittest.main()
