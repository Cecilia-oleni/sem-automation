# 兼容旧安琪入口，推荐统一使用 sem.py。
# 终端输入：& '.\.venv\Scripts\python.exe' '.\angel_yeast_monthly_report.py' --help
import argparse
from pathlib import Path
import shutil
from sem_automation.core.paths import PROJECT_ROOT
from sem_automation.reporting.angel_yeast.dataset import DEFAULT_CONFIG
from sem_automation.reporting.angel_yeast.pipeline import run_report

def main():
    p=argparse.ArgumentParser(description='安琪兼容入口：生成数据与三份 Excel；推荐 sem.py reports angel-yeast')
    p.add_argument('--month',required=True);p.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    p.add_argument('--output-json',type=Path)
    p.add_argument('--reuse-raw',action='store_true');p.add_argument('--skip-calibration',action='store_true');p.add_argument('--skip-translation',action='store_true');p.add_argument('--node')
    a=p.parse_args()
    source=a.output_json or PROJECT_ROOT/'outputs/_archive/angel_yeast'/a.month/'_internal/direct_monthly_data.json'
    run=run_report(config=a.config,month=a.month,reuse_raw=source if a.reuse_raw else None,skip_translation=a.skip_translation,skip_calibration=a.skip_calibration,node=a.node)
    if a.output_json and not a.reuse_raw:
        a.output_json.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(run/'_internal/direct_monthly_data.json',a.output_json)
    print(f'完成：{run}')

if __name__=='__main__':main()
