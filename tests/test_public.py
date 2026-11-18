"""Anonymous visitor isolation and shared resource budgets, with synthetic data."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.request import Request, ProxyHandler
from concurrent.futures import ThreadPoolExecutor

from jobcompass.public import (SessionStore, SessionManager, RateLimiter, PublicConfig, sanitize_public,
                              validate_page_url, PublicRedirect, collect_public_page, fetch_public_page)
from jobcompass.storage import Store, now

JOB = {'source':'JobsDB historical','title':'Python developer','company':'Demo',
       'description':'Python SQL developer required','url':'https://hk.jobsdb.com/job/1','skills':['Python']}


class VisitorStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = Store(self.root / 'base.sqlite')
        self.base.upsert_jobs([JOB])
        self.jid = self.base.jobs()[0]['id']
        self.a = SessionStore(self.base, Store(self.root / 'a.sqlite'))
        self.b = SessionStore(self.base, Store(self.root / 'b.sqlite'))

    def tearDown(self):
        self.temp.cleanup()

    def test_owner_resume_notes_and_ai_are_not_shared(self):
        self.base.set('resume', 'OWNER PRIVATE')
        self.base.set('ai_analysis', {'private':True})
        self.base.application(self.jid, '收藏', 'OWNER NOTE')
        self.assertIsNone(self.a.get('resume'))
        self.assertIsNone(self.a.get('ai_analysis'))
        self.assertIsNone(self.a.jobs()[0]['note'])
        self.assertIsNone(self.a.jobs()[0]['status'])

    def test_resume_preferences_and_research_results_are_private(self):
        for key in ('resume','preferences','research_runs','research_cohorts','ai_analysis'):
            self.a.set(key, 'A only')
            self.assertIsNone(self.b.get(key))
            self.assertIsNone(self.base.get(key))

    def test_shared_research_config_is_readonly(self):
        self.base.set('research_source', '/private/source.sqlite')
        self.assertEqual(self.a.get('research_source'), '/private/source.sqlite')
        with self.assertRaises(ValueError):
            self.a.set('research_source', '/malicious')

    def test_application_preserves_legacy_shared_id_and_isolates_history(self):
        with self.base.connection() as con:
            con.execute('UPDATE jobs SET id=? WHERE id=?', ('legacy-record-id', self.jid))
        self.a.application('legacy-record-id', '收藏', 'A NOTE')
        self.assertEqual(self.a.jobs()[0]['id'], 'legacy-record-id')
        self.assertEqual(self.a.jobs()[0]['note'], 'A NOTE')
        self.assertIsNone(self.b.jobs()[0]['note'])
        self.assertEqual(self.b.history_status(), {'undo':0,'redo':0})
        self.a.application_history('undo')
        self.assertIsNone(self.a.jobs()[0]['note'])

    def test_import_updates_only_visitor_and_preserves_shared_identity(self):
        with self.base.connection() as con:
            con.execute('UPDATE jobs SET id=? WHERE id=?', ('legacy-record-id', self.jid))
        self.a.upsert_jobs([dict(JOB, title='Updated private title', source='JobsDB live')])
        self.assertEqual(len(self.a.jobs()), 1)
        self.assertEqual(self.a.jobs()[0]['id'], 'legacy-record-id')
        self.assertEqual(self.b.jobs()[0]['title'], JOB['title'])
        self.assertEqual(len(self.base.jobs()), 1)

    def test_cooldown_shared_across_visitors(self):
        self.a.reserve_jobsdb_attempt(now())
        with self.assertRaises(ValueError):
            self.b.reserve_jobsdb_attempt(now())

    def test_invalid_application_does_not_copy_job(self):
        with self.assertRaises(ValueError):
            self.a.application(self.jid, 'bad', '')
        self.assertEqual(self.a.private.jobs(), [])

    def test_private_log_does_not_leak_to_other_visitors(self):
        self.a.log('test', 'done', 1, 'private import')
        self.assertEqual(self.b.logs(), [])
        self.assertEqual(self.base.logs(), [])

    def test_public_collection_cooldown_is_global_and_rows_are_private(self):
        posting = {'@type':'JobPosting', 'title':'Synthetic role', 'hiringOrganization':{'name':'Demo'},
                   'description':'Python SQL software engineering requirements'}
        html = '<script type="application/ld+json">' + json.dumps(posting) + '</script>'
        with patch('jobcompass.public.fetch_public_page', side_effect=['User-agent: *\nAllow: /', html]) as fetch:
            result = collect_public_page('https://jobs.example.com/role', self.a, {'jobs.example.com'})
            self.assertEqual(result['count'], 1)
            with self.assertRaisesRegex(ValueError, '15'):
                collect_public_page('https://jobs.example.com/role', self.b, {'jobs.example.com'})
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(len(self.a.jobs()), 2)
        self.assertEqual(len(self.b.jobs()), 1)

    def test_public_collection_obeys_robots_before_fetching_advertisement(self):
        with patch('jobcompass.public.fetch_public_page', return_value='User-agent: *\nDisallow: /') as fetch:
            with self.assertRaisesRegex(ValueError, 'robots'):
                collect_public_page('https://jobs.example.com/role', self.a, {'jobs.example.com'})
        fetch.assert_called_once()
        self.assertEqual(self.a.private.jobs(), [])


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = Store(self.root / 'base.sqlite')
        self.clock = Mock(return_value=0)
        self.factory = lambda store, directory: SimpleNamespace(store=store, tasks=SimpleNamespace(active=lambda: []))
        self.manager = SessionManager(self.base, self.root/'sessions', self.factory, ttl_seconds=10,
                                      max_sessions=2, clock=self.clock, secure=True)

    def tearDown(self):
        self.manager.close()
        self.temp.cleanup()

    @staticmethod
    def cookie(value):
        return value.split(';',1)[0]

    def test_new_cookie_is_opaque_and_secure(self):
        with self.manager.session(None) as visitor:
            cookie = visitor.set_cookie
            self.assertIn('HttpOnly', cookie)
            self.assertIn('SameSite=Strict', cookie)
            self.assertIn('Secure', cookie)
            self.assertNotIn(str(visitor.directory), cookie)
            visitor.store.set('resume', 'A')
        with self.manager.session(self.cookie(cookie)) as same:
            self.assertEqual(same.store.get('resume'), 'A')
        with self.manager.session(None) as other:
            self.assertIsNone(other.store.get('resume'))

    def test_unknown_or_traversal_cookie_cannot_choose_session_path(self):
        with self.manager.session('jobcompass_session=../../base.sqlite') as visitor:
            self.assertEqual(visitor.directory.parent, self.root/'sessions')
            self.assertEqual(len(visitor.directory.name), 64)
            self.assertIsNotNone(visitor.set_cookie)

    def test_registry_cap_rejects_without_evicting_live_data(self):
        with self.manager.session(None): pass
        with self.manager.session(None): pass
        with self.assertRaises(ValueError):
            with self.manager.session(None): pass

    def test_second_process_registry_cannot_delete_live_session(self):
        with self.manager.session(None) as visitor:
            with self.assertRaises(ValueError):
                SessionManager(self.base, self.root/'sessions', self.factory)
            self.assertTrue(visitor.directory.exists())

    def test_expired_idle_session_data_deleted_and_cookie_rotated(self):
        with self.manager.session(None) as visitor:
            cookie, directory = self.cookie(visitor.set_cookie), visitor.directory
        self.clock.return_value = 11
        self.manager.cleanup()
        self.assertFalse(directory.exists())
        with self.manager.session(cookie) as fresh:
            self.assertNotEqual(fresh.directory, directory)

    def test_active_request_and_background_job_prevent_deletion(self):
        with self.manager.session(None) as visitor:
            self.clock.return_value = 11
            self.manager.cleanup()
            self.assertTrue(visitor.directory.exists())
        visitor.app.tasks.active = lambda: [{'id':'running'}]
        self.clock.return_value = 25
        self.manager.cleanup()
        self.assertTrue(visitor.directory.exists())
        visitor.app.tasks.active = lambda: []
        self.manager.cleanup()
        self.assertFalse(visitor.directory.exists())

    def test_cookie_churn_limited_but_existing_cookie_still_works(self):
        self.manager.close()
        limiter = RateLimiter(per_ip=1, global_limit=3, max_active=1, window_seconds=60, clock=self.clock)
        self.manager = SessionManager(self.base, self.root/'sessions', self.factory,
                                      creation_limiter=limiter, clock=self.clock)
        with self.manager.session(None, peer='192.0.2.1') as visitor:
            cookie = self.cookie(visitor.set_cookie)
            visitor.store.set('resume', 'preserved')
        with self.assertRaises(ValueError):
            with self.manager.session(None, peer='192.0.2.1'): pass
        with self.manager.session(cookie, peer='192.0.2.1') as visitor:
            self.assertEqual(visitor.store.get('resume'), 'preserved')
        with self.manager.session(None, peer='192.0.2.2'): pass

    def test_failed_creation_releases_active_slot_without_refunding_allowance(self):
        self.manager.close()
        limiter = RateLimiter(per_ip=2, global_limit=4, max_active=1, window_seconds=60, clock=self.clock)
        self.manager = SessionManager(self.base, self.root/'sessions', Mock(side_effect=ValueError('failed factory')),
                                      creation_limiter=limiter, clock=self.clock)
        with self.assertRaises(ValueError):
            with self.manager.session(None, peer='192.0.2.1'): pass
        self.manager.factory = self.factory
        with self.manager.session(None, peer='192.0.2.1'): pass
        with self.assertRaises(ValueError):
            with self.manager.session(None, peer='192.0.2.1'): pass


class LimitAndConfigTests(unittest.TestCase):
    def test_public_page_hosts_exactly_match_every_redirect(self):
        allowed = frozenset({'jobs.example.com'})
        with patch('jobcompass.public.validate_url') as resolver:
            for url in ('http://jobs.example.com/a', 'https://jobs.example.com.evil/a',
                        'https://sub.jobs.example.com/a', 'https://user@jobs.example.com/a',
                        'https://jobs.example.com:444/a'):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    validate_page_url(url, allowed, resolve=True)
            resolver.assert_not_called()
            redirect = PublicRedirect(allowed)
            request = Request('https://jobs.example.com/a')
            with self.assertRaises(ValueError):
                redirect.redirect_request(request, None, 302, 'redirect', {}, 'https://unapproved.example/b')
            resolver.assert_not_called()
            result = redirect.redirect_request(request, None, 302, 'redirect', {}, 'https://jobs.example.com/b')
            self.assertEqual(result.full_url, 'https://jobs.example.com/b')
            resolver.assert_called_once_with('https://jobs.example.com/b')

    def test_public_fetch_disables_proxy_environment_and_uses_bound(self):
        with patch('jobcompass.public.validate_url'), patch('jobcompass.public.build_opener') as build:
            build.return_value.open.return_value.__enter__.return_value.read.return_value = b'public text'
            self.assertEqual(fetch_public_page('https://jobs.example.com/a', {'jobs.example.com'}), 'public text')
            proxy = next(handler for handler in build.call_args.args if isinstance(handler, ProxyHandler))
            self.assertEqual(proxy.proxies, {})
            response = build.return_value.open.return_value.__enter__.return_value
            response.read.assert_called_once_with(8 * 1024 * 1024 + 1)
            self.assertEqual(build.return_value.open.call_args.kwargs['timeout'], 25)

    def test_public_page_config_rejects_wildcards_and_url_entries(self):
        settings = {'JOBCOMPASS_PUBLIC_ORIGIN':'https://jobs.example.com',
                    'JOBCOMPASS_ALLOWED_HOSTS':'jobs.example.com'}
        for host in ('*.example.com', 'https://jobs.example.com', 'jobs.example.com/role'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                PublicConfig.from_env(dict(settings, JOBCOMPASS_PAGE_HOSTS=host))
        self.assertEqual(PublicConfig.from_env(dict(settings, JOBCOMPASS_PAGE_HOSTS='jobs.example.com')).page_hosts,
                         frozenset({'jobs.example.com'}))

    def test_new_cookie_cannot_bypass_ip_limit_and_release_is_idempotent(self):
        limiter = RateLimiter(per_ip=1, global_limit=4, max_active=2, window_seconds=60)
        permit = limiter.reserve('192.0.2.1')
        permit.release(); permit.release()
        with self.assertRaises(ValueError): limiter.reserve('192.0.2.1')
        second = limiter.reserve('192.0.2.2')
        second.release()

    def test_global_and_active_caps_and_window_reset(self):
        clock = Mock(return_value=0)
        limiter = RateLimiter(per_ip=3, global_limit=2, max_active=1, window_seconds=10, clock=clock)
        permit = limiter.reserve('192.0.2.1')
        with self.assertRaises(ValueError): limiter.reserve('192.0.2.2')
        permit.release()
        limiter.reserve('192.0.2.2').release()
        with self.assertRaises(ValueError): limiter.reserve('192.0.2.3')
        clock.return_value = 11
        limiter.reserve('192.0.2.3').release()

    def test_config_requires_exact_origin_and_host(self):
        with self.assertRaises(ValueError): PublicConfig.from_env({})
        config = PublicConfig.from_env({'JOBCOMPASS_PUBLIC_ORIGIN':'https://jobs.example.com',
                                        'JOBCOMPASS_ALLOWED_HOSTS':'jobs.example.com'})
        self.assertTrue(config.valid_request('jobs.example.com', 'https://jobs.example.com', write=True))
        self.assertFalse(config.valid_request('evil.example', 'https://jobs.example.com', write=True))
        self.assertFalse(config.valid_request('jobs.example.com', 'https://evil.example', write=True))
        self.assertFalse(config.valid_request('jobs.example.com', None, write=True))

    def test_forwarded_address_only_accepted_from_configured_proxy(self):
        config = PublicConfig.from_env({'JOBCOMPASS_PUBLIC_ORIGIN':'https://jobs.example.com',
                                        'JOBCOMPASS_ALLOWED_HOSTS':'jobs.example.com',
                                        'JOBCOMPASS_TRUSTED_PROXIES':'127.0.0.1'})
        self.assertEqual(config.client_ip('192.0.2.1', '192.0.2.9'), '192.0.2.1')
        self.assertEqual(config.client_ip('127.0.0.1', '192.0.2.9'), '192.0.2.9')
        self.assertEqual(config.client_ip('127.0.0.1', 'invalid'), '127.0.0.1')

    def test_active_limit_is_atomic_under_concurrent_reservations(self):
        limiter = RateLimiter(per_ip=20, global_limit=20, max_active=2)
        def attempt(index):
            try:
                return limiter.reserve('192.0.2.' + str(index))
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            permits = [permit for permit in pool.map(attempt, range(1, 17)) if permit]
        self.assertEqual(len(permits), 2)
        for permit in permits:
            permit.release()

    def test_insecure_or_wildcard_public_configuration_rejected(self):
        for origin, hosts in (('http://jobs.example.com','jobs.example.com'),
                              ('https://jobs.example.com','*'),
                              ('https://jobs.example.com','other.example.com'),
                              ('https://jobs.example.com:invalid','jobs.example.com:invalid')):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                PublicConfig.from_env({'JOBCOMPASS_PUBLIC_ORIGIN':origin, 'JOBCOMPASS_ALLOWED_HOSTS':hosts})

    def test_public_metadata_removes_local_paths(self):
        data = {'path':'/Users/private/a.sqlite','index':{'source_path':'/private/b','rows':2},
                'error':'Cannot open /Users/private/a.sqlite','ready':True}
        output = sanitize_public(data)
        self.assertNotIn('/Users', json.dumps(output))
        self.assertNotIn('/private', json.dumps(output))
        self.assertEqual(output['index']['rows'], 2)

    def test_sanitization_preserves_job_urls_and_salary_units(self):
        self.assertEqual(sanitize_public('https://hk.jobsdb.com/job/123'), 'https://hk.jobsdb.com/job/123')
        self.assertEqual(sanitize_public('HK$20,000 /month'), 'HK$20,000 /month')


if __name__ == '__main__':
    unittest.main()
