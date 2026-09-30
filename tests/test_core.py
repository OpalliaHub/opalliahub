"""Deterministic offline tests; no external network or real personal data."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from jobcompass.resume import skills_in, parse_resume, experience, extract_file, redact
from jobcompass.matching import rank_jobs, text_scores
from jobcompass.sources import normalize, import_jobs, parse_jsonld, validate_url, plain, collect_api
from jobcompass.storage import Store
from jobcompass.server import Application, csv_export, Tasks
from jobcompass.ai import call_ai

RESUME = '计算机本科应届生，0 年工作经验。技能 Python SQL Pandas Git。项目使用 Python 和 SQL 实现数据分析。'
JOB = {'title':'Python developer','company':'Demo','description':'Python SQL Git development. Bachelor degree, entry level.', 'location':'香港','url':'','source':'test','skills':['Python','SQL','Git']}


class ResumeTests(unittest.TestCase):
    def test_word_boundaries(self):
        self.assertNotIn('Java', skills_in('JavaScript'))
        self.assertNotIn('Go', skills_in('Google'))
        self.assertIn('C++', skills_in('C++ engineer'))

    def test_aliases(self):
        self.assertEqual(set(skills_in('MySQL 机器学习 大模型')), {'SQL','Machine Learning','LLM'})

    def test_evidence(self):
        profile=parse_resume(RESUME)
        self.assertIn('Python', profile['evidence']['Python'])
        self.assertEqual(profile['education'],'本科')

    def test_short_resume(self):
        with self.assertRaises(ValueError): parse_resume('abc')

    def test_long_resume(self):
        with self.assertRaises(ValueError): parse_resume('x'*40001)

    def test_experience(self):
        self.assertEqual(experience('3–5年工作经验'),3)
        self.assertEqual(experience('3 years experience'),3)
        self.assertEqual(experience('0 年工作经验'),0)
        self.assertEqual(experience('本科应届生'),0)
        self.assertIsNone(experience('Python 开发'))

    def test_redaction(self):
        value=redact('test@example.com 13812345678 110101200001011234')
        for raw in ['test@example.com','13812345678','110101200001011234']: self.assertNotIn(raw,value)

    def test_txt_bom(self): self.assertEqual(extract_file('r.txt',b'\xef\xbb\xbfPython'),'Python')

    def test_unsupported_file(self):
        with self.assertRaises(ValueError): extract_file('r.exe',b'x')

    def test_corrupt_docx(self):
        with self.assertRaises(ValueError): extract_file('r.docx',b'bad')

    def test_docx(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z: z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:document>')
        self.assertEqual(extract_file('r.docx',buffer.getvalue()),'Hello')

    def test_large_file(self):
        with self.assertRaises(ValueError): extract_file('r.txt',b'x'*(5*1024*1024+1))


class MatchingTests(unittest.TestCase):
    def rank(self, jobs, prefs=None):
        return rank_jobs(RESUME,parse_resume(RESUME),[dict(j,id=str(i)) for i,j in enumerate(jobs)],prefs)

    def test_relevance(self):
        bad=dict(JOB,title='Designer',description='Figma design',skills=['Figma'])
        result=self.rank([bad,JOB]);self.assertEqual(result[0]['title'],'Python developer')

    def test_generic_skill_does_not_dominate(self):
        resume=RESUME+' 熟悉英语，善于沟通。'
        profile=parse_resume(resume)
        writer=dict(JOB,id='writer',title='Freelance Writer',description='English communication for writers.',skills=['English','Communication'])
        result=rank_jobs(resume,profile,[writer,dict(JOB,id='dev')])
        self.assertEqual(result[0]['id'],'dev')

    def test_bounds(self):
        for j in self.rank([JOB]): self.assertTrue(0<=j['score']<=100)

    def test_missing_weight(self):
        j=dict(JOB,description='Python SQL Git',skills=['Python'],location='')
        result=self.rank([j])[0]
        self.assertEqual(next(b for b in result['breakdown'] if b['key']=='experience')['value'],None)
        self.assertAlmostEqual(sum(b['weight'] for b in result['breakdown']),100,delta=.2)

    def test_experience_penalty(self):
        a=self.rank([dict(JOB,description=JOB['description']+' 5 years experience')])[0]
        self.assertTrue(any('5.0' in w for w in a['warnings']))
        self.assertEqual(next(b for b in a['breakdown'] if b['key']=='experience')['value'],0)

    def test_remote_restrictions(self):
        j=dict(JOB,location='United States',remote=True)
        result=self.rank([j],{'location':'香港','experience_years':0})[0]
        self.assertEqual(next(b for b in result['breakdown'] if b['key']=='location')['value'],0)

    def test_worldwide(self):
        j=dict(JOB,location='Worldwide')
        result=self.rank([j],{'location':'香港'})[0]
        self.assertEqual(next(b for b in result['breakdown'] if b['key']=='location')['value'],100)

    def test_empty_corpus(self): self.assertEqual(text_scores('', ['']),[0])
    def test_same_text(self): self.assertAlmostEqual(text_scores('Python SQL',['Python SQL'])[0],1)
    def test_deterministic(self): self.assertEqual(self.rank([JOB]),self.rank([JOB]))


class ImportTests(unittest.TestCase):
    def test_plain(self): self.assertEqual(plain('<script>evil()</script><p>Python &amp; SQL</p>'),'Python & SQL')
    def test_required_fields(self):
        with self.assertRaises(ValueError): normalize({'title':'x'})
    def test_script_url(self):
        with self.assertRaises(ValueError): normalize(dict(JOB,url='javascript:alert(1)'))
    def test_remote_false_string(self): self.assertFalse(normalize(dict(JOB,remote='false'))['remote'])
    def test_json(self): self.assertEqual(len(import_jobs('jobs.json',json.dumps([JOB]))),1)
    def test_invalid_json(self):
        with self.assertRaises(ValueError): import_jobs('jobs.json','broken')
    def test_csv(self):
        self.assertEqual(len(import_jobs('a.csv','title,company,description\nPython,Demo,Python SQL developer required\n')),1)
    def test_empty_import(self):
        with self.assertRaises(ValueError): import_jobs('j.json','[]')
    def test_jsonld_graph(self):
        block={'@graph':[{'@type':'JobPosting','title':'Python','hiringOrganization':{'name':'Demo'},'description':'Python SQL developer required','jobLocation':{'address':{'addressLocality':'香港'}}}]}
        jobs=parse_jsonld('<script type="application/ld+json">'+json.dumps(block)+'</script>')
        self.assertEqual(jobs[0]['location'],'香港')
    def test_jsonld_absent(self):
        with self.assertRaises(ValueError): parse_jsonld('<p>no jobs</p>')
    def test_private_network(self):
        with patch('socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError): validate_url('https://example.com')
    def test_bad_schemes(self):
        for url in ['file:///etc/passwd','http://example.com','https://a:b@example.com','https://example.com:8080']:
            with self.subTest(url=url),self.assertRaises(ValueError):validate_url(url)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db.sqlite';self.store=Store(self.path)
    def tearDown(self): self.temp.cleanup()
    def test_upsert(self):
        self.store.upsert_jobs([JOB,JOB]);self.assertEqual(len(self.store.jobs()),1)
    def test_preserve_application(self):
        self.store.upsert_jobs([JOB]);jid=self.store.jobs()[0]['id'];self.store.application(jid,'已投递','demo')
        self.store.upsert_jobs([JOB]);self.assertEqual(self.store.jobs()[0]['status'],'已投递')
    def test_application_missing_job(self):
        with self.assertRaises(ValueError):self.store.application('missing','收藏','')
    def test_invalid_status(self):
        with self.assertRaises(ValueError):self.store.application('missing','other','')
    def test_sql_injection(self):
        self.store.set("x';DROP TABLE jobs;--", {'ok':True});self.assertEqual(self.store.jobs(),[])
    def test_persistence(self):
        self.store.set('x',{'value':'中文'});self.assertEqual(Store(self.path).get('x'),{'value':'中文'})
    def test_cache_no_network(self):
        payload={'jobs':[dict(JOB,company_name='Demo',candidate_required_location='Worldwide')]}
        with patch('jobcompass.sources.fetch',return_value=json.dumps(payload)) as mock:
            collect_api('Remotive',self.store);collect_api('Remotive',self.store);self.assertEqual(mock.call_count,1)
    def test_failed_collection(self):
        with patch('jobcompass.sources.fetch',side_effect=ValueError('连接失败')):
            with self.assertRaises(ValueError):collect_api('Arbeitnow',self.store)
        self.assertEqual(self.store.logs()[0]['status'],'error')
    def test_import_transaction(self):
        with self.assertRaises(ValueError):import_jobs('j.json',json.dumps([JOB,{}]))
        self.assertEqual(self.store.jobs(),[])


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(Path(self.temp.name)/'db.sqlite')
    def tearDown(self): self.app.tasks.pool.shutdown(wait=True);self.temp.cleanup()
    def test_seed_once(self):
        self.assertEqual(len(self.app.store.jobs()),12)
    def test_resume_invalid_no_overwrite(self):
        self.app.post('/api/resume',{'text':RESUME})
        with self.assertRaises(ValueError):self.app.post('/api/resume',{'text':'abc'})
        self.assertEqual(self.app.store.get('resume'),RESUME)
    def test_clear_resume(self):
        self.app.post('/api/resume',{'text':RESUME});self.app.post('/api/resume/clear',{})
        self.assertFalse(self.app.state()['resume']);self.assertEqual(len(self.app.state()['jobs']),12)
    def test_preference_validation(self):
        for value in [-1,51,'abc','NaN','Infinity']:
            with self.subTest(value=value),self.assertRaises(ValueError):self.app.post('/api/preferences',{'experience_years':value})
    def test_ai_requires_consent(self):
        self.app.post('/api/resume',{'text':RESUME})
        with self.assertRaises(ValueError):self.app.post('/api/ai',{'task':'analyze'})
    def test_no_key_exposed(self):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'secret-example'}):
            self.assertNotIn('secret-example',json.dumps(self.app.state()))
    def test_export_formula_escape(self):
        j=dict(normalize(dict(JOB,title='=1+1')),is_demo=False)
        self.assertIn("'=1+1",csv_export([j]).decode())
    def test_ai_missing_key(self):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':''}):
            with self.assertRaises(ValueError):call_ai('analyze',RESUME)
    def test_ai_schema(self):
        response={'choices':[{'message':{'content':json.dumps({'summary':'有效','strengths':[],'suggestions':[],'questions':[]})}}]}
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test'}),patch('jobcompass.ai.fetch',return_value=json.dumps(response)):
            self.assertEqual(call_ai('analyze',RESUME)['summary'],'有效')
    def test_ai_malformed(self):
        with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test'}),patch('jobcompass.ai.fetch',return_value='{}'):
            with self.assertRaises(ValueError):call_ai('analyze',RESUME)


if __name__=='__main__':unittest.main()
