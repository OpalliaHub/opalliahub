"""Read-only SQLite OLAP with typed dimensions, exact drilldown and real totals."""
import hashlib
import json
import re
import time
from contextlib import contextmanager

from .research import BITS, PROBES, WARNINGS, readonly, validate_plan


DIMENSIONS = {'month': '月份', 'quarter': '季度', 'year': '年份', 'sector': '职业类别', 'location': '地区'}
MEASURES = {'ads': ('广告数', '条'), 'employers': ('雇主标签数', '个'),
            'mentions': ('提及广告数', '条'), 'share_pct': ('全文提及率', '%')}
TEMPORAL = ('month', 'quarter', 'year')
_VALID_DATE = "CAST(strftime('%Y',published) AS INTEGER) BETWEEN 1 AND 9999 AND date(published,'+0 days')=substr(published,1,10)"
_EXPRESSIONS = {
    'month': "CASE WHEN " + _VALID_DATE + " THEN strftime('%Y-%m',published) ELSE 'Unknown' END",
    'quarter': "CASE WHEN " + _VALID_DATE + " THEN strftime('%Y',published)||'-Q'||CAST((CAST(strftime('%m',published) AS INTEGER)-1)/3+1 AS TEXT) ELSE 'Unknown' END",
    'year': "CASE WHEN " + _VALID_DATE + " THEN strftime('%Y',published) ELSE 'Unknown' END",
    'sector': "COALESCE(NULLIF(trim(sector),''),'Unknown')",
    'location': "COALESCE(NULLIF(trim(location),''),'Unknown')",
}
_EMPLOYERS = "COUNT(DISTINCT CASE WHEN lower(trim(company)) NOT IN ('','confidential','company confidential','unknown') THEN lower(trim(company)) END)"
_DATE_MEANING = '研究库按首个有效观察版本的来源标示日期分组；当前库按岗位来源标示日期分组。Unknown 保留缺失或不可解析日期，不把缺月当作零需求。'
_EMPLOYER_DEFINITION = '去掉空白及 confidential/unknown 占位值后，对去空格、小写化的雇主显示标签去重；不等于已核实的法人或招聘人数。'


def validate_query(raw):
    if not isinstance(raw, dict):
        raise ValueError('OLAP 指令必须是 JSON 对象。')
    allowed = {'dataset', 'dimensions', 'measure', 'concept', 'filters', 'exact_filters', 'dedup', 'limit', 'sort'}
    if set(raw) - allowed:
        raise ValueError('OLAP 指令含不支持的字段。')
    query = {'dataset': 'current', 'dimensions': ['month'], 'measure': 'ads', 'concept': 'python',
             'filters': {}, 'exact_filters': {}, 'dedup': 'id', 'limit': 50, 'sort': 'label'}
    query.update(raw)
    dimensions = query['dimensions']
    if (not isinstance(dimensions, list) or not 1 <= len(dimensions) <= 2
            or any(not isinstance(item, str) or item not in DIMENSIONS for item in dimensions)
            or len(set(dimensions)) != len(dimensions)):
        raise ValueError('请选择 1–2 个不同的合法分析维度。')
    if not isinstance(query['measure'], str) or query['measure'] not in MEASURES:
        raise ValueError('分析指标无效。')
    if type(query['limit']) is not int or not 1 <= query['limit'] <= 100:
        raise ValueError('结果分组数上限需为 1–100 的整数。')
    if query['sort'] not in ('label', 'value_desc'):
        raise ValueError('排序仅支持 label 或 value_desc。')
    plan = validate_plan({key: query[key] for key in ('dataset', 'concept', 'filters', 'dedup', 'limit')})
    query['filters'] = plan['filters']
    exact = query['exact_filters']
    if not isinstance(exact, dict) or any(key not in DIMENSIONS for key in exact):
        raise ValueError('精确筛选只接受已定义的维度。')
    for dimension, value in exact.items():
        if not isinstance(value, str) or not 1 <= len(value) <= 150:
            raise ValueError('精确筛选值须为 1–150 个字符。')
        if value == 'Unknown' or dimension not in TEMPORAL:
            continue
        pattern = {'month': r'[0-9]{4}-(?:0[1-9]|1[0-2])',
                   'quarter': r'[0-9]{4}-Q[1-4]', 'year': r'[0-9]{4}'}[dimension]
        if not re.fullmatch(pattern, value) or value.startswith('0000'):
            raise ValueError('精确时间维度值无效。')
    return json.loads(json.dumps(query, ensure_ascii=False, allow_nan=False))


def _totals(row):
    ads, employers, mentions = int(row['ads']), int(row['employers']), int(row['mentions'])
    return {'ads': ads, 'employers': employers, 'mentions': mentions,
            'share_pct': round(100 * mentions / ads, 4) if ads else None}


def build_pivot(rows, dimensions):
    """Pivot displayed groups only; absent/truncated intersections remain null."""
    if len(dimensions) != 2:
        return None
    first, second = dimensions
    row_labels = sorted({row[first] for row in rows})
    column_labels = sorted({row[second] for row in rows})
    lookup = {(row[first], row[second]): row['value'] for row in rows}
    return {'row_dimension': first, 'column_dimension': second, 'row_labels': row_labels,
            'column_labels': column_labels,
            'values': [[lookup.get((row, column)) for column in column_labels] for row in row_labels]}


class OLAP:
    def __init__(self, research):
        self.research = research

    @contextmanager
    def _connection(self, dataset, include_mask=True):
        with self.research.lock:
            if dataset == 'research':
                status = self.research.status()
                if not status.get('ready'):
                    raise ValueError('研究分析索引尚未就绪，请先连接数据并构建索引，或选择当前岗位库。')
                connection = readonly(self.research.root / 'research.sqlite')
                fingerprint = self.research.fingerprint()
                updated_at = status.get('index', {}).get('built_at')
            else:
                connection = self.research._current(include_mask=include_mask)
                fingerprint = None
                if include_mask:
                    digest = hashlib.sha256()
                    # Hash the same snapshot used by queries. Metadata-only
                    # catalogs omit the incomplete projection's fingerprint.
                    for row in connection.execute('SELECT * FROM ads ORDER BY id'):
                        digest.update(json.dumps(tuple(row), ensure_ascii=False).encode('utf-8'))
                        digest.update(b'\n')
                    fingerprint = digest.hexdigest()
                updated_at = connection.execute('SELECT MAX(observed) FROM ads').fetchone()[0]
            try:
                yield connection, fingerprint, updated_at
            finally:
                connection.close()

    def _scope(self, query):
        plan = validate_plan({key: query[key] for key in ('dataset', 'concept', 'filters', 'dedup', 'limit')})
        selection, args = self.research._selection(plan)
        dimensions = ','.join(expression + ' AS d_' + key for key, expression in _EXPRESSIONS.items())
        clauses, exact_args = [], []
        for key in sorted(query['exact_filters']):
            clauses.append('d_' + key + '=?')
            exact_args.append(query['exact_filters'][key])
        cte = ('WITH selected AS (' + selection + '), dimensional AS (SELECT *,' + dimensions
               + ' FROM selected), scoped AS (SELECT * FROM dimensional WHERE '
               + (' AND '.join(clauses) if clauses else '1=1') + ') ')
        return cte, tuple(args) + tuple(exact_args)

    def run(self, raw):
        query = validate_query(raw)
        started = time.monotonic()
        cte, parameters = self._scope(query)
        count_sql = 'COUNT(*) ads,' + _EMPLOYERS + ' employers,COALESCE(SUM((mask & ?)!=0),0) mentions'
        columns = ','.join('d_' + key for key in query['dimensions'])
        labels = ','.join('d_' + key + ' AS ' + key for key in query['dimensions'])
        label_sort = ','.join(key + ' COLLATE NOCASE ASC,' + key + ' ASC' for key in query['dimensions'])
        ordering = (query['measure'] + ' DESC,' if query['sort'] == 'value_desc' else '') + label_sort
        with self._connection(query['dataset']) as (connection, fingerprint, updated_at):
            totals = _totals(connection.execute(cte + 'SELECT ' + count_sql + ' FROM scoped',
                                                parameters + (BITS[query['concept']],)).fetchone())
            total_groups = connection.execute(cte + 'SELECT COUNT(*) FROM (SELECT 1 FROM scoped GROUP BY '
                                              + columns + ')', parameters).fetchone()[0]
            sql = (cte + ', grouped AS (SELECT ' + labels + ',' + count_sql + ' FROM scoped GROUP BY '
                   + columns + ') SELECT *,CASE WHEN ads>0 THEN ROUND(100.0*mentions/ads,4) END share_pct '
                   + 'FROM grouped ORDER BY ' + ordering + ' LIMIT ?')
            rows = [dict(row) for row in connection.execute(sql, parameters + (BITS[query['concept']], query['limit']))]
        for row in rows:
            row.update(_totals(row))
            row['value'] = row[query['measure']]
        warnings = list(WARNINGS)
        if query['dataset'] == 'current':
            warnings.append('当前库排除演示广告；它是可变的最新状态，不能当作完整纵向历史，职业类别可能为 Unknown。')
        if query['filters'].get('common_only') is not True:
            warnings.append('未限定共同三类，跨期差异可能受到类别覆盖变化影响。')
        if total_groups > len(rows):
            warnings.append('图表只显示部分分组；总体指标独立计算，不能由当前图表求和还原。')
        return {'query': query, 'rows': rows, 'totals': totals, 'pivot': build_pivot(rows, query['dimensions']),
                'metadata': {'fingerprint': fingerprint, 'truncated': total_groups > len(rows),
                             'total_groups': total_groups, 'returned_groups': len(rows), 'warnings': warnings,
                             'date_meaning': _DATE_MEANING, 'employer_definition': _EMPLOYER_DEFINITION,
                             'updated_at': updated_at, 'elapsed_seconds': round(time.monotonic() - started, 4),
                             'label_source': 'rule_derived', 'unknown_bucket': 'Unknown',
                             'pivot_scope': 'displayed_groups_only'}}

    def catalog(self, dataset=None):
        if dataset is not None and dataset not in ('research', 'current'):
            raise ValueError('数据集无效。')
        status = self.research.status()
        ready = bool(status.get('ready'))
        default = 'research' if ready else 'current'
        selected = dataset or default
        datasets, facets = [], {key: [] for key in DIMENSIONS}
        for name, label, available in [('research', 'JobsDB 纵向研究库', ready), ('current', '当前岗位样本', True)]:
            item = {'id': name, 'label': label, 'available': available}
            if not available:
                item['reason'] = '研究索引尚未就绪；可先使用当前岗位样本。'
                datasets.append(item)
                continue
            if name != selected:
                # Switching datasets requests a new catalog; cold startup does
                # not build or scan a dataset the visitor has not selected.
                if name == 'research':
                    index = status.get('index', {})
                    if type(index.get('rows')) is int and index['rows'] >= 0:
                        item['ads'] = index['rows']
                    if index.get('built_at'):
                        item['updated_at'] = index['built_at']
                datasets.append(item)
                continue
            with self._connection(name, include_mask=False) as (connection, fingerprint, updated_at):
                row = connection.execute('SELECT COUNT(*) ads,' + _EMPLOYERS + ' employers,'
                    'MIN(CASE WHEN ' + _VALID_DATE + ' THEN substr(published,1,10) END) first_date,'
                    'MAX(CASE WHEN ' + _VALID_DATE + ' THEN substr(published,1,10) END) last_date FROM ads').fetchone()
                item.update(ads=row['ads'], employers=row['employers'],
                            date_range=[row['first_date'], row['last_date']], updated_at=updated_at)
                if fingerprint is not None:
                    item['fingerprint'] = fingerprint
                if name == selected:
                    for dimension, expression in _EXPRESSIONS.items():
                        rows = connection.execute('SELECT ' + expression + ' value,COUNT(*) ads FROM ads '
                            'GROUP BY value ORDER BY ads DESC,value COLLATE NOCASE,value LIMIT 50')
                        facets[dimension] = [dict(row) for row in rows]
            datasets.append(item)
        return {'dataset': selected, 'default_dataset': default, 'datasets': datasets,
                'dimensions': [{'id': key, 'label': label} for key, label in DIMENSIONS.items()],
                'measures': [{'id': key, 'label': value[0], 'unit': value[1]} for key, value in MEASURES.items()],
                'concepts': [{'id': key, 'label': key.replace('_', ' ')} for key in PROBES],
                'facets': facets, 'facet_limit': 50, 'date_meaning': _DATE_MEANING}
