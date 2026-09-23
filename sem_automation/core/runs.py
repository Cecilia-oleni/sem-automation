# 模块：sem_automation/core/runs.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
"""Isolated runs and auditable output fingerprints."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import uuid
import shutil
from sem_automation.core.paths import PROJECT_ROOT, safe_name

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def new_run(client, kind, period, root=None):
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    run = Path(root or PROJECT_ROOT) / 'outputs/reports' / safe_name(client) / safe_name(kind) / safe_name(period) / 'runs' / run_id
    for name in ('deliverables', '_internal', 'history_candidates'):
        (run / name).mkdir(parents=True, exist_ok=False)
    write_json(run / '_internal/status.json', {'status':'running', 'client':client, 'kind':kind, 'period':period})
    return run

def tidy_run(run):
    """Keep only deliverable workbooks in the user-facing delivery folder."""
    run=Path(run)
    for p in list((run/'deliverables').iterdir()):
        if p.is_file() and p.suffix=='.xlsx':continue
        target=run/'_internal/rendering'/p.name
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise FileExistsError(target)
        shutil.move(str(p),target)
    for p in list(run.iterdir()):
        if not p.is_file():continue
        target=run/'_internal/data_exports'/p.name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(p),target)
