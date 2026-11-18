"""Evidence-backed CV strengths and bounded, explainable job recommendations.

This is a deterministic rule system, not a trained suitability or hiring model.
The legacy matcher is reused once on a controlled professional projection.
"""
import copy
import hashlib
import json
import math
import re
from datetime import datetime, time, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit

from .jobsdb import expiry_status
from .matching import GENERAL_SKILLS, rank_jobs, tokens
from .resume import SKILLS, skills_in

VERSION = 'resume-evidence-1.0'
WEIGHTS = {'baseline': 0.75, 'project_evidence': 0.20, 'target_role': 0.05}
_LABELS = {'baseline': '岗位基础匹配', 'project_evidence': '行动与项目证据', 'target_role': '目标职位名称'}
_DOMAINS = {
    'recruitment': ('招聘', ['recruitment', 'recruiting', 'talent acquisition', '招聘']),
    'human resources': ('人力资源', ['human resources', 'hr', '人力资源', '人力資源']),
    'onboarding': ('入职流程', ['onboarding', '入职', '入職']),
    'payroll': ('薪酬处理', ['payroll', '薪酬', '工资核算']),
    'training': ('培训', ['training', '培训', '培訓']),
    'customer service': ('客户服务', ['customer service', 'customer support', '客户服务', '客戶服務', '客服']),
    'customer': ('客户工作', ['customer', 'client', '客户', '客戶']),
    'sales': ('销售', ['sales', '销售', '銷售']),
    'marketing': ('市场营销', ['marketing', '市场营销', '市場營銷']),
    'operations': ('运营', ['operations', 'operational', '运营', '營運']),
    'logistics': ('物流', ['logistics', '物流']),
    'inventory': ('库存', ['inventory', '库存', '庫存']),
    'procurement': ('采购', ['procurement', 'purchasing', '采购', '採購']),
    'accounting': ('会计', ['accounting', 'bookkeeping', '会计', '會計']),
    'finance': ('财务', ['finance', 'financial', '财务', '財務']),
    'budget': ('预算', ['budget', 'budgeting', '预算', '預算']),
    'teaching': ('教学', ['teaching', 'teacher', '教学', '教學']),
    'research': ('研究工作', ['research', '研究']),
    'administration': ('行政', ['administration', 'administrative', '行政']),
    'events': ('活动执行', ['events', 'event management', '活动', '活動']),
    'project management': ('项目管理', ['project management', '项目管理', '項目管理']),
    'reporting': ('报表与报告', ['reporting', 'reports', 'dashboard', 'dashboards', '报表', '報表']),
    'design': ('设计', ['design', 'designer', '设计', '設計']),
    'writing': ('内容写作', ['writing', 'editing', 'content', '文案', '写作', '寫作']),
    'software': ('软件开发', ['software', 'developer', 'development', '软件', '軟件', '开发', '開發']),
    'quality assurance': ('质量管理', ['quality assurance', 'quality control', '质量', '品質']),
    'scheduling': ('排程', ['scheduling', 'schedule', '排班', '排程']),
}


def _pattern(aliases):
    return re.compile('|'.join((r'(?<![a-z0-9_])' + re.escape(alias) + r'(?![a-z0-9_])')
                              if alias.isascii() else re.escape(alias) for alias in sorted(set(aliases), key=len, reverse=True)), re.I)


_SKILL_PATTERNS = {skill: _pattern([skill] + aliases) for skill, aliases in SKILLS.items()}
_DOMAIN_PATTERNS = {name: _pattern(aliases) for name, (_, aliases) in _DOMAINS.items()}
_ALIASES = {alias.casefold(): name for name, aliases in SKILLS.items() for alias in [name] + aliases}
_PERSONAL = re.compile(r'^\s*(?:姓名|全名|性别|性別|年龄|年齡|出生|国籍|國籍|民族|婚姻|邮箱|郵箱|电话|電話|手机|手機|地址|name|full name|age|gender|sex|nationality|citizenship|ethnicity|race|religion|dob|date of birth|marital status|email|e-mail|phone|contact|address)\s*[:：\- ]', re.I)
_NEGATIVE = re.compile(r'不会|不懂|不熟悉|未掌握|从未|從未|没有|沒有|不具备|不具備|\b(?:no|never|without)\b|\bnot\b(?!\s+only)', re.I)
_GOAL = re.compile(r'求职意向|求職意向|目标岗位|目標崗位|目标职位|期望职位|意向职位|职业目标|\b(?:objective|seeking|desired role|career goal)\b|计划|計劃|希望|打算|想要|准备学习|準備學習|正在学习|正在學習|学习中|學習中|待学习|\b(?:want|hope|plan|intend|aim)\b|\b(?:learning|studying)\b', re.I)
_ACTION = re.compile(r'使用|运用|運用|完成|实现|實現|开发|開發|搭建|负责|負責|协调|協調|组织|組織|管理|交付|分析|优化|優化|提升|减少|減少|\b(?:used|built|developed|implemented|delivered|automated|managed|coordinated|led|designed|created|analyzed|analysed|improved|reduced|organized|trained)\b', re.I)
_PAST = re.compile(r'已使用|已经|已經|曾使用|完成了|实现了|實現了|\b(?:used|built|developed|implemented|delivered|managed|coordinated|led|created)\b', re.I)
_PROJECT = re.compile(r'项目|項目|作品|\b(?:project|portfolio|capstone)\b', re.I)
_SKILL_HEADING = re.compile(r'^\s*(?:技能(?:列表)?|专业技能|專業技能|技术栈|技術棧|skills?(?: list)?|technical skills?|technologies)\s*[:：]', re.I)
_PRACTICAL_ACTION = re.compile(r'使用|运用|運用|完成|实现|實現|开发了|開發了|搭建|负责|負責|交付|优化了|優化了|\b(?:used|built|developed|implemented|delivered|automated|managed|coordinated|led|created|analyzed|analysed|improved|reduced|organized|trained)\b', re.I)
_SPLIT = re.compile(r'[\n\r;；。!?！？]+|(?<=\.)\s+|\bbut\b|\bhowever\b|但是|然而|不过|不過|(?<!不)但(?=已|使用|我|熟悉)', re.I)


def validate_options(options=None):
    if options is None:
        options = {}
    defaults = {'limit': 10, 'target_role': '', 'min_score': 0, 'strict_location': False, 'include_demo': False}
    if not isinstance(options, dict) or set(options) - set(defaults):
        raise ValueError('推荐选项包含不支持的字段。')
    result = dict(defaults, **options)
    if type(result['limit']) is not int or not 1 <= result['limit'] <= 30:
        raise ValueError('推荐数量需为 1–30 的整数。')
    if not isinstance(result['target_role'], str) or len(result['target_role']) > 100:
        raise ValueError('目标岗位须为最多 100 个字符的文本。')
    score = result['min_score']
    if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError('最低匹配分须为 0–100 的有限数值。')
    if any(type(result[key]) is not bool for key in ('strict_location', 'include_demo')):
        raise ValueError('地区与演示筛选开关必须是布尔值。')
    result['target_role'] = result['target_role'].strip()
    return result


def _preferences(preferences):
    if preferences is None:
        preferences = {}
    if not isinstance(preferences, dict) or set(preferences) - {'location', 'experience_years'}:
        raise ValueError('求职偏好仅接受地区和工作年限。')
    result = {'location': '', 'experience_years': None}
    result.update(preferences)
    if not isinstance(result['location'], str) or len(result['location']) > 200:
        raise ValueError('地区偏好须为最多 200 个字符的文本。')
    years = result['experience_years']
    if years is not None and (type(years) not in (int, float) or not math.isfinite(years) or not 0 <= years <= 80):
        raise ValueError('工作年限须为 0–80 的有限数值或空值。')
    return result


def _units(text):
    return [unit.strip() for unit in _SPLIT.split(text) if unit.strip() and not _PERSONAL.search(unit)]


def _claim_status(unit, match):
    prefix, suffix = unit[:match.start()], unit[match.end():]
    local = re.split(r'[,，]', prefix)[-1]
    # A fresh affirmative clause resets an earlier comma-separated denial.
    scope = local if _ACTION.search(local) or _NEGATIVE.search(local) or _GOAL.search(local) else prefix
    negatives, goals, past = list(_NEGATIVE.finditer(scope)), list(_GOAL.finditer(scope)), list(_PAST.finditer(scope))
    latest_past = past[-1].start() if past else -1
    if negatives and negatives[-1].start() > latest_past:
        return 'denied'
    if re.match(r'\s*(?:is\s+|are\s+|[:：(（]\s*)?(?:不会|不熟悉|未掌握|not\b|没有|沒有)', suffix, re.I):
        return 'denied'
    if goals and goals[-1].start() > latest_past:
        return 'aspirational'
    if re.match(r'\s*[:：(（]?\s*(?:学习中|學習中|待学习|to learn\b)', suffix, re.I):
        return 'aspirational'
    return 'affirmed'


def _hits(unit, patterns):
    for name, pattern in patterns.items():
        for match in pattern.finditer(unit):
            if name == 'Go' and match.group().lower() == 'go' and match.group() != 'Go' and not re.search(r'programming|技能|编程|语言|开发', unit, re.I):
                continue
            yield name, match, _claim_status(unit, match)


def _quote(unit, match=None):
    start = max(0, (match.start() if match else 0) - 70)
    return unit[start:start + 240].strip()


def _education(text):
    for value, pattern in [('博士', r'博士|\bph\.?d\b'), ('硕士', r'硕士|碩士|\bmaster(?:\x27s)?\s+(?:degree|of\b)'),
                           ('本科', r'本科|学士|學士|\bbachelor\b'), ('专科', r'专科|專科|\bassociate degree\b')]:
        if re.search(pattern, text, re.I):
            return value
    return '未识别'


def _experience(text):
    values = re.findall(r'(\d+(?:\.\d+)?)\s*(?:[-–至]\s*\d+\s*)?(?:年(?:相关|相關|工作|开发|開發|实习|實習)?经验|年(?:相关|相關|工作)?經驗|years?\s+(?:(?:of|professional|work|relevant)\s+)*experience)', text, re.I)
    if values:
        return min(80.0, max(float(value) for value in values))
    return 0.0 if re.search(r'应届|應屆|fresh graduate|entry.level', text, re.I) else None


def _analyze(text):
    if not isinstance(text, str) or not 30 <= len(text.strip()) <= 40000:
        raise ValueError('简历需为 30–40,000 个字符的文本。')
    units, observations, domain_evidence, cards = _units(text), {}, {}, []
    for unit in units:
        action = bool(_ACTION.search(unit)) and (not _SKILL_HEADING.search(unit) or bool(_PRACTICAL_ACTION.search(unit)))
        kind = 'project' if action and _PROJECT.search(unit) else ('experience' if action else 'skill')
        sid = hashlib.sha256((kind + '|' + unit).encode('utf-8')).hexdigest()[:12]
        local_skills, quotes = [], []
        for skill, match, status in _hits(unit, _SKILL_PATTERNS):
            entry = {'status': status, 'kind': kind, 'text': _quote(unit, match), 'strength_id': sid}
            observations.setdefault(skill, []).append(entry)
            if status == 'affirmed':
                local_skills.append(skill)
                quotes.append(entry['text'])
        local_domains = []
        for domain, match, status in _hits(unit, _DOMAIN_PATTERNS):
            if status == 'affirmed':
                domain_evidence.setdefault(domain, []).append({'text': _quote(unit, match), 'kind': kind, 'strength_id': sid})
                local_domains.append(domain)
                quotes.append(_quote(unit, match))
        if local_skills or (action and local_domains):
            evidence = list(dict.fromkeys(quotes))[:3]
            visible_skills = [skill for skill in dict.fromkeys(local_skills) if skill in skills_in(' '.join(evidence))]
            title = ('项目中出现的实践线索' if kind == 'project' else '行动与相关经历' if action else '简历明确列出的技能')
            cards.append({'id': sid, 'title': title, 'skills': visible_skills, 'evidence': evidence, 'kind': kind})
    accepted, excluded, evidence, project_features = [], [], {}, set()
    for skill in SKILLS:
        entries = observations.get(skill, [])
        good = [entry for entry in entries if entry['status'] == 'affirmed']
        denied = [entry for entry in entries if entry['status'] == 'denied']
        if good and not denied:
            accepted.append(skill)
            evidence['s:' + skill] = good
            if any(entry['kind'] in ('project', 'experience') for entry in good):
                project_features.add('s:' + skill)
        elif entries:
            status = 'conflicting' if denied and good else 'denied' if denied else 'aspirational'
            excluded.append({'skill': skill, 'status': status, 'evidence': list(dict.fromkeys(entry['text'] for entry in entries))[:2]})
    for domain, entries in domain_evidence.items():
        evidence['d:' + domain] = entries
        if any(entry['kind'] in ('project', 'experience') for entry in entries):
            project_features.add('d:' + domain)
    for card in cards:
        card['skills'] = [skill for skill in card['skills'] if skill in accepted]
    domain_card_ids = {entry['strength_id'] for entries in domain_evidence.values() for entry in entries}
    cards = [card for card in cards if card['skills'] or card['id'] in domain_card_ids]
    factual = '\n'.join(unit for unit in units if not _GOAL.search(unit) and not _NEGATIVE.search(unit))
    level, years = _education(factual), _experience(factual)
    questions = []
    if not project_features:
        questions.append('可补充实际完成的任务、使用的方法和可核查的结果，帮助区分技能列表与实践证据。')
    if excluded:
        questions.append('部分技能被标为否定、计划学习或表述冲突；如识别不准确，请把实际使用经历写清楚。')
    if years is None:
        questions.append('可在求职偏好中填写实际工作年限；年龄和出生日期不用于推断工作经验。')
    if not accepted and not domain_evidence:
        questions.append('尚未识别具体职业线索；请补充岗位职责、项目、作品或服务对象。')
    profile = {'skills': accepted, 'strengths': cards[:12], 'questions': questions, 'excluded_skills': excluded,
               'education': level, 'experience_years': years,
               'professional_domains': [{'id': key, 'label': _DOMAINS[key][0], 'evidence': list(dict.fromkeys(row['text'] for row in entries))[:2]}
                                        for key, entries in domain_evidence.items()],
               'label_source': 'rule_derived', 'evidence_policy': '简历原文线索，不是熟练度认证。'}
    projection = ' '.join(accepted + list(domain_evidence))
    return profile, evidence, project_features, projection


def analyze_strengths(text):
    return _analyze(text)[0]


def _canonical_skills(values):
    if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() or len(value) > 120 for value in values):
        raise ValueError('岗位技能必须是文本列表。')
    return list(dict.fromkeys(_ALIASES.get(value.strip().casefold(), value.strip()) for value in values))


def _url_key(url):
    if not url:
        return ''
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()
        port = parsed.port
    except (ValueError, TypeError):
        raise ValueError('岗位链接需为有效 HTTP/HTTPS 地址。')
    host = parsed.hostname.lower() + (':' + str(port) if port not in (None, 80, 443) else '')
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.casefold().startswith('utm_') and key.casefold() not in ('gclid', 'fbclid')]
    return host + (parsed.path.rstrip('/') or '/') + ('?' + urlencode(sorted(query)) if query else '')


def _job(raw):
    if not isinstance(raw, dict):
        raise ValueError('岗位记录必须是对象。')
    row = copy.deepcopy(raw)
    for key in ('id', 'title', 'description', 'company', 'source', 'location', 'url', 'availability', 'expires_at'):
        row.setdefault(key, '')
        if not isinstance(row[key], str):
            raise ValueError('岗位 {} 必须是文本。'.format(key))
    if not row['title'].strip():
        raise ValueError('岗位标题不能为空。')
    if type(row.get('is_demo', False)) not in (bool, int) or row.get('is_demo', False) not in (0, 1):
        raise ValueError('岗位演示标记须为布尔值或 0/1。')
    row['is_demo'] = bool(row.get('is_demo', False))
    required = _canonical_skills(row.get('skills', []))
    row['skills'] = required or skills_in(row['title'] + ' ' + row['description'])
    url_key = _url_key(row['url'])
    identity = ('url:' + url_key if url_key else 'id:' + row['id'] if row['id'] else
                'fields:' + '|'.join(row[key].strip().casefold() for key in ('source', 'title', 'company', 'location')))
    row['id'] = row['id'] or hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]
    return row, identity


def _location_match(location, preference):
    wanted = [item.strip().casefold() for item in re.split(r'[,，;/]', preference) if item.strip()]
    actual = location.strip().casefold()
    return bool(wanted) and (actual in ('worldwide', 'anywhere', '全球') or any(item in actual for item in wanted))


def _availability(job):
    """Interpret ambiguous ISO expiry conservatively without changing the legacy helper.

    Past naive timestamps use UTC; a date-only value expires at its UTC day end.
    Future naive/invalid values remain unconfirmed rather than asserting active.
    """
    status = expiry_status(job)
    raw = job['expires_at'].strip()
    if not raw or status.strip().casefold() in ('expired', 'closed', 'inactive', 'unavailable', 'removed'):
        return status, []
    try:
        stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return 'unknown', ['到期时间格式无法确认，请到原站核实岗位状态。']
    if stamp.tzinfo is None:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            stamp = datetime.combine(stamp.date(), time.max)
        stamp = stamp.replace(tzinfo=timezone.utc)
        if stamp <= datetime.now(timezone.utc):
            return 'expired', []
        return 'unknown', ['到期时间未含时区，暂不确认有效；历史值按 UTC 判断，到原站核实后再申请。']
    return status, []


def _job_features(job):
    text = job['title'] + '\n' + job['description']
    # Cheap literal rejection avoids scanning every long ad with every regex.
    # Preserve re.I's exceptional Unicode I/S matches; Kelvin K lowercases to k.
    lowered = text.lower().replace('\u0131', 'i').replace('\u017f', 's').replace('i\u0307', 'i')
    domains = [name for name, pattern in _DOMAIN_PATTERNS.items()
               if any(alias in lowered for alias in _DOMAINS[name][1]) and pattern.search(text)]
    features = {'s:' + skill for skill in job['skills']} | {'d:' + domain for domain in domains}
    professional_text = '\n'.join(_units(text))
    level = _education(professional_text)
    degree = {'本科': 'bachelor degree', '硕士': 'master degree', '博士': 'PhD', '专科': 'associate degree'}.get(level, '')
    projected = dict(job, title=' '.join(job['skills'] + domains), description=degree,
                     experience_years=_experience(professional_text))
    if job.get('experience_years') is not None:
        years = job['experience_years']
        if type(years) not in (int, float) or not math.isfinite(years) or not 0 <= years <= 80:
            raise ValueError('岗位工作年限无效。')
        projected['experience_years'] = years
    return features, projected


def _feature_weight(feature):
    return 0.2 if feature.startswith('s:') and feature[2:] in GENERAL_SKILLS else 1.0


def build_recommendations(resume, jobs, preferences=None, options=None):
    options, preferences = validate_options(options), _preferences(preferences)
    if not isinstance(jobs, list):
        raise ValueError('岗位数据必须是列表。')
    if options['strict_location'] and not preferences['location'].strip():
        raise ValueError('严格地区筛选需要先填写求职地区。')
    profile, evidence, project_features, projection = _analyze(resume)
    records = [_job(job) for job in jobs]
    has_real = any(not row['is_demo'] for row, _ in records)
    demo_fallback = bool(records) and not has_real
    summary = dict(total=len(records), eligible=0, returned=0, excluded_expired=0, excluded_demo=0,
                   excluded_duplicates=0, excluded_location=0, excluded_min_score=0, available_after_score_filter=0,
                   data_mode='empty', demo_fallback=demo_fallback, weak_matches=0, empty_reason='')
    selected, seen, seen_ids, status_notes = [], set(), set(), {}
    for row, identity in records:
        if row['is_demo'] and has_real and not options['include_demo']:
            summary['excluded_demo'] += 1
            continue
        if identity in seen or row['id'] in seen_ids:
            summary['excluded_duplicates'] += 1
            continue
        seen.add(identity)
        seen_ids.add(row['id'])
        row['availability'], status_notes[row['id']] = _availability(row)
        if row['availability'].strip().casefold() in ('expired', 'closed', 'inactive', 'unavailable', 'removed'):
            summary['excluded_expired'] += 1
            continue
        if options['strict_location'] and not _location_match(row['location'], preferences['location']):
            summary['excluded_location'] += 1
            continue
        selected.append(row)
    summary['eligible'] = len(selected)
    summary['data_mode'] = ('mixed' if any(row['is_demo'] for row in selected) and any(not row['is_demo'] for row in selected)
                            else 'demo' if selected and selected[0]['is_demo'] else 'observed' if records and has_real else 'empty')
    original = {row['id']: row for row in selected}
    features, projected = {}, []
    for row in selected:
        features[row['id']], projection_job = _job_features(row)
        projected.append(projection_job)
    ranked = rank_jobs(projection, profile, projected, preferences) if projected else []
    output = []
    own_features = set(evidence)
    target_tokens = set(tokens(options['target_role']))
    visible_strength_ids = {card['id'] for card in profile['strengths']}
    for base in ranked:
        row, job_features = copy.deepcopy(original[base['id']]), features[base['id']]
        overlap = own_features & job_features
        practical = project_features & job_features
        project_fit = (100 * sum(_feature_weight(key) for key in practical) / sum(_feature_weight(key) for key in job_features)
                       if project_features and job_features else None)
        title_tokens = set(tokens(row['title']))
        role_fit = 100 * 2 * len(target_tokens & title_tokens) / (len(target_tokens) + len(title_tokens)) if target_tokens and title_tokens else None
        values = {'baseline': base['score'], 'project_evidence': project_fit, 'target_role': role_fit}
        active = sum(WEIGHTS[key] for key in WEIGHTS if values[key] is not None)
        breakdown = [{'key': key, 'label': _LABELS[key], 'value': round(value, 1) if value is not None else None,
                      'weight': round(WEIGHTS[key] / active * 100, 2) if value is not None else 0,
                      'base_weight': WEIGHTS[key] * 100,
                      'contribution': round(value * WEIGHTS[key] / active, 2) if value is not None else 0}
                     for key, value in values.items()]
        score = round(sum(values[key] * WEIGHTS[key] for key in values if values[key] is not None) / active, 1)
        substantive = {key for key in overlap if not (key.startswith('s:') and key[2:] in GENERAL_SKILLS)}
        unknown = [part['key'] for part in base['breakdown'] if part['value'] is None]
        if project_fit is None:
            unknown.append('project_evidence')
        if not projection:
            unknown.append('professional_evidence')
        effective_total = 1 if options['target_role'] else 0.95
        coverage = (0.75 * (base['coverage'] if projection else 0) + (20 if project_fit is not None else 0)
                    + (5 if role_fit is not None else 0)) / effective_total
        matches = []
        for key in sorted(overlap, key=lambda item: (item not in practical, item))[:12]:
            entries = evidence[key]
            matches.append({'skill': key[2:] if key.startswith('s:') else _DOMAINS[key[2:]][0],
                            'kind': 'project' if key in project_features else 'declared',
                            'feature_type': 'skill' if key.startswith('s:') else 'domain',
                            'evidence': list(dict.fromkeys(item['text'] for item in entries))[:2],
                            'strength_ids': list(dict.fromkeys(item['strength_id'] for item in entries if item['strength_id'] in visible_strength_ids))[:3]})
        reasons = []
        if base['matched_skills']:
            reasons.append('岗位提及与简历相交的技能：' + '、'.join(base['matched_skills'][:8]))
        if practical:
            reasons.append('相关技能或职责在简历的行动/项目句中有原文线索，可逐条核对。')
        if role_fit:
            reasons.append('岗位标题与指定目标职位存在文字重合。')
        warnings = list(status_notes[row['id']])
        if base['missing_skills']:
            warnings.append('简历尚未体现：' + '、'.join(base['missing_skills'][:6]))
        if any(part['key'] == 'location' and part['value'] == 0 for part in base['breakdown']):
            warnings.append('岗位地区与偏好不符，远程岗位也可能限制居住地。')
        if base['required_years'] is not None and (preferences['experience_years'] if preferences['experience_years'] is not None else profile['experience_years']) is not None:
            years = preferences['experience_years'] if preferences['experience_years'] is not None else profile['experience_years']
            if years < base['required_years']:
                warnings.append('岗位文本提及的经验年限高于当前填写年限，请核实是否为必需条件。')
        if row['availability'] not in ('active', 'live', 'available'):
            warnings.append('当前没有已确认的有效状态，请到原站核实是否仍接受申请。')
        if not substantive:
            warnings.append('可核查的职业重合线索较少；这是候选排序，不应视为已确认适合。')
        if row['is_demo']:
            warnings.append('这是虚构演示岗位，不能作为真实招聘机会。')
        row.update(score=score, baseline_score=base['score'], breakdown=breakdown,
                   baseline_breakdown=base['breakdown'], matched_skills=base['matched_skills'],
                   missing_skills=base['missing_skills'], reasons=reasons, evidence_matches=matches,
                   warnings=warnings, effective_coverage=round(min(100, coverage), 1),
                   unknown_fields=unknown, weak_signal=not bool(substantive))
        if score < options['min_score']:
            summary['excluded_min_score'] += 1
        else:
            output.append(row)
    output.sort(key=lambda row: (-row['score'], row['id']))
    summary['available_after_score_filter'] = len(output)
    output = output[:options['limit']]
    summary.update(returned=len(output), weak_matches=sum(row['weak_signal'] for row in output))
    if not output:
        summary['empty_reason'] = '没有候选达到明确设置的最低分。' if summary['excluded_min_score'] else '当前没有符合有效状态、来源和地区筛选的岗位。'
    fingerprint = hashlib.sha256(json.dumps({'version': VERSION, 'resume': resume, 'jobs': jobs,
        'preferences': preferences, 'options': options}, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()
    return {'profile': profile, 'jobs': output, 'summary': summary,
            'method': {'version': VERSION, 'weights': dict(WEIGHTS), 'options': options,
                'limitations': ['固定规则权重，未训练或校准为录用概率；不报告未经人工标签验证的准确率。',
                    '技能和职责均来自词典与原文线索，不代表熟练度或岗位硬性条件。',
                    '基础排序只输入正向技能和有限职业概念，不使用姓名、性别、年龄、国籍等身份字段。',
                    '未知条件保留未知；缺少实践证据不等于没有能力，非词典领域可能遗漏。',
                    '仅排除已知失效记录，不主动联网验证每条岗位；跨来源相同规范链接保留首条记录。']},
            'fingerprint': fingerprint}
