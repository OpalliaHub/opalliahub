"""Persistent application history: user-level undo/redo, rollback and concurrency."""
import concurrent.futures
import tempfile
import unittest
from pathlib import Path

from jobcompass.storage import Store


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'history.sqlite'
        self.store = Store(self.path)
        self.store.upsert_jobs([dict(source='Manual', title='Python Engineer', company='Demo',
                                     description='Python SQL', url='https://example.com/job')])
        self.jid = self.store.jobs()[0]['id']

    def tearDown(self):
        self.temp.cleanup()

    def status(self):
        return self.store.jobs()[0]['status'], self.store.jobs()[0]['note']

    def test_round_trip_create_update_delete(self):
        self.store.application(self.jid, '收藏', 'first')
        self.store.application(self.jid, '已投递', 'second')
        self.store.application(self.jid, '未收藏', '')
        self.assertEqual(self.status(), (None, None))
        self.store.application_history('undo')
        self.assertEqual(self.status(), ('已投递', 'second'))
        self.store.application_history('undo')
        self.assertEqual(self.status(), ('收藏', 'first'))
        self.store.application_history('undo')
        self.assertEqual(self.status(), (None, None))
        for _ in range(3):
            self.store.application_history('redo')
        self.assertEqual(self.status(), (None, None))
        self.assertEqual(self.store.history_status(), {'undo': 3, 'redo': 0})

    def test_new_change_discards_redo_branch(self):
        self.store.application(self.jid, '收藏', '')
        self.store.application(self.jid, '已投递', '')
        self.store.application_history('undo')
        self.store.application(self.jid, '面试中', 'new branch')
        self.assertEqual(self.store.history_status(), {'undo': 2, 'redo': 0})
        with self.assertRaises(ValueError):
            self.store.application_history('redo')

    def test_noop_preserves_redo(self):
        self.store.application(self.jid, '收藏', '')
        self.store.application_history('undo')
        self.store.application(self.jid, '未收藏', 'ignored')
        self.assertEqual(self.store.history_status(), {'undo': 0, 'redo': 1})

    def test_restart_and_private_notes(self):
        self.store.application(self.jid, '已投递', 'private interview note')
        self.store = Store(self.path)
        self.assertEqual(self.store.history_status(), {'undo': 1, 'redo': 0})
        self.store.application_history('undo')
        self.store.application_history('redo')
        self.assertEqual(self.status(), ('已投递', 'private interview note'))

    def test_empty_and_invalid_actions(self):
        for action in ('undo', 'redo', 'delete'):
            with self.assertRaises(ValueError):
                self.store.application_history(action)
        with self.assertRaises(ValueError):
            self.store.application('missing', '收藏', '')
        with self.assertRaises(ValueError):
            self.store.application(self.jid, 'broken', '')
        self.assertEqual(self.store.history_status(), {'undo': 0, 'redo': 0})

    def test_bounded_history(self):
        for i in range(55):
            self.store.application(self.jid, '收藏', str(i))
        self.assertEqual(self.store.history_status()['undo'], 50)
        for _ in range(50):
            self.store.application_history('undo')
        self.assertEqual(self.status(), ('收藏', '4'))

    def test_concurrent_updates_are_serializable(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: self.store.application(self.jid, '收藏', str(i)), range(12)))
        self.assertEqual(self.store.history_status()['undo'], 12)
        for _ in range(12):
            self.store.application_history('undo')
        self.assertEqual(self.status(), (None, None))

    def test_existing_schema_migrates_without_losing_records(self):
        self.store.application(self.jid, '已录用', 'preserve')
        with self.store.connection() as con:
            con.execute('DROP TABLE application_history')
        self.store = Store(self.path)
        self.assertEqual(self.status(), ('已录用', 'preserve'))
        self.assertEqual(self.store.history_status(), {'undo': 0, 'redo': 0})
