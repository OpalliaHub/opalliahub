"""The production entry point must never expose the local owner's database."""
import os
import unittest
from unittest.mock import patch

from jobcompass import wsgi


class ProductionEntryTests(unittest.TestCase):
    def test_missing_public_mode_fails_before_opening_owner_database(self):
        with patch.dict(os.environ, {'JOBCOMPASS_PUBLIC': '0'}), \
                patch.object(wsgi, '_application', None), \
                patch.object(wsgi, 'Application') as factory:
            with self.assertRaisesRegex(ValueError, 'JOBCOMPASS_PUBLIC=1'):
                wsgi.application({}, lambda status, headers: None)
            factory.assert_not_called()

    def test_invalid_public_origin_fails_before_opening_database(self):
        with patch.dict(os.environ, {'JOBCOMPASS_PUBLIC': '1',
                                    'JOBCOMPASS_PUBLIC_ORIGIN': 'http://example.test'}), \
                patch.object(wsgi, '_application', None), \
                patch.object(wsgi, 'Application') as factory:
            with self.assertRaises(ValueError):
                wsgi.application({}, lambda status, headers: None)
            factory.assert_not_called()
