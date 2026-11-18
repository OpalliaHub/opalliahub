import unittest
from scripts.static_checks import lint_source


class StaticCheckTests(unittest.TestCase):
    def test_shared_mutable_defaults(self):
        for value in ('[]', '{}', 'set()', 'dict()', '([],)', '(1, {"x":[]})'):
            with self.subTest(value=value):
                self.assertEqual(lint_source('def f(x={}): pass'.format(value))[0][1], 'JC001')

    def test_async_keyword_default(self):
        self.assertEqual(lint_source('async def f(*, x=[]): pass')[0][1], 'JC001')

    def test_immutable_defaults_are_allowed(self):
        self.assertEqual(lint_source('def f(x=None, y=(1, "a")):\n return x'), [])

    def test_bare_except_is_flagged(self):
        self.assertEqual(lint_source('try: pass\nexcept: pass')[0][1], 'JC002')
        self.assertEqual(lint_source('try: pass\nexcept ValueError: pass'), [])

    def test_dynamic_execution_and_wildcard(self):
        self.assertEqual([row[1] for row in lint_source('from os import *\neval("1")\nexec("a=1")')], ['JC004','JC003','JC003'])

    def test_comments_and_strings_are_not_code(self):
        self.assertEqual(lint_source('"eval(code)"\n# exec(code)\nx = 1'), [])

    def test_invalid_source_has_controlled_diagnostic(self):
        self.assertEqual(lint_source('def bad('), [(1,'JC000','Syntax error')])
