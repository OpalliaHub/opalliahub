#!/usr/bin/env python3
"""Explicit small ONLINE JobsDB check; never used by CI or ordinary startup.

Uses a disposable database and prints metadata only. Does not read resumes,
cookies from a browser, or research source databases. Normal module configuration
may load the local .env; no configuration values are sent to JobsDB or printed.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jobcompass import __version__
from jobcompass.jobsdb import collect
from jobcompass.storage import Store, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, choices=range(1, 6), default=1)
    parser.add_argument('--output', type=Path, help='Optional metadata-only JSON evidence')
    args = parser.parse_args()
    start = time.monotonic()
    evidence = {'version': __version__, 'checked_at': now(), 'requested': args.limit,
                'database': 'disposable', 'keyword': '', 'online': True}
    with tempfile.TemporaryDirectory(prefix='jobcompass-jobsdb-check-') as folder:
        store = Store(Path(folder) / 'check.db')
        try:
            result = collect(store, limit=args.limit)
        except ValueError as error:
            result = store.get('jobsdb_last_run') or {'status': 'error', 'message': str(error)}
        evidence.update({key: result.get(key) for key in (
            'status', 'message', 'count', 'found', 'checked', 'rejected', 'unavailable',
            'expired', 'pages', 'search_total', 'search_api', 'stop_code')})
        evidence['stored_rows'] = len(store.jobs())
    evidence['elapsed_seconds'] = round(time.monotonic() - start, 3)
    body = json.dumps(evidence, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(body, encoding='utf-8')
    print(body, end='')
    return 0 if evidence.get('status') == 'success' and evidence.get('count', 0) > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
