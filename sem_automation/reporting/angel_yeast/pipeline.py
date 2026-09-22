# 模块：sem_automation/reporting/angel_yeast/pipeline.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports angel-yeast --month 2026-08 --reuse-raw '.\outputs\_archive\angel_yeast\2026-08\_internal\direct_monthly_data.json' --skip-translation
# 该示例复用本地数据；详见 docs/月报操作说明.md。
"""Angel Yeast dataset + unchanged three-workbook renderer."""
import json
import shutil
import subprocess
from pathlib import Path
from sem_automation.core.paths import PROJECT_ROOT, renderer
from sem_automation.core.runs import new_run, write_json, digest, tidy_run
from sem_automation.reporting.angel_yeast.dataset import build_dataset, rebuild_existing_dataset, load_config, month_range
from sem_automation.reporting.standard.pipeline import resolve_node

def run_report(*, config, month, reuse_raw=None, skip_translation=False, skip_calibration=False, node=None):
    month_range(month)
    runtime = resolve_node(node)
    cfg = load_config(config)
    if reuse_raw:
        source = Path(reuse_raw).resolve()
        data = json.loads(source.read_text(encoding='utf-8'))
        meta = data['meta']
        if meta.get('report_month') != month or meta.get('client_login') != cfg['client_login']:
            raise ValueError('原始数据的月份或客户与本次配置不一致')
        for field in ('goals', 'attribution_model', 'include_vat', 'include_discount'):
            if meta.get(field) != cfg.get(field):
                raise ValueError(f'原始数据 {field} 与配置不一致')
        if not data.get('geo_country_map'):
            raise ValueError('原始数据缺少地域映射，无法离线重建；请先联网生成完整数据')
    run = new_run('angel_yeast', 'angel-yeast', month)
    dataset = run / '_internal/direct_monthly_data.json'
    try:
        if reuse_raw:
            shutil.copy2(source, dataset)
            rebuild_existing_dataset(report_month=month, dataset_path=dataset, config_path=config, translate_keywords=not skip_translation)
        else:
            build_dataset(report_month=month, output_json=dataset, config_path=config, calibrate=not skip_calibration, translate_keywords=not skip_translation)
        subprocess.run([runtime, str(renderer('angel_yeast', 'direct_report_workbooks.mjs')), '--input', str(dataset), '--out-dir', str(run/'deliverables'), '--preview-dir', str(run/'_internal/previews')], cwd=PROJECT_ROOT, check=True)
        files = list((run/'deliverables').glob('*.xlsx'))
        if len(files) != 3:
            raise RuntimeError('安琪报告未完整生成三份工作簿')
        tidy_run(run)
        write_json(run/'_internal/manifest.json', {'schema':1, 'kind':'angel-yeast', 'month':month, 'config_sha256':digest(config), 'outputs':{str(p):digest(p) for p in files}})
        write_json(run/'_internal/status.json', {'status':'completed'})
        return run
    except Exception as exc:
        write_json(run/'_internal/status.json', {'status':'failed','error':str(exc)})
        raise
