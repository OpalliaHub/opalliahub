"""Public API adapters, robots-aware JSON-LD collector and local imports."""
import csv
import io
import ipaddress
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from .resume import skills_in

AGENT = 'JobCompass-CourseProject/1.0'
ENDPOINTS = {'Remotive': 'https://remotive.com/api/remote-jobs',
             'Arbeitnow': 'https://www.arbeitnow.com/api/job-board-api'}
TRUSTED_SERVICES = {'api.deepseek.com', 'remotive.com', 'www.arbeitnow.com', 'hk.jobsdb.com'}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('p', 'br', 'li', 'div', 'h2', 'h3'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(str(value or ''))
    parser.close()  # Flush buffered text such as a trailing bare "R&D" at EOF.
    return re.sub(r'\n\s*\n+', '\n', ''.join(parser.parts)).strip()


def validate_url(url, trusted_service=False):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('仅支持不含账户信息的公开 HTTPS 地址。')
    # Fixed integration destinations support local proxy Fake-IP DNS. Arbitrary
    # webpage URLs still require public DNS addresses; callers cannot extend this list.
    if trusted_service and parsed.hostname in TRUSTED_SERVICES:
        return url
    try:
        infos = socket.getaddrinfo(parsed.hostname, 443)
    except OSError:
        raise ValueError('无法解析网站地址，请检查网络。')
    if not infos or any(not ipaddress.ip_address(info[4][0]).is_global for info in infos):
        raise ValueError('不能采集本机、内网或保留地址。')
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.has_header('Authorization'):
            raise ValueError('带凭据的 API 请求不允许重定向。')
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, data=None, headers=None, timeout=25, trusted_service=False):
    validate_url(url, trusted_service=trusted_service)
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    opener = urllib.request.build_opener(SafeRedirect(), urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(url, data=data, headers=dict({'User-Agent': AGENT, 'Accept': 'application/json,text/html'}, **(headers or {})))
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError('网站返回内容过大。')
            return body.decode('utf-8-sig')
    except urllib.error.HTTPError as exc:
        messages = {401: '认证失败，请检查 API 密钥。', 402: 'API 余额不足。', 403: '网站拒绝访问，请使用手动导入。', 429: '请求过于频繁，请稍后再试。'}
        raise ValueError(messages.get(exc.code, '外部服务返回 HTTP {}。'.format(exc.code)))
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError('连接失败或超时，请检查网络，仍可使用本地功能。')


def normalize(item, source='手动导入'):
    if not isinstance(item, dict):
        raise ValueError('每条岗位必须是一个对象。')
    title = plain(item.get('title'))[:200]
    company = plain(item.get('company') or item.get('company_name'))[:200]
    description = plain(item.get('description'))[:30000]
    if not title or not company or len(description) < 15:
        raise ValueError('岗位需要 title、company 和至少 15 字符的 description。')
    url = str(item.get('url') or '')[:2000]
    parsed = urllib.parse.urlsplit(url)
    if url and (parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password):
        raise ValueError('岗位链接必须是有效的 HTTP 或 HTTPS 地址。')
    skills = item.get('skills')
    if not isinstance(skills, list) or any(not isinstance(s, str) for s in skills):
        skills = skills_in(title + ' ' + description)
    remote = item.get('remote', False)
    remote = remote is True or str(remote).lower() in ('true', '1', 'yes')
    return {'title': title, 'company': company, 'description': description,
            'source': source, 'url': url, 'location': plain(item.get('location'))[:200],
            'salary': plain(item.get('salary'))[:150], 'skills': skills[:60],
            'published_at': str(item.get('published_at') or '')[:50], 'remote': remote,
            'is_demo': item.get('is_demo') is True}


def collect_api(source, store):
    if source not in ENDPOINTS:
        raise ValueError('请选择支持的数据源。')
    stamp = store.get('last_fetch_' + source)
    if stamp and (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds() < 21600:
        count = sum(j['source'] == source for j in store.jobs())
        if not count:
            raise ValueError('上次采集未获得岗位；为遵守频率限制，请在上次尝试 6 小时后重试。可先导入岗位文件。')
        message = '使用 6 小时缓存，共 {} 条岗位。'.format(count)
        store.log(source, 'cached', count, message)
        return {'source': source, 'count': count, 'message': message}
    # Reserve the attempt before IO, including failed requests, to respect rate limits.
    store.set('last_fetch_' + source, datetime.now(timezone.utc).isoformat())
    try:
        payload = json.loads(fetch(ENDPOINTS[source], trusted_service=True))
        raw = payload.get('jobs' if source == 'Remotive' else 'data')
        if not isinstance(raw, list):
            raise ValueError('数据源格式变化，请使用本地岗位或手动导入。')
        jobs = []
        for row in raw[:1500]:
            try:
                if source == 'Remotive':
                    row = dict(row, location=row.get('candidate_required_location', ''), remote=True,
                               published_at=row.get('publication_date', ''))
                else:
                    row = dict(row, published_at=datetime.fromtimestamp(row.get('created_at', 0), timezone.utc).isoformat())
                jobs.append(normalize(row, source))
            except (ValueError, TypeError, OverflowError):
                continue
        if raw and not jobs:
            raise ValueError('所有岗位均未通过字段检查，请检查数据源格式。')
        count = store.upsert_jobs(jobs)
        message = '采集完成，{} 条岗位已新增或更新。'.format(count)
        store.log(source, 'success', count, message)
        return {'source': source, 'count': count, 'message': message}
    except (ValueError, TypeError, KeyError) as exc:
        store.log(source, 'error', 0, str(exc))
        raise ValueError(str(exc))


class JsonLD(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.blocks = []
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type', '').lower() == 'application/ld+json':
            self.capture = True
            self.current = []

    def handle_data(self, data):
        if self.capture:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.capture:
            self.blocks.append(''.join(self.current))
            self.capture = False


def parse_jsonld(html, url=''):
    parser = JsonLD()
    parser.feed(html)
    jobs = []

    def walk(obj):
        if isinstance(obj, list):
            for sub in obj:
                walk(sub)
        elif isinstance(obj, dict):
            kinds = obj.get('@type', [])
            if 'JobPosting' in (kinds if isinstance(kinds, list) else [kinds]):
                org = obj.get('hiringOrganization') or {}
                locs = obj.get('jobLocation') or []
                locs = locs if isinstance(locs, list) else [locs]
                locations = []
                for loc in locs:
                    addr = loc.get('address', {}) if isinstance(loc, dict) else {}
                    if isinstance(addr, dict):
                        locations.append(' '.join(str(addr.get(k, '')) for k in ('addressLocality', 'addressRegion', 'addressCountry')).strip())
                jobs.append(normalize({'title': obj.get('title'), 'company': org.get('name') if isinstance(org, dict) else org,
                           'description': obj.get('description'), 'location': ', '.join(locations),
                           'published_at': obj.get('datePosted'), 'url': obj.get('url') or url,
                           'remote': obj.get('jobLocationType') == 'TELECOMMUTE'}, '网页导入'))
            else:
                for value in obj.values():
                    if isinstance(value, (dict, list)):
                        walk(value)
    for block in parser.blocks:
        try:
            walk(json.loads(block))
        except (ValueError, TypeError):
            continue
    if not jobs:
        raise ValueError('没有发现可解析的 JobPosting 结构化岗位。可改用 CSV／JSON 或手动录入。')
    return jobs


def collect_page(url, store):
    validate_url(url)
    parsed = urllib.parse.urlsplit(url)
    host_key = 'page_fetch_' + parsed.hostname
    last = store.get(host_key)
    if last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < 15:
        raise ValueError('同一网站的采集间隔至少为 15 秒。')
    store.set(host_key, datetime.now(timezone.utc).isoformat())
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(fetch(urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, '/robots.txt', '', ''))).splitlines())
    if not robots.can_fetch(AGENT, url):
        raise ValueError('网站 robots.txt 不允许自动采集此页面，请使用授权导出或手动录入。')
    jobs = parse_jsonld(fetch(url), url)
    count = store.upsert_jobs(jobs)
    store.log(parsed.hostname, 'success', count, '公开网页结构化采集')
    return {'count': count, 'message': '已导入 {} 条网页岗位。'.format(count)}


def import_jobs(filename, content):
    suffix = filename.lower().rsplit('.', 1)[-1]
    if suffix in ('html', 'htm'):
        return parse_jsonld(content)
    if suffix == 'json':
        rows = json.loads(content)
        if isinstance(rows, dict):
            rows = rows.get('jobs', [])
    elif suffix == 'csv':
        rows = list(csv.DictReader(io.StringIO(content.lstrip('\ufeff'))))
    else:
        raise ValueError('岗位导入支持 CSV、JSON 和包含 JobPosting 的 HTML。')
    if not isinstance(rows, list) or not rows or len(rows) > 2000:
        raise ValueError('请导入 1 至 2000 条岗位记录。')
    return [normalize(row) for row in rows]
