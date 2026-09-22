# 终端输入：& '.\.venv\Scripts\python.exe' -X utf8 '.\tests\repeat_yutong.py'
# 将候选副本作为下次输入，验证同月重跑。绝不执行真实同步。
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sem_automation.core.runs import write_json
from sem_automation.reporting.yutong.pipeline import prepare, run_report, workbook_rows, COUNTRIES
from sem_automation.reporting.yutong.history import blocks
root=Path(__file__).resolve().parents[1]
config,_=prepare(root/'config/reports/yutong/2026-08.json','2026-08')
original=sorted((root/'outputs/reports/yutong/yandex/2026-08/runs').glob('*/_internal/manifest.json'))[-1].parent.parent
for key,pattern in [('countryHistory','*country_history*.xlsx'),('ytdHistory','*ytd_history*.xlsx')]:config['paths'][key]=str(next((original/'history_candidates').glob(pattern)))
config={k:v for k,v in config.items() if not k.startswith('_')}
path=root/'outputs/_migration/2026-09-20/repeat_config.json';write_json(path,config)
run=run_report(config_path=path,month='2026-08')
for key,pattern,sheet in [('countryHistory','*country_history*.xlsx','整理数值'),('ytdHistory','*ytd_history*.xlsx','月度源数据')]:
    old=workbook_rows(config['paths'][key]);new=workbook_rows(next((run/'history_candidates').glob(pattern)))
    before=blocks(old[sheet],COUNTRIES);after=blocks(new[sheet],COUNTRIES)
    assert before.keys()==after.keys()
    assert before['2026-08']['start']==after['2026-08']['start']
    assert before['2026-08']['rows']==after['2026-08']['rows']
write_json(root/'outputs/_migration/2026-09-20/repeat_result.json',{'status':'passed','run':str(run),'same_month_unique':True,'same_values':True})
print('同月重跑：月份数量、行位置、国家数值均保持一致。',run)
