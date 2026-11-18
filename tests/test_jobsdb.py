"""Offline contract tests for direct JobsDB updates; never call the website."""
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from jobcompass.benchmark import convert_record
from jobcompass.jobsdb import collect, options, expiry_status, read_json
from jobcompass.server import Application, Tasks
from jobcompass.storage import Store
from tests.test_benchmark import fixture


class ImmediateEvent:
    def __init__(self): self.stopped = False
    def wait(self, seconds): return self.stopped
    def is_set(self): return self.stopped
    def set(self): self.stopped = True


class JobsDBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name)/'jobs.db')
    def tearDown(self): self.tmp.cleanup()
    def run_collect(self, responses, **kwargs):
        with patch('jobcompass.jobsdb.read_json', side_effect=responses) as request:
            result = collect(self.store, cancel=kwargs.pop('cancel', ImmediateEvent()), **kwargs)
        return result, request

    def test_options_are_bounded(self):
        for n in [0, 201, True, '20', None, 1.5]:
            with self.subTest(n=n), self.assertRaises(ValueError): options({'limit':n})
        with self.assertRaises(ValueError): options({'keyword': 'x'*101})

    def test_list_dedup_and_detail_id_fallback(self):
        result, request = self.run_collect([
            {'data':[{'id':'12345678'},{'id':'12345678'},{'solMetadata':{'jobId':'87654321'}}]},
            fixture(), fixture('87654321')], limit=2, keyword='Python')
        self.assertEqual(result['count'], 2)
        self.assertEqual(request.call_count, 3)
        self.assertIn('keywords=Python', request.call_args_list[0].args[0])
        self.assertNotIn('cookie', str(request.call_args_list).lower())

    def test_live_update_reuses_snapshot_id_and_preserves_application(self):
        self.store.upsert_jobs([convert_record(fixture())])
        old = self.store.jobs()[0]
        self.store.application(old['id'], '面试中', 'original note')
        self.run_collect([{'data':[{'id':'12345678'}]}, fixture()], limit=1)
        new = self.store.jobs()[0]
        self.assertEqual(new['id'], old['id'])
        self.assertEqual(new['note'], 'original note')
        self.assertEqual(new['source'], 'JobsDB')
        self.assertTrue(new['last_live_checked'])
        self.assertEqual(len(self.store.jobs()), 1)
        self.store.upsert_jobs([convert_record(fixture())])
        self.assertEqual(self.store.jobs()[0]['source'], 'JobsDB')

    def test_partial_failure_preserves_completed_jobs_and_stops(self):
        result, request = self.run_collect([{'data':[{'id':'12345678'},{'id':'87654321'}]},
            fixture(), ValueError('HTTP 429')], limit=2)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['count'], 1)
        self.assertEqual(request.call_count, 3)
        self.assertIn('429', self.store.logs()[0]['message'])

    def test_access_refusal_does_not_retry_or_destroy_jobs(self):
        self.store.upsert_jobs([convert_record(fixture())])
        with patch('jobcompass.jobsdb.read_json', side_effect=ValueError('HTTP 403')) as request:
            with self.assertRaisesRegex(ValueError, '403'): collect(self.store, cancel=ImmediateEvent())
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(self.store.jobs()), 1)
        self.assertEqual(self.store.get('jobsdb_last_run')['status'], 'error')

    def test_id_mismatch_not_written(self):
        result, _ = self.run_collect([{'data':[{'id':'12345678'}]}, fixture('87654321')], limit=1)
        self.assertEqual(result['rejected'], 1)
        self.assertEqual(self.store.jobs(), [])

    def test_missing_details_skipped(self):
        result, _ = self.run_collect([{'data':[{'id':'12345678'}]}, {'data':{'jobDetails':None}}], limit=1)
        self.assertEqual(result['unavailable'], 1)

    def test_expired_record_saved_for_tracker(self):
        result, _ = self.run_collect([{'data':[{'id':'12345678'}]}, fixture(expired=True)], limit=1)
        self.assertEqual(result['expired'], 1)
        self.assertEqual(self.store.jobs()[0]['availability'], 'expired')

    def test_expiry_date_recomputed(self):
        job = {'availability':'current','expires_at':'2026-10-01T00:00:00Z'}
        self.assertEqual(expiry_status(job, datetime(2026,10,8,tzinfo=timezone.utc)), 'expired')
        self.assertEqual(expiry_status(dict(job, expires_at='bad')), 'current')

    def test_cancel_keeps_completed_records(self):
        event = ImmediateEvent()
        def progress(**data):
            if data.get('saved') == 1: event.set()
        result, request = self.run_collect([{'data':[{'id':'12345678'},{'id':'87654321'}]}, fixture()],
                                          limit=2, cancel=event, progress=progress)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(result['count'], 1)
        self.assertEqual(request.call_count, 2)

    def test_empty_search_does_not_remove_existing_records(self):
        self.store.upsert_jobs([convert_record(fixture())])
        result, _ = self.run_collect([{'data':[]}])
        self.assertEqual(result['found'], 0)
        self.assertEqual(len(self.store.jobs()), 1)

    def test_attempt_cooldown_persists_across_connections(self):
        self.run_collect([{'data':[]}])
        other = Store(Path(self.tmp.name)/'jobs.db')
        with patch('jobcompass.jobsdb.read_json') as request:
            with self.assertRaisesRegex(ValueError, '60'): collect(other)
        request.assert_not_called()

    def test_broken_graphql_is_not_success(self):
        for payload in ['bad json', '[]', '{"errors":[{"message":"no access"}]}']:
            with self.subTest(payload=payload), patch('jobcompass.jobsdb.fetch', return_value=payload):
                with self.assertRaises(ValueError): read_json('https://hk.jobsdb.com/graphql')

    def test_default_initialization_uses_jobsdb(self):
        with patch('jobcompass.server.import_snapshot') as seed:
            app=Application(Path(self.tmp.name)/'app.db')
            seed.assert_called_once_with(app.store)
            app.tasks.pool.shutdown(wait=True)

    def test_legacy_database_migration(self):
        p=Path(self.tmp.name)/'legacy.db'
        with sqlite3.connect(str(p)) as con:
            con.execute('CREATE TABLE jobs (id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL, company TEXT NOT NULL, location TEXT, salary TEXT, url TEXT, description TEXT NOT NULL, skills TEXT, published_at TEXT, collected_at TEXT NOT NULL, is_demo INTEGER DEFAULT 0, remote INTEGER DEFAULT 0)')
        old=Store(p);old.upsert_jobs([convert_record(fixture())])
        self.assertIn('last_live_checked', old.jobs()[0])

    def test_task_progress_cancel_and_resume_state(self):
        task=Tasks(); ready=threading.Event(); done=threading.Event()
        def work(progress, event):
            progress(phase='test',completed=1,total=2,saved=1)
            ready.set();event.wait(2);done.set()
            return {'status':'cancelled' if event.is_set() else 'success'}
        try:
            tid=task.submit('更新 JobsDB 岗位', work, controlled=True)['task_id']
            self.assertTrue(ready.wait(2))
            self.assertEqual(task.active()[0]['progress']['saved'], 1)
            with self.assertRaises(ValueError):task.submit('更新 JobsDB 岗位', lambda:None)
            task.cancel(tid)
            self.assertTrue(done.wait(2))
        finally:task.pool.shutdown(wait=True)
        self.assertEqual(task.get(tid)['status'], 'cancelled')
