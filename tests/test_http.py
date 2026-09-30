"""HTTP boundary tests run against an isolated temporary local server."""
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from jobcompass.server import Application, make_server


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.app=Application(Path(cls.temp.name)/'test.db')
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


if __name__=='__main__':unittest.main()
