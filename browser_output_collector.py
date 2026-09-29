"""Local-only form for collecting ChatGPT browser answers; never calls an LLM API."""
import csv
import argparse
import hashlib
import html
import json
import secrets
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
ARGS = None
RUN = ROOT / 'outputs/browser_detailed_324'
META = RUN / 'run_metadata.json'
TOKEN = secrets.token_urlsafe(32)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def persist(data):
    temporary = META.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(META)


def prepare():
    if META.exists():
        data = json.loads(META.read_text(encoding='utf-8'))
        if data['protocol'] != 'project_detailed_v1_full_precision':
            raise ValueError('Collector only accepts detailed run metadata')
        for trial in data['trials']:
            if digest(ROOT / trial['prompt_file']) != trial['prompt_sha256']:
                raise ValueError('Prompt changed since run preparation')
            if trial['status'] == 'collected' and digest(ROOT / trial['answer_file']) != trial['response_sha256']:
                raise ValueError('Collected answer changed since capture')
        return data
    source = ROOT / 'data/manual_trial_order_detailed.csv'
    manifest_file = ROOT / 'prompts/detailed/prompt_manifest.json'
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    entries = {r['scenario_id']: r for r in manifest['prompts']}
    with source.open(encoding='utf-8-sig', newline='') as stream:
        order = list(csv.DictReader(stream))
    assert len(order) == len({r['scenario_id'] for r in order}) == 324
    trials = []
    for row in order:
        entry = entries[row['scenario_id']]
        assert entry['prompt_file'] == row['prompt_file']
        assert digest(ROOT / entry['prompt_file']) == entry['prompt_sha256']
        answer = 'outputs/detailed_llm/' + row['answer_filename']
        if (ROOT / answer).exists() or (ROOT / answer).with_suffix('.json').exists():
            raise FileExistsError(answer)
        trials.append({**row, 'trial': int(row['trial']), 'answer_file': answer,
                       'prompt_sha256': entry['prompt_sha256'], 'status': 'not_started'})
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / 'trial_order.csv').write_bytes(source.read_bytes())
    data = {
        'run_id': 'chatgpt_browser_detailed_324', 'created_at': now(),
        'status': 'ready', 'protocol': manifest['protocol'], 'n_planned_scenarios': 324,
        'n_responses_collected': 0, 'api_used': False, 'interface_used': 'ChatGPT web, Chrome extension UI',
        'model_name_as_shown': None, 'model_version_if_known': None,
        'model_version_evidence': 'Fill observed UI label on first submission; do not infer backend snapshot.',
        'reasoning_setting_as_shown': None, 'temporary_chat_setting': None,
        'personalization': None,
        'personalization_evidence': None,
        'account_settings_unchanged': True,
        'observed_account_settings': {'memory': True, 'custom_instruction_fields': 'empty',
            'base_style': '專業', 'warmth': '多一點', 'web_search': True, 'library_search': True,
            'connector_search': True, 'quick_answers': True},
        'initial_usage_observation': 'Sidebar displayed 6% remaining, reset 02:12; applicability to Instant is not confirmed.',
        'new_chat_per_scenario': True, 'first_response_only': True,
        'selection_policy': 'All 324 rows of the existing seeded order, without consulting ground truth.',
        'trial_order_file': 'outputs/browser_detailed_324/trial_order.csv',
        'trial_order_sha256': digest(source), 'prompt_manifest_sha256': digest(manifest_file),
        'prompt_manifest_file': 'prompts/detailed/prompt_manifest.json',
        'started_at_with_timezone': None, 'finished_at_with_timezone': None,
        'raw_response_policy': 'Save first completed visible answer verbatim; no retries based on answer correctness or formatting.',
        'trials': trials,
    }
    data.pop('observed_account_settings')
    data.pop('initial_usage_observation')
    persist(data)
    return data


DATA = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path != '/':
            self.send_error(404)
            return
        current = next((r for r in DATA['trials'] if r['status'] != 'collected'), None)
        body = '<h1>Traffic browser collector</h1><p id="progress">%s/324 saved</p>' % DATA['n_responses_collected']
        if current:
            prompt = ROOT / current['prompt_file']
            assert digest(prompt) == current['prompt_sha256']
            body += '<p id="scenario">%s</p><p id="trial-status">%s</p>' % (current['scenario_id'], current['status'])
            body += '<label>Prompt<textarea id="prompt" readonly rows="12">%s</textarea></label>' % html.escape(prompt.read_text(encoding='utf-8'))
            body += '<form method="post" action="/"><input type="hidden" name="token" value="%s"><input type="hidden" name="scenario" value="%s">' % (TOKEN, current['scenario_id'])
            body += '<label>Response<textarea name="response" id="response" rows="12"></textarea></label>'
            body += '<label>Evidence JSON<textarea name="evidence" id="evidence" rows="4">{}</textarea></label>'
            body += '<button name="action" value="start">Mark started</button> <button name="action" value="save">Save original answer</button></form>'
        else:
            body += '<p>COMPLETE</p>'
        page = '<!doctype html><meta charset="utf-8"><title>Traffic collector</title><style>body{font:16px sans-serif;margin:24px}textarea{display:block;width:96%;margin:8px 0}button{padding:12px}</style>' + body
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(page.encode('utf-8'))

    def do_POST(self):
        try:
            if self.headers.get('Origin') not in (None, 'http://127.0.0.1:8766'):
                raise ValueError('Unexpected origin')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length < 2_000_000:
                raise ValueError('Invalid payload size')
            fields = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True)
            if fields.get('token', [''])[0] != TOKEN:
                raise ValueError('Invalid form token')
            row = next(r for r in DATA['trials'] if r['status'] != 'collected')
            if fields['scenario'][0] != row['scenario_id']:
                raise ValueError('Scenario mismatch')
            action = fields['action'][0]
            evidence = json.loads(fields['evidence'][0])
            if not isinstance(evidence, dict):
                raise ValueError('Evidence must be an object')
            if action == 'start':
                if row['status'] != 'not_started':
                    raise ValueError('Already started; inspect existing chat before retrying')
                if evidence.get('model_name_as_shown') != '即時' or evidence.get('personalization') != '非個人化' or evidence.get('temporary_chat') is not True:
                    raise ValueError('Verify Instant / non-personalized temporary chat before submitting')
                if DATA['model_name_as_shown'] is None:
                    DATA.update(model_name_as_shown=evidence['model_name_as_shown'],
                        reasoning_setting_as_shown=evidence['model_name_as_shown'],
                        personalization=evidence['personalization'], temporary_chat_setting=True,
                        model_version_evidence='Model selector showed 即時; exact backend version not exposed.')
                row.update(status='in_progress', submitted_at=now(), start_evidence=evidence)
                DATA['status'] = 'collecting'
                DATA['started_at_with_timezone'] = DATA['started_at_with_timezone'] or now()
            elif action == 'save':
                response = fields['response'][0]
                if row['status'] != 'in_progress' or not response.strip():
                    raise ValueError('No started trial or empty response')
                if evidence.get('scenario_id') != row['scenario_id'] or evidence.get('model_name_as_shown') != '即時':
                    raise ValueError('Response evidence mismatch')
                path = ROOT / row['answer_file']
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('x', encoding='utf-8', newline='') as stream:
                    stream.write(response)
                row.update(status='collected', response_completed_at=now(), response_sha256=digest(path), evidence=evidence)
                DATA['n_responses_collected'] += 1
                if DATA['n_responses_collected'] == 324:
                    DATA.update(status='complete', finished_at_with_timezone=now())
            else:
                raise ValueError('Unknown action')
            persist(DATA)
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
        except Exception as exc:
            self.send_error(400, str(exc))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--prepare-only', action='store_true', help='Prepare metadata without opening a server or sending prompts')
    ARGS = ap.parse_args()
    DATA = prepare()
    if ARGS.prepare_only:
        print(f'Prepared detailed run: {META}')
        raise SystemExit(0)
    print('Local browser collector: http://127.0.0.1:8766', flush=True)
    HTTPServer(('127.0.0.1', 8766), Handler).serve_forever()
