# Wordstat 实验模块；从项目根目录运行。
# 终端输入：& '.\.venv\Scripts\python.exe' -X utf8 '.\experiments\wordstat\export_review.py'
# API 请求只由 wordstat.py --execute 显式触发；报告/清单脚本仅操作本地缓存。
"""Local-only initial review export. Refuse to overwrite human review files."""
import json
from pathlib import Path
from keyword_list import read_keywords

root = Path(__file__).resolve().parent
target = root / 'keywords.txt'
expansion = root / 'expanded_keywords.txt'
if target.read_text(encoding='utf-8').startswith('#') or expansion.exists():
    raise SystemExit('Review files already exist; not overwriting manual decisions.')
keywords = read_keywords()
records = [json.loads(p.read_text(encoding='utf-8')) for p in (root / 'results').glob('*.json')]
records = {r['request']['phrase']: r for r in records if r.get('method') == 'topRequests'}
notes = [
    '# 测试日期：2026-09-14；最近30天；全部地区；全部设备。列之间为制表符，可复制到表格。',
    '# 搜索量为包含关键词的搜索次数，不是精确匹配量或独立人数；各行不可直接相加。',
    '# 未返回不等于已确认的0。采用与人工备注列可自行填写；脚本不会据此自动生成筛选后的报告。',
    '# 本次14次关键词请求预计费用：RUB 0.28（含税）或 USD 0.0022950816（未税），按合同币种；未核实账单。',
]
lines = notes + ['# 关键词\t搜索量\t返回状态\t采用（待定/是/否）\t人工备注']
for phrase in keywords:
    response = records[phrase]['response']
    lines.append('\t'.join([phrase, response.get('totalCount', '未返回'),
                            '空响应 {}' if not response else '有数据', '待定', '']))
target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
lines = notes + ['# 保留所有热门词和关联词供人工筛选；关联词中有明显无关内容。热门词可能包含种子词本身。',
                 '# 关键词\t搜索量\t来源类型\t来源种子词\t采用（待定/是/否）\t人工备注']
count = 0
for phrase in keywords:
    for field, label in [('results', '热门词'), ('associations', '关联词')]:
        for item in records[phrase]['response'].get(field, []):
            lines.append('\t'.join([item['phrase'], item.get('count', '未返回'), label, phrase, '待定', '']))
            count += 1
expansion.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'Saved {len(keywords)} queried keywords and {count} expansion rows; no API requests.')
