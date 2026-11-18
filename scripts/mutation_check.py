"""Targeted mutation experiment using disposable copies, never the working tree.

A passing baseline is required. Only assertion failures kill a mutant; syntax,
import, timeout and other errors are inconclusive and fail the experiment.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = (
    ('ranking_order', 'jobcompass/matching.py', "(-j['score'], j['id'])", "(j['score'], j['id'])", 'tests.test_core.MatchingTests'),
    ('skill_intersection', 'jobcompass/matching.py', 'mass(own & required)', 'mass(own | required)', 'tests.test_core.MatchingTests'),
    ('experience_penalty', 'jobcompass/matching.py', 'min(1.0, own_years / years)', '1.0', 'tests.test_core.MatchingTests'),
    ('plan_limit_boundary', 'jobcompass/research.py', "1 <= p['limit'] <= 200", "1 <= p['limit'] <= 201", 'tests.test_research.ResearchTests'),
    ('plan_boolean_limit', 'jobcompass/research.py', "type(p['limit']) is not int", "not isinstance(p['limit'], int)", 'tests.test_research.ResearchTests'),
)


def fingerprint():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted({m[1] for m in MUTANTS})}


def prepare(destination):
    def excluded(directory, names):
        private = shutil.ignore_patterns('__pycache__', '*.pyc', '.env*', '.git', '*.db*', '*.sqlite*', 'private', 'raw')
        return set(private(directory, names)) | {name for name in names if (Path(directory) / name).is_symlink()}

    shutil.copytree(str(ROOT / 'jobcompass'), str(destination / 'jobcompass'),
                    ignore=excluded)
    (destination / 'tests').mkdir()
    (destination / 'tests/__init__.py').write_text('')
    for name in ('test_core.py', 'test_research.py'):
        shutil.copyfile(str(ROOT / 'tests' / name), str(destination / 'tests' / name))
    (destination / 'data').mkdir()
    for name in ('demo_jobs.json', 'demo_resume.txt'):
        shutil.copyfile(str(ROOT / 'data' / name), str(destination / 'data' / name))


def run_tests(destination, targets, output):
    environment = dict(os.environ, PYTHONPATH='', PYTHONDONTWRITEBYTECODE='1', DEEPSEEK_API_KEY='')
    try:
        process = subprocess.run([sys.executable, '-m', 'unittest', '-v'] + list(targets),
                                 cwd=str(destination), env=environment, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        output.write_text('Test subprocess exceeded 60 seconds.\n')
        return {'exit_code': 124, 'assertion_failures': 0, 'errors': 1}
    text = process.stdout.decode('utf-8', errors='replace')
    output.write_text(text, encoding='utf-8')
    failures = re.search(r'FAILED \(failures=(\d+)', text)
    errors = re.search(r'errors=(\d+)', text)
    tests = re.search(r'Ran (\d+) tests?', text)
    return {'exit_code': process.returncode,
            'tests': int(tests.group(1)) if tests else 0,
            'assertion_failures': int(failures.group(1)) if failures else 0,
            'errors': int(errors.group(1)) if errors else 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/quality/mutations')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    before = fingerprint()
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'mutants': [],
              'scope': 'Five hand-selected faults; not whole-project mutation coverage.'}
    with tempfile.TemporaryDirectory(prefix='jobcompass-mutation-') as temporary:
        base = Path(temporary) / 'baseline'
        prepare(base)
        targets = sorted({m[4] for m in MUTANTS})
        report['baseline'] = run_tests(base, targets, args.output / 'baseline.log')
        if report['baseline']['exit_code'] == 0 and report['baseline']['tests'] > 0:
            for name, file, old, new, target in MUTANTS:
                destination = Path(temporary) / name
                shutil.copytree(str(base), str(destination), ignore=shutil.ignore_patterns('__pycache__'))
                path = destination / file
                text = path.read_text(encoding='utf-8')
                if text.count(old) != 1:
                    report['mutants'].append({'name': name, 'status': 'invalid', 'reason': 'Mutation anchor is not unique.'})
                    continue
                path.write_text(text.replace(old, new, 1), encoding='utf-8')
                result = run_tests(destination, [target], args.output / (name + '.log'))
                status = 'survived' if result['exit_code'] == 0 else 'inconclusive'
                if result['exit_code'] == 1 and result['assertion_failures'] and not result['errors']:
                    status = 'killed'
                report['mutants'].append(dict(result, name=name, file=file, before=old, after=new,
                                              test_target=target, status=status))
    report['source_unchanged'] = before == fingerprint()
    report['source_sha256'] = before
    report['killed'] = sum(m['status'] == 'killed' for m in report['mutants'])
    report['total'] = len(MUTANTS)
    report['status'] = 'passed' if report['killed'] == len(MUTANTS) and report['source_unchanged'] else 'failed'
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status', 'killed', 'total', 'source_unchanged')}))
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    sys.exit(main())
