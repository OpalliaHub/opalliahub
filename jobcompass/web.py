"""Shared HTTP boundary for the local server and the production WSGI adapter."""
import json
import mimetypes
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .config import ROOT
from .config import MODEL
from .public import PublicConfig, SessionManager, RateLimiter, sanitize_public, validate_page_url, collect_public_page
from .research import export_csv

MAX_BODY = 7 * 1024 * 1024
AI_ROUTES = frozenset({'/api/ai', '/api/research/plan', '/api/research/explain',
                       '/api/research/agent', '/api/analytics/command'})
ADMIN_ROUTES = frozenset({'/api/research/connect', '/api/research/build'})
POST_ROUTES = frozenset({'/api/analytics/query', '/api/analytics/command', '/api/research/agent',
    '/api/research/connect', '/api/research/build', '/api/research/run', '/api/research/plan',
    '/api/research/explain', '/api/research/cohort', '/api/learning', '/api/application/history',
    '/api/resume', '/api/resume/file', '/api/resume/clear', '/api/preferences', '/api/collect',
    '/api/jobsdb/update', '/api/tasks/cancel', '/api/benchmark/import', '/api/collect/page',
    '/api/import', '/api/job', '/api/application', '/api/ai', '/api/recommendations'})
GET_ROUTES = frozenset({'/api/health', '/api/state', '/api/status', '/api/analytics/catalog',
                       '/api/research/status', '/api/export', '/api/demo-resume'})
HEAVY_GET_ROUTES = frozenset({'/api/state', '/api/analytics/catalog', '/api/export', '/api/research/status'})
ASSETS = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css',
          '/research.js': 'research.js', '/learning.js': 'learning.js', '/analytics.js': 'analytics.js',
          '/vendor/echarts.min.js': 'vendor/echarts.min.js'}


def response(data, status=200, content_type='application/json; charset=utf-8', extra=None):
    if isinstance(data, (dict, list)):
        data = json.dumps(data, ensure_ascii=False).encode('utf-8')
    elif isinstance(data, str):
        data = data.encode('utf-8')
    headers = [('Content-Type', content_type), ('Content-Length', str(len(data))),
               ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
               ('Referrer-Policy', 'no-referrer'),
               ('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")]
    headers.extend(extra or [])
    return status, headers, data


class WebGateway:
    def __init__(self, app, port=8765, public_config=None):
        self.app, self.port, self.config = app, port, public_config
        self.sessions = None
        self._stop = threading.Event()
        self._maintenance = None
        if public_config is not None:
            from .server import Application

            def factory(store, directory):
                visitor = Application(Path(store.path), store=store, pool=app.tasks.pool,
                                      index_root=app.research.root, result_root=directory / 'results')
                visitor.deployment = {'public_mode': True, 'label': '公开研究工作台',
                                      'session_ttl_seconds': self.ttl,
                                      'message': '免登录访客会话；记录仅对当前浏览器可见，闲置到期或服务重启后清除。'}
                return visitor

            self.ttl = int(os.environ.get('JOBCOMPASS_SESSION_TTL', '3600'))
            creation_limit = RateLimiter(per_ip=int(os.environ.get('JOBCOMPASS_SESSION_PER_IP', '12')),
                                         global_limit=int(os.environ.get('JOBCOMPASS_SESSION_GLOBAL', '120')),
                                         max_active=4, window_seconds=3600, label='新访客会话')
            self.sessions = SessionManager(app.store, Path(app.store.path).parent / 'private' / 'visitors',
                                           factory, ttl_seconds=self.ttl,
                                           max_sessions=int(os.environ.get('JOBCOMPASS_MAX_SESSIONS', '32')),
                                           secure=public_config.secure, creation_limiter=creation_limit)
            self.ai_limit = RateLimiter(per_ip=int(os.environ.get('JOBCOMPASS_AI_PER_IP', '10')),
                                        global_limit=int(os.environ.get('JOBCOMPASS_AI_GLOBAL', '100')),
                                        max_active=int(os.environ.get('JOBCOMPASS_AI_ACTIVE', '3')), window_seconds=3600)
            self.recommendation_limit = RateLimiter(per_ip=30, global_limit=300,
                max_active=int(os.environ.get('JOBCOMPASS_RECOMMEND_ACTIVE', '3')),
                window_seconds=3600, label='岗位推荐')
            self.work_limit = RateLimiter(per_ip=120, global_limit=1200, max_active=16, window_seconds=60, label='数据请求')
            def maintain():
                while not self._stop.wait(30):
                    self.sessions.cleanup()
            self._maintenance = threading.Thread(target=maintain, name='visitor-expiry', daemon=True)
            self._maintenance.start()

    def close(self):
        self._stop.set()
        if self._maintenance:
            self._maintenance.join(timeout=2)
        if self.sessions:
            self.sessions.close()

    def valid_request(self, headers, write=False):
        if self.config:
            return self.config.valid_request(headers.get('host'), headers.get('origin'), write=write)
        hosts = ('127.0.0.1:{}'.format(self.port), 'localhost:{}'.format(self.port))
        return headers.get('host') in hosts and (not write or not headers.get('origin') or
                                                headers['origin'] in tuple('http://' + host for host in hosts))

    @contextmanager
    def scoped(self, headers, path, peer):
        # Health checks and assets carry no personal data and do not allocate visitors.
        if self.sessions and (path == '/' or path.startswith('/api/') and path != '/api/health'):
            ip = self.config.client_ip(peer, headers.get('x-real-ip'))
            with self.sessions.session(headers.get('cookie', ''), peer=ip) as session:
                yield session.app, [('Set-Cookie', session.set_cookie)]
        else:
            yield self.app, []

    def handle(self, method, target, headers, body=b'', peer='127.0.0.1'):
        headers = {key.lower():value for key,value in headers.items()}
        path = urlsplit(target).path
        if method not in ('GET', 'POST'):
            return response({'error': '不支持的请求方式。'}, 405)
        health_probe = method == 'GET' and path == '/api/health' and peer in ('127.0.0.1', '::1')
        if (not health_probe and not self.valid_request(headers, write=method == 'POST')) or (method == 'POST' and
                (headers.get('x-jobcompass') != '1' or headers.get('sec-fetch-site') == 'cross-site')):
            return response({'error': '请求来源无效。'}, 403)
        resource = any(path.startswith(prefix) and path[len(prefix):] and '/' not in path[len(prefix):]
                       for prefix in ('/api/research/result/', '/api/tasks/'))
        known = path in POST_ROUTES if method == 'POST' else path in GET_ROUTES or path in ASSETS or resource
        if not known:
            return response({'error':'页面不存在。'}, 404)
        extra, permit, work, queued = [], None, None, False
        try:
            if self.config and path in ADMIN_ROUTES:
                return response({'error': '研究数据源由服务器配置；公开页面可直接分析已经提供的数据集。'}, 403)
            if method == 'POST':
                if not 0 < len(body) <= MAX_BODY:
                    raise ValueError('请求不能为空，且不能超过 7 MB。')
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise ValueError('请求必须是 JSON 对象。')
                if self.config and path == '/api/collect/page':
                    validate_page_url(payload.get('url'), self.config.page_hosts)
            if self.config and (method == 'POST' or path in HEAVY_GET_ROUTES):
                ip = self.config.client_ip(peer, headers.get('x-real-ip'))
                work = self.work_limit.reserve(ip)
                if method == 'POST' and path in AI_ROUTES:
                    permit = self.ai_limit.reserve(ip)
                elif method == 'POST' and path == '/api/recommendations':
                    # Admit before copying a potentially large private job corpus;
                    # the task releases this separate CPU slot in its finally block.
                    permit = self.recommendation_limit.reserve(ip)
            with self.scoped(headers, path, peer) as (app, extra):
                if method == 'POST':
                    if self.config and path == '/api/collect/page':
                        result = app.tasks.submit('网页采集', lambda: collect_public_page(payload['url'], app.store, self.config.page_hosts))
                    else:
                        result = app.post(path, payload, permit=permit)
                    queued = isinstance(result, dict) and 'task_id' in result
                    return response(result, extra=extra)
                if path == '/api/health':
                    return response({'status':'ok', 'version':__version__})
                if path == '/api/state':
                    return response(app.state(), extra=extra)
                if path == '/api/status':
                    return response({'version':__version__, 'deployment':app.deployment,
                                     'ai':{'configured':bool(os.environ.get('DEEPSEEK_API_KEY')), 'model':MODEL}}, extra=extra)
                if path == '/api/analytics/catalog':
                    query = parse_qs(urlsplit(target).query)
                    catalog = app.analytics.catalog(query.get('dataset', [None])[0])
                    catalog.update(version=__version__, deployment=app.deployment,
                                   ai={'configured':bool(os.environ.get('DEEPSEEK_API_KEY')), 'model':MODEL})
                    return response(catalog, extra=extra)
                if path == '/api/research/status':
                    data = app.research.status()
                    return response(sanitize_public(data) if self.config else data, extra=extra)
                if path.startswith('/api/research/result/'):
                    rid = path.rsplit('/', 1)[-1]
                    if rid.endswith('.csv'):
                        return response(export_csv(app.research.result(rid[:-4])), content_type='text/csv; charset=utf-8', extra=extra)
                    return response(app.research.result(rid[:-5] if rid.endswith('.json') else rid), extra=extra)
                if path.startswith('/api/tasks/'):
                    data = app.tasks.get(path.rsplit('/',1)[-1])
                    if self.config and data.get('error'):
                        data['error'] = sanitize_public(data['error'])
                    return response(data, extra=extra)
                if path == '/api/export':
                    from .server import csv_export
                    return response(csv_export(app.state()['jobs']), content_type='text/csv; charset=utf-8', extra=extra)
                if path == '/api/demo-resume':
                    return response({'text': (ROOT / 'data' / 'demo_resume.txt').read_text(encoding='utf-8')}, extra=extra)
                if path in ASSETS:
                    file = ROOT / 'jobcompass' / 'static' / ASSETS[path]
                    return response(file.read_bytes(), content_type=(mimetypes.guess_type(str(file))[0] or 'application/octet-stream') + '; charset=utf-8', extra=extra)
                return response({'error':'页面不存在。'}, 404, extra=extra)
        except (ValueError, UnicodeError) as error:
            status = getattr(error, 'status_code', 400)
            if hasattr(error, 'retry_after'):
                extra = extra + [('Retry-After', str(error.retry_after))]
            return response({'error': sanitize_public(str(error)) if self.config else str(error)}, status, extra=extra)
        except Exception:
            return response({'error':'服务处理失败，请检查输入或稍后重试。'}, 500, extra=extra)
        finally:
            if permit and not queued:
                permit.release()
            if work:
                work.release()
