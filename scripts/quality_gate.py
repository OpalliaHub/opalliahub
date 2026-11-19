"""Offline publication checks; local .env files and symlinks are never read."""
import argparse
import ast
import hashlib
import io
import json
import os
import platform
import re
import stat
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('jobcompass', 'tests', 'scripts', 'docs', '.github', '.vscode', 'deploy')
SOURCE_FILES = ('main.py', 'README.md', 'AGENTS.md', 'requirements.txt', 'requirements-server.txt', 'LICENSE', 'Dockerfile', 'compose.yaml', '.dockerignore', '.env.example', '.gitignore', '启动JobCompass.command')
TEXT_SUFFIXES = {'.py', '.js', '.html', '.css', '.md', '.txt', '.json', '.yml', '.yaml', '.csv', '.command'}
RULES = (
    ('provider_api_key', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b')),
    ('github_token', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b')),
    ('private_key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
)
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
# Source releases deliberately omit presentation/report deliverables even when
# an old local copy is accidentally returned to an otherwise allowed folder.
EXCLUDED_RELEASE_NAMES = frozenset({
    'project_proposal.md', 'project_report.md', 'individual_report_draft.md',
    'demo_script.md', 'debugging_lab.md', 'course_topics.json',
})
EXCLUDED_RELEASE_SUFFIXES = frozenset({
    '.doc', '.docx', '.pdf', '.ppt', '.pptx', '.xls', '.xlsx', '.odt', '.odp', '.zip',
})


def private_reason(name):
    """Explain why a relative source/archive path contains local private state.

    >>> private_reason('.env')
    'local environment file'
    >>> private_reason('.env.example') is None
    True
    >>> private_reason('data/private/resume.txt')
    'private or generated directory'
    >>> private_reason('.github/workflows/tests.yml') is None
    True
    """
    parts = PurePosixPath(name).parts
    if any(part in {'.git', '.venv', '.idea', '__pycache__', 'private', 'raw', 'output', 'dist'} for part in parts):
        return 'private or generated directory'
    if any((part == '.env' or part.startswith('.env.')) and part != '.env.example' for part in parts):
        return 'local environment file'
    if parts and (re.search(r'\.(?:db|sqlite|sqlite3)(?:-wal|-shm|-journal)?$', parts[-1], re.I) or parts[-1].endswith('.pyc')):
        return 'local database or bytecode'
    return None


def release_exclusion(name):
    """Reject non-source deliverables independently of private-data checks."""
    parts = PurePosixPath(name).parts
    lower = [part.casefold() for part in parts]
    if (any(part in {'submission', 'coursework', 'classroom'}
            or part.startswith('course_') or re.match(r'^group[0-9]+(?:_|$)', part)
            for part in lower)
            or lower and lower[-1] in EXCLUDED_RELEASE_NAMES
            or PurePosixPath(name).suffix.casefold() in EXCLUDED_RELEASE_SUFFIXES):
        return 'excluded_release_material'
    return None


def source_files(root):
    """Yield allowlisted files without following file or directory symlinks."""
    root = Path(root)
    for name in SOURCE_FILES:
        path = root / name
        if path.is_file() and not path.is_symlink():
            yield path
    for folder in SOURCE_DIRS:
        base = root / folder
        if not base.is_dir() or base.is_symlink():
            continue
        for directory, children, names in os.walk(str(base), followlinks=False):
            children[:] = sorted(child for child in children if not (Path(directory) / child).is_symlink()
                                 and not private_reason((Path(directory) / child).relative_to(root).as_posix())
                                 and not release_exclusion((Path(directory) / child).relative_to(root).as_posix()))
            for name in sorted(names):
                path = Path(directory) / name
                if (not path.is_symlink() and not private_reason(path.relative_to(root).as_posix())
                        and not release_exclusion(path.relative_to(root).as_posix())):
                    yield path


def text_findings(name, raw):
    """Inspect supported text and Office XML, returning redacted findings."""
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in ('.docx', '.pptx'):
        results = []
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as document:
                if sum(info.file_size for info in document.infolist()) > MAX_ARCHIVE_BYTES:
                    return [{'path': name, 'rule': 'document_too_large'}]
                for info in document.infolist():
                    if info.filename.endswith('.xml'):
                        if info.file_size > MAX_MEMBER_BYTES:
                            results.append({'path': name, 'rule': 'document_part_too_large'})
                        else:
                            results.extend(text_findings(name + '::' + info.filename + '.txt', document.read(info)))
        except (zipfile.BadZipFile, RuntimeError):
            results.append({'path': name, 'rule': 'invalid_office_document'})
        return results
    if suffix not in TEXT_SUFFIXES and PurePosixPath(name).name not in SOURCE_FILES:
        return []
    text = raw.decode('utf-8', errors='replace')
    return [{'path': name, 'line': text.count('\n', 0, match.start()) + 1, 'rule': rule}
            for rule, expression in RULES for match in expression.finditer(text)]


def scan_source(root):
    findings = []
    count = 0
    for path in source_files(root):
        name = path.relative_to(root).as_posix()
        if path.suffix.lower() not in TEXT_SUFFIXES | {'.docx', '.pptx'} and path.name not in SOURCE_FILES:
            continue
        count += 1
        if path.stat().st_size > MAX_MEMBER_BYTES:
            findings.append({'path': name, 'rule': 'source_file_too_large'})
        else:
            findings.extend(text_findings(name, path.read_bytes()))
    return {'scanned_files': count, 'findings': findings,
            'scope': 'Allowlisted source; private state, symlinks and excluded report/presentation deliverables are not read.'}


def syntax_report(root):
    errors = []
    count = 0
    for path in source_files(root):
        if path.suffix != '.py':
            continue
        count += 1
        try:
            ast.parse(path.read_bytes(), filename=path.relative_to(root).as_posix())
        except SyntaxError as exc:
            errors.append({'path': path.relative_to(root).as_posix(), 'line': exc.lineno, 'reason': exc.msg})
    return {'files': count, 'errors': errors}


def archive_relative(name):
    """Validate a source-release member's root and return its project-relative path.

    >>> archive_relative('jobcompass/main.py')
    'main.py'
    >>> archive_relative('jobcompass/.github/workflows/tests.yml')
    '.github/workflows/tests.yml'
    >>> archive_relative('jobcompass/../escape.py')
    Traceback (most recent call last):
        ...
    ValueError: invalid_member_path
    >>> archive_relative('/jobcompass/main.py')
    Traceback (most recent call last):
        ...
    ValueError: invalid_member_path
    """
    parts = PurePosixPath(name).parts
    components = name.rstrip('/').split('/')
    if not parts or name.startswith('/') or '\\' in name or any(part in ('', '.', '..') for part in components) or parts[0] != 'jobcompass':
        raise ValueError('invalid_member_path')
    return '/'.join(parts[1:])


def package_report(path):
    """Validate ZIP structure and CRC without extracting or executing its files."""
    path = Path(path)
    report = {'members': 0, 'sha256': '', 'errors': []}
    required = {'main.py', 'README.md', 'requirements.txt', 'jobcompass/__init__.py', '.env.example'}
    try:
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            report['errors'].append({'rule': 'archive_too_large'})
            return report
        report['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            report['members'] = len(infos)
            if sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES or len(infos) > 10000:
                report['errors'].append({'rule': 'archive_too_large'})
                return report
            seen, relative_names, roots = set(), set(), set()
            for info in infos:
                name = info.filename
                parts = PurePosixPath(name).parts
                if name in seen:
                    report['errors'].append({'path': name, 'rule': 'duplicate_member'})
                seen.add(name)
                try:
                    relative = archive_relative(name)
                except ValueError:
                    report['errors'].append({'path': name, 'rule': 'invalid_member_path'})
                    continue
                roots.add(parts[0])
                relative_names.add(relative)
                reason = private_reason(relative) or release_exclusion(relative)
                if reason:
                    report['errors'].append({'path': name, 'rule': reason})
                    continue
                if stat.S_ISLNK(info.external_attr >> 16):
                    report['errors'].append({'path': name, 'rule': 'symlink_member'})
                    continue
                if info.file_size > MAX_MEMBER_BYTES:
                    report['errors'].append({'path': name, 'rule': 'member_too_large'})
                    continue
                if not info.is_dir():
                    report['errors'].extend(text_findings(name, archive.read(info)))
            if len(roots) != 1:
                report['errors'].append({'rule': 'expected_one_project_root'})
            for name in sorted(required - relative_names):
                report['errors'].append({'path': name, 'rule': 'missing_required_member'})
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        report['errors'].append({'rule': 'unreadable_or_corrupt_archive'})
    return report


def run_command(arguments, output, name):
    start = time.perf_counter()
    try:
        result = subprocess.run([sys.executable] + arguments, cwd=str(ROOT), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=180, check=False)
        text = result.stdout.decode('utf-8', errors='replace')
        code = result.returncode
    except subprocess.TimeoutExpired:
        text, code = 'Command exceeded the 180-second budget.\n', 124
    for _, pattern in RULES:
        text = pattern.sub('[REDACTED]', text)
    (output / (name + '.log')).write_text(text, encoding='utf-8')
    return {'command': [sys.executable] + arguments, 'exit_code': code,
            'seconds': round(time.perf_counter() - start, 3), 'log': name + '.log'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/quality')
    parser.add_argument('--quick', action='store_true', help='Source, syntax and doctests only; no full-suite or release claim.')
    parser.add_argument('--mutations', action='store_true', help='Also run isolated targeted mutation checks.')
    parser.add_argument('--package', type=Path, help='Validate this ZIP instead of building the default JobCompass source ZIP.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'mode': 'quick' if args.quick else 'full', 'cloud_ci_verified': False, 'commands': []}
    report['source'] = scan_source(ROOT)
    report['syntax'] = syntax_report(ROOT)
    report['commands'].append(run_command(['-m', 'doctest', '-v', 'scripts/quality_gate.py'], args.output, 'doctest'))
    if (ROOT / 'scripts/static_checks.py').is_file():
        report['commands'].append(run_command(['scripts/static_checks.py'], args.output, 'static_checks'))
    failed = bool(report['source']['findings'] or report['syntax']['errors'] or any(command['exit_code'] for command in report['commands']))
    if not args.quick and not failed:
        report['commands'].append(run_command(['-m', 'unittest', 'discover', '-v'], args.output, 'unittest'))
        failed = bool(report['commands'][-1]['exit_code'])
        if args.mutations and not failed:
            report['commands'].append(run_command(['scripts/mutation_check.py', '--output', str(args.output / 'mutations')], args.output, 'mutation'))
            failed = bool(report['commands'][-1]['exit_code'])
        if not failed and not args.package:
            report['commands'].append(run_command(['scripts/package_project.py'], args.output, 'package'))
            failed = bool(report['commands'][-1]['exit_code'])
        if not failed:
            report['package'] = package_report(args.package or ROOT / 'dist/jobcompass.zip')
            failed = bool(report['package']['errors'])
    elif args.package and not failed:
        report['package'] = package_report(args.package)
        failed = bool(report['package']['errors'])
    report['status'] = 'failed' if failed else ('quick_checks_passed' if args.quick else 'passed')
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(args.output / 'report.json')}, ensure_ascii=False))
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
