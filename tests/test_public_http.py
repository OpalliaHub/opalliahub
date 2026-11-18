"""Anonymous browser boundaries, tested without external services."""
import io
import json
import tempfile
import threading
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from jobcompass.public import PublicConfig, RateLimiter
from jobcompass.server import Application
from jobcompass.web import WebGateway
from jobcompass.wsgi import WSGIApplication


class PublicHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Application(Path(self.tmp.name) / 'base.db', demo=True)
        self.base.store.set('resume', 'owner private resume')
        self.config = PublicConfig('https://research.example.test', frozenset({'research.example.test'}), frozenset())
        self.web = WebGateway(self.base, public_config=self.config)
        self.a, self.b = self.cookie(), self.cookie()

    def tearDown(self):
        self.base.tasks.pool.shutdown(wait=True)
        self.web.close()
        self.tmp.cleanup()

    def request(self, method, path, data=None, cookie='', origin=True):
        headers = {'Host':'research.example.test', 'X-JobCompass':'1', 'Cookie':cookie}
        if origin:
            headers['Origin'] = self.config.origin
        status, output, raw = self.web.handle(method, path, headers,
                                            json.dumps(data).encode() if data is not None else b'', '203.0.113.10')
        return status, dict(output), json.loads(raw) if dict(output)['Content-Type'].startswith('application/json') else raw

    def cookie(self):
        status, headers, _ = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertIn('Secure', headers['Set-Cookie'])
        value = SimpleCookie(headers['Set-Cookie'])['jobcompass_session'].value
        return 'jobcompass_session=' + value

    def test_owner_and_visitors_do_not_share_resume(self):
        self.assertEqual(self.request('GET', '/api/state', cookie=self.a)[2]['resume'], '')
        text = '本科应届生。技能 Python SQL Pandas Git。使用 Python 分析课程数据并实现完整测试。'
        self.assertEqual(self.request('POST','/api/resume',{'text':text},self.a)[0],200)
        self.assertEqual(self.request('GET','/api/state',cookie=self.a)[2]['resume'],text)
        self.assertEqual(self.request('GET','/api/state',cookie=self.b)[2]['resume'],'')
        self.assertEqual(self.base.store.get('resume'),'owner private resume')

    def test_import_and_application_are_private(self):
        job={'title':'Private imported Python role','company':'Fictional Company','description':'Python SQL data analysis requirement'}
        self.assertEqual(self.request('POST','/api/job',job,self.a)[0],200)
        shared_id=self.base.store.jobs()[0]['id']
        self.request('POST','/api/application',{'id':shared_id,'status':'已投递','note':'visitor A note'},self.a)
        a=self.request('GET','/api/state',cookie=self.a)[2]
        b=self.request('GET','/api/state',cookie=self.b)[2]
        self.assertEqual(len(a['jobs']),13);self.assertEqual(len(b['jobs']),12)
        self.assertEqual(next(j for j in a['jobs'] if j['id']==shared_id)['note'],'visitor A note')
        self.assertIsNone(next(j for j in b['jobs'] if j['id']==shared_id)['note'])
        self.assertEqual(b['history'],{'undo':0,'redo':0})

    def test_tasks_and_saved_results_cannot_cross_sessions(self):
        with self.web.sessions.session(self.a) as a, self.web.sessions.session(self.b) as b:
            task=a.app.tasks.submit('private task',lambda:{'result':'A only'})
            self.assertNotEqual(a.app.research.result_root,b.app.research.result_root)
            self.assertEqual(a.app.research.root,b.app.research.root)
            result=a.app.research.run({'dataset':'current','action':'overview'})
        self.assertEqual(self.request('GET','/api/tasks/'+task['task_id'],cookie=self.b)[0],400)
        self.assertEqual(self.request('GET','/api/research/result/'+result['id'],cookie=self.b)[0],400)
        self.assertEqual(self.request('GET','/api/research/result/'+result['id'],cookie=self.a)[0],200)

    def test_public_cannot_configure_server_paths(self):
        for route in ('connect','build'):
            self.assertEqual(self.request('POST','/api/research/'+route,{'path':'/etc/passwd'},self.a)[0],403)
        status,_,data=self.request('GET','/api/research/status',cookie=self.a)
        self.assertEqual(status,200);self.assertNotIn('path',data)

    def test_writes_require_exact_origin(self):
        self.assertEqual(self.request('POST','/api/preferences',{},self.a,origin=False)[0],403)
        status,_,_=self.web.handle('POST','/api/preferences',{'Host':'research.example.test','Origin':'https://evil.test','X-JobCompass':'1'},b'{}')
        self.assertEqual(status,403)

    def test_new_cookie_does_not_bypass_ai_limit(self):
        self.web.ai_limit=RateLimiter(per_ip=1,global_limit=5,max_active=3)
        completed=threading.Event()
        def fake(*args):
            completed.set();return {'message':'mocked locally'}
        with patch('jobcompass.server.compile_and_run',side_effect=fake) as compile:
            status,_,_=self.request('POST','/api/analytics/command',{'command':'count ads','dataset':'current'},self.a)
            self.assertEqual(status,200);self.assertTrue(completed.wait(2))
            status,headers,_=self.request('POST','/api/analytics/command',{'command':'count ads','dataset':'current'},self.b)
            self.assertEqual(status,429);self.assertIn('Retry-After',headers)
            self.assertEqual(compile.call_count,1)

    def test_health_is_available_to_loopback_probe(self):
        status,_,_=self.web.handle('GET','/api/health',{'Host':'127.0.0.1:8765'},peer='127.0.0.1')
        self.assertEqual(status,200)

    def test_unknown_routes_do_not_allocate_visitors(self):
        count = len(self.web.sessions._items)
        for method in ('GET', 'POST'):
            status, headers, _ = self.request(method, '/api/not-a-route', {} if method == 'POST' else None)
            self.assertEqual(status, 404)
            self.assertNotIn('Set-Cookie', headers)
        self.assertEqual(len(self.web.sessions._items), count)

    def test_creation_budget_applies_to_cookie_churn_not_existing_visitors(self):
        self.web.sessions.creation_limiter = RateLimiter(per_ip=1, global_limit=10, max_active=2, label='新访客会话')
        self.assertEqual(self.request('GET', '/')[0], 200)
        status, headers, result = self.request('GET', '/')
        self.assertEqual(status, 429)
        self.assertIn('Retry-After', headers)
        self.assertIn('新访客会话', result['error'])
        self.assertEqual(self.request('GET', '/api/state', cookie=self.a)[0], 200)

    def test_heavy_gets_share_work_budget_without_blocking_health_or_status(self):
        self.web.work_limit = RateLimiter(per_ip=1, global_limit=10, max_active=2, label='数据请求')
        self.assertEqual(self.request('GET', '/api/state', cookie=self.a)[0], 200)
        self.assertEqual(self.request('GET', '/api/analytics/catalog', cookie=self.a)[0], 429)
        self.assertEqual(self.request('GET', '/api/status', cookie=self.a)[0], 200)
        self.assertEqual(self.request('GET', '/api/health')[0], 200)

    def test_public_arbitrary_page_collection_is_disabled_by_default(self):
        with patch('jobcompass.server.collect_page', return_value={'count':0}) as collector:
            status, _, data = self.request('POST', '/api/collect/page', {'url':'https://unapproved.example/job'}, self.a)
        self.assertEqual(status, 403)
        self.assertIn('导入', data['error'])
        collector.assert_not_called()

    def test_allowlisted_page_collection_uses_restricted_transport(self):
        self.web.config = PublicConfig(self.config.origin, self.config.allowed_hosts,
                                       frozenset(), page_hosts=frozenset({'jobs.allowed.example'}))
        done = threading.Event()
        def collect(url, store, hosts):
            self.assertEqual(url, 'https://jobs.allowed.example/role')
            self.assertEqual(hosts, frozenset({'jobs.allowed.example'}))
            self.assertIsNot(store, self.base.store)
            done.set()
            return {'count':0}
        with patch('jobcompass.web.collect_public_page', side_effect=collect) as collector:
            status, _, _ = self.request('POST', '/api/collect/page', {'url':'https://jobs.allowed.example/role'}, self.a)
            self.assertTrue(done.wait(2))
        self.assertEqual(status, 200)
        self.assertEqual(collector.call_count, 1)

    def test_wsgi_boundary_uses_same_gateway(self):
        # Reuse the tested gateway without opening a second registry over its files.
        wsgi=WSGIApplication.__new__(WSGIApplication);wsgi.gateway=self.web
        captured=[]
        environment={'REQUEST_METHOD':'GET','PATH_INFO':'/api/state','HTTP_HOST':'research.example.test',
                     'HTTP_COOKIE':self.a,'REMOTE_ADDR':'203.0.113.10','wsgi.input':io.BytesIO()}
        data=b''.join(wsgi(environment,lambda status,headers:captured.append((status,dict(headers)))))
        self.assertTrue(captured[0][0].startswith('200'))
        self.assertEqual(json.loads(data)['resume'],'')
        environment.update(REQUEST_METHOD='POST',CONTENT_LENGTH=str(8*1024*1024))
        b''.join(wsgi(environment,lambda status,headers:captured.append((status,dict(headers)))))
        self.assertTrue(captured[-1][0].startswith('400'))
