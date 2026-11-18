"""Recommendation HTTP contracts with fictional text and no external inference."""
import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from jobcompass.public import PublicConfig, RateLimiter
from jobcompass.server import Application
from jobcompass.web import WebGateway

# Invented, deliberately non-personal fixtures: no names or contact details.
RESUME_A = '本科应届生。技能 Python SQL Pandas Git。使用 Python 完成课程数据分析、测试与文档项目。'
RESUME_B = '本科应届生。技能 JavaScript React HTML CSS。使用 React 完成课程前端界面、组件和测试项目。'


def fake_recommendations(resume, *args, **kwargs):
    return {'fingerprint': hashlib.sha256(resume.encode()).hexdigest(), 'recommendations': [],
            'message':'Fictional offline integration fixture'}


class RecommendationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Application(Path(self.temp.name) / 'shared.sqlite', demo=True)
        self.base.post('/api/resume', {'text':RESUME_B})
        self.config = PublicConfig('https://jobs.example.test', frozenset({'jobs.example.test'}), frozenset())
        self.web = WebGateway(self.base, public_config=self.config)
        self.a, self.b = self.cookie(), self.cookie()
        self.releases = []

    def tearDown(self):
        for event in self.releases:
            event.set()
        self.base.tasks.pool.shutdown(wait=True)
        self.web.close()
        self.temp.cleanup()

    def request(self, method, path, data=None, cookie=''):
        headers = {'Host':'jobs.example.test', 'Origin':self.config.origin,
                   'X-JobCompass':'1', 'Cookie':cookie}
        status, output, raw = self.web.handle(method, path, headers,
            json.dumps(data).encode() if data is not None else b'', peer='192.0.2.10')
        output = dict(output)
        result = json.loads(raw) if output['Content-Type'].startswith('application/json') else raw
        return status, output, result

    def cookie(self):
        status, headers, _ = self.request('GET', '/')
        self.assertEqual(status, 200)
        return headers['Set-Cookie'].split(';', 1)[0]

    def save(self, cookie, text=RESUME_A):
        self.assertEqual(self.request('POST', '/api/resume', {'text':text}, cookie)[0], 200)

    def finish(self, task_id, cookie):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status, _, task = self.request('GET', '/api/tasks/' + task_id, cookie=cookie)
            self.assertEqual(status, 200)
            if task['status'] not in ('queued', 'running'):
                return task
            threading.Event().wait(0.005)
        self.fail('Fictional offline task did not finish within three seconds')

    def gated(self):
        started, release = threading.Event(), threading.Event()
        self.releases.append(release)
        def build(resume, *args, **kwargs):
            started.set()
            if not release.wait(3):
                raise AssertionError('Test did not release the controlled recommendation task')
            return fake_recommendations(resume)
        return build, started, release

    def test_missing_visitor_resume_does_not_use_owner_profile_or_enqueue(self):
        with patch('jobcompass.server.build_recommendations', create=True) as build:
            status, _, _ = self.request('POST', '/api/recommendations', {}, self.a)
            self.assertEqual(status, 400)
            build.assert_not_called()
        with self.web.sessions.session(self.a) as visitor:
            self.assertEqual(visitor.app.tasks.items, {})
            self.assertEqual(visitor.store.get('resume', ''), '')

    def test_invalid_options_rejected_before_background_submission(self):
        self.save(self.a)
        invalid = ({'target_role':[]}, {'limit':True}, {'limit':-1}, {'limit':9999},
                   {'min_score':-1}, {'min_score':101}, {'strict_location':'yes'},
                   {'include_demo':'yes'}, {'sql':'SELECT * FROM private'})
        with patch('jobcompass.server.build_recommendations', create=True) as build:
            for options in invalid:
                with self.subTest(options=options):
                    self.assertEqual(self.request('POST', '/api/recommendations', options, self.a)[0], 400)
            build.assert_not_called()
        with self.web.sessions.session(self.a) as visitor:
            self.assertEqual(visitor.app.tasks.items, {})

    def test_recommendation_inputs_outputs_and_tasks_are_visitor_scoped(self):
        self.save(self.a, RESUME_A)
        self.save(self.b, RESUME_B)
        self.request('POST', '/api/preferences', {'location':'Hong Kong','experience_years':0}, self.a)
        self.request('POST', '/api/preferences', {'location':'Singapore','experience_years':2}, self.b)
        private_title = 'Fictional visitor A private analyst role'
        self.assertEqual(self.request('POST', '/api/job',
            {'title':private_title,'company':'Fictional','description':'Python SQL reporting and testing'}, self.a)[0], 200)
        self.base.store.application(self.base.store.jobs()[0]['id'], '收藏', 'fictional operator-only note')
        with patch('jobcompass.server.build_recommendations', side_effect=fake_recommendations, create=True) as build:
            tasks = []
            for cookie in (self.a, self.b):
                status, _, response = self.request('POST', '/api/recommendations', {'include_demo':True}, cookie)
                self.assertEqual(status, 200)
                tasks.append(response['task_id'])
            result_a, result_b = self.finish(tasks[0], self.a), self.finish(tasks[1], self.b)
            calls = {call.args[0]:call.args for call in build.call_args_list}
            self.assertEqual(calls[RESUME_A][2]['location'], 'Hong Kong')
            self.assertEqual(calls[RESUME_B][2]['location'], 'Singapore')
            self.assertIn(private_title, [job['title'] for job in calls[RESUME_A][1]])
            self.assertNotIn(private_title, [job['title'] for job in calls[RESUME_B][1]])
            self.assertNotIn('fictional operator-only note', json.dumps(build.call_args_list, default=str))
        self.assertEqual(result_a['status'], 'done')
        self.assertEqual(result_b['status'], 'done')
        self.assertEqual(result_a['result']['fingerprint'], hashlib.sha256(RESUME_A.encode()).hexdigest())
        self.assertEqual(result_b['result']['fingerprint'], hashlib.sha256(RESUME_B.encode()).hexdigest())
        self.assertEqual(self.request('GET', '/api/tasks/' + tasks[0], cookie=self.b)[0], 400)
        self.assertEqual(self.request('GET', '/api/tasks/' + tasks[1], cookie=self.a)[0], 400)
        self.assertNotIn(RESUME_A, json.dumps(result_a, ensure_ascii=False))
        self.assertNotIn(RESUME_B, json.dumps(result_b, ensure_ascii=False))

    def test_offline_recommendation_needs_no_ai_allowance_and_preserves_inputs(self):
        self.save(self.a)
        self.request('POST', '/api/preferences', {'location':'Hong Kong','experience_years':0}, self.a)
        with self.web.sessions.session(self.a) as visitor:
            before = {key:visitor.store.get(key) for key in ('resume','profile','preferences')}
            jobs = visitor.store.jobs()
        with patch.object(self.web.ai_limit, 'reserve', side_effect=AssertionError('Offline recommendation must not spend AI allowance')), \
             patch('jobcompass.server.call_ai', side_effect=AssertionError('Offline recommendation must not call AI')) as ai, \
             patch('jobcompass.server.build_recommendations', side_effect=fake_recommendations, create=True):
            status, _, response = self.request('POST', '/api/recommendations', {'include_demo':True}, self.a)
            self.assertEqual(status, 200)
            self.assertEqual(self.finish(response['task_id'], self.a)['status'], 'done')
            ai.assert_not_called()
        with self.web.sessions.session(self.a) as visitor:
            self.assertEqual(before, {key:visitor.store.get(key) for key in before})
            self.assertEqual(jobs, visitor.store.jobs())
            self.assertEqual(visitor.store.logs(), [])

    def test_resume_changed_during_task_prevents_publication(self):
        self.save(self.a)
        build, started, release = self.gated()
        with patch('jobcompass.server.build_recommendations', side_effect=build, create=True):
            status, _, response = self.request('POST', '/api/recommendations', {}, self.a)
            self.assertEqual(status, 200)
            self.assertTrue(started.wait(2))
            self.save(self.a, RESUME_B)
            release.set()
            task = self.finish(response['task_id'], self.a)
        self.assertEqual(task['status'], 'error')
        self.assertNotIn('result', task)
        self.assertRegex(task['error'], '简历|偏好|变化|更新|过期')
        self.assertEqual(self.request('GET', '/api/state', cookie=self.a)[2]['resume'], RESUME_B)

    def test_preferences_changed_during_task_prevents_publication(self):
        self.save(self.a)
        build, started, release = self.gated()
        with patch('jobcompass.server.build_recommendations', side_effect=build, create=True):
            status, _, response = self.request('POST', '/api/recommendations', {}, self.a)
            self.assertEqual(status, 200)
            self.assertTrue(started.wait(2))
            self.request('POST', '/api/preferences', {'location':'Singapore','experience_years':3}, self.a)
            release.set()
            task = self.finish(response['task_id'], self.a)
        self.assertEqual(task['status'], 'error')
        self.assertNotIn('result', task)
        self.assertRegex(task['error'], '简历|偏好|变化|更新|过期')
        self.assertEqual(self.request('GET', '/api/state', cookie=self.a)[2]['preferences']['location'], 'Singapore')

    def test_duplicate_active_recommendation_is_rejected_without_second_computation(self):
        self.save(self.a)
        build, started, release = self.gated()
        with patch('jobcompass.server.build_recommendations', side_effect=build, create=True) as builder:
            status, _, response = self.request('POST', '/api/recommendations', {}, self.a)
            self.assertEqual(status, 200)
            self.assertTrue(started.wait(2))
            self.assertEqual(self.request('POST', '/api/recommendations', {}, self.a)[0], 400)
            release.set()
            self.assertEqual(self.finish(response['task_id'], self.a)['status'], 'done')
            self.assertEqual(builder.call_count, 1)

    def test_job_corpus_changed_during_task_prevents_publication(self):
        self.save(self.a)
        build, started, release = self.gated()
        with patch('jobcompass.server.build_recommendations', side_effect=build, create=True):
            status, _, response = self.request('POST', '/api/recommendations', {}, self.a)
            self.assertEqual(status, 200)
            self.assertTrue(started.wait(2))
            job = {'title':'Fictional new role','company':'Demo','description':'Python SQL software testing required'}
            self.assertEqual(self.request('POST', '/api/job', job, self.a)[0], 200)
            release.set()
            task = self.finish(response['task_id'], self.a)
        self.assertEqual(task['status'], 'error')
        self.assertNotIn('result', task)
        self.assertRegex(task['error'], '岗位|数据|变化|更新|过期')

    def test_application_note_changes_do_not_invalidate_matching_inputs(self):
        self.save(self.a)
        build, started, release = self.gated()
        with patch('jobcompass.server.build_recommendations', side_effect=build, create=True):
            status, _, response = self.request('POST', '/api/recommendations', {}, self.a)
            self.assertEqual(status, 200)
            self.assertTrue(started.wait(2))
            jid = self.base.store.jobs()[0]['id']
            self.assertEqual(self.request('POST', '/api/application',
                {'id':jid,'status':'收藏','note':'fictional private note'}, self.a)[0], 200)
            release.set()
            task = self.finish(response['task_id'], self.a)
        self.assertEqual(task['status'], 'done')
        self.assertEqual(self.request('GET', '/api/state', cookie=self.a)[2]['history']['undo'], 1)

    def test_recommendation_capacity_is_global_and_released_after_completion(self):
        self.save(self.a)
        self.save(self.b, RESUME_B)
        self.web.recommendation_limit = RateLimiter(per_ip=30, global_limit=300, max_active=1, label='岗位推荐')
        build, started, release = self.gated()
        with patch('jobcompass.server.build_recommendations', side_effect=build, create=True) as builder:
            status, _, first = self.request('POST', '/api/recommendations', {}, self.a)
            self.assertEqual(status, 200)
            self.assertTrue(started.wait(2))
            with self.web.sessions.session(self.b) as visitor:
                with patch.object(visitor.store, 'jobs', side_effect=AssertionError('Corpus capture must follow admission')) as capture:
                    status, headers, _ = self.request('POST', '/api/recommendations', {}, self.b)
                    self.assertEqual(status, 429)
                    self.assertIn('Retry-After', headers)
                    capture.assert_not_called()
                self.assertEqual(visitor.app.tasks.items, {})
            self.assertEqual(builder.call_count, 1)
            release.set()
            self.assertEqual(self.finish(first['task_id'], self.a)['status'], 'done')
            status, _, second = self.request('POST', '/api/recommendations', {}, self.b)
            self.assertEqual(status, 200)
            self.assertEqual(self.finish(second['task_id'], self.b)['status'], 'done')
            self.assertEqual(builder.call_count, 2)


if __name__ == '__main__':
    unittest.main()
