"""HTTP boundary tests run against an isolated temporary local server."""
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.client import HTTPConnection
from pathlib import Path
from jobcompass.server import Application, make_server


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.app=Application(Path(cls.temp.name)/'test.db', demo=True)
        cls.server=make_server(cls.app,0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        cls.app.tasks.pool.shutdown(wait=True);cls.temp.cleanup()

    def request(self,method,path,body=None,headers=None):
        conn=HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        conn.request(method,path,body=body,headers=headers or {})
        r=conn.getresponse();result=(r.status,dict(r.getheaders()),r.read());conn.close();return result

    def test_health(self):
        status,headers,body=self.request('GET','/api/health')
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['status'],'ok')
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])

    def test_unknown_route(self):self.assertEqual(self.request('GET','/missing')[0],404)
    def test_env_not_served(self):self.assertEqual(self.request('GET','/.env')[0],404)
    def test_traversal(self):self.assertEqual(self.request('GET','/../../.env')[0],404)
    def test_bad_host(self):self.assertEqual(self.request('GET','/api/state',headers={'Host':'evil.example'})[0],403)
    def test_no_header_csrf(self):self.assertEqual(self.request('POST','/api/resume',body='{}')[0],403)
    def test_cross_origin(self):
        self.assertEqual(self.request('POST','/api/resume',body='{}',headers={'X-JobCompass':'1','Origin':'https://evil.example'})[0],403)
    def test_invalid_json(self):
        self.assertEqual(self.request('POST','/api/resume',body='{bad',headers={'X-JobCompass':'1'})[0],400)
    def test_oversize(self):
        self.assertEqual(self.request('POST','/api/resume',body='x',headers={'X-JobCompass':'1','Content-Length':str(8*1024*1024)})[0],400)
    def test_full_flow(self):
        headers={'X-JobCompass':'1','Content-Type':'application/json'}
        resume='本科应届生。技能 Python SQL Pandas Git。用 Python 编写数据分析工具和测试，有完整课程项目经验。'
        self.assertEqual(self.request('POST','/api/resume',json.dumps({'text':resume}),headers)[0],200)
        data=json.loads(self.request('GET','/api/state')[2]);self.assertIn('score',data['jobs'][0])
        body=json.dumps({'id':data['jobs'][0]['id'],'status':'面试中','note':'test note'})
        self.assertEqual(self.request('POST','/api/application',body,headers)[0],200)
        data=json.loads(self.request('GET','/api/state')[2]);self.assertEqual(data['jobs'][0]['status'],'面试中')
    def test_export(self):
        status,headers,body=self.request('GET','/api/export');self.assertEqual(status,200)
        self.assertIn('text/csv',headers['Content-Type']);self.assertTrue(body.startswith(b'\xef\xbb\xbf'))

    def test_learning_endpoint_and_validation(self):
        headers={'X-JobCompass':'1'}
        status,_,body=self.request('POST','/api/learning',json.dumps({'target':'Python','limit':5}),headers)
        self.assertEqual(status,200);self.assertIn('learning_order',json.loads(body))
        for invalid in ({'target':[]}, {'target':'x'*101}, {'limit':True}, {'limit':21}):
            self.assertEqual(self.request('POST','/api/learning',json.dumps(invalid),headers)[0],400)
        self.assertEqual(self.request('GET','/learning.js')[0],200)

    def test_agent_rejects_unapproved_or_unbounded_request(self):
        headers={'X-JobCompass':'1'}
        with patch('jobcompass.server.run_agent') as agent:
            for body in ({'command':'test'}, {'command':'test','consent':True,'max_steps':5},
                         {'command':'test','consent':True,'max_steps':True},
                         {'command':'x'*1001,'consent':True}):
                self.assertEqual(self.request('POST','/api/research/agent',json.dumps(body),headers)[0],400)
            agent.assert_not_called()

    def test_agent_runs_as_cancellable_task(self):
        called=threading.Event()
        def fake(command,dataset,runner,**kwargs):
            kwargs['progress'](phase='offline agent test',completed=1,total=3)
            self.assertEqual(command,'研究 Python');self.assertEqual(dataset,'current')
            self.assertEqual(kwargs['max_steps'],3);self.assertIsNotNone(kwargs['cancel'])
            called.set()
            return {'status':'completed','steps':[],'message':'offline test'}
        with patch('jobcompass.server.run_agent',side_effect=fake):
            status,_,body=self.request('POST','/api/research/agent',json.dumps({'command':'研究 Python','dataset':'current','consent':True}),{'X-JobCompass':'1'})
            self.assertEqual(status,200);self.assertTrue(called.wait(2))
            tid=json.loads(body)['task_id']
            self.assertIn(tid,self.app.tasks.cancellations)

    def test_clear_resume_releases_ranking_cache(self):
        headers={'X-JobCompass':'1'}
        resume='本科应届生。技能 Python SQL Pandas Git。用 Python 编写数据分析工具和测试，有完整课程项目经验。'
        self.request('POST','/api/resume',json.dumps({'text':resume}),headers)
        self.request('GET','/api/state')
        self.assertEqual(self.app.ranking_cache.cache_info().currsize,1)
        self.request('POST','/api/resume/clear','{}',headers)
        self.assertEqual(self.app.ranking_cache.cache_info().currsize,0)

    def test_history_api_round_trip(self):
        headers={'X-JobCompass':'1'}
        jid=self.app.store.jobs()[0]['id']
        self.request('POST','/api/application',json.dumps({'id':jid,'status':'已投递','note':'history-api'}),headers)
        for action in ('undo','redo'):
            status,_,body=self.request('POST','/api/application/history',json.dumps({'action':action}),headers)
            self.assertEqual(status,200);self.assertIn('undo',json.loads(body))
        self.assertEqual(self.app.store.jobs()[0]['note'],'history-api')
        self.assertEqual(self.request('POST','/api/application/history','{"action":"drop"}',headers)[0],400)

    def test_jobsdb_invalid_limit_rejected_before_network(self):
        with patch('jobcompass.server.collect_jobsdb') as collect:
            status, _, _ = self.request('POST','/api/jobsdb/update',json.dumps({'limit':999}),{'X-JobCompass':'1'})
        self.assertEqual(status,400);collect.assert_not_called()

    def test_jobsdb_update_uses_background_task(self):
        completed=threading.Event()
        def collect(store, **kwargs):
            kwargs['progress'](phase='test',completed=1,total=1,saved=1)
            completed.set()
            return {'count':1,'status':'success'}
        with patch('jobcompass.server.collect_jobsdb',side_effect=collect):
            status, _, body = self.request('POST','/api/jobsdb/update',json.dumps({'limit':1}),{'X-JobCompass':'1'})
            self.assertEqual(status,200)
            self.assertTrue(completed.wait(2))
            tid=json.loads(body)['task_id']
            status, _, body = self.request('GET','/api/tasks/'+tid)
            self.assertEqual(status,200);self.assertEqual(json.loads(body)['progress']['saved'],1)

    def test_cancel_unknown_task(self):
        self.assertEqual(self.request('POST','/api/tasks/cancel',json.dumps({'task_id':'missing'}),{'X-JobCompass':'1'})[0],400)



    def test_research_status(self):
        status,_,body=self.request('GET','/api/research/status');self.assertEqual(status,200);self.assertIn('concepts',json.loads(body))
    def test_research_rejects_executable_plan(self):
        status,_,body=self.request('POST','/api/research/run',json.dumps({'plan':{'sql':'DROP TABLE jobs'}}),{'X-JobCompass':'1'})
        self.assertEqual(status,400)
    def test_research_result_path_boundary(self):
        self.assertEqual(self.request('GET','/api/research/result/.env')[0],400)

if __name__=='__main__':unittest.main()
