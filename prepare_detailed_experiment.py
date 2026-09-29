"""Prepare detailed prompts/run records only. No browser or LLM requests."""
import csv
import io
import json
from pathlib import Path

from export_manual_prompts import export_prompts


def prepare(root=Path(__file__).resolve().parent):
    # Keep project-relative manifest paths reproducible.
    if Path.cwd().resolve() != root.resolve():
        raise ValueError('Run this command from the project root')
    manifest = export_prompts(Path('data/scenarios'), Path('prompts/detailed'), protocol='detailed')
    entries = {r['scenario_id']: r for r in manifest['prompts']}
    with Path('data/manual_trial_order.csv').open(encoding='utf-8-sig', newline='') as stream:
        order = list(csv.DictReader(stream))
    if len(order) != len(entries) or {r['scenario_id'] for r in order} != set(entries):
        raise ValueError('Detailed scenarios differ from frozen original trial order')
    for row in order:
        row['prompt_file'] = entries[row['scenario_id']]['prompt_file']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(order[0]))
    writer.writeheader()
    writer.writerows(order)
    data = buffer.getvalue().encode('utf-8-sig')
    path = Path('data/manual_trial_order_detailed.csv')
    if path.exists() and path.read_bytes() != data:
        raise FileExistsError('Existing detailed trial order differs; do not overwrite an experiment')
    path.write_bytes(data)
    Path('outputs/detailed_llm').mkdir(parents=True, exist_ok=True)
    from browser_output_collector import prepare as prepare_collector
    run = prepare_collector()
    print(json.dumps({'protocol': manifest['protocol'], 'n_prompts': manifest['n_scenarios'],
        'n_responses_collected': run['n_responses_collected'], 'status': run['status']}, ensure_ascii=False))


if __name__ == '__main__':
    prepare()
