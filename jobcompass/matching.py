"""Explainable ranking. Scores are ranking indicators, not hiring probabilities."""
import math
import re
from collections import Counter
from .resume import skills_in, experience, education

WEIGHTS = {'skills': 0.45, 'text': 0.25, 'experience': 0.15, 'location': 0.10, 'education': 0.05}
LABELS = {'skills': '技能契合', 'text': '文本相关', 'experience': '经验要求', 'location': '地区偏好', 'education': '学历要求'}
GENERAL_SKILLS = {'Communication', 'English'}


def skill_fit(own, required):
    """Weighted F1 avoids rating unrelated jobs highly on one generic skill."""
    if not required:
        return None
    mass = lambda skills: sum(0.2 if s in GENERAL_SKILLS else 1.0 for s in skills)
    common = mass(own & required)
    precision = common / mass(own) if own else 0
    recall = common / mass(required)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0


def tokens(text):
    low = text.lower()
    english = re.findall(r'[a-z][a-z0-9+#.]*', low)
    stop = {'the', 'and', 'a', 'to', 'of', 'in', 'for', 'with', 'you', 'we', 'is', 'our', 'an', 'on', 'or', 'as', 'be', 'will'}
    chinese = []
    for block in re.findall(r'[\u4e00-\u9fff]+', low):
        chinese.extend(block[i:i + 2] for i in range(len(block) - 1))
    return [x for x in english if x not in stop] + chinese


def text_scores(resume, descriptions):
    docs = [Counter(tokens(x)) for x in [resume] + descriptions]
    df = Counter(t for doc in docs for t in doc)
    n = len(docs)
    vectors = [{t: (1 + math.log(c)) * (math.log((n + 1) / (df[t] + 1)) + 1) for t, c in doc.items()} for doc in docs]
    first = vectors[0]
    norm = math.sqrt(sum(v * v for v in first.values()))
    scores = []
    for vec in vectors[1:]:
        denom = norm * math.sqrt(sum(v * v for v in vec.values()))
        scores.append(sum(v * first.get(t, 0) for t, v in vec.items()) / denom if denom else 0)
    return scores


def rank_jobs(resume, profile, jobs, preferences=None):
    preferences = preferences or {}
    descriptions = [j['title'] + ' ' + j['description'] for j in jobs]
    similarity = text_scores(resume, descriptions)
    result = []
    own = set(profile.get('skills', []))
    own_years = preferences.get('experience_years')
    if own_years is None:
        own_years = profile.get('experience_years')
    levels = {'未识别': 0, '专科': 1, '本科': 2, '硕士': 3, '博士': 4}
    for job, text_sim, description in zip(jobs, similarity, descriptions):
        required = set(job.get('skills') or skills_in(description))
        hit = sorted(own & required)
        missing = sorted(required - own)
        years = job.get('experience_years')
        if years is None:
            years = experience(description)
        required_edu = education(description)
        components = {'skills': skill_fit(own, required),
                      'text': text_sim,
                      'experience': (min(1.0, own_years / years) if years else 1.0) if years is not None and own_years is not None else None,
                      'education': float(levels.get(profile.get('education'), 0) >= levels[required_edu]) if required_edu != '未识别' and profile.get('education') != '未识别' else None,
                      'location': None}
        locations = [s.strip().lower() for s in re.split(r'[,，;/]', preferences.get('location', '')) if s.strip()]
        if locations:
            loc = job.get('location', '').lower()
            # Remote is not worldwide: region restrictions are retained and scored.
            components['location'] = float(any(s in loc for s in locations) or loc in ('worldwide', 'anywhere', '全球')) if loc else None
        active = sum(WEIGHTS[k] for k, v in components.items() if v is not None)
        score = round(100 * sum(WEIGHTS[k] * v for k, v in components.items() if v is not None) / active, 1) if active else 0
        breakdown = [{'key': k, 'label': LABELS[k], 'value': round(v * 100, 1) if v is not None else None,
                      'weight': round(WEIGHTS[k] / active * 100, 1) if v is not None else 0} for k, v in components.items()]
        warnings = []
        if years is not None and own_years is not None and own_years < years:
            warnings.append('岗位要求至少 {} 年经验，当前填写 {} 年。'.format(years, own_years))
        if components['location'] == 0:
            warnings.append('岗位地区与偏好不符，远程岗位也可能限制居住地。')
        if missing:
            warnings.append('简历尚未体现：' + '、'.join(missing[:6]))
        result.append(dict(job, score=score, matched_skills=hit, missing_skills=missing,
                           breakdown=breakdown, warnings=warnings,
                           coverage=round(active * 100), required_years=years))
    return sorted(result, key=lambda j: (-j['score'], j['id']))
