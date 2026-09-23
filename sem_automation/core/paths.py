# 模块：sem_automation/core/paths.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
"""Only this module locates the repository root; importing it never writes files."""

from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def safe_name(value):
    if not value or value in {'.', '..'} or re.search(r'[<>:"/\\|?*]', value):
        raise ValueError(f'无效目录名称: {value!r}')
    return value

def material_dir(kind, project, root=None):
    return Path(root or PROJECT_ROOT) / kind / 'materials' / safe_name(project)

def renderer(family, filename):
    return PROJECT_ROOT / 'sem_automation' / 'reporting' / 'renderers' / family / filename
