"""Local HTTP application with bounded background work and JSON API."""
import base64
import csv
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
from .ai import call_ai
from .config import ROOT, MODEL
from .matching import rank_jobs
from .resume import parse_resume, extract_file
from .sources import collect_api, collect_page, import_jobs, normalize
from .storage import Store


class Tasks:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.lock = threading.Lock()
        self.items = {}

    def submit(self, label, fn):
        with self.lock:
            if any(x['label'] == label and x['status'] in ('queued', 'running') for x in self.items.values()):
                raise ValueError('同类任务正在处理中，请等待完成。')
            if sum(x['status'] in ('queued', 'running') for x in self.items.values()) >= 3:
                raise ValueError('已有 3 个任务正在处理，请稍后再试。')
            if len(self.items) >= 100:
                for old in list(self.items):
                    if self.items[old]['status'] in ('done', 'error'):
                        del self.items[old]
                        break
            tid = secrets.token_hex(10)
            self.items[tid] = {'id': tid, 'label': label, 'status': 'queued', 'created_at': time.time()}

        def work():
            with self.lock:
                self.items[tid]['status'] = 'running'
            try:
                result = fn()
                update = {'status': 'done', 'result': result}
            except ValueError as exc:
                update = {'status': 'error', 'error': str(exc)}
            except Exception:
                update = {'status': 'error', 'error': '处理失败，请检查文件或网络后重试。'}
            with self.lock:
                self.items[tid].update(update)
        self.pool.submit(work)
        return {'task_id': tid}

    def get(self, tid):
        with self.lock:
            item = self.items.get(tid)
            if item is None:
                raise ValueError('任务不存在或服务已重启。')
            return dict(item)


class Application:
    def __init__(self, db_path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.store = Store(db_path)
        try:
            db_path.chmod(0o600)
        except OSError:
            pass
        self.tasks = Tasks()
        if not self.store.get('initialized'):
            self.store.upsert_jobs(json.loads((ROOT / 'data' / 'demo_jobs.json').read_text(encoding='utf-8')))
            self.store.set('initialized', True)

    def state(self):
        jobs = self.store.jobs()
        resume = self.store.get('resume', '')
        profile = self.store.get('profile', {})
        preferences = self.store.get('preferences', {})
        if resume:
            jobs = rank_jobs(resume, profile, jobs, preferences)
        return {'version': __version__, 'jobs': jobs, 'resume': resume, 'profile': profile,
                'preferences': preferences, 'logs': self.store.logs(),
                'ai': {'configured': bool(os.environ.get('DEEPSEEK_API_KEY')), 'model': MODEL},
                'ai_analysis': self.store.get('ai_analysis'), 'polished': self.store.get('polished')}

    def post(self, path, body):
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
            return self.tasks.submit('采集 ' + source, lambda: collect_api(source, self.store))
        if path == '/api/collect/page':
            url = str(body.get('url', ''))
            return self.tasks.submit('网页采集', lambda: collect_page(url, self.store))
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
            return self.tasks.submit('AI ' + task, run_ai)
        raise ValueError('接口不存在。')


def csv_export(jobs):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['岗位', '公司', '地区', '薪资原文', '来源', '匹配分', '投递状态', '链接', '示例数据'])
    for j in jobs:
        values = [j['title'], j['company'], j['location'], j['salary'], j['source'], j.get('score', ''), j.get('status', ''), j['url'], bool(j['is_demo'])]
        writer.writerow(["'" + str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
    return ('\ufeff' + output.getvalue()).encode('utf-8')


def make_server(app, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Never log request bodies, resume text, or credentials.
            pass

        def valid_host(self):
            return self.headers.get('Host') in ('127.0.0.1:{}'.format(self.server.server_port), 'localhost:{}'.format(self.server.server_port))

        def send(self, data, content_type='application/json; charset=utf-8', status=200):
            if isinstance(data, (dict, list)):
                data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if not self.valid_host():
                self.send({'error': '仅允许本机访问。'}, status=403)
                return
            path = urlsplit(self.path).path
            try:
                if path == '/api/state':
                    self.send(app.state())
                elif path == '/api/health':
                    self.send({'status': 'ok', 'version': __version__})
                elif path.startswith('/api/tasks/'):
                    self.send(app.tasks.get(path.rsplit('/', 1)[-1]))
                elif path == '/api/export':
                    self.send(csv_export(app.state()['jobs']), 'text/csv; charset=utf-8')
                elif path == '/api/demo-resume':
                    self.send({'text': (ROOT / 'data' / 'demo_resume.txt').read_text(encoding='utf-8')})
                elif path in ('/', '/app.js', '/style.css'):
                    file = ROOT / 'jobcompass' / 'static' / ('index.html' if path == '/' else path[1:])
                    self.send(file.read_bytes(), mimetypes.guess_type(str(file))[0] + '; charset=utf-8')
                else:
                    self.send({'error': '页面不存在。'}, status=404)
            except ValueError as exc:
                self.send({'error': str(exc)}, status=400)
            except Exception:
                self.send({'error': '服务处理失败，请重试。'}, status=500)

        def do_POST(self):
            # A non-simple custom header plus same-host checks blocks browser CSRF.
            origin = self.headers.get('Origin')
            if not self.valid_host() or self.headers.get('X-JobCompass') != '1' or (origin and origin not in ('http://127.0.0.1:{}'.format(self.server.server_port), 'http://localhost:{}'.format(self.server.server_port))):
                self.send({'error': '请求来源无效。'}, status=403)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 7 * 1024 * 1024:
                    raise ValueError('请求不能为空，且不能超过 7 MB。')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('请求必须是 JSON 对象。')
                self.send(app.post(urlsplit(self.path).path, body))
            except (ValueError, UnicodeError) as exc:
                self.send({'error': str(exc)}, status=400)
            except Exception:
                self.send({'error': '输入处理失败，请检查输入格式后重试。'}, status=500)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
