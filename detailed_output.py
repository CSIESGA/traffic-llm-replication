"""Validate archived eight-field predictions and adapt immutable author labels."""
import json
import math
import re

KEYS = {'is_conflict', 'number_of_conflicts', 'places_of_conflicts',
        'conflict_vehicles', 'decisions', 'priority_order', 'waiting_times', 'explanation'}
ACTIONS = {'proceed', 'slow_down', 'yield', 'stop'}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _bad_number(value):
    raise ValueError(f'Non-finite JSON number: {value}')


def load_json(text):
    return json.loads(text, object_pairs_hook=_object, parse_constant=_bad_number)


def pair_key(a, b):
    return tuple(sorted((a, b)))


def parse_detailed(text, vehicle_ids):
    """Return full JSON and semantic warnings; never extract JSON from prose.

    A single JSON Markdown fence is accepted and recorded. Structural defects
    invalidate the response. Well-typed but inconsistent predictions remain
    scored, with explicit consistency warnings rather than silently repaired.
    """
    text = text.lstrip('\ufeff').strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', text, re.S | re.I)
    formatting = 'json_fence' if fenced else 'plain_json'
    data = load_json(fenced.group(1).strip() if fenced else text)
    if not isinstance(data, dict) or set(data) != KEYS:
        raise ValueError('Expected exactly the eight archived output keys')
    if type(data['is_conflict']) is not bool:
        raise ValueError('is_conflict must be a JSON boolean')
    if type(data['number_of_conflicts']) is not int or data['number_of_conflicts'] < 0:
        raise ValueError('number_of_conflicts must be a nonnegative integer')
    ids = set(vehicle_ids)
    if len(ids) != len(vehicle_ids) or not ids:
        raise ValueError('Invalid scenario IDs')
    for name in ('places_of_conflicts', 'conflict_vehicles', 'decisions', 'priority_order'):
        if not isinstance(data[name], list):
            raise ValueError(f'{name} must be an array')
    if any(not isinstance(v, str) or not v.strip() for v in data['places_of_conflicts']):
        raise ValueError('places_of_conflicts must contain nonempty strings')
    seen = set()
    for pair in data['conflict_vehicles']:
        if not isinstance(pair, dict) or set(pair) != {'vehicle1_id', 'vehicle2_id', 'reason'}:
            raise ValueError('Invalid conflict pair fields')
        a, b = pair['vehicle1_id'], pair['vehicle2_id']
        if not isinstance(a, str) or not isinstance(b, str) or a not in ids or b not in ids or a == b:
            raise ValueError('Conflict pair has unknown/self vehicle ID')
        key = pair_key(a, b)
        if key in seen:
            raise ValueError('Duplicate unordered conflict pair')
        seen.add(key)
        if not isinstance(pair['reason'], str) or not pair['reason'].strip():
            raise ValueError('Every conflict pair needs a reason string')
    decision_ids = []
    for decision in data['decisions']:
        if not isinstance(decision, dict) or set(decision) != {'vehicle_id', 'action', 'reason'}:
            raise ValueError('Invalid decision fields')
        vid, action = decision['vehicle_id'], decision['action']
        if not isinstance(vid, str) or vid not in ids:
            raise ValueError('Decision has unknown vehicle ID')
        if not isinstance(action, str) or action not in ACTIONS:
            raise ValueError('Unknown action')
        if not isinstance(decision['reason'], str) or not decision['reason'].strip():
            raise ValueError('Every decision needs a reason string')
        decision_ids.append(vid)
    order = data['priority_order']
    if any(not isinstance(v, str) for v in order):
        raise ValueError('Priority entries must be vehicle ID strings')
    if set(decision_ids) != ids or len(decision_ids) != len(ids):
        raise ValueError('decisions must contain every vehicle exactly once')
    if set(order) != ids or len(order) != len(ids):
        raise ValueError('priority_order must contain every vehicle exactly once')
    waits = data['waiting_times']
    if not isinstance(waits, dict) or set(waits) != ids:
        raise ValueError('waiting_times must contain every vehicle exactly once')
    for value in waits.values():
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError('Waiting times must be finite nonnegative numbers, not booleans')
    if not isinstance(data['explanation'], str) or not data['explanation'].strip():
        raise ValueError('explanation must be a nonempty string')
    warnings = []
    if data['number_of_conflicts'] != len(seen):
        warnings.append('count_disagrees_with_pairs')
    if data['is_conflict'] != bool(seen):
        warnings.append('boolean_disagrees_with_pairs')
    if len(data['places_of_conflicts']) != len(seen):
        warnings.append('location_count_disagrees_with_pairs')
    involved = {v for pair in seen for v in pair}
    if [v for v in order if v in involved] != order[:len(involved)]:
        warnings.append('nonconflicting_vehicle_before_conflicting_vehicle')
    return data, {'format': formatting, 'consistency_warnings': warnings}


def author_reference(gt, vehicle_ids):
    """Use original author fields, not the historical reconstruction rules."""
    if gt.get('ground_truth_backend') != 'official_zenodo_14171746':
        raise ValueError('Detailed evaluator requires pinned official Ground Truth')
    raw = gt['official_raw_output']
    if raw['is_conflict'] not in ('yes', 'no'):
        raise ValueError('Unexpected author label')
    ids = set(vehicle_ids)
    pairs = {pair_key(p['vehicle1_id'], p['vehicle2_id']) for p in raw['conflict_vehicles']}
    if any(a not in ids or b not in ids or a == b for a, b in pairs):
        raise ValueError('Invalid author pair IDs')
    if len(pairs) != len(raw['conflict_vehicles']) or len(pairs) != raw['number_of_conflicts']:
        raise ValueError('Invalid author conflict count')
    if (raw['is_conflict'] == 'yes') != bool(pairs):
        raise ValueError('Inconsistent author binary label')
    if set(raw['priority_order']) != ids or set(raw['waiting_times']) != ids:
        raise ValueError('Author priority/waiting IDs differ from scenario')
    ranks = raw['priority_order']
    ranked = sorted((v for v in vehicle_ids if ranks[v] is not None), key=lambda v: ranks[v])
    involved = {v for pair in pairs for v in pair}
    if set(ranked) != involved or [ranks[v] for v in ranked] != list(range(1, len(ranked) + 1)):
        raise ValueError('Invalid author rank sequence')
    if any(type(w) not in (int, float) or not math.isfinite(w) or w < 0 for w in raw['waiting_times'].values()):
        raise ValueError('Invalid author waits')
    relations = []
    for text in raw['decisions']:
        match = re.fullmatch(r'Potential conflict: Vehicle (\S+) must yield to Vehicle (\S+)', text)
        if not match or match[1] not in ids or match[2] not in ids:
            raise ValueError('Unrecognized author yielding decision')
        if pair_key(match[1], match[2]) not in pairs:
            raise ValueError('Author decision references a nonconflict pair')
        relations.append((match[1], match[2]))
    if len(relations) != len(pairs):
        raise ValueError('Author decision count mismatch')
    yielding = {a for a, _ in relations}
    warnings = [f'pair_yield_vs_global_rank:{a}->{b}' for a, b in relations if ranks[a] < ranks[b]]
    return {
        'is_conflict': raw['is_conflict'] == 'yes', 'pairs': pairs,
        'number_of_conflicts': raw['number_of_conflicts'],
        'places_of_conflicts': raw['places_of_conflicts'],
        'actions': {v: 'yield' if v in yielding else 'proceed' for v in vehicle_ids},
        'ranked_order': ranked, 'unranked_vehicle_ids': [v for v in vehicle_ids if v not in involved],
        'waiting_times': raw['waiting_times'], 'yield_relations': relations,
        'warnings': warnings,
    }
