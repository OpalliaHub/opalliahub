"""Research statistics, non-destructive plans and AI boundaries on a tiny temporal corpus."""
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from jobcompass.storage import Store
from jobcompass.research import Research, validate_plan, export_csv, readonly
from jobcompass.research_ai import plan_command, explain_result


def source_fixture(path):
    c=sqlite3.connect(str(path))
    c.executescript('''CREATE TABLE jobs(job_id TEXT,first_record_hash TEXT,latest_record_hash TEXT,first_scrape TEXT,last_scrape TEXT,n_snapshots INT);
    CREATE TABLE records(record_hash TEXT,job_id TEXT,title TEXT,advertiser TEXT,classifications TEXT,location TEXT,salary TEXT,post_time TEXT,content_text TEXT,text_hash TEXT);
    CREATE TABLE record_quality(record_hash TEXT,valid_job_id INT,valid_post_time INT,has_content INT);
    CREATE TABLE snapshots(snapshot_id TEXT,scrape_time TEXT,row_count INT,is_consolidated INT);
    CREATE TABLE observations(snapshot_id TEXT,job_id TEXT,record_hash TEXT);''')
    for i,dt in enumerate(['2025-03-15','2026-03-15','2026-04-10']):c.execute('INSERT INTO snapshots VALUES (?,?,?,0)',(str(i),dt,2))
    bodies=['Python is required. '+('Work duties and projects. '*8),'Teaching and learning. '+('Work duties and projects. '*8),'Python is preferred. '+('Work duties and projects. '*8)]
    for jid,title,company,date,observed,body,category in [
        ('1','Developer','A','2025-03-01','2025-03-15',bodies[0],'Information & Communication Technology'),
        ('2','Teacher','B','2025-03-01','2025-03-15',bodies[1],'Education & Training'),
        ('3','Developer','A','2026-03-01','2026-03-15',bodies[0],'Information & Communication Technology'),
        ('4','Developer','C','2026-03-01','2026-03-15',bodies[2],'Information & Communication Technology'),
        ('5','Late ad','D','2025-03-01','2026-03-15',bodies[2],'Engineering')]:
        h=jid+'a';last=jid+'b' if jid=='2' else h
        c.execute('INSERT INTO jobs VALUES (?,?,?,?,?,1)',(jid,h,last,observed,'2026-04-10' if jid=='2' else observed))
        for rh,txt in [(h,body)]+([(last,body+' Python is now a plus.')] if jid=='2' else []):
            c.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?)',(rh,jid,title,company,'Role ('+category+')','Hong Kong','',date,txt,hashlib.sha256(txt.encode()).hexdigest()))
            c.execute('INSERT INTO record_quality VALUES (?,1,1,1)',(rh,))
        c.execute('INSERT INTO observations VALUES (?,?,?)',('0',jid,h))
    c.commit();c.close()


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'source.sqlite';source_fixture(self.source)
        self.store=Store(self.root/'app.db');self.r=Research(self.store);self.r.connect(str(self.source));self.r.build()
    def tearDown(self):self.tmp.cleanup()
    def plan(self,action='compare',**extra):
        p={'dataset':'research','action':action,'concept':'python','filters':{'common_only':True,'fresh_only':True},'period_a':['2025-03-01','2025-03-31'],'period_b':['2026-03-01','2026-03-31']};p.update(extra);return p
    def test_real_denominators_and_percentage_points(self):
        r=self.r.run(self.plan());self.assertEqual([x['n'] for x in r['rows']],[2,2]);self.assertEqual(r['details']['difference_pp'],50)
    def test_cutoff_excludes_old_ads_observed_in_future(self):
        p=self.plan('overview',filters={'cutoff':'2025-12-31'});self.assertEqual(self.r.run(p)['population_n'],2)
    def test_family_sensitivity_removes_reposted_same_body(self):
        self.assertEqual(self.r.run(self.plan('overview',dedup='family'))['population_n'],3)
    def test_build_does_not_modify_source(self):
        h=hashlib.sha256(self.source.read_bytes()).hexdigest();self.r.build();self.assertEqual(h,hashlib.sha256(self.source.read_bytes()).hexdigest())
    def test_dataset_operation_does_not_require_probe_match(self):
        r=self.r.run(self.plan('dataset',filters={'title':'Teacher'}))
        self.assertEqual(len(r['rows']),1);self.assertEqual(r['rows'][0]['id'],'2')
    def test_overlapping_comparison_rejected(self):
        with self.assertRaises(ValueError):validate_plan(self.plan(period_b=['2025-03-15','2025-04-01']))
    def test_sample_offsets_locate_original_mention(self):
        r=self.r.run(self.plan('sample'))['rows'][0]
        with readonly(self.source) as c:text=c.execute('SELECT content_text FROM records WHERE record_hash=?',(r['record_hash'],)).fetchone()[0]
        self.assertEqual(text[r['match_start']:r['match_end']],'Python')
    def test_readonly_db_rejects_writes(self):
        with readonly(self.source) as c:
            with self.assertRaises(sqlite3.OperationalError):c.execute('DELETE FROM jobs')
    def test_empty_cohort_returns_unknown_not_zero_rate(self):
        r=self.r.run(self.plan(filters={'title':'missing'}));self.assertIsNone(r['details']['difference_pp']);self.assertIsNone(r['rows'][0]['share_pct'])
    def test_sql_injection_is_literal_filter(self):
        r=self.r.run(self.plan('overview',filters={'title':"' OR 1=1 --"}));self.assertEqual(r['population_n'],0)
    def test_model_cannot_execute_code(self):
        for raw in ({'action':'delete'},{'sql':'DELETE FROM jobs'},{'python':'print(1)'},{'filters':{'path':'/tmp/a'}},{'concept':'unknown'},{'limit':True},{'limit':201},{'concept':[]},{'dataset':{}},{'filters':{'cutoff':'2026-02-30'}}):
            with self.subTest(raw=raw),self.assertRaises(ValueError):validate_plan(raw)
    def test_pairs_have_rule_labels_and_no_fake_gold(self):
        r=self.r.run(self.plan('pairs'));self.assertEqual(len(r['rows']),1);self.assertEqual(r['rows'][0]['change'],'added');self.assertIsNone(r['rows'][0]['human_gold'])
    def test_pairs_cutoff_avoids_future_version(self):
        r=self.r.run(self.plan('pairs',filters={'cutoff':'2025-12-31'}));self.assertEqual(r['rows'],[])
    def test_saved_cohort_and_exports_reproduce_plan(self):
        p=self.plan();self.r.save_cohort('test',p);r=self.r.run(p);self.assertEqual(self.r.result(r['id'])['rows'],r['rows']);self.assertEqual(len(self.store.get('research_cohorts')),1)
    def test_export_csv_blocks_formula_cells(self):
        data=export_csv({'rows':[{'title':'=HYPERLINK("bad")'}]}).decode('utf-8-sig');self.assertIn("'=HYPERLINK",data)
    def test_result_path_traversal(self):
        with self.assertRaises(ValueError):self.r.result('../../.env')
    def test_cancel_keeps_completed_index(self):
        event=threading.Event();event.set();self.assertEqual(self.r.build(cancel=event)['status'],'cancelled');self.assertTrue(self.r.status()['ready'])
    def test_source_change_marks_index_stale(self):
        with sqlite3.connect(str(self.source)) as c:c.execute("UPDATE records SET title='changed' WHERE job_id='1'")
        self.assertFalse(self.r.status()['ready'])
    def test_skill_percentages_count_ads_once(self):
        r=self.r.run(self.plan('skills'));python=next(x for x in r['rows'] if x['concept']=='python');self.assertEqual(python['mentions'],3);self.assertEqual(python['share_pct'],75)
    def test_current_excludes_synthetic_jobs(self):
        self.store.upsert_jobs([{'source':'test','title':'Demo','company':'A','description':'Python','is_demo':True},{'source':'test','title':'Real','company':'B','description':'Python Python','is_demo':False}]);r=self.r.run({'dataset':'current','action':'skills'});self.assertEqual(r['population_n'],1)
    def test_forecast_freezes_training_and_excludes_unmatured_august(self):
        from datetime import datetime
        with sqlite3.connect(str(self.r.root/'research.sqlite')) as c:
            c.execute('DELETE FROM ads')
            months=['2025-09','2025-10','2025-11','2025-12']+['2026-%02d'%m for m in range(1,11)]
            for i,m in enumerate(months):
                c.execute('INSERT INTO ads VALUES ('+','.join('?'*15)+')',(str(i),'Role','A','Engineering','HK','',m+'-01',m+'-10',m+'-10',str(i),0,1,str(i),str(i),1))
            # A late-discovered October advertisement cannot alter frozen October training.
            c.execute('INSERT INTO ads VALUES ('+','.join('?'*15)+')',('late','Role','A','Engineering','HK','','2025-10-01','2026-03-10','2026-03-10','late',1<<15,0,'late','late',1))
        meta=self.store.get('research_index');meta['snapshots']=[{'scrape_time':m+'-20','row_count':1} for m in months[:-1]]+[{'scrape_time':'2026-10-05T13:38:15','row_count':1}];self.store.set('research_index',meta)
        rows=self.r.run(self.plan('forecast',filters={'common_only':True}))['rows']
        self.assertEqual([r['month'] for r in rows],['2026-02','2026-03','2026-04','2026-05','2026-06'])
        self.assertEqual(rows[0]['last_mature_month'],'2025-11')
        self.assertTrue(all(r['mean3_pct']==0 for r in rows))
    def test_forecast_no_mature_training_returns_no_claim(self):
        r=self.r.run(self.plan('forecast',filters={'cutoff':'2025-03-31'}));self.assertEqual(r['rows'],[])


class ResearchAITests(unittest.TestCase):
    def test_plan_response_is_validated(self):
        with patch('jobcompass.research_ai._call',return_value=({'plan':{'action':'skills','dataset':'research'},'explanation':'ok'},{'total_tokens':12})):
            r=plan_command('分析技能');self.assertEqual(r['plan']['action'],'skills');self.assertEqual(r['usage']['total_tokens'],12)
    def test_injected_sql_response_rejected(self):
        with patch('jobcompass.research_ai._call',return_value=({'plan':{'sql':'DROP TABLE jobs'}},{})),self.assertRaises(ValueError):plan_command('删除数据')
    def test_unsupported_question_not_silently_replaced(self):
        with patch('jobcompass.research_ai._call',return_value=({'unsupported':'没有录用因果数据'},{})),self.assertRaisesRegex(ValueError,'没有录用'):plan_command('预测录用因果')
    def test_no_raw_text_sent_for_explanation(self):
        result={'plan':{'action':'skills','concept':'python'},'population_n':2,'rows':[{'concept':'python','mentions':1,'evidence':'SECRET','company':'PRIVATE'}],'warnings':[]}
        with patch('jobcompass.research_ai._call',return_value=({'summary':'ok','limitations':[],'next_steps':[]},{})) as call:
            explain_result(result);self.assertNotIn('SECRET',str(call.call_args));self.assertNotIn('PRIVATE',str(call.call_args))
    def test_evidence_not_sent(self):
        with patch('jobcompass.research_ai._call') as call,self.assertRaises(ValueError):explain_result({'plan':{'action':'pairs'}})
        call.assert_not_called()
