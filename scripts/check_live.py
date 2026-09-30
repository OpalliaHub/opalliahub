"""Explicit opt-in external integration smoke check using only synthetic resume data."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jobcompass.config import ROOT, DB_PATH
from jobcompass.storage import Store, now
from jobcompass.sources import collect_api
from jobcompass.ai import call_ai

def main():
    report = {'checked_at': now(), 'results': {}}
    store = Store(DB_PATH)
    for source in ('Remotive', 'Arbeitnow'):
        try:
            report['results'][source] = {'status': 'ok', 'result': collect_api(source, store)}
        except ValueError as exc:
            report['results'][source] = {'status': 'unavailable', 'message': str(exc)}
        print(source, json.dumps(report['results'][source], ensure_ascii=False), flush=True)
    try:
        result = call_ai('analyze', (ROOT / 'data/demo_resume.txt').read_text(encoding='utf-8'))
        report['results']['DeepSeek'] = {'status': 'ok', 'model': result['model'], 'usage': result.get('usage')}
    except ValueError as exc:
        report['results']['DeepSeek'] = {'status': 'unavailable', 'message': str(exc)}
    print('DeepSeek', json.dumps(report['results']['DeepSeek'], ensure_ascii=False), flush=True)
    (ROOT / 'docs/live_check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
