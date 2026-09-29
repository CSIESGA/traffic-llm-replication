"""Scientific scoring checks. All constructed predictions stay in temp files."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from detailed_output import author_reference, parse_detailed
from evaluate_detailed import aggregate, compare, evaluate, write_results
from parser import load_scenario
from prompt_builder import build_detailed_prompt, build_manual_prompt

ROOT = Path(__file__).resolve().parents[1]


def reference_case(number='001'):
    source = ROOT / f'data/scenarios/scenario_{number}.json'
    ids = [v.vehicle_id for v in load_scenario(str(source))]
    gt = json.loads((ROOT / f'data/ground_truth_official/scenario_{number}_gt.json').read_text(encoding='utf-8'))
    ref = author_reference(gt, ids)
    prediction = {
        'is_conflict': ref['is_conflict'], 'number_of_conflicts': len(ref['pairs']),
        'places_of_conflicts': list(ref['places_of_conflicts']),
        'conflict_vehicles': [{'vehicle1_id': a, 'vehicle2_id': b, 'reason': 'Synthetic test fixture.'} for a, b in sorted(ref['pairs'])],
        'decisions': [{'vehicle_id': v, 'action': ref['actions'][v], 'reason': 'Synthetic test fixture.'} for v in ids],
        'priority_order': ref['ranked_order'] + ref['unranked_vehicle_ids'],
        'waiting_times': dict(ref['waiting_times']), 'explanation': 'Synthetic evaluator test, not an LLM response.',
    }
    return ids, ref, prediction


class DetailedTests(unittest.TestCase):
    def test_archive_schema_is_accepted_without_claiming_correctness(self):
        for path in (ROOT / 'archive/legacy_reconstruction_20260928/manual_llm').glob('scenario_*.json'):
            ids = [v.vehicle_id for v in load_scenario(str(ROOT / 'data/scenarios' / path.name))]
            parsed, _ = parse_detailed(path.read_text(encoding='utf-8-sig'), ids)
            self.assertIn('explanation', parsed)

    def test_unordered_pair_is_same_but_priority_is_ordered(self):
        ids, ref, pred = reference_case()
        pair = pred['conflict_vehicles'][0]
        pair['vehicle1_id'], pair['vehicle2_id'] = pair['vehicle2_id'], pair['vehicle1_id']
        pred['priority_order'].reverse()
        pred, validation = parse_detailed(json.dumps(pred), ids)
        score = compare(pred, ref, validation)
        self.assertTrue(score['pair_set_exact'])
        self.assertFalse(score['priority_order_exact'])

    def test_wrong_pair_has_both_false_positive_and_false_negative(self):
        ids = ['A', 'B', 'C']
        ref = {'is_conflict': True, 'pairs': {('A', 'B')}, 'number_of_conflicts': 1,
               'places_of_conflicts': ['intersection'], 'actions': dict.fromkeys(ids, 'proceed'),
               'ranked_order': ['A', 'B'], 'unranked_vehicle_ids': ['C'],
               'waiting_times': {'A': 0, 'B': 2, 'C': 0}}
        pred = {'is_conflict': True, 'number_of_conflicts': 1, 'places_of_conflicts': ['intersection'],
                'conflict_vehicles': [{'vehicle1_id': 'A', 'vehicle2_id': 'C', 'reason': 'Test.'}],
                'decisions': [{'vehicle_id': v, 'action': 'proceed', 'reason': 'Test.'} for v in ids],
                'priority_order': ['A', 'C', 'B'], 'waiting_times': {'A': 0, 'B': 2, 'C': 0},
                'explanation': 'Test.'}
        pred, validation = parse_detailed(json.dumps(pred), ids)
        score = compare(pred, ref, validation)
        summary = aggregate([{'status': 'evaluated', **score}])
        self.assertEqual((score['pair_tp'], score['pair_fp'], score['pair_fn']), (0, 1, 1))
        self.assertEqual(summary['conflict_pairs']['f1'], 0)
        self.assertTrue(score['reported_count_exact'])
        self.assertEqual(score['missing_pairs'], [('A', 'B')])

    def test_semantic_inconsistency_is_scored_and_flagged(self):
        ids, ref, pred = reference_case()
        pred['number_of_conflicts'] = 0
        pred['is_conflict'] = False
        pred, validation = parse_detailed(json.dumps(pred), ids)
        score = compare(pred, ref, validation)
        self.assertIn('boolean_disagrees_with_pairs', validation['consistency_warnings'])
        self.assertFalse(score['binary_correct'])
        self.assertFalse(score['all_scored_fields_exact'])
        self.assertTrue(score['pair_set_exact'])

    def test_strict_shape_duplicate_keys_and_finite_numbers(self):
        ids, _, original = reference_case()
        for mutation in ('missing', 'unknown', 'self_pair', 'duplicate_pair', 'bool_wait', 'nan_wait', 'duplicate_order', 'unknown_action'):
            pred = copy.deepcopy(original)
            if mutation == 'missing': del pred['explanation']
            if mutation == 'unknown': pred['decisions'][0]['vehicle_id'] = 'INVENTED'
            if mutation == 'self_pair': pred['conflict_vehicles'][0]['vehicle2_id'] = pred['conflict_vehicles'][0]['vehicle1_id']
            if mutation == 'duplicate_pair': pred['conflict_vehicles'].append(dict(pred['conflict_vehicles'][0]))
            if mutation == 'bool_wait': pred['waiting_times'][ids[0]] = True
            if mutation == 'nan_wait': pred['waiting_times'][ids[0]] = float('nan')
            if mutation == 'duplicate_order': pred['priority_order'][1] = pred['priority_order'][0]
            if mutation == 'unknown_action': pred['decisions'][0]['action'] = 'fly'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                parse_detailed(json.dumps(pred), ids)
        with self.assertRaises(ValueError):
            parse_detailed('{"is_conflict":true,"is_conflict":false}', ids)

    def test_json_fence_allowed_but_prose_and_binary_rejected(self):
        ids, _, pred = reference_case()
        text = json.dumps(pred)
        self.assertEqual(parse_detailed('```json\n' + text + '\n```', ids)[1]['format'], 'json_fence')
        for invalid in ('yes', 'Answer: ' + text, text + '\nExplanation.'):
            with self.assertRaises(ValueError): parse_detailed(invalid, ids)

    def test_author_contradiction_is_reported_and_not_repaired(self):
        _, ref, _ = reference_case()
        self.assertIn('pair_yield_vs_global_rank:V101->V102', ref['warnings'])
        self.assertEqual(ref['actions']['V101'], 'yield')
        self.assertEqual(ref['ranked_order'][0], 'V101')
        self.assertEqual(ref['waiting_times']['V101'], 0)

    def test_no_conflict_priority_undefined_not_perfect(self):
        ids, ref, pred = reference_case('003')
        self.assertFalse(ref['is_conflict'])
        pred['priority_order'].reverse()
        pred, validation = parse_detailed(json.dumps(pred), ids)
        score = compare(pred, ref, validation)
        summary = aggregate([{'status': 'evaluated', **score}])
        self.assertIsNone(summary['priority']['order_exact_rate'])
        self.assertIsNone(summary['conflict_pairs']['f1'])
        self.assertEqual(summary['conflict_pairs']['scenario_exact_rate'], 1)
        self.assertIsNone(summary['waiting']['gt_conflicting_vehicles']['mae_seconds'])

    def test_action_wait_and_coarse_location_scores(self):
        ids, ref, pred = reference_case()
        pred['decisions'][0]['action'] = 'stop'
        pred['waiting_times'][ids[0]] += 4
        pred['places_of_conflicts'] = ['intersection_center']
        pred, validation = parse_detailed(json.dumps(pred), ids)
        score = compare(pred, ref, validation)
        self.assertEqual(score['action_correct'], 1)
        self.assertEqual(score['waiting_mae'], 2)
        self.assertTrue(score['places_coarse_exact'])
        self.assertFalse(score['waiting_exact'])

    def test_missing_invalid_and_duplicate_do_not_become_correct(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / 'scenario_001.txt').write_text('yes', encoding='utf-8')
            (directory / 'scenario_002.txt').write_text('no', encoding='utf-8')
            (directory / 'scenario_002.json').write_text('{}', encoding='utf-8')
            rows, summary, parsed = evaluate(ROOT / 'data/ground_truth_official', directory, ROOT / 'data/scenarios')
            self.assertEqual(summary['n_evaluated'], 0)
            self.assertEqual(summary['status_counts']['invalid_prediction'], 1)
            self.assertEqual(summary['status_counts']['ambiguous_prediction'], 1)
            self.assertIsNone(summary['binary']['accuracy'])
            self.assertEqual(parsed, {})
            write_results(rows, summary, parsed, directory / 'evaluation')

    def test_all_324_author_shaped_fixtures_score_exact_in_temp_only(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for path in (ROOT / 'data/scenarios').glob('scenario_*.json'):
                _, _, pred = reference_case(path.stem.split('_')[1])
                (directory / path.name).write_text(json.dumps(pred), encoding='utf-8')
            _, summary, parsed = evaluate(ROOT / 'data/ground_truth_official', directory, ROOT / 'data/scenarios')
            self.assertEqual(summary['n_evaluated'], 324)
            self.assertEqual(sum(x['n_expected'] for x in summary['by_ground_truth_consistency'].values()), 324)
            self.assertEqual(summary['all_scored_fields_exact_rate'], 1)
            self.assertEqual(summary['waiting']['all_vehicles']['mae_seconds'], 0)
            self.assertEqual(len(parsed), 324)

    def test_detailed_prompt_full_precision_no_answer_or_movement_hint(self):
        vehicles = load_scenario(str(ROOT / 'data/scenarios/scenario_025.json'))
        text = build_detailed_prompt(vehicles)
        for vehicle in vehicles:
            self.assertIn(repr(vehicle.speed), text)
            self.assertIn(repr(vehicle.distance_to_intersection), text)
        self.assertNotIn("Respond only with 'yes' or 'no'", text)
        self.assertNotIn('V101', text)
        self.assertNotIn('time_to_intersection', text)
        self.assertIn('explanation', text)
        self.assertIn("Respond only with 'yes' or 'no'", build_manual_prompt(vehicles))


if __name__ == '__main__':
    unittest.main()
