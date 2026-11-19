"""JobsDB collection through the real anonymous HTTP boundary, with offline IO."""
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from jobcompass.benchmark import convert_record
from jobcompass.jobsdb_http import JobsDBError
from jobcompass.public import PublicConfig
from jobcompass.server import Application
from jobcompass.web import WebGateway
from tests.test_benchmark import fixture
from tests.test_jobsdb_v7 import search


class JobsDBPublicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Application(Path(self.tmp.name) / 'operator.db', demo=True)
        self.base.store.upsert_jobs([convert_record(fixture())])
        self.shared = next(job for job in self.base.store.jobs() if job['url'] == 'https://hk.jobsdb.com/job/12345678')
        self.base.store.application(self.shared['id'], '收藏', 'fictional operator note')
        self.base.store.set('resume', 'fictional operator private resume')
        self.base.store.set('jobsdb_last_run', {'status': 'operator-only'})
        self.config = PublicConfig('https://research.example.test', frozenset({'research.example.test'}), frozenset())
        self.web = WebGateway(self.base, public_config=self.config)
        self.a, self.b = self.cookie(), self.cookie()
        self.outbound_guard = patch('jobcompass.jobsdb_http.JobsDBClient._send',
                                    side_effect=AssertionError('Live network is prohibited in this test'))
        self.outbound_guard.start()

    def tearDown(self):
        self.base.tasks.pool.shutdown(wait=True)
        self.outbound_guard.stop()
        self.web.close()
        self.tmp.cleanup()

    def request(self, method, path, data=None, cookie='', overrides=None):
        headers = {'Host': 'research.example.test', 'Origin': self.config.origin,
                   'X-JobCompass': '1', 'Cookie': cookie}
        for key, value in (overrides or {}).items():
            if value is None:
                headers.pop(key, None)
            else:
                headers[key] = value
        status, output, raw = self.web.handle(method, path, headers,
            json.dumps(data).encode('utf-8') if data is not None else b'', '203.0.113.10')
        result = json.loads(raw) if dict(output)['Content-Type'].startswith('application/json') else raw
        return status, dict(output), result

    def cookie(self):
        status, headers, _ = self.request('GET', '/api/status')
        self.assertEqual(status, 200)
        self.assertIn('Secure', headers['Set-Cookie'])
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        return 'jobcompass_session=' + SimpleCookie(headers['Set-Cookie'])['jobcompass_session'].value

    def start(self, cookie, limit=1):
        status, _, result = self.request('POST', '/api/jobsdb/update', {'limit': limit}, cookie)
        self.assertEqual(status, 200, result)
        self.assertIn('task_id', result)
        return result['task_id']

    def wait_task(self, cookie, task_id):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status, _, task = self.request('GET', '/api/tasks/' + task_id, cookie=cookie)
            self.assertEqual(status, 200)
            if task['status'] in ('done', 'error', 'cancelled'):
                return task
            time.sleep(0.01)
        self.fail('Mocked JobsDB task did not finish within three seconds')

    def state(self, cookie):
        status, _, state = self.request('GET', '/api/state', cookie=cookie)
        self.assertEqual(status, 200)
        return state

    def test_success_updates_only_requesting_visitor_and_preserves_notes(self):
        status, _, _ = self.request('POST', '/api/application',
            {'id': self.shared['id'], 'status': '面试中', 'note': 'fictional visitor A note'}, self.a)
        self.assertEqual(status, 200)
        changed = fixture()
        changed['data']['jobDetails']['job']['title'] = 'Updated Python Research Role'
        with patch('jobcompass.jobsdb.read_json', side_effect=[
                search(['12345678', '87654321']), changed, fixture('87654321')]) as outbound:
            task_id = self.start(self.a, limit=2)
            task = self.wait_task(self.a, task_id)
        self.assertEqual(task['status'], 'done', task)
        self.assertEqual(task['result']['count'], 2)
        self.assertEqual(task['result']['search_api'], 'JobSearchV7')
        self.assertEqual(outbound.call_count, 3)
        a, b = self.state(self.a), self.state(self.b)
        a_jobs, b_jobs = ({job['url']: job for job in state['jobs']} for state in (a, b))
        self.assertEqual(a_jobs[self.shared['url']]['id'], self.shared['id'])
        self.assertEqual(a_jobs[self.shared['url']]['title'], 'Updated Python Research Role')
        self.assertEqual(a_jobs[self.shared['url']]['note'], 'fictional visitor A note')
        self.assertEqual(b_jobs[self.shared['url']]['title'], self.shared['title'])
        self.assertIsNone(b_jobs[self.shared['url']]['note'])
        self.assertIn('https://hk.jobsdb.com/job/87654321', a_jobs)
        self.assertNotIn('https://hk.jobsdb.com/job/87654321', b_jobs)
        self.assertEqual(a['jobsdb']['last_run']['count'], 2)
        self.assertIsNone(b['jobsdb']['last_run'])
        self.assertEqual(b['resume'], '')
        self.assertEqual(self.base.store.get('resume'), 'fictional operator private resume')
        self.assertEqual(self.base.store.get('jobsdb_last_run'), {'status': 'operator-only'})
        owner_job = next(job for job in self.base.store.jobs() if job['id'] == self.shared['id'])
        self.assertEqual(owner_job['title'], self.shared['title'])
        self.assertEqual(owner_job['note'], 'fictional operator note')
        status, _, hidden = self.request('GET', '/api/tasks/' + task_id, cookie=self.b)
        self.assertEqual(status, 400)
        self.assertNotIn('result', hidden)
        self.assertNotIn('Updated Python', json.dumps(hidden))

    def test_invalid_origin_host_marker_or_cross_site_never_enqueue_or_fetch(self):
        cases = ({'Origin': None}, {'Origin': 'https://evil.example.test'},
                 {'Origin': self.config.origin + '.evil.test'}, {'Host': 'evil.example.test'},
                 {'X-JobCompass': None}, {'Sec-Fetch-Site': 'cross-site'})
        with patch('jobcompass.jobsdb.read_json') as outbound:
            for overrides in cases:
                with self.subTest(overrides=overrides):
                    status, _, _ = self.request('POST', '/api/jobsdb/update', {'limit': 1}, self.a, overrides)
                    self.assertEqual(status, 403)
            outbound.assert_not_called()
        self.assertIsNone(self.base.store.get('jobsdb_last_attempt'))
        for cookie in (self.a, self.b):
            with self.web.sessions.session(cookie) as session:
                self.assertEqual(session.app.tasks.items, {})

    def test_cooldown_is_shared_across_visitors_and_not_bypassed_by_new_cookie(self):
        with patch('jobcompass.jobsdb.read_json', return_value=search()) as outbound:
            a_task = self.wait_task(self.a, self.start(self.a))
            self.assertEqual(a_task['status'], 'done')
            self.assertEqual(outbound.call_count, 1)
            b_task = self.wait_task(self.b, self.start(self.b))
            self.assertEqual(b_task['status'], 'error')
            self.assertIn('60', b_task['error'])
            fresh = self.cookie()
            new_task = self.wait_task(fresh, self.start(fresh))
            self.assertEqual(new_task['status'], 'error')
            self.assertEqual(outbound.call_count, 1)
        self.assertIsNone(self.state(self.b)['jobsdb']['last_run'])
        self.assertIsNotNone(self.base.store.get('jobsdb_last_attempt'))

    def test_in_progress_collection_lock_is_shared_and_other_visitor_cannot_cancel(self):
        entered, release = threading.Event(), threading.Event()
        def slow_search(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise AssertionError('Test did not release fake JobsDB response')
            return search()
        with patch('jobcompass.jobsdb.read_json', side_effect=slow_search) as outbound:
            a_id = self.start(self.a)
            try:
                self.assertTrue(entered.wait(1))
                status, _, _ = self.request('POST', '/api/tasks/cancel', {'task_id': a_id}, self.b)
                self.assertEqual(status, 400)
                b_task = self.wait_task(self.b, self.start(self.b))
                self.assertEqual(b_task['status'], 'error')
                self.assertIn('正在进行', b_task['error'])
                self.assertEqual(outbound.call_count, 1)
                self.assertEqual(self.request('GET', '/api/tasks/' + a_id, cookie=self.a)[2]['status'], 'running')
            finally:
                release.set()
                a_task = self.wait_task(self.a, a_id)
            self.assertEqual(a_task['status'], 'done')

    def test_provider_retry_after_survives_new_cookie_beyond_normal_cooldown(self):
        with patch('jobcompass.jobsdb.read_json', side_effect=JobsDBError('rate_limited', retry_after=600)) as outbound:
            a_task = self.wait_task(self.a, self.start(self.a))
            self.assertEqual(a_task['status'], 'error')
            self.assertEqual(outbound.call_count, 1)
            future = (datetime.now(timezone.utc) + timedelta(seconds=61)).isoformat()
            fresh = self.cookie()
            with patch('jobcompass.jobsdb.now', return_value=future):
                for cookie in (self.b, fresh):
                    task = self.wait_task(cookie, self.start(cookie))
                    self.assertEqual(task['status'], 'error')
                    self.assertIn('冷却', task['error'])
            self.assertEqual(outbound.call_count, 1)
        self.assertEqual(self.state(self.a)['jobsdb']['last_run']['stop_code'], 'rate_limited')
        self.assertIsNone(self.state(self.b)['jobsdb']['last_run'])
        self.assertIsNone(self.state(fresh)['jobsdb']['last_run'])
        self.assertEqual(self.base.store.get('jobsdb_last_run'), {'status': 'operator-only'})

    def test_partial_provider_failure_keeps_completed_private_result_only(self):
        with patch('jobcompass.jobsdb.read_json', side_effect=[search(['87654321', '11223344']),
                fixture('87654321'), JobsDBError('access_denied')]) as outbound:
            task_id = self.start(self.a, limit=2)
            task = self.wait_task(self.a, task_id)
        self.assertEqual(task['status'], 'done')
        self.assertEqual(task['result']['status'], 'partial')
        self.assertEqual(task['result']['stop_code'], 'access_denied')
        self.assertEqual(task['result']['count'], 1)
        self.assertEqual(outbound.call_count, 3)
        a, b = self.state(self.a), self.state(self.b)
        self.assertIn('https://hk.jobsdb.com/job/87654321', [job['url'] for job in a['jobs']])
        self.assertNotIn('https://hk.jobsdb.com/job/87654321', [job['url'] for job in b['jobs']])
        self.assertEqual(a['jobsdb']['last_run']['status'], 'partial')
        self.assertIsNone(b['jobsdb']['last_run'])
        self.assertEqual(self.request('GET', '/api/tasks/' + task_id, cookie=self.b)[0], 400)


if __name__ == '__main__':
    unittest.main()
