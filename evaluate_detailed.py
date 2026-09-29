"""Evaluate the archived eight-field schema against the author's full GT.

All secondary metrics are project-defined; this is not the paper's exact
evaluation protocol. Raw replies are never edited or replaced by parsed JSON.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path

from detailed_output import author_reference, load_json, pair_key, parse_detailed
from evaluate_manual import _classification_metrics, _read_scenario_groups
from parser import load_scenario


def ratio(a, b):
    return a / b if b else None


def file_record(path):
    return {'path': path.as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def pair_metrics(tp, fp, fn):
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': ratio(tp, tp + fp),
            'recall': ratio(tp, tp + fn), 'f1': ratio(2 * tp, 2 * tp + fp + fn)}


def compare(pred, ref, validation, tolerance=1e-6):
    predicted = {pair_key(p['vehicle1_id'], p['vehicle2_id']) for p in pred['conflict_vehicles']}
    true_pairs = ref['pairs']
    actions = {d['vehicle_id']: d['action'] for d in pred['decisions']}
    action_records = [{'vehicle_id': v, 'expected': truth, 'predicted': actions[v], 'correct': truth == actions[v]}
                      for v, truth in ref['actions'].items()]
    ranked = ref['ranked_order']
    # Archive schema ranks ALL vehicles; author null ranks are not an arbitrary
    # complete ordering. Only compare the relative order of author-ranked IDs.
    filtered = [v for v in pred['priority_order'] if v in set(ranked)]
    pair_order_correct = sum(filtered.index(a) < filtered.index(b) for a, b in combinations(ranked, 2))
    waiting = [{'vehicle_id': v, 'expected': truth, 'predicted': pred['waiting_times'][v],
                'absolute_error': abs(pred['waiting_times'][v] - truth),
                'within_tolerance': abs(pred['waiting_times'][v] - truth) <= tolerance,
                'gt_conflicting': v in ranked} for v, truth in ref['waiting_times'].items()]
    # Author locations contain no sub-intersection geometry. This explicit alias
    # enables legacy outputs without pretending to verify their precise places.
    normalize_place = lambda s: 'intersection' if s in ('intersection', 'intersection_center') else s
    coarse_places = Counter(map(normalize_place, pred['places_of_conflicts'])) == Counter(ref['places_of_conflicts'])
    result = {
        'gt_conflict': ref['is_conflict'], 'llm_conflict': pred['is_conflict'],
        'binary_correct': pred['is_conflict'] == ref['is_conflict'],
        'gt_pair_count': len(true_pairs), 'predicted_pair_count': len(predicted),
        'pair_tp': len(true_pairs & predicted), 'pair_fp': len(predicted - true_pairs), 'pair_fn': len(true_pairs - predicted),
        'pair_set_exact': predicted == true_pairs,
        'missing_pairs': sorted(true_pairs - predicted), 'extra_pairs': sorted(predicted - true_pairs),
        'reported_count_exact': pred['number_of_conflicts'] == ref['number_of_conflicts'],
        'reported_count_absolute_error': abs(pred['number_of_conflicts'] - ref['number_of_conflicts']),
        'action_correct': sum(r['correct'] for r in action_records), 'action_total': len(action_records),
        'action_records': action_records, 'actions_exact': all(r['correct'] for r in action_records),
        'gt_ranked_order': ranked, 'predicted_order_filtered_to_gt_ranked': filtered,
        'priority_order_exact': filtered == ranked if ranked else None,
        'priority_rank_correct': sum(a == b for a, b in zip(ranked, filtered)),
        'priority_rank_total': len(ranked), 'priority_pair_correct': pair_order_correct,
        'priority_pair_total': len(ranked) * (len(ranked) - 1) // 2,
        'unranked_vehicle_ids': ref['unranked_vehicle_ids'],
        'waiting_records': waiting,
        'waiting_mae': sum(r['absolute_error'] for r in waiting) / len(waiting),
        'waiting_exact': all(r['within_tolerance'] for r in waiting),
        'places_coarse_exact': coarse_places, 'validation': validation,
    }
    result['all_scored_fields_exact'] = all((result['binary_correct'], result['pair_set_exact'],
        result['reported_count_exact'], result['actions_exact'], result['priority_order_exact'] is not False,
        result['waiting_exact'], coarse_places, not validation['consistency_warnings']))
    return result


def aggregate(rows):
    valid = [r for r in rows if r['status'] == 'evaluated']
    n = len(valid)
    waits = [w for r in valid for w in r['waiting_records']]
    ranked_rows = [r for r in valid if r['priority_order_exact'] is not None]
    positive = [r for r in valid if r['gt_pair_count']]
    actions = [a for r in valid for a in r['action_records']]
    def rate(key, population=valid):
        return ratio(sum(r[key] for r in population), len(population))
    def waiting_stats(items):
        return {'n_vehicles': len(items), 'mae_seconds': ratio(sum(w['absolute_error'] for w in items), len(items)),
                'within_tolerance_rate': ratio(sum(w['within_tolerance'] for w in items), len(items))}
    return {
        'n_expected': len(rows), 'n_evaluated': n, 'coverage': ratio(n, len(rows)),
        'status_counts': dict(Counter(r['status'] for r in rows)),
        'binary': _classification_metrics([(r['gt_conflict'], r['llm_conflict']) for r in valid]),
        'conflict_pairs': {**pair_metrics(sum(r['pair_tp'] for r in valid), sum(r['pair_fp'] for r in valid), sum(r['pair_fn'] for r in valid)),
            'scenario_exact_rate': rate('pair_set_exact'), 'positive_scenario_exact_rate': rate('pair_set_exact', positive),
            'n_positive_scenarios_evaluated': len(positive)},
        'reported_conflict_count': {'exact_rate': rate('reported_count_exact'), 'mae': rate('reported_count_absolute_error')},
        'actions': {'n_vehicles': len(actions), 'vehicle_accuracy': ratio(sum(a['correct'] for a in actions), len(actions)),
            'scenario_exact_rate': rate('actions_exact'),
            'confusion': dict(Counter(a['expected'] + '->' + a['predicted'] for a in actions))},
        'priority': {'n_applicable_scenarios': len(ranked_rows), 'order_exact_rate': rate('priority_order_exact', ranked_rows),
            'n_ranked_vehicles': sum(r['priority_rank_total'] for r in valid),
            'rank_accuracy': ratio(sum(r['priority_rank_correct'] for r in valid), sum(r['priority_rank_total'] for r in valid)),
            'pairwise_order_accuracy': ratio(sum(r['priority_pair_correct'] for r in valid), sum(r['priority_pair_total'] for r in valid))},
        'waiting': {'all_vehicles': waiting_stats(waits), 'gt_conflicting_vehicles': waiting_stats([w for w in waits if w['gt_conflicting']]),
            'scenario_exact_rate': rate('waiting_exact')},
        'places_coarse_exact_rate': rate('places_coarse_exact'),
        'all_scored_fields_exact_rate': rate('all_scored_fields_exact'),
        'n_inconsistent_predictions': sum(bool(r['validation']['consistency_warnings']) for r in valid),
        'n_fenced_json_predictions': sum(r['validation']['format'] == 'json_fence' for r in valid),
        'reason_and_explanation_semantic_score': None,
    }


def evaluate(gt_dir, pred_dir, scenario_dir, *, tolerance=1e-6, run_metadata=None, scenario_manifest=None):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Tolerance must be finite and nonnegative')
    gt_dir, pred_dir, scenario_dir = map(Path, (gt_dir, pred_dir, scenario_dir))
    scenarios = sorted(scenario_dir.glob('*.json'))
    if not scenarios:
        raise ValueError('No scenarios found')
    groups = _read_scenario_groups(Path(scenario_manifest)) if scenario_manifest else {}
    predictions = {}
    for p in sorted(pred_dir.glob('*')):
        if p.is_file() and p.suffix.lower() in ('.txt', '.json'):
            predictions.setdefault(p.stem, []).append(p)
    expected = {p.stem for p in scenarios}
    rows, parsed, provenance, warnings = [], {}, [], []
    for source in scenarios:
        sid = source.stem
        row = {'scenario': sid, 'group': groups.get(sid, 'original_or_unassigned'), 'status': 'pending'}
        record = {'scenario': file_record(source), 'prediction_files': [file_record(p) for p in predictions.get(sid, [])]}
        try:
            vehicles = load_scenario(str(source))
            ids = [v.vehicle_id for v in vehicles]
            truth_path = gt_dir / (sid + '_gt.json')
            record['ground_truth'] = file_record(truth_path)
            gt = load_json(truth_path.read_text(encoding='utf-8-sig'))
            if gt.get('scenario_id') != sid or gt.get('scenario_sha256') != record['scenario']['sha256']:
                raise ValueError('GT scenario ID/hash mismatch')
            ref = author_reference(gt, ids)
            record['ground_truth_backend'] = gt['ground_truth_backend']
            row['ground_truth_warnings'] = ref['warnings']
            if ref['warnings']:
                warnings.append({'scenario': sid, 'warnings': ref['warnings']})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row.update(status='invalid_ground_truth_or_scenario', error=str(exc))
            rows.append(row)
            provenance.append(record)
            continue
        candidates = predictions.get(sid, [])
        if not candidates:
            row['status'] = 'missing_prediction'
        elif len(candidates) != 1:
            row['status'] = 'ambiguous_prediction'
        else:
            try:
                pred, validation = parse_detailed(candidates[0].read_text(encoding='utf-8-sig'), ids)
                row.update(compare(pred, ref, validation, tolerance))
                row['status'] = 'evaluated'
                parsed[sid] = {'raw_source': record['prediction_files'][0], 'prediction': pred, 'validation': validation}
            except (OSError, ValueError, TypeError, KeyError) as exc:
                row.update(status='invalid_prediction', error=str(exc))
        rows.append(row)
        provenance.append(record)
    stats = aggregate(rows)
    n = stats['n_evaluated']
    metadata = load_json(Path(run_metadata).read_text(encoding='utf-8-sig')) if run_metadata else None
    summary = {
        'task': 'detailed_conflict_output_comparison', 'protocol': 'project_detailed_v1_full_precision',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'pending' if n == 0 else ('complete' if n == len(rows) else 'partial'),
        **stats, 'by_group': {group: aggregate([r for r in rows if r['group'] == group]) for group in sorted({r['group'] for r in rows})},
        'by_ground_truth_consistency': {
            'no_pair_global_rank_disagreement': aggregate([r for r in rows if r.get('ground_truth_warnings') == []]),
            'pair_global_rank_disagreement': aggregate([r for r in rows if r.get('ground_truth_warnings')]),
        },
        'waiting_tolerance_seconds': tolerance, 'ground_truth_warning_scenarios': warnings,
        'extra_prediction_files': [file_record(p) for sid, paths in predictions.items() if sid not in expected for p in paths],
        'provenance': provenance, 'run_metadata': metadata,
        'run_metadata_file': file_record(Path(run_metadata)) if run_metadata else None,
        'evaluation_code': [file_record(Path(__file__)), file_record(Path(__file__).with_name('detailed_output.py'))],
        'metric_policy': {
            'scope': 'Project-defined detailed metrics; not a claim of exact paper evaluation replication.',
            'population': 'Only structurally valid complete predictions are scored. Missing/invalid/ambiguous predictions are unscored and included in coverage denominator.',
            'conflicts': 'Unordered vehicle-pair sets. Empty/empty exact match is true; zero micro denominators are null.',
            'actions': 'Project normalization of author pair decisions: yield if named as yielding in ANY pair, otherwise proceed. stop/slow_down remain distinct and count as mismatches.',
            'priority': 'Compare relative order only among author non-null ranks. Do not score order of nonconflicting vehicles. Zero applicable vehicles/scenarios gives null.',
            'waiting': 'Compare full-precision author dataset-level waits. Report all vehicles and author-conflicting vehicles separately.',
            'places': 'Only coarse location multiset is scored; intersection_center explicitly aliases intersection. No precise spatial GT exists.',
            'explanations': 'Validate/store text only; no semantic correctness score and no ROUGE claimed.',
            'yield_relations': 'Not directly scored: archived output schema has per-vehicle actions but no structured yield-to ID.',
            'gt_inconsistency': 'Retain and report author pair-yield versus global-rank contradictions; score these fields separately, not as a single physical ground truth.',
            'all_fields': 'All scored structured fields exact (waiting uses declared tolerance), excluding reason/explanation semantics and unranked order; requires consistency checks to pass.',
            'run_metadata': 'Recorded experiment metadata is not independently verified by evaluator.',
        },
    }
    return rows, summary, parsed


def write_results(rows, summary, parsed, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, value in [('evaluation_summary.json', summary), ('per_scenario.json', rows), ('parsed_predictions.json', parsed)]:
        (output_dir / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    fields = ['scenario', 'group', 'status', 'error', 'binary_correct', 'pair_tp', 'pair_fp', 'pair_fn',
              'pair_set_exact', 'reported_count_exact', 'reported_count_absolute_error', 'action_correct',
              'action_total', 'priority_order_exact', 'waiting_mae', 'places_coarse_exact', 'all_scored_fields_exact']
    with (output_dir / 'evaluation.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--gt-dir', default='data/ground_truth_official')
    ap.add_argument('--pred-dir', default='outputs/detailed_llm')
    ap.add_argument('--scenario-dir', default='data/scenarios')
    ap.add_argument('--output-dir', default='outputs/evaluation_detailed')
    ap.add_argument('--run-metadata', default='outputs/browser_detailed_324/run_metadata.json')
    ap.add_argument('--scenario-manifest', default='data/scenario_generation_manifest.json')
    ap.add_argument('--waiting-tolerance', type=float, default=1e-6)
    args = ap.parse_args()
    if Path(args.output_dir).resolve() in (Path(args.pred_dir).resolve(), Path(args.gt_dir).resolve(), Path(args.scenario_dir).resolve()):
        ap.error('Evaluation output directory must be separate from inputs')
    rows, summary, parsed = evaluate(args.gt_dir, args.pred_dir, args.scenario_dir, tolerance=args.waiting_tolerance,
        run_metadata=args.run_metadata, scenario_manifest=args.scenario_manifest)
    write_results(rows, summary, parsed, args.output_dir)
    print(json.dumps({key: summary[key] for key in ('status', 'n_expected', 'n_evaluated', 'coverage')}, ensure_ascii=False))
    print('Author pair/global inconsistency scenarios:', len(summary['ground_truth_warning_scenarios']))


if __name__ == '__main__':
    main()
