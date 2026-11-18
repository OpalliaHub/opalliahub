"""Local, reproducible research workbench. Source databases are always read-only.

The compact index contains FIRST observed versions, never silently latest text.
Plans are a closed data language; no model-provided SQL, Python or paths execute.
"""
import csv
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from .benchmark import clean_text
from .storage import now

PROBE_FILE = Path(__file__).with_name('research_probes.json')
PROBES = json.loads(PROBE_FILE.read_text(encoding='utf-8'))['patterns']
PATTERNS = {k: re.compile(v, re.I) for k, v in PROBES.items()}
BITS = {name: 1 << i for i, name in enumerate(PROBES)}
COMMON = ['Information & Communication Technology', 'Engineering', 'Education & Training']
ACTIONS = ['overview', 'skills', 'trend', 'compare', 'sample', 'pairs', 'forecast', 'dataset']
WARNINGS = [
    '全文提及不等于真实要求、强制要求或新兴技能；本词典为 2026-10-06 回顾性探针。',
    'JobsDB 便利样本不代表香港整体劳动力市场，广告 ID 不等于招聘人数。',
    '前期约 30 类、后期主要 3 类；2025 年 5–8 月有长断档，空缺不按零需求处理。',
    '日期是首次观察版本的来源标示日期；抓取时间来自文件名，时区未核实。',
    '雇主正文族是显示名与全文哈希的严格去重敏感性口径，不证明是同一空缺。',
]


def readonly(path):
    c = sqlite3.connect('file:' + quote(str(Path(path).resolve()), safe='/') + '?mode=ro', uri=True, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    c.execute('PRAGMA trusted_schema=OFF')
    return c


def date_value(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        return None


def mask_for(text):
    return sum(BITS[k] for k, p in PATTERNS.items() if p.search(text))


def canonical(text):
    return ' '.join(unicodedata.normalize('NFKC', text or '').casefold().split())


def validate_plan(raw):
    if not isinstance(raw, dict):
        raise ValueError('分析计划必须是 JSON 对象。')
    allowed = {'dataset', 'action', 'concept', 'filters', 'dedup', 'limit', 'period_a', 'period_b'}
    if set(raw) - allowed:
        raise ValueError('分析计划包含不支持的操作字段。')
    p = {'dataset': 'research', 'action': 'overview', 'concept': 'python', 'dedup': 'id', 'limit': 30, 'filters': {}}
    p.update(raw)
    if any(not isinstance(p[k],str) for k in ('dataset','action','concept','dedup')):
        raise ValueError('数据集、操作、探针与去重方式必须为文本。')
    if p['dataset'] not in ('research', 'current') or p['action'] not in ACTIONS or p['concept'] not in PROBES or p['dedup'] not in ('id', 'family'):
        raise ValueError('数据集、操作、探针或去重方式无效。')
    if type(p['limit']) is not int or not 1 <= p['limit'] <= 200:
        raise ValueError('返回行数需在 1–200 之间。')
    f = p['filters']
    if not isinstance(f, dict) or set(f) - {'title', 'company', 'location', 'sector', 'start', 'end', 'cutoff', 'common_only', 'fresh_only'}:
        raise ValueError('筛选字段不受支持。')
    for k, v in f.items():
        if k in ('common_only', 'fresh_only'):
            if type(v) is not bool:
                raise ValueError('筛选开关必须是布尔值。')
        elif not isinstance(v, str) or len(v) > 150:
            raise ValueError('筛选值须为不超过 150 字符的文本。')
        elif k in ('start', 'end', 'cutoff') and v:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v) or not date_value(v):
                raise ValueError('日期格式为 YYYY-MM-DD。')
    if f.get('start') and f.get('end') and f['start'] > f['end']:
        raise ValueError('开始日期不能晚于结束日期。')
    for key in ('period_a', 'period_b'):
        if key in p:
            span = p[key]
            if not isinstance(span, list) or len(span) != 2 or any(not isinstance(x,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',x) or not date_value(x) for x in span) or span[0] > span[1]:
                raise ValueError('比较窗口必须包含两个有效且有序的日期。')
    if p['action'] == 'compare' and all(k in p for k in ('period_a','period_b')) and max(p['period_a'][0],p['period_b'][0]) <= min(p['period_a'][1],p['period_b'][1]):
        raise ValueError('两期比较窗口不能重叠。')
    if p['action'] == 'compare' and not all(k in p for k in ('period_a', 'period_b')):
        raise ValueError('两期比较需要 period_a 和 period_b。')
    if p['action'] in ('pairs','forecast') and p['dataset'] != 'research':
        raise ValueError('修订与历史回测需要连接纵向研究数据库。')
    if p['action'] == 'pairs' and p['dedup'] != 'id':
        raise ValueError('同广告修订对比使用唯一 ID 口径。')
    return json.loads(json.dumps(p))


class Research:
    def __init__(self, store, index_root=None, result_root=None):
        self.store = store
        self.root = Path(index_root) if index_root else Path(store.path).parent / 'private' / 'analytics'
        self.root.mkdir(parents=True, exist_ok=True)
        self.result_root = Path(result_root) if result_root else self.root
        self.result_root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.default_source = Path(os.environ.get('JOBCOMPASS_RESEARCH_DB', str(Path(__file__).resolve().parents[2] / 'jobdb_plus/research/data_audit/jobsdb.sqlite')))

    def source(self):
        return Path(self.store.get('research_source', str(self.default_source))).expanduser()

    def connect(self, path):
        if not isinstance(path, str) or not path.strip():
            raise ValueError('请输入研究 SQLite 文件路径。')
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise ValueError('研究数据库文件不存在。')
        try:
            with readonly(p) as c:
                for table, cols in {'jobs': {'job_id','first_record_hash','latest_record_hash','first_scrape','last_scrape'}, 'records': {'record_hash','content_text','text_hash','post_time','classifications'}, 'snapshots': {'snapshot_id','scrape_time','is_consolidated'}, 'observations': {'job_id','record_hash'}, 'record_quality': {'record_hash','valid_job_id','valid_post_time','has_content'}}.items():
                    if not cols.issubset({r['name'] for r in c.execute('PRAGMA table_info('+table+')')}):
                        raise ValueError('数据库不符合 JobsDB 研究索引结构：'+table)
        except sqlite3.Error:
            raise ValueError('不能读取研究数据库。')
        self.store.set('research_source', str(p))
        return {'message': '已只读连接研究数据库；请构建分析索引。'}

    def fingerprint(self):
        p = self.source()
        if not p.is_file():
            return ''
        s = p.stat()
        return hashlib.sha256((str(p.resolve())+str(s.st_size)+str(s.st_mtime_ns)+PROBE_FILE.read_text()).encode()).hexdigest()

    def status(self):
        meta = self.store.get('research_index', {})
        return {'connected': self.source().is_file(), 'path': str(self.source()),
                'ready': bool(meta and meta.get('fingerprint') == self.fingerprint() and (self.root/'research.sqlite').exists()),
                'index': meta, 'concepts': list(PROBES), 'sectors': COMMON, 'actions': ACTIONS,
                'runs': self.store.get('research_runs', [])[:20], 'cohorts': self.store.get('research_cohorts', []),
                'ai_configured': bool(os.environ.get('DEEPSEEK_API_KEY'))}

    def build(self, progress=None, cancel=None):
        with self.lock:
            self.connect(str(self.source()))
            fingerprint = self.fingerprint()
            temp = self.root/'building.sqlite'
            temp.unlink(missing_ok=True)
            try:
                with readonly(self.source()) as source, sqlite3.connect(str(temp)) as out:
                    out.execute('CREATE TABLE ads(id TEXT PRIMARY KEY,title TEXT,company TEXT,sector TEXT,location TEXT,salary TEXT,published TEXT,observed TEXT,last_observed TEXT,family TEXT,mask INTEGER,fresh INTEGER,record_hash TEXT,latest_hash TEXT,n_snapshots INTEGER)')
                    total = source.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
                    n = 0
                    rows = source.execute('''SELECT j.*,r.* FROM jobs j JOIN records r ON r.record_hash=j.first_record_hash
                      JOIN record_quality q ON q.record_hash=r.record_hash
                      WHERE q.valid_job_id=1 AND q.valid_post_time=1 AND q.has_content=1
                      AND j.n_snapshots>0 AND length(r.content_text)>=100 ORDER BY j.first_scrape,j.job_id''')
                    batch=[]
                    for r in rows:
                        if cancel and cancel.is_set():
                            return {'status':'cancelled','message':'已停止构建，原分析索引保留。'}
                        pub, obs = date_value(r['post_time']), date_value(r['first_scrape'])
                        sector = re.search(r'\(([^()]*)\)\s*$',r['classifications'] or '')
                        fresh = bool(pub and obs and -1 <= (obs-pub).total_seconds()/86400 <= 35)
                        batch.append((r['job_id'],clean_text(r['title']),clean_text(r['advertiser']),sector.group(1) if sector else 'Unknown',clean_text(r['location']),clean_text(r['salary']),r['post_time'][:10],r['first_scrape'][:10],r['last_scrape'][:10],canonical(r['advertiser'])+'|'+r['text_hash'],mask_for(r['content_text']),int(fresh),r['record_hash'],r['latest_record_hash'],r['n_snapshots']))
                        n += 1
                        if len(batch)>=1000:
                            out.executemany('INSERT INTO ads VALUES ('+','.join('?'*15)+')',batch);batch=[]
                            if progress: progress(phase='提取首版正文与 36 类词语探针',completed=n,total=total,saved=n)
                    out.executemany('INSERT INTO ads VALUES ('+','.join('?'*15)+')',batch)
                    out.executescript('CREATE INDEX ads_date ON ads(published); CREATE INDEX ads_obs ON ads(observed); CREATE INDEX ads_family ON ads(family); CREATE INDEX ads_sector ON ads(sector);')
                    snapshots = [dict(r) for r in source.execute('SELECT snapshot_id,scrape_time,row_count FROM snapshots WHERE is_consolidated=0 ORDER BY scrape_time')]
                    observations = source.execute('''SELECT COUNT(*) FROM observations o JOIN snapshots s USING(snapshot_id) JOIN record_quality q USING(record_hash) WHERE s.is_consolidated=0 AND q.valid_job_id=1 AND q.valid_post_time=1 AND q.has_content=1''').fetchone()[0]
                if fingerprint != self.fingerprint():
                    raise ValueError('源数据库在构建期间发生变化，请重新构建。')
                os.replace(str(temp),str(self.root/'research.sqlite'))
                (self.root/'research.sqlite').chmod(0o600)
                meta={'fingerprint':fingerprint,'rows':n,'observations':observations,'snapshots':snapshots,'built_at':now(),'probe_sha256':hashlib.sha256(PROBE_FILE.read_bytes()).hexdigest()}
                self.store.set('research_index',meta)
                return {'message':'研究索引完成：{:,} 个首版广告，36 类探针。'.format(n),'index':meta}
            finally:
                temp.unlink(missing_ok=True)

    def _current(self, include_mask=True):
        """Snapshot current ads; catalog-only callers may skip vocabulary scans."""
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE ads(id,title,company,sector,location,salary,published,observed,last_observed,family,mask,fresh,record_hash,latest_hash,n_snapshots)')
        for j in self.store.jobs():
            if j.get('is_demo'):continue
            text=j['description'];pub=(j.get('published_at') or '')[:10];obs=(j.get('last_live_checked') or j['collected_at'])[:10]
            c.execute('INSERT INTO ads VALUES ('+','.join('?'*15)+')',(j['id'],j['title'],j['company'],'Unknown',j['location'],j['salary'],pub,obs,obs,canonical(j['company'])+'|'+hashlib.sha256(canonical(text).encode()).hexdigest(),mask_for(text) if include_mask else 0,0,j['id'],j['id'],1))
        return c

    def _selection(self,p):
        clauses=['1=1'];args=[];f=p['filters']
        for k in ('title','company','location','sector'):
            if f.get(k):
                clauses.append('instr(lower('+k+'),lower(?))>0');args.append(f[k])
        for key,col,op in [('start','published','>='),('end','published','<='),('cutoff','observed','<=')]:
            if f.get(key):clauses.append(col+op+'?');args.append(f[key])
        if f.get('common_only'):clauses.append('sector IN (?,?,?)');args.extend(COMMON)
        if f.get('fresh_only'):clauses.append('fresh=1')
        # Family sensitivity retains first globally observed employer+body, before filters.
        if p['dedup']=='family':
            clauses.append('id=(SELECT b.id FROM ads b WHERE b.family=ads.family ORDER BY b.observed,b.published,b.id LIMIT 1)')
        return 'SELECT * FROM ads WHERE '+' AND '.join(clauses),args

    def run(self,raw):
        p=validate_plan(raw);start=time.monotonic()
        with self.lock:
            if p['dataset']=='research':
                if not self.status()['ready']:raise ValueError('请先连接研究数据库并构建分析索引。')
                c=readonly(self.root/'research.sqlite');fingerprint=self.fingerprint()
            else:
                c=self._current();fingerprint=hashlib.sha256(json.dumps(self.store.jobs(),sort_keys=True).encode()).hexdigest()
            try:
                sql,args=self._selection(p)
                # SELECT-only parameterized queries over the bounded validated plan.
                def query(tail,extra=()):
                    return [dict(r) for r in c.execute('WITH selected AS ('+sql+') '+tail,tuple(args)+tuple(extra))]
                n=query('SELECT COUNT(*) n FROM selected')[0]['n'];bit=BITS[p['concept']]
                rows=[];a=p['action'];extra={}
                if a=='overview':
                    rows=query('SELECT sector AS label,COUNT(*) n,COUNT(DISTINCT company) advertisers FROM selected GROUP BY sector ORDER BY n DESC LIMIT 40')
                    extra['locations']=query('SELECT location AS label,COUNT(*) n FROM selected GROUP BY location ORDER BY n DESC LIMIT 12')
                    extra['titles']=query('SELECT title AS label,COUNT(*) n FROM selected GROUP BY title ORDER BY n DESC LIMIT 12')
                    extra['quality']=query("SELECT COUNT(DISTINCT family) families,SUM(CASE WHEN salary='' THEN 1 ELSE 0 END) missing_salary,MIN(published) first_date,MAX(published) last_date FROM selected")[0]
                    extra['snapshots']=self.store.get('research_index',{}).get('snapshots',[]) if p['dataset']=='research' else []
                elif a=='dataset':
                    rows=query('SELECT id,title,company,sector,location,salary,published,observed,n_snapshots FROM selected ORDER BY observed,id LIMIT ?', (p['limit'],))
                    extra['method']='筛选、去重后的数据预览与导出，最多 200 行。完整队列定义保存在分析计划中；不会删改原始记录。'
                elif a=='skills':
                    sums=query('SELECT '+','.join('COALESCE(SUM((mask & {})!=0),0) AS c{}'.format(b,i) for i,b in enumerate(BITS.values()))+' FROM selected')[0]
                    rows=[{'concept':k,'mentions':sums['c'+str(i)],'n':n,'share_pct':round(100*sums['c'+str(i)]/n,3) if n else None} for i,k in enumerate(BITS)]
                    rows.sort(key=lambda r:-r['mentions'])
                elif a in ('trend','forecast'):
                    rows=query('SELECT substr(published,1,7) month,COUNT(*) n,SUM((mask & ?)!=0) mentions,COUNT(DISTINCT CASE WHEN (mask & ?)!=0 AND lower(company) NOT IN (\'\',\'confidential\',\'company confidential\') THEN company END) advertisers FROM selected WHERE published!=\'\' GROUP BY month ORDER BY month',(bit,bit))
                    for r in rows:r['share_pct']=round(100*r['mentions']/r['n'],3)
                    if a=='forecast':
                        rows=self._forecast(c,p)
                        extra['method']='报告协议的单探针回顾性诊断：2025-09 起训练，2026-01 至 08 为候选起点，排除 7 月缺口；至少三个成熟训练月。各月以次月初加 35 天冻结，按上一完整日截断。六月随访跨七月缺口，结果需做剔除六月的敏感性。'
                elif a=='compare':
                    for label,key in [('A','period_a'),('B','period_b')]:
                        lo,hi=p[key]
                        r=query('SELECT COUNT(*) n,COALESCE(SUM((mask & ?)!=0),0) mentions FROM selected WHERE published BETWEEN ? AND ?',(bit,lo,hi))[0]
                        r.update(period=label,start=lo,end=hi,share_pct=round(100*r['mentions']/r['n'],4) if r['n'] else None);rows.append(r)
                    extra['difference_pp']=round(rows[1]['share_pct']-rows[0]['share_pct'],4) if all(r['n'] for r in rows) else None
                    extra['method']='样本内两期全文提及率的百分点差；没有推断总体变化或统计显著性。'
                elif a in ('sample','pairs'):
                    tail='SELECT * FROM selected WHERE (mask & ?)!=0 ORDER BY observed,id LIMIT ?'
                    candidates=query(tail,(bit,p['limit'])) if a=='sample' else query('SELECT * FROM selected WHERE record_hash!=latest_hash ORDER BY observed,id')
                    if p['dataset']=='research':
                        with readonly(self.source()) as src:
                            for r in candidates:
                                before=src.execute('SELECT content_text FROM records WHERE record_hash=?',(r['record_hash'],)).fetchone()[0]
                                if a=='sample':
                                    hit=PATTERNS[p['concept']].search(before)
                                    excerpt=before[max(0,hit.start()-120):hit.end()+180] if hit else before[:300]
                                    rows.append({'job_id':r['id'],'title':r['title'],'observed':r['observed'],'published':r['published'],'record_hash':r['record_hash'],'match_start':hit.start() if hit else None,'match_end':hit.end() if hit else None,'evidence':clean_text(excerpt),'label_source':'rule_derived','human_gold':None})
                                else:
                                    cutoff=p['filters'].get('cutoff')
                                    if cutoff and r['last_observed']>cutoff:continue
                                    after=src.execute('SELECT content_text FROM records WHERE record_hash=?',(r['latest_hash'],)).fetchone()[0]
                                    bm,am=PATTERNS[p['concept']].search(before),PATTERNS[p['concept']].search(after)
                                    if bool(bm)==bool(am):continue
                                    rows.append({'job_id':r['id'],'title':r['title'],'first_observed':r['observed'],'last_observed':r['last_observed'],'first_record_hash':r['record_hash'],'last_record_hash':r['latest_hash'],'change':'added' if am else 'removed','before':clean_text(before[max(0,bm.start()-100):bm.end()+160] if bm else before[:260]),'after':clean_text(after[max(0,am.start()-100):am.end()+160] if am else after[:260]),'label_source':'rule_derived','human_gold':None})
                                    if len(rows)>=p['limit']:break
                        extra['method']='修订展示首末观察版本中探针新增/删除；非要求强化。截止日模式仅含首末均已观察到的广告，非截止日前最后版本重建。' if a=='pairs' else '按观察日期和 ID 排序的确定性证据样例，不是随机金标准样本。'
                    else:
                        jobs={j['id']:j for j in self.store.jobs()}
                        rows=[{'job_id':r['id'],'title':r['title'],'evidence':clean_text(jobs[r['id']]['description'][:500]),'label_source':'rule_derived','human_gold':None} for r in candidates]
                warnings=list(WARNINGS)
                if p['dataset']=='current':warnings.append('当前岗位库为可变最新状态，不能作为纵向首版历史；没有研究分类和近期队列标记。')
                if p['filters'].get('common_only') is not True:warnings.append('未限定共同三类，跨期差异可能受类别覆盖变化影响。')
                result={'id':secrets.token_hex(12),'created_at':now(),'plan':p,'population_n':n,'rows':rows,'details':extra,'warnings':warnings,'dataset_fingerprint':fingerprint,'elapsed_seconds':round(time.monotonic()-start,3),'label_source':'rule_derived'}
                self._save_run(result)
                return result
            finally:c.close()

    def _forecast(self,c,p):
        """Frozen report protocol: Sep-2025 training, Jan-Aug-2026 origins.

        Each month freezes observations at next-month start + 35 days. No
        future observation may backfill an earlier training vintage.
        """
        dates=[date_value(s['scrape_time']) for s in self.store.get('research_index',{}).get('snapshots',[])]
        dates=[d for d in dates if d]
        if not dates:return []
        asof=min(max(dates),date_value(p['filters'].get('cutoff')) or max(dates))
        def maturity(month):
            dt=datetime.strptime(month+'-01','%Y-%m-%d')
            return (dt.replace(day=28)+timedelta(days=4)).replace(day=1)+timedelta(days=35)
        observed_months=sorted({d.strftime('%Y-%m') for d in dates})
        rates={}
        for month in observed_months:
            if month<'2025-09' or month>'2026-08' or month=='2026-07' or maturity(month)>asof:continue
            q=json.loads(json.dumps(p))
            # Conservative day-level cutoff: previous full calendar day.
            q['filters']['cutoff']=(maturity(month)-timedelta(days=1)).strftime('%Y-%m-%d')
            qsql,args=self._selection(q)
            r=dict(c.execute('WITH selected AS ('+qsql+') SELECT COUNT(*) n,100.0*SUM((mask & ?)!=0)/COUNT(*) rate FROM selected WHERE substr(published,1,7)=?',tuple(args)+(BITS[p['concept']],month)).fetchone())
            if r['n']:rates[month]=r
        output=[]
        for month,target in sorted(rates.items()):
            if not '2026-01'<=month<='2026-08':continue
            origin=datetime.strptime(month+'-01','%Y-%m-%d')
            train=[(m,r) for m,r in sorted(rates.items()) if maturity(m)<=origin]
            if len(train)<3:continue
            last_month,last_row=train[-1];last=last_row['rate'];mean=sum(r['rate'] for _,r in train[-3:])/3
            output.append({'month':month,'n':target['n'],'actual_pct':round(target['rate'],4),'last_mature_month':last_month,'last_pct':round(last,4),'mean3_pct':round(mean,4),'last_abs_error_pp':round(abs(last-target['rate']),4),'mean3_abs_error_pp':round(abs(mean-target['rate']),4)})
        return output

    def _save_run(self,result):
        dest=self.result_root/(result['id']+'.json')
        dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');dest.chmod(0o600)
        runs=self.store.get('research_runs',[])
        runs.insert(0,{k:result[k] for k in ('id','created_at','plan','population_n','elapsed_seconds')})
        self.store.set('research_runs',runs[:100])

    def result(self,rid):
        if not isinstance(rid,str) or not re.fullmatch(r'[a-f0-9]{24}',rid):raise ValueError('分析记录 ID 无效。')
        try:return json.loads((self.result_root/(rid+'.json')).read_text(encoding='utf-8'))
        except FileNotFoundError:raise ValueError('分析记录不存在。')

    def save_cohort(self,name,plan):
        if not isinstance(name,str) or not 1<=len(name.strip())<=60:raise ValueError('队列名称需要 1–60 个字符。')
        p=validate_plan(plan)
        with self.lock:
            items=self.store.get('research_cohorts',[])
            items=[x for x in items if x['name']!=name.strip()]
            items.insert(0,{'name':name.strip(),'plan':p,'saved_at':now()})
            self.store.set('research_cohorts',items[:30])
        return {'message':'已保存筛选队列，原始数据未改写。'}


def export_csv(result):
    out=io.StringIO();rows=result['rows']
    if not rows:return b'\xef\xbb\xbf'
    writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader()
    for row in rows:
        writer.writerow({k:("'"+str(v) if str(v).lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return ('\ufeff'+out.getvalue()).encode('utf-8')
