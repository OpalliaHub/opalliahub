"""Focused AST lint rules for errors highlighted in the programming lectures."""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def mutable_default(node):
    if isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in ('list', 'dict', 'set', 'bytearray')
    return isinstance(node, ast.Tuple) and any(mutable_default(item) for item in node.elts)


def lint_source(source, filename='<source>'):
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as error:
        return [(error.lineno or 1, 'JC000', 'Syntax error')]
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in list(node.args.defaults) + list(node.args.kw_defaults):
                if default is not None and mutable_default(default):
                    findings.append((default.lineno, 'JC001', 'Shared mutable function default'))
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append((node.lineno, 'JC002', 'Bare except also hides interrupts'))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec'):
            findings.append((node.lineno, 'JC003', 'Direct dynamic code execution'))
        elif isinstance(node, ast.ImportFrom) and any(item.name == '*' for item in node.names):
            findings.append((node.lineno, 'JC004', 'Wildcard import obscures names'))
    return sorted(findings)


def main():
    paths = [ROOT / 'main.py'] + sorted((ROOT / 'jobcompass').rglob('*.py')) + sorted((ROOT / 'scripts').glob('*.py'))
    count = 0
    for path in paths:
        findings = lint_source(path.read_text(encoding='utf-8'), str(path))
        for line, code, message in findings:
            print('{}:{}: {} {}'.format(path.relative_to(ROOT), line, code, message))
        count += len(findings)
    print('{} Python files; {} focused AST findings. Not a type checker or full style linter.'.format(len(paths), count))
    return int(bool(count))


if __name__ == '__main__':
    sys.exit(main())
