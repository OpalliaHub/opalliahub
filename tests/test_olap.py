"""Real SQLite cube tests: denominators, groups, drilldown and read-only scope."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jobcompass.olap import OLAP, validate_query
from jobcompass.research import BITS, Research, mask_for
from jobcompass.storage import Store


class OLAPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'app.db')
        self.research = Research(self.store)
        self.path = self.research.root / 'research.sqlite'
        empty = self.research._current()
        with sqlite3.connect(str(self.path)) as destination:
            empty.backup(destination)
            fixtures = [
                ('1', 'Data Engineer', 'Alpha', 'Engineering', 'Hong Kong', '2026-01-10', '2026-01-11', 'same', BITS['python']),
                ('2', 'Data Analyst', 'Beta', 'Information & Communication Technology', 'Hong Kong', '2026-01-20', '2026-01-21', 'two', BITS['sql']),
                ('3', 'Teacher', 'Alpha', 'Education & Training', 'Kowloon', '2026-01-25', '2026-01-26', 'three', BITS['sql']),
                ('4', 'Data Engineer', 'Alpha', 'Engineering', 'Hong Kong', '2026-02-10', '2026-02-11', 'same', BITS['python']),
                ('5', 'Unknown Date', '', '', '', '', '2026-03-01', 'five', BITS['sql']),
            ]
            for jid, title, company, sector, location, published, observed, family, mask in fixtures:
                destination.execute('INSERT INTO ads VALUES (' + ','.join('?' * 15) + ')',
                    (jid, title, company, sector, location, '', published, observed, observed, family, mask, 1, jid, jid, 1))
        empty.close()
        self.status_patch = patch.object(self.research, 'status', return_value={'ready': True, 'index': {'built_at': '2026-11-18T12:00:00Z'}})
        self.fingerprint_patch = patch.object(self.research, 'fingerprint', return_value='fixture-fingerprint')
        self.status_patch.start()
        self.fingerprint_patch.start()
        self.olap = OLAP(self.research)

    def tearDown(self):
        self.fingerprint_patch.stop()
        self.status_patch.stop()
        self.temp.cleanup()

    def query(self, **changes):
        query = {'dataset': 'research', 'dimensions': ['month'], 'measure': 'share_pct', 'concept': 'python'}
        query.update(changes)
        return self.olap.run(query)

    def test_total_rate_is_weighted_by_ads_and_distinct_employers_are_not_summed(self):
        result = self.query(filters={'start': '2026-01-01', 'end': '2026-02-28'})
        self.assertEqual(result['totals'], {'ads': 4, 'employers': 2, 'mentions': 2, 'share_pct': 50.0})
        self.assertEqual([row['ads'] for row in result['rows']], [3, 1])
        self.assertAlmostEqual(result['rows'][0]['share_pct'], 33.3333)
        self.assertEqual(sum(row['employers'] for row in result['rows']), 3)
        self.assertEqual(result['rows'][1]['value'], 100.0)

    def test_missing_month_is_explicit_and_kept_in_total_denominator(self):
        result = self.query()
        self.assertEqual(result['totals']['ads'], 5)
        self.assertEqual(result['totals']['share_pct'], 40.0)
        missing = next(row for row in result['rows'] if row['month'] == 'Unknown')
        self.assertEqual((missing['ads'], missing['mentions'], missing['share_pct']), (1, 0, 0.0))

    def test_quarter_and_year_grouping(self):
        for dimension, expected in [('quarter', '2026-Q1'), ('year', '2026')]:
            with self.subTest(dimension=dimension):
                result = self.query(dimensions=[dimension])
                row = next(row for row in result['rows'] if row[dimension] == expected)
                self.assertEqual((row['ads'], row['mentions']), (4, 2))

    def test_quarter_boundaries_cross_years_correctly(self):
        with sqlite3.connect(str(self.path)) as connection:
            for jid, date in [('1', '2025-12-31'), ('2', '2026-03-31'), ('3', '2026-04-01'), ('4', '2026-10-01')]:
                connection.execute('UPDATE ads SET published=? WHERE id=?', (date, jid))
        result = self.query(dimensions=['quarter'])
        self.assertEqual([row['quarter'] for row in result['rows']], ['2025-Q4', '2026-Q1', '2026-Q2', '2026-Q4', 'Unknown'])

    def test_impossible_dates_are_unknown_instead_of_false_month_groups(self):
        with sqlite3.connect(str(self.path)) as connection:
            connection.execute("UPDATE ads SET published='2026-02-30' WHERE id='1'")
            connection.execute("UPDATE ads SET published='0000-01-01' WHERE id='2'")
        result = self.query(exact_filters={'month': 'Unknown'})
        self.assertEqual(result['totals']['ads'], 3)

    def test_limit_does_not_change_totals_or_total_group_count(self):
        result = self.query(measure='ads', sort='value_desc', limit=1)
        self.assertEqual(len(result['rows']), 1)
        self.assertEqual(result['rows'][0]['month'], '2026-01')
        self.assertEqual(result['totals']['ads'], 5)
        self.assertEqual(result['metadata']['total_groups'], 3)
        self.assertTrue(result['metadata']['truncated'])

    def test_value_sort_uses_selected_measure(self):
        result = self.query(sort='value_desc')
        self.assertEqual([row['month'] for row in result['rows']], ['2026-02', '2026-01', 'Unknown'])

    def test_exact_filters_support_drilldown_and_missing_bucket(self):
        result = self.query(exact_filters={'sector': 'Engineering', 'month': '2026-02'})
        self.assertEqual(result['totals']['ads'], 1)
        self.assertEqual(result['totals']['share_pct'], 100.0)
        missing = self.query(exact_filters={'month': 'Unknown', 'location': 'Unknown'})
        self.assertEqual(missing['totals']['ads'], 1)
        self.assertEqual(missing['totals']['employers'], 0)

    def test_two_dimensions_return_pivot_without_filling_missing_cells_with_zero(self):
        result = self.query(dimensions=['month', 'sector'], measure='mentions')
        pivot = result['pivot']
        row = pivot['row_labels'].index('2026-02')
        column = pivot['column_labels'].index('Engineering')
        self.assertEqual(pivot['values'][row][column], 1)
        absent = pivot['column_labels'].index('Education & Training')
        self.assertIsNone(pivot['values'][row][absent])
        january = pivot['row_labels'].index('2026-01')
        self.assertEqual(pivot['values'][january][absent], 0)

    def test_empty_cohort_has_zero_counts_and_unknown_rate(self):
        result = self.query(filters={'title': 'not present'})
        self.assertEqual(result['rows'], [])
        self.assertEqual(result['totals'], {'ads': 0, 'employers': 0, 'mentions': 0, 'share_pct': None})
        self.assertEqual(result['metadata']['total_groups'], 0)
        self.assertFalse(result['metadata']['truncated'])

    def test_shared_family_dedup_keeps_first_global_record_before_date_filter(self):
        result = self.query(dedup='family', filters={'start': '2026-02-01'})
        self.assertEqual(result['totals']['ads'], 0)

    def test_filters_are_parameters_and_read_only_source_is_unchanged(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        for value in ("' OR 1=1 --", '%', 'Engineering\"; DROP TABLE ads; --'):
            self.assertEqual(self.query(exact_filters={'sector': value})['totals']['ads'], 0)
            self.assertEqual(self.query(filters={'title': value})['totals']['ads'], 0)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_current_dataset_excludes_demo_and_returns_only_aggregates(self):
        self.store.upsert_jobs([
            {'title': 'PRIVATE_TITLE', 'company': 'PRIVATE_COMPANY', 'description': 'Python PRIVATE_BODY',
             'source': 'test', 'location': 'Hong Kong', 'published_at': '2026-01-02'},
            {'title': 'Demo', 'company': 'Demo', 'description': 'Python', 'source': 'test', 'is_demo': True},
        ])
        result = self.query(dataset='current')
        self.assertEqual(result['totals']['ads'], 1)
        self.assertNotIn('PRIVATE_', str(result))
        self.assertEqual(result['rows'][0]['month'], '2026-01')

    def test_employer_labels_are_normalized_without_counting_placeholders(self):
        with sqlite3.connect(str(self.path)) as connection:
            connection.execute("UPDATE ads SET company=' alpha ' WHERE id='2'")
            connection.execute("UPDATE ads SET company='CONFIDENTIAL' WHERE id='3'")
        self.assertEqual(self.query()['totals']['employers'], 1)

    def test_current_fingerprint_changes_with_source_body_and_uses_same_snapshot(self):
        job = {'title': 'Role', 'company': 'A', 'description': 'Python', 'source': 'test',
               'url': 'https://example.test/job/1'}
        self.store.upsert_jobs([job])
        first = self.query(dataset='current')
        job['description'] = 'SQL'
        self.store.upsert_jobs([job])
        second = self.query(dataset='current')
        self.assertNotEqual(first['metadata']['fingerprint'], second['metadata']['fingerprint'])
        self.assertEqual((first['totals']['mentions'], second['totals']['mentions']), (1, 0))

    def test_catalog_has_labels_availability_and_bounded_facets(self):
        catalog = self.olap.catalog('research')
        self.assertEqual(catalog['dataset'], 'research')
        self.assertEqual({row['id'] for row in catalog['dimensions']}, {'month', 'quarter', 'year', 'sector', 'location'})
        self.assertTrue(next(row for row in catalog['datasets'] if row['id'] == 'research')['available'])
        self.assertEqual(next(row for row in catalog['datasets'] if row['id'] == 'research')['ads'], 5)
        self.assertTrue(all(len(rows) <= 50 for rows in catalog['facets'].values()))
        self.assertEqual(next(row for row in catalog['facets']['sector'] if row['value'] == 'Engineering')['ads'], 2)
        self.assertNotIn(str(self.path), str(catalog))

    def test_unavailable_research_has_no_false_zero_count(self):
        with patch.object(self.research, 'status', return_value={'ready': False, 'index': {}}):
            catalog = self.olap.catalog()
            research = next(row for row in catalog['datasets'] if row['id'] == 'research')
            self.assertFalse(research['available'])
            self.assertNotIn('ads', research)
            self.assertEqual(catalog['default_dataset'], 'current')
            with self.assertRaises(ValueError):
                self.query()

    def test_facets_are_limited_independently_of_dataset_counts(self):
        self.store.upsert_jobs([{'title': 'Role ' + str(i), 'company': 'A', 'description': 'Python',
                                'source': 'test', 'location': 'Location {:02d}'.format(i)} for i in range(61)])
        catalog = self.olap.catalog('current')
        self.assertEqual(len(catalog['facets']['location']), 50)
        self.assertEqual(next(item for item in catalog['datasets'] if item['id'] == 'current')['ads'], 61)

    def test_catalog_does_not_build_unselected_current_snapshot(self):
        with patch.object(self.research, '_current', side_effect=AssertionError('Unselected snapshot was built')):
            catalog = self.olap.catalog('research')
        current = next(item for item in catalog['datasets'] if item['id'] == 'current')
        self.assertTrue(current['available'])
        self.assertNotIn('employers', current)

    def test_selected_current_catalog_skips_probe_matching_but_query_does_not(self):
        self.store.upsert_jobs([{'title': 'Role', 'company': 'A', 'description': 'Python', 'source': 'test'}])
        with patch('jobcompass.research.mask_for', side_effect=AssertionError('Catalog scanned probes')):
            catalog = self.olap.catalog('current')
        selected = next(item for item in catalog['datasets'] if item['id'] == 'current')
        self.assertEqual(selected['ads'], 1)
        self.assertNotIn('fingerprint', selected)
        with patch('jobcompass.research.mask_for', wraps=mask_for) as matcher:
            result = self.query(dataset='current')
        self.assertEqual(matcher.call_count, 1)
        self.assertEqual(result['totals']['mentions'], 1)
        self.assertTrue(result['metadata']['fingerprint'])


class OLAPValidationTests(unittest.TestCase):
    def test_validation_rejects_instructions_outside_closed_query_language(self):
        invalid = [{'sql': 'SELECT * FROM jobs'}, {'dimensions': []}, {'dimensions': 'month'},
                   {'dimensions': ['month', 'month']}, {'dimensions': ['month', 'sector', 'location']},
                   {'dimensions': [['month']]}, {'dimensions': ['company']}, {'measure': 'salary'},
                   {'concept': 'unknown'}, {'limit': True}, {'limit': 101}, {'limit': 0}, {'sort': 'random'},
                   {'dataset': 'other'}, {'filters': {'path': '/tmp/file'}}, {'exact_filters': {'title': 'Developer'}},
                   {'exact_filters': {'month': '2026-13'}}, {'exact_filters': {'quarter': '2026-Q5'}},
                   {'exact_filters': {'year': '0000'}}, {'exact_filters': {'sector': ['Engineering']}},
                   {'filters': {'start': '2026-02-30'}}, {'dedup': 'none'}]
        for query in invalid:
            with self.subTest(query=query), self.assertRaises(ValueError):
                validate_query(query)

    def test_validation_returns_independent_normalized_query(self):
        raw = {'dimensions': ['sector'], 'filters': {'title': 'Data'}}
        normalized = validate_query(raw)
        normalized['filters']['title'] = 'changed'
        self.assertEqual(raw['filters']['title'], 'Data')
        self.assertEqual(normalized['measure'], 'ads')
        self.assertEqual(normalized['exact_filters'], {})


if __name__ == '__main__':
    unittest.main()
