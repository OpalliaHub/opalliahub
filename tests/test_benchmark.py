"""Boundary and reproducibility tests for research data, using fictional fixtures."""
import copy
import gzip
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from jobcompass.benchmark import convert_record, convert_archive, write_snapshot, load_snapshot, import_snapshot
from jobcompass.storage import Store


def fixture(jid='12345678', expired=False):
    return {'data': {'jobDetails': {'job': {
        'id': jid, 'title': 'Python Developer', 'advertiser': {'name': 'Fictional Test Co'},
        'content': '<p>Python SQL development and testing. Contact demo@example.com or +852 9123 4567.</p>',
        'phoneNumber': '91234567', 'contactMatches': ['private'], 'tracking': {'private': 'metadata'},
        'location': {'label': 'Hong Kong'}, 'salary': {'label': '$25,000 per month'},
        'listedAt': {'dateTimeUtc': '2026-09-28T00:00:00Z'}, 'isExpired': expired
    }}}}


class BenchmarkTests(unittest.TestCase):
    def test_normalization_removes_contacts_and_tracking(self):
        job = convert_record(fixture())
        body = json.dumps(job)
        self.assertNotIn('demo@example.com', body)
        self.assertNotIn('9123', body)
        self.assertNotIn('tracking', body)
        self.assertNotIn('phoneNumber', body)
        self.assertEqual(job['salary'], '$25,000 per month')
        self.assertEqual(job['url'], 'https://hk.jobsdb.com/job/12345678')
        self.assertIn('Python', job['skills'])

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError): convert_record(fixture('../bad'))

    def test_archive_filters_metadata_and_counts_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'input.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('snapshot/original_data/a.json', json.dumps(fixture()))
                z.writestr('snapshot/original_data/b.json', json.dumps(fixture()))
                z.writestr('snapshot/original_data/bad.json', '{}')
                z.writestr('__MACOSX/snapshot/original_data/._a.json', 'not json')
            jobs, counts, _ = convert_archive(path)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(counts['input_records'], 3)
            self.assertEqual(counts['duplicate_ids'], 1)
            self.assertEqual(counts['rejected_records'], 1)

    def test_gzip_is_reproducible_and_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'a.gz', Path(tmp)/'b.gz'
            jobs = [convert_record(fixture())]
            self.assertEqual(write_snapshot(jobs, a), write_snapshot(jobs, b))
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(load_snapshot(a), jobs)

    def test_duplicate_snapshot_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'jobs.gz'
            job = convert_record(fixture())
            write_snapshot([job, job], path)
            with self.assertRaises(ValueError): load_snapshot(path)

    def test_expired_jobs_excluded_and_repeat_import_preserves_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'jobs.gz'
            write_snapshot([convert_record(fixture()), convert_record(fixture('87654321', True))], path)
            store = Store(Path(tmp)/'test.db')
            self.assertEqual(import_snapshot(store, path)['count'], 1)
            jid = store.jobs()[0]['id']
            store.application(jid, '面试中', 'fictional test note')
            import_snapshot(store, path)
            self.assertEqual(len(store.jobs()), 1)
            self.assertEqual(store.jobs()[0]['note'], 'fictional test note')

    def test_invalid_batch_does_not_write_to_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'jobs.gz'
            job = convert_record(fixture())
            invalid = dict(job, id='other', description='')
            write_snapshot([job, invalid], path)
            store = Store(Path(tmp)/'test.db')
            with self.assertRaises(ValueError): import_snapshot(store, path)
            self.assertEqual(store.jobs(), [])
