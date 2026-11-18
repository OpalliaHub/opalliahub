"""Local HTTP application with bounded background work and JSON API."""
import base64
import csv
import hashlib
import io
import json
import mimetypes
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from . import __version__
from .learning import build_learning_plan
from .ranking_cache import RankedJobsCache
from .recommendations import build_recommendations, validate_options
from .research_agent import run_agent
from .olap import OLAP
from .analytics_ai import compile_and_run
from .ai import call_ai
from .config import ROOT, MODEL
from .resume import parse_resume, extract_file
from .sources import collect_api, collect_page, import_jobs, normalize
from .storage import Store
from .research import Research, validate_plan, export_csv as research_csv
from .research_ai import plan_command, explain_result
from .benchmark import import_snapshot
from .jobsdb import collect as collect_jobsdb, options as jobsdb_options, expiry_status


def recommendation_snapshot_token(resume, preferences, jobs):
    """Compare recommendation inputs without making application notes a signal."""
    corpus = [{key: value for key, value in job.items() if key not in ('status', 'note')}
              for job in jobs]
    corpus.sort(key=lambda job: str(job.get('id', '')))
    raw = json.dumps([resume, preferences, corpus], sort_keys=True,
                     ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class Tasks:
    def __init__(self, pool=None):
        self.pool = pool if pool is not None else ThreadPoolExecutor(max_workers=3)
        self.lock = threading.Lock()
        self.items = {}
        self.cancellations = {}

    def submit(self, label, fn, controlled=False, on_done=None):
        with self.lock:
            if any(x['label'] == label and x['status'] in ('queued', 'running') for x in self.items.values()):
                raise ValueError('同类任务正在处理中，请等待完成。')
            if sum(x['status'] in ('queued', 'running') for x in self.items.values()) >= 3:
                raise ValueError('已有 3 个任务正在处理，请稍后再试。')
            if len(self.items) >= 100:
                for old in list(self.items):
                    if self.items[old]['status'] in ('done', 'error', 'cancelled'):
                        del self.items[old]
                        self.cancellations.pop(old, None)
                        break
            tid = secrets.token_hex(10)
            self.items[tid] = {'id': tid, 'label': label, 'status': 'queued', 'created_at': time.time()}
            event = threading.Event()
            if controlled:
                self.cancellations[tid] = event

        def progress(**values):
            with self.lock:
                self.items[tid]['progress'] = values

        def work():
            with self.lock:
                self.items[tid]['status'] = 'running'
            try:
                result = fn(progress, event) if controlled else fn()
                update = {'status': 'cancelled' if isinstance(result, dict) and result.get('status') == 'cancelled' else 'done', 'result': result}
            except ValueError as exc:
                update = {'status': 'error', 'error': str(exc)}
            except Exception:
                update = {'status': 'error', 'error': '处理失败，请检查文件或网络后重试。'}
            finally:
                if on_done:
                    on_done()
            with self.lock:
                self.items[tid].update(update)
        try:
            self.pool.submit(work)
        except Exception:
            with self.lock:
                self.items.pop(tid, None)
                self.cancellations.pop(tid, None)
            if on_done:
                on_done()
            raise
        return {'task_id': tid}

    def cancel(self, tid):
        with self.lock:
            if tid not in self.cancellations:
                raise ValueError('此任务不能取消或已不存在。')
            self.cancellations[tid].set()
        return {'message': '正在停止；当前请求或计算步骤结束后停止，已完成的结果会保留。'}

    def get(self, tid):
        with self.lock:
            item = self.items.get(tid)
            if item is None:
                raise ValueError('任务不存在或服务已重启。')
            return dict(item)

    def active(self):
        with self.lock:
            return [dict(x) for x in self.items.values() if x['status'] in ('queued', 'running')]


class Application:
    def __init__(self, db_path, demo=False, store=None, pool=None, index_root=None, result_root=None):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.store = Store(db_path) if store is None else store
        try:
            db_path.chmod(0o600)
        except OSError:
            pass
        self.tasks = Tasks(pool)
        self.ranking_cache = RankedJobsCache()
        self.research = Research(self.store, index_root=index_root, result_root=result_root)
        self.analytics = OLAP(self.research)
        self.deployment = {'public_mode': False, 'label': '本地研究工作台'}
        if store is None and not self.store.get('initialized'):
            if demo:
                self.store.upsert_jobs(json.loads((ROOT / 'data' / 'demo_jobs.json').read_text(encoding='utf-8')))
            else:
                import_snapshot(self.store)
            self.store.set('initialized', True)

    def state(self):
        jobs = self.store.jobs()
        for job in jobs:
            job['source_family'] = 'JobsDB' if job['source'].startswith('JobsDB') else job['source']
            job['availability'] = expiry_status(job)
        resume = self.store.get('resume', '')
        profile = self.store.get('profile', {})
        preferences = self.store.get('preferences', {})
        if resume:
            jobs = self.ranking_cache.rank(resume, profile, jobs, preferences)
        return {'version': __version__, 'deployment': self.deployment, 'jobs': jobs, 'resume': resume, 'profile': profile,
                'active_tasks': self.tasks.active(), 'history': self.store.history_status(),
                'preferences': preferences, 'logs': self.store.logs(),
                'jobsdb': {'last_run': self.store.get('jobsdb_last_run'),
                           'primary': True, 'default_limit': 50},
                'ai': {'configured': bool(os.environ.get('DEEPSEEK_API_KEY')), 'model': MODEL},
                'ai_analysis': self.store.get('ai_analysis'), 'polished': self.store.get('polished')}

    def post(self, path, body, permit=None):
        def submit(label, fn, controlled=False):
            return self.tasks.submit(label, fn, controlled=controlled,
                                     on_done=permit.release if permit else None)

        if path == '/api/recommendations':
            options = validate_options(body)
            resume = self.store.get('resume', '')
            if not resume:
                raise ValueError('请先保存简历，再提炼优势并推荐岗位。')
            preferences = self.store.get('preferences', {})
            jobs = self.store.jobs()
            token = recommendation_snapshot_token(resume, preferences, jobs)

            def recommend():
                result = build_recommendations(resume, jobs, preferences, options)
                current = recommendation_snapshot_token(self.store.get('resume', ''),
                    self.store.get('preferences', {}), self.store.jobs())
                if token != current:
                    raise ValueError('简历、求职偏好或岗位数据已更新，请重新生成推荐。')
                result['source_token'] = token
                result['message'] = '优势与岗位推荐已生成，请结合原始岗位核实。'
                return result

            return submit('优势与岗位推荐', recommend)
        if path == '/api/analytics/query':
            return self.analytics.run(body.get('query', body))
        if path == '/api/analytics/command':
            return submit('自然语言数据分析', lambda: compile_and_run(
                body.get('command'), body.get('dataset', 'research'), self.analytics, body.get('context')))
        if path == '/api/research/agent':
            command, dataset, steps = body.get('command'), body.get('dataset', 'research'), body.get('max_steps', 3)
            if body.get('consent') is not True:
                raise ValueError('请先同意将指令与聚合统计发送给 DeepSeek。')
            if not isinstance(command, str) or not 1 <= len(command.strip()) <= 1000:
                raise ValueError('研究指令需为 1–1000 个字符。')
            if dataset not in ('research', 'current') or type(steps) is not int or not 1 <= steps <= 4:
                raise ValueError('数据集无效或轮数不在 1–4 之间。')
            return submit('多步职业研究',
                lambda progress,event: run_agent(command, dataset, self.research.run,
                                                max_steps=steps, progress=progress, cancel=event), controlled=True)
        if path == '/api/learning':
            jobs = self.store.jobs()
            for job in jobs:
                job['availability'] = expiry_status(job)
            return build_learning_plan(jobs, self.store.get('profile', {}),
                                       target=body.get('target', ''), limit=body.get('limit', 10))
        if path == '/api/application/history':
            return self.store.application_history(body.get('action'))
        if path == '/api/research/connect':
            return self.research.connect(body.get('path'))
        if path == '/api/research/build':
            return submit('构建研究索引', lambda progress,event:self.research.build(progress,event), controlled=True)
        if path == '/api/research/run':
            plan=validate_plan(body.get('plan'))
            return submit('职业研究分析',lambda:self.research.run(plan))
        if path == '/api/research/plan':
            command=body.get('command');dataset=body.get('dataset','research')
            return submit('DeepSeek 分析计划',lambda:plan_command(command,dataset))
        if path == '/api/research/explain':
            result=self.research.result(body.get('id'))
            return submit('DeepSeek 统计解读',lambda:explain_result(result))
        if path == '/api/research/cohort':
            return self.research.save_cohort(body.get('name'),body.get('plan'))
        if path == '/api/resume':
            text = body.get('text', '')
            if not isinstance(text, str):
                raise ValueError('简历文本格式不正确。')
            profile = parse_resume(text)
            self.store.set('resume', text.strip())
            self.store.set('profile', profile)
            self.store.set('ai_analysis', None)
            self.store.set('polished', None)
            return profile
        if path == '/api/resume/file':
            try:
                data = base64.b64decode(body.get('data', ''), validate=True)
            except (ValueError, TypeError):
                raise ValueError('文件编码无效。')
            text = extract_file(str(body.get('filename', '')), data)
            parse_resume(text)
            return {'text': text}
        if path == '/api/resume/clear':
            self.store.clear_resume()
            self.ranking_cache.clear()
            return {'message': '已清除当前简历和 AI 结果。'}
        if path == '/api/preferences':
            location = str(body.get('location', '')).strip()[:200]
            years = body.get('experience_years')
            if years not in (None, ''):
                try:
                    years = float(years)
                except (ValueError, TypeError):
                    raise ValueError('经验年限必须是数字。')
                if not 0 <= years <= 50:
                    raise ValueError('经验年限必须在 0 至 50 之间。')
            else:
                years = None
            self.store.set('preferences', {'location': location, 'experience_years': years})
            return {'message': '求职偏好已更新。'}
        if path == '/api/collect':
            source = str(body.get('source', ''))
            return submit('采集 ' + source, lambda: collect_api(source, self.store))
        if path == '/api/jobsdb/update':
            settings = jobsdb_options(body)
            return submit('更新 JobsDB 岗位',
                lambda progress, event: collect_jobsdb(self.store, progress=progress, cancel=event, **settings), controlled=True)
        if path == '/api/tasks/cancel':
            return self.tasks.cancel(str(body.get('task_id', '')))
        if path == '/api/benchmark/import':
            return submit('导入 JobsDB 研究快照', lambda: import_snapshot(self.store))
        if path == '/api/collect/page':
            url = str(body.get('url', ''))
            return submit('网页采集', lambda: collect_page(url, self.store))
        if path == '/api/import':
            jobs = import_jobs(str(body.get('filename', '')), str(body.get('content', '')))
            count = self.store.upsert_jobs(jobs)
            self.store.log('手动导入', 'success', count, '文件字段校验通过')
            return {'count': count}
        if path == '/api/job':
            job = normalize(body)
            self.store.upsert_jobs([job])
            return {'message': '岗位已加入岗位库。'}
        if path == '/api/application':
            self.store.application(str(body.get('id', '')), str(body.get('status', '')), str(body.get('note', '')))
            return {'message': '投递记录已保存。'}
        if path == '/api/ai':
            task = body.get('task')
            if task not in ('analyze', 'polish', 'explain'):
                raise ValueError('未知的 AI 操作。')
            resume = self.store.get('resume', '')
            if not resume:
                raise ValueError('请先保存一份简历。')
            if body.get('consent') is not True:
                raise ValueError('请先勾选同意将简历发送至 DeepSeek。')
            job = next((j for j in self.store.jobs() if j['id'] == body.get('job_id')), None)
            if task == 'explain' and job is None:
                raise ValueError('请先选择岗位。')

            def run_ai():
                result = call_ai(task, resume, job)
                if self.store.get('resume') == resume and task in ('analyze', 'polish'):
                    self.store.set('ai_analysis' if task == 'analyze' else 'polished', result)
                return result
            return submit('AI ' + task, run_ai)
        raise ValueError('接口不存在。')


def csv_export(jobs):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['岗位', '公司', '地区', '薪资原文', '来源', '匹配分', '投递状态', '链接', '示例数据'])
    for j in jobs:
        values = [j['title'], j['company'], j['location'], j['salary'], j['source'], j.get('score', ''), j.get('status', ''), j['url'], bool(j['is_demo'])]
        writer.writerow(["'" + str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
    return ('\ufeff' + output.getvalue()).encode('utf-8')


def make_server(app, port=8765, host='127.0.0.1', public_config=None):
    from .web import WebGateway, MAX_BODY, response
    gateway = WebGateway(app, port, public_config)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def dispatch(self):
            self.connection.settimeout(20)
            body = b''
            try:
                if self.command == 'POST':
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= MAX_BODY:
                        raise ValueError('请求不能为空，且不能超过 7 MB。')
                    body = self.rfile.read(size)
                result = gateway.handle(self.command, self.path, dict(self.headers), body, self.client_address[0])
            except (ValueError, TimeoutError):
                result = response({'error':'请求大小无效或读取超时。'}, 400)
            status, headers, data = result
            self.send_response(status)
            for key, value in headers:
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        do_GET = dispatch
        do_POST = dispatch

    class Server(ThreadingHTTPServer):
        def server_close(self):
            super().server_close()
            gateway.close()

    server = Server((host, port), Handler)
    gateway.port = server.server_port
    server.gateway = gateway
    return server
