"""Offline evidence and personalized recommendation behavior, using fictional CVs."""
import copy
import json
import unittest
from unittest.mock import patch

from jobcompass.recommendations import analyze_strengths, build_recommendations, validate_options


CV = '计算机本科毕业。拥有 2 年工作经验。项目中使用 SQL 完成销售报表并自动化数据清洗。技能列表：Python、SQL、Git。'


def job(jid, skills, **changes):
    row = {'id': jid, 'title': 'Data Analyst', 'company': 'Fictional Ltd', 'source': 'test',
           'description': 'Data analysis SQL reporting. Bachelor degree. 2 years experience.',
           'skills': skills, 'location': 'Hong Kong', 'url': '', 'is_demo': False, 'availability': 'active'}
    row.update(changes)
    return row


class StrengthTests(unittest.TestCase):
    def test_target_job_lines_are_goals_not_existing_skills(self):
        for heading in ('求职意向：', '目标岗位：', 'Objective: ', 'Seeking a '):
            with self.subTest(heading=heading):
                profile = analyze_strengths(heading + 'Python Developer. Built SQL reporting dashboards and documented the project results.')
                self.assertNotIn('Python', profile['skills'])
                self.assertIn('SQL', profile['skills'])
                self.assertEqual(next(row['status'] for row in profile['excluded_skills'] if row['skill'] == 'Python'), 'aspirational')

    def test_positive_denied_and_aspirational_skills_have_separate_statuses(self):
        text = '计算机本科毕业。不会 Java，也没有 Python 经验。计划学习 Docker。项目中已使用 SQL 完成销售报表，并使用 Excel 进行核对。'
        profile = analyze_strengths(text)
        self.assertIn('SQL', profile['skills'])
        self.assertIn('Excel', profile['skills'])
        self.assertNotIn('Java', profile['skills'])
        self.assertNotIn('Python', profile['skills'])
        self.assertNotIn('Docker', profile['skills'])
        excluded = {row['skill']: row['status'] for row in profile['excluded_skills']}
        self.assertEqual(excluded['Docker'], 'aspirational')
        self.assertEqual(excluded['Python'], 'denied')

    def test_english_negation_scope_does_not_erase_an_actual_other_skill(self):
        profile = analyze_strengths('Bachelor degree. No experience with Python or Java, but used SQL to build reporting dashboards. Hope to learn Docker.')
        self.assertEqual(profile['skills'], ['SQL'])

    def test_not_only_is_not_negation_and_bare_negative_lists_propagate(self):
        positive = analyze_strengths('Built a reporting project with not only Python but also SQL, and documented the practical work in a portfolio.')
        self.assertTrue({'Python', 'SQL'}.issubset(positive['skills']))
        negative = analyze_strengths('No Python, Java or Docker experience. Used SQL to build a reporting project and document its workflow.')
        self.assertEqual(negative['skills'], ['SQL'])

    def test_strength_evidence_is_a_local_verbatim_excerpt_and_not_mastery_claim(self):
        profile = analyze_strengths(CV)
        self.assertTrue(profile['strengths'])
        self.assertTrue(any(row['kind'] == 'project' for row in profile['strengths']))
        for row in profile['strengths']:
            self.assertTrue(row['id'])
            for evidence in row['evidence']:
                self.assertIn(evidence, CV)
            self.assertNotIn('精通', row['title'])

    def test_nontechnical_actual_work_has_evidence_and_role_features(self):
        profile = analyze_strengths('Human resources experience. Managed recruitment interviews and employee onboarding. Coordinated training and payroll for a growing team.')
        self.assertTrue(any(row['kind'] in ('experience', 'project') for row in profile['strengths']))
        self.assertTrue(profile['professional_domains'])

    def test_explicit_personal_identity_lines_do_not_become_strengths(self):
        text = 'Name: Python Java\nAge: 35\nGender: female\nNationality: English\nEmail: candidate@example.test\nBuilt SQL reporting dashboards and documented the project workflow.'
        profile = analyze_strengths(text)
        self.assertEqual(profile['skills'], ['SQL'])
        self.assertTrue(all('candidate@example.test' not in str(row) for row in profile['strengths']))

    def test_skill_heading_nouns_are_not_practical_actions(self):
        profile = analyze_strengths('计算机本科毕业，目前希望寻找合适的初级岗位。技能：Python、SQL、数据分析、项目管理。')
        self.assertTrue(profile['strengths'])
        self.assertTrue(all(row['kind'] == 'skill' for row in profile['strengths']))
        actual = analyze_strengths('计算机本科毕业，目前寻找合适的初级岗位。技能：在项目中使用 Python 完成数据分析。')
        self.assertTrue(any(row['kind'] == 'project' for row in actual['strengths']))

    def test_conflicting_skill_does_not_leave_an_empty_practical_strength(self):
        profile = analyze_strengths('I used Python in a project. I have no Python experience. This resume needs the conflicting description clarified.')
        self.assertNotIn('Python', profile['skills'])
        self.assertEqual(profile['strengths'], [])
        self.assertEqual(profile['excluded_skills'][0]['status'], 'conflicting')


class RecommendationTests(unittest.TestCase):
    def test_actual_project_evidence_outweighs_an_equal_generic_skill_mention(self):
        jobs = [job('python', ['Python'], title='Python Developer', description='Python software development.'),
                job('sql', ['SQL'], title='SQL Developer', description='SQL software development.')]
        result = build_recommendations('Computer science graduate. Skills: Python, SQL. Built a project using SQL and documented the implementation.', jobs)
        self.assertEqual(result['jobs'][0]['id'], 'sql')
        row = result['jobs'][0]
        self.assertTrue(any(match['skill'] == 'SQL' for match in row['evidence_matches']))
        self.assertGreater(next(part['value'] for part in row['breakdown'] if part['key'] == 'project_evidence'), 0)

    def test_multiple_real_skills_fit_better_than_a_single_generic_overlap(self):
        text = 'Built Python and SQL reporting dashboards using Pandas. Delivered automated data analysis and documented project outcomes. English communication skills.'
        result = build_recommendations(text, [job('related', ['Python', 'SQL', 'Pandas']),
            job('generic', ['English'], title='Content Writer', description='English writing and editing.')])
        self.assertEqual(result['jobs'][0]['id'], 'related')
        self.assertGreater(result['jobs'][0]['score'], result['jobs'][1]['score'])

    def test_all_scores_bounded_deterministic_and_breakdown_reconciles(self):
        jobs = [job('1', ['SQL', 'Python']), job('2', ['Java']), job('3', [])]
        first = build_recommendations(CV, jobs, {'location': 'Hong Kong', 'experience_years': 2}, {'target_role': 'Data Analyst'})
        self.assertEqual(first, build_recommendations(CV, jobs, {'location': 'Hong Kong', 'experience_years': 2}, {'target_role': 'Data Analyst'}))
        for row in first['jobs']:
            self.assertTrue(0 <= row['score'] <= 100)
            self.assertTrue(0 <= row['baseline_score'] <= 100)
            self.assertTrue(0 <= row['effective_coverage'] <= 100)
            self.assertAlmostEqual(row['score'], sum(part['contribution'] for part in row['breakdown']), delta=0.2)
            self.assertAlmostEqual(sum(part['weight'] for part in row['breakdown']), 100, delta=0.2)
        json.dumps(first, allow_nan=False)

    def test_nontechnical_recruitment_work_ranks_relevant_work_above_software(self):
        text = 'Managed recruitment interviews and onboarding. Coordinated payroll, employee training and human resources operations across departments.'
        result = build_recommendations(text, [job('hr', [], title='HR Coordinator', description='Recruitment onboarding payroll training and human resources operations.'),
            job('dev', ['Java'], title='Java Developer', description='Java software development Docker Kubernetes.')])
        self.assertEqual(result['jobs'][0]['id'], 'hr')
        self.assertFalse(result['jobs'][0]['weak_signal'])

    def test_changing_only_identity_fields_does_not_change_scores_or_order(self):
        jobs = [job('a', ['SQL']), job('b', ['Python'])]
        a = 'Name: Jane Doe\nAge: 24\nGender: female\nNationality: Canadian\nDOB: 2002-01-01\n' + CV
        b = 'Name: John Smith\nAge: 58\nGender: male\nNationality: Chinese\nDOB: 1968-12-31\n' + CV
        first, second = build_recommendations(a, jobs), build_recommendations(b, jobs)
        self.assertEqual([(row['id'], row['score']) for row in first['jobs']], [(row['id'], row['score']) for row in second['jobs']])

    def test_expiry_url_dedup_demo_and_missing_status_are_explained(self):
        jobs = [job('1', ['SQL'], url='https://EXAMPLE.test/jobs/1/?utm_source=a#apply'),
                job('2', ['SQL'], source='another', url='http://example.test/jobs/1'),
                job('3', ['SQL'], availability='expired'), job('4', ['SQL'], is_demo=True),
                job('5', ['SQL'], availability='')]
        result = build_recommendations(CV, jobs)
        self.assertEqual(result['summary']['excluded_duplicates'], 1)
        self.assertEqual(result['summary']['excluded_expired'], 1)
        self.assertEqual(result['summary']['excluded_demo'], 1)
        self.assertEqual(result['summary']['eligible'], 2)
        self.assertTrue(next(row for row in result['jobs'] if row['id'] == '5')['warnings'])

    def test_expired_newest_duplicate_does_not_resurrect_older_active_copy(self):
        result = build_recommendations(CV, [job('1', ['SQL'], url='https://example.test/1', availability='expired'),
                                           job('2', ['SQL'], url='https://example.test/1', availability='active')])
        self.assertEqual(result['jobs'], [])

    def test_past_expiry_timestamp_excludes_record_even_if_marked_active(self):
        result = build_recommendations(CV, [job('old', ['SQL'], expires_at='2000-01-01T00:00:00Z')])
        self.assertEqual(result['jobs'], [])
        self.assertEqual(result['summary']['excluded_expired'], 1)

    def test_naive_expiry_has_an_explicit_conservative_policy(self):
        for date in ('2000-01-01', '2000-01-01T00:00:00'):
            with self.subTest(date=date):
                result = build_recommendations(CV, [job('old', ['SQL'], expires_at=date)])
                self.assertEqual(result['jobs'], [])
                self.assertEqual(result['summary']['excluded_expired'], 1)
        future = build_recommendations(CV, [job('future', ['SQL'], expires_at='2999-01-01')])['jobs'][0]
        self.assertEqual(future['availability'], 'unknown')
        self.assertTrue(any('时区' in warning for warning in future['warnings']))

    def test_soft_location_preference_retains_mismatch_warning(self):
        result = build_recommendations(CV, [job('us', ['SQL'], location='United States')], {'location': 'Hong Kong'})
        self.assertEqual(len(result['jobs']), 1)
        self.assertTrue(any('地区' in warning for warning in result['jobs'][0]['warnings']))

    def test_application_notes_and_status_do_not_affect_ranking_or_evidence(self):
        first = build_recommendations(CV, [job('one', ['SQL'], note='Python Java expert', status='applied')])
        second = build_recommendations(CV, [job('one', ['SQL'], note='recruitment payroll training', status='rejected')])
        for field in ('score', 'baseline_score', 'breakdown', 'evidence_matches', 'weak_signal'):
            self.assertEqual(first['jobs'][0][field], second['jobs'][0][field])

    def test_evidence_references_only_bounded_visible_strength_cards(self):
        text = ' '.join('Built Python project number {}.'.format(index) for index in range(18)) + ' Built SQL project later.'
        result = build_recommendations(text, [job('sql', ['SQL'])])
        cards = result['profile']['strengths']
        self.assertLessEqual(len(cards), 12)
        visible = {row['id'] for row in cards}
        for match in result['jobs'][0]['evidence_matches']:
            self.assertTrue(set(match['strength_ids']) <= visible)

    def test_demo_only_corpus_and_explicit_include_demo_are_labeled(self):
        result = build_recommendations(CV, [job('d', ['SQL'], is_demo=True)])
        self.assertTrue(result['summary']['demo_fallback'])
        self.assertEqual(result['summary']['data_mode'], 'demo')
        mixed = build_recommendations(CV, [job('d', ['SQL'], is_demo=True), job('r', ['SQL'])], options={'include_demo': True})
        self.assertEqual(mixed['summary']['returned'], 2)
        self.assertEqual(mixed['summary']['data_mode'], 'mixed')

    def test_strict_location_does_not_treat_remote_as_worldwide(self):
        result = build_recommendations(CV, [job('us', ['SQL'], location='United States', remote=True),
            job('global', ['SQL'], location='Worldwide'), job('hk', ['SQL'])],
            {'location': 'Hong Kong'}, {'strict_location': True})
        self.assertEqual({row['id'] for row in result['jobs']}, {'global', 'hk'})
        self.assertEqual(result['summary']['excluded_location'], 1)

    def test_unknown_evidence_is_weak_not_certified_fit_and_minimum_is_explicit(self):
        text = 'I am seeking a new professional opportunity. More details about my previous work will be added to this document later.'
        result = build_recommendations(text, [job('j', ['Java'], title='Java Developer', description='Java development.')])
        self.assertTrue(result['jobs'][0]['weak_signal'])
        self.assertTrue(result['jobs'][0]['unknown_fields'])
        filtered = build_recommendations(text, [job('j', ['Java'])], options={'min_score': 100})
        self.assertEqual(filtered['jobs'], [])
        self.assertTrue(filtered['summary']['empty_reason'])
        self.assertEqual(filtered['summary']['excluded_min_score'], 1)

    def test_inputs_are_unchanged_and_ranker_runs_once(self):
        from jobcompass.matching import rank_jobs
        jobs, prefs, options = [job('1', ['SQL'])], {'location': 'Hong Kong'}, {'limit': 1}
        before = copy.deepcopy((jobs, prefs, options))
        with patch('jobcompass.recommendations.rank_jobs', wraps=rank_jobs) as rank:
            build_recommendations(CV, jobs, prefs, options)
        self.assertEqual(rank.call_count, 1)
        self.assertEqual((jobs, prefs, options), before)

    def test_invalid_options_and_preferences_fail_without_ranking(self):
        bad = [{'limit': True}, {'limit': 0}, {'limit': 31}, {'target_role': 3}, {'target_role': 'x' * 101},
               {'min_score': -1}, {'min_score': 101}, {'min_score': float('nan')}, {'min_score': True},
               {'strict_location': 'yes'}, {'include_demo': 1}, {'sql': 'SELECT 1'}, []]
        for options in bad:
            with self.subTest(options=options), self.assertRaises(ValueError):
                validate_options(options)
        for prefs in ({'age': 22}, {'experience_years': True}, {'experience_years': -1}, {'location': []}):
            with self.subTest(prefs=prefs), self.assertRaises(ValueError):
                build_recommendations(CV, [], prefs)
        with self.assertRaises(ValueError):
            build_recommendations(CV, [], options={'strict_location': True})


if __name__ == '__main__':
    unittest.main()
