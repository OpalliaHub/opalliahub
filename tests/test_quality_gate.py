"""Acceptance boundaries for publication checks; fixtures never contain real credentials."""
import json
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.quality_gate import private_reason, package_report, scan_source, syntax_report


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def archive(self, extras=None):
        path = self.root / 'submission.zip'
        members = {'group11_project/main.py': 'print("demo")',
                   'group11_project/README.md': 'Demo',
                   'group11_project/requirements.txt': '',
                   'group11_project/jobcompass/__init__.py': '',
                   'group11_project/.env.example': 'DEEPSEEK_API_KEY='}
        members.update(extras or {})
        with zipfile.ZipFile(path, 'w') as archive:
            for name, value in members.items():
                archive.writestr(name, value)
        return path

    def test_private_paths_and_env_example_exception(self):
        for name in ('.env', '.env.local', 'data/private/a.json', 'data/raw/a.csv',
                     'data/user.db', '.git/config', 'x/__pycache__/a.pyc'):
            with self.subTest(name=name):
                self.assertIsNotNone(private_reason(name))
        self.assertIsNone(private_reason('.env.example'))
        self.assertIsNone(private_reason('.github/workflows/tests.yml'))

    def test_scan_reports_location_but_never_secret_value(self):
        secret = 'sk-' + 'A' * 32
        self.write('jobcompass/leak.py', 'key = "' + secret + '"\n')
        report = scan_source(self.root)
        self.assertEqual(report['findings'][0]['path'], 'jobcompass/leak.py')
        self.assertEqual(report['findings'][0]['line'], 1)
        self.assertNotIn(secret, json.dumps(report))

    def test_scan_never_opens_private_env_or_symlink(self):
        secret_path = self.write('.env', 'private local content')
        self.write('jobcompass/safe.py', 'x = 1\n')
        (self.root / 'jobcompass/link.py').symlink_to(secret_path)
        original = Path.read_bytes

        def guard(path):
            if path.name == '.env' or path.is_symlink():
                raise AssertionError('Private content must not be read')
            return original(path)

        with patch.object(Path, 'read_bytes', guard):
            report = scan_source(self.root)
        self.assertEqual(report['scanned_files'], 1)
        self.assertEqual(report['findings'], [])

    def test_private_root_directory_symlink_is_not_followed(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'leak.py').write_text('key="sk-' + 'B' * 32 + '"')
        (self.root / 'jobcompass').symlink_to(outside, target_is_directory=True)
        self.assertEqual(scan_source(self.root)['scanned_files'], 0)

    def test_placeholder_is_allowed(self):
        self.write('.env.example', 'DEEPSEEK_API_KEY=your_key_here\n')
        self.assertEqual(scan_source(self.root)['findings'], [])

    def test_syntax_failure_contains_location_without_source(self):
        self.write('jobcompass/broken.py', 'def invalid(:\n')
        report = syntax_report(self.root)
        self.assertEqual(report['errors'][0]['line'], 1)
        self.assertNotIn('def invalid', json.dumps(report))

    def test_valid_archive_has_digest_and_counts(self):
        report = package_report(self.archive())
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['members'], 5)
        self.assertEqual(len(report['sha256']), 64)

    def test_archive_traversal_and_absolute_paths_rejected(self):
        for name in ('../escape.py', '/tmp/escape.py', 'group11_project/../escape.py',
                     'group11_project/dir\\escape.py', 'group11_project/./main.py',
                     'group11_project//main.py'):
            with self.subTest(name=name):
                self.assertTrue(package_report(self.archive({name: ''}))['errors'])

    def test_archive_private_files_rejected(self):
        for name in ('.env', 'data/private/a.json', 'data/app.sqlite', '.git/config'):
            with self.subTest(name=name):
                report = package_report(self.archive({'group11_project/' + name: 'private'}))
                self.assertTrue(report['errors'])

    def test_archive_missing_entrypoint_rejected(self):
        path = self.root / 'empty.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('group11_project/readme.txt', 'missing source')
        self.assertTrue(package_report(path)['errors'])

    def test_archive_secret_redacted(self):
        secret = 'sk-' + 'C' * 32
        report = package_report(self.archive({'group11_project/leak.txt': secret}))
        self.assertTrue(report['errors'])
        self.assertNotIn(secret, json.dumps(report))

    def test_archive_symlink_rejected(self):
        path = self.archive()
        link = zipfile.ZipInfo('group11_project/link')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(path, 'a') as archive:
            archive.writestr(link, '../../private')
        self.assertTrue(package_report(path)['errors'])

    def test_archive_duplicate_rejected(self):
        path = self.archive()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(path, 'a') as archive:
                archive.writestr('group11_project/main.py', 'replaced')
        self.assertIn('duplicate_member', [e['rule'] for e in package_report(path)['errors']])

    def test_archive_total_size_limit_checked_before_content(self):
        path = self.archive()
        with patch('scripts.quality_gate.MAX_ARCHIVE_BYTES', 1):
            self.assertEqual(package_report(path)['errors'], [{'rule': 'archive_too_large'}])

    def test_office_xml_secret_scanned(self):
        import io
        document = io.BytesIO()
        with zipfile.ZipFile(document, 'w') as archive:
            archive.writestr('word/document.xml', '<document>' + 'sk-' + 'D' * 32 + '</document>')
        path = self.archive({'group11_project/docs/report.docx': document.getvalue()})
        report = package_report(path)
        self.assertIn('provider_api_key', [e['rule'] for e in report['errors']])

    def test_corrupt_archive_returns_structured_failure(self):
        path = self.root / 'bad.zip'
        path.write_bytes(b'not a ZIP')
        self.assertTrue(package_report(path)['errors'])


if __name__ == '__main__':
    unittest.main()
