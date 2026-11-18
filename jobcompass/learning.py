"""Explainable learning plans from the selected vacancy corpus, without an LLM.

Frequency describes this input sample. The prerequisite graph is a small,
authored teaching aid; its edges are not extracted employer requirements.
"""
import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from functools import lru_cache
from types import MappingProxyType

from .resume import SKILLS, skills_in


_ALIASES = {alias.casefold(): name for name, aliases in SKILLS.items()
            for alias in [name] + aliases}

# These are suggested study dependencies, not statements about hiring criteria.
_DEFAULT_EDGES = {
    'NumPy': ('Python',), 'Pandas': ('Python',),
    'Data Analysis': ('Statistics', 'SQL', 'Pandas'),
    'Machine Learning': ('Statistics', 'NumPy', 'Pandas'),
    'PyTorch': ('Machine Learning',), 'TensorFlow': ('Machine Learning',),
    'LLM': ('Python', 'Machine Learning'),
    'Flask': ('Python', 'HTML/CSS'), 'Django': ('Python', 'SQL', 'HTML/CSS'),
    'FastAPI': ('Python',), 'Testing': ('Python',),
    'TypeScript': ('JavaScript',), 'React': ('JavaScript', 'HTML/CSS'),
    'Vue': ('JavaScript', 'HTML/CSS'), 'Docker': ('Linux',),
    'Kubernetes': ('Docker',), 'Spark': ('Python', 'SQL'),
    'Power BI': ('Excel', 'SQL'), 'Tableau': ('Statistics',),
}


def _canonical(skill):
    if not isinstance(skill, str) or not skill.strip() or len(skill) > 120:
        raise ValueError('技能名称必须是 1–120 个字符的字符串。')
    name = skill.strip()
    return _ALIASES.get(name.casefold(), name)


def _skill_names(value):
    if not isinstance(value, (list, tuple)):
        raise ValueError('skills 必须是技能名称列表。')
    names = {}
    for item in value:
        name = _canonical(item)
        names.setdefault(name.casefold(), name)
    return tuple(names.values())


class PrerequisiteGraph:
    """An immutable dependency graph with recursive, cached topological walks.

    Each DFS tracks both the active recursion path (cycle detection) and the
    completed set (shared prerequisites appear once). Cached tuples cannot be
    accidentally changed by a caller. Custom graphs are useful for unit tests
    and for extending the teaching taxonomy without changing ranking logic.
    """

    def __init__(self, edges=None):
        edges = _DEFAULT_EDGES if edges is None else edges
        if not isinstance(edges, Mapping) or len(edges) > 128:
            raise ValueError('先修图必须是最多 128 个节点的映射。')
        copied = {}
        for name, prerequisites in edges.items():
            canonical = _canonical(name)
            if canonical in copied:
                raise ValueError('先修图包含重复的技能别名。')
            copied[canonical] = _skill_names(prerequisites)
        self._edges = MappingProxyType(copied)
        # Reject a broken graph at construction, before serving any plans.
        for name in self._edges:
            self._ordered(name)

    def _ordered(self, skill):
        completed, active_set, active, order = set(), set(), [], []

        def visit(node):
            if node in active_set:
                start = active.index(node)
                raise ValueError('先修关系存在循环 (cycle): ' + ' -> '.join(active[start:] + [node]))
            if node in completed:
                return
            active.append(node)
            active_set.add(node)
            for prerequisite in self._edges.get(node, ()):
                visit(prerequisite)
            active.pop()
            active_set.remove(node)
            completed.add(node)
            order.append(node)

        visit(skill)
        return tuple(order)

    @lru_cache(maxsize=256)
    def prerequisites(self, skill):
        """Return transitive prerequisites, foundation first, excluding skill."""
        return self._ordered(_canonical(skill))[:-1]


@dataclass(frozen=True)
class JobExample:
    id: str
    title: str
    company: str


@dataclass(frozen=True)
class SkillGap:
    skill: str
    count: int
    share_pct: float
    already_known: bool
    prerequisites: tuple
    learning_order: tuple
    example_jobs: tuple

    def to_dict(self):
        result = asdict(self)
        for field in ('prerequisites', 'learning_order', 'example_jobs'):
            result[field] = list(result[field])
        return result


@dataclass(frozen=True)
class _JobSample:
    example: JobExample
    skills: tuple
    is_demo: bool
    expired: bool


def _job_sample(job):
    if not isinstance(job, dict):
        raise ValueError('每条岗位数据必须是对象。')
    text = {}
    for field in ('title', 'company', 'source', 'description', 'location', 'url', 'availability'):
        value = job.get(field, '')
        if not isinstance(value, str):
            raise ValueError('岗位 {} 必须是字符串。'.format(field))
        text[field] = value
    demo = job.get('is_demo', False)
    if not isinstance(demo, (bool, int)) or demo not in (0, 1):
        raise ValueError('is_demo 必须是布尔值或 0/1。')
    jid = job.get('id', '')
    if not isinstance(jid, (str, int)) or isinstance(jid, bool):
        raise ValueError('岗位 id 必须是字符串或整数。')
    jid = str(jid).strip()
    if not jid:
        identity = (text['source'], text['url']) if text['url'] else (
            text['source'], text['title'], text['company'], text['location'])
        # Length prefixes prevent ambiguous concatenations of user-supplied text.
        identity = ''.join('{}:{}'.format(len(value), value) for value in identity)
        jid = 'sample-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]
    names = _skill_names(job.get('skills', []))
    if not names:
        names = tuple(skills_in(text['title'] + '\n' + text['description']))
    return _JobSample(JobExample(jid, text['title'], text['company']), names, bool(demo),
                      text['availability'].strip().casefold() == 'expired')


class LearningPlanner:
    """Build a deterministic plan while keeping corpus scope and evidence visible."""

    def __init__(self, graph=None):
        if graph is not None and not isinstance(graph, PrerequisiteGraph):
            raise ValueError('graph 必须是 PrerequisiteGraph。')
        self.graph = graph if graph is not None else PrerequisiteGraph()

    def build(self, jobs, profile, target='', limit=10):
        if not isinstance(jobs, (list, tuple)):
            raise ValueError('jobs 必须是岗位列表。')
        if not isinstance(profile, dict):
            raise ValueError('profile 必须是简历画像对象。')
        if not isinstance(target, str) or len(target) > 100:
            raise ValueError('目标职位须为不超过 100 个字符的字符串。')
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError('limit 必须是 1–20 的整数。')
        known = {name.casefold() for name in _skill_names(profile.get('skills', []))}
        samples = [_job_sample(job) for job in jobs]
        target = target.strip()
        demo_fallback = bool(samples) and all(sample.is_demo for sample in samples)
        eligible = [s for s in samples if demo_fallback or not s.is_demo]
        unique = {}
        for sample in eligible:
            unique.setdefault(sample.example.id, sample)  # First/latest input record wins.
        available = [s for s in unique.values() if not s.expired]
        selected = [s for s in available if target.casefold() in s.example.title.casefold()]

        counts, names, examples = Counter(), {}, {}
        for sample in selected:
            for skill in sample.skills:
                key = skill.casefold()
                names.setdefault(key, skill)
                counts[key] += 1
                examples.setdefault(key, [])
                if len(examples[key]) < 3:
                    examples[key].append(sample.example)

        ranked = sorted(counts, key=lambda key: (-counts[key], key))[:limit]
        rows, learning_order, scheduled = [], [], set()
        for key in ranked:
            name = names[key]
            prerequisites = self.graph.prerequisites(name)
            already_known = key in known
            steps = () if already_known else tuple(
                skill for skill in prerequisites + (name,) if skill.casefold() not in known)
            for skill in steps:
                if skill.casefold() not in scheduled:
                    scheduled.add(skill.casefold())
                    learning_order.append(skill)
            rows.append(SkillGap(name, counts[key], round(counts[key] * 100 / len(selected), 2),
                                 already_known, prerequisites, steps, tuple(examples[key])).to_dict())

        mode = 'demo' if demo_fallback else ('observed' if samples else 'empty')
        summary = '{}岗位样本 {} 条，识别 {} 种技能；展示频率最高的 {} 种，其中 {} 种未在简历技能中出现。'.format(
            '演示' if demo_fallback else '当前', len(selected), len(counts), len(rows),
            sum(not row['already_known'] for row in rows))
        if not selected:
            summary += '当前筛选没有可分析岗位，请调整职位名称或更新数据。'
        return {
            'summary': summary, 'skills': rows, 'learning_order': learning_order,
            'metrics': {
                'input_jobs': len(samples), 'excluded_demo_jobs': len(samples) - len(eligible),
                'duplicate_jobs': len(eligible) - len(unique), 'analyzed_jobs': len(selected),
                'excluded_expired_jobs': len(unique) - len(available),
                'jobs_with_skills': sum(bool(s.skills) for s in selected),
                'distinct_skills': len(counts), 'returned_skills': len(rows),
                'missing_skills': sum(not row['already_known'] for row in rows),
                'learning_steps': len(learning_order), 'target': target, 'limit': limit,
                'data_mode': mode, 'demo_fallback': demo_fallback,
                'prerequisite_source': 'authored_learning_suggestions',
                'limitations': ('频率仅描述筛选后去重岗位样本，不代表整个招聘市场；'
                                '技能来自结构化字段或关键词，可能漏报或误报。'
                                '先修顺序是人工编写的学习建议，并非雇主要求；'
                                '简历出现某技能不等于能力认证；已标记过期的岗位被排除，'
                                '其他岗位的实时有效性仍需到原站核实。'),
            },
        }


# Reusing the planner also reuses its bounded immutable prerequisite cache.
_PLANNER = LearningPlanner()


def build_learning_plan(jobs, profile, target='', limit=10):
    """Public JSON-ready API; does not modify jobs, resume data or stored state."""
    return _PLANNER.build(jobs, profile, target=target, limit=limit)
