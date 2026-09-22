# 终端输入：& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s tests -v
import ast
from pathlib import Path
import unittest

class ArchitectureTests(unittest.TestCase):
    def test_dependency_boundaries(self):
        root=Path(__file__).resolve().parents[1]/'sem_automation'
        for p in root.rglob('*.py'):
            layer=p.relative_to(root).parts[0]
            forbidden={'reporting'} if layer=='materials' else {'materials'} if layer=='reporting' else {'materials','reporting'} if layer in {'core','ai','readers','integrations'} else set()
            for node in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
                imports=[node.module or ''] if isinstance(node,ast.ImportFrom) else [a.name for a in node.names] if isinstance(node,ast.Import) else []
                for name in imports:
                    for target in forbidden:self.assertFalse(name.startswith(f'sem_automation.{target}'),f'{p}: {name}')
