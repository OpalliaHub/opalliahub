import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

from jobcompass.server import Tasks


class TaskQueueTests(unittest.TestCase):
    def test_executor_rejection_leaves_no_permanent_queued_task(self):
        pool=ThreadPoolExecutor(max_workers=1)
        pool.shutdown(wait=True)
        tasks=Tasks(pool)
        release=Mock()
        with self.assertRaises(RuntimeError):
            tasks.submit('rejected',lambda progress,event:None,controlled=True,on_done=release)
        self.assertEqual(tasks.active(),[])
        self.assertEqual(tasks.items,{})
        self.assertEqual(tasks.cancellations,{})
        release.assert_called_once_with()
