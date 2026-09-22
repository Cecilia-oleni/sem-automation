# Wordstat 实验模块；从项目根目录运行。
# 终端输入：& '.\.venv\Scripts\python.exe' -X utf8 '.\experiments\wordstat\make_report.py'
# API 请求只由 wordstat.py --execute 显式触发；报告/清单脚本仅操作本地缓存。
"""Build a Markdown report from cached results; no network access."""
import json
from pathlib import Path
from keyword_list import read_keywords

root = Path(__file__).resolve().parent
records = [json.loads(p.read_text(encoding='utf-8')) for p in (root / 'results').glob('*.json')]
records = {r['request']['phrase']: r for r in records if r.get('method') == 'topRequests'}
keywords = read_keywords()
original = [phrase for phrase in keywords if phrase.startswith('gobroad ')]
lines = ['# Wordstat API 首次实验结果', '', '测试日期：2026-09-14。接口：GetTop；全部地区、全部设备、最近 30 天；每次最多返回 50 个热门词。',
         '', '搜索次数是包含查询关键词的统计，不是独立人数，也不是精确匹配月均量；不同词的数据可能重叠，不应相加。',
         '', '## 原始 12 个关键词', '', '| 关键词 | 返回搜索次数 | 原始响应 |', '|---|---:|---|']
for phrase in original:
    response = records[phrase]['response']
    lines.append(f"| {phrase} | {response.get('totalCount', '未返回')} | {'空对象 {}' if not response else '有数据'} |")
lines += ['', '上述空对象表示接口成功但未返回统计字段或词列表，本报告不将缺失字段直接标成已确认的 0 次。',
          '', '## 不带品牌的对照与热门词', '']
for phrase in keywords:
    if phrase.startswith('gobroad '):
        continue
    response = records[phrase]['response']
    lines += [f"### {phrase} — {response['totalCount']} 次", '', '| 接口返回的热门词 | 搜索次数 |', '|---|---:|']
    lines += [f"| {x['phrase']} | {x['count']} |" for x in response.get('results', [])]
    lines += ['', f"另返回 {len(response.get('associations', []))} 条关联词，完整内容保存在 results JSON；存在明显无关词，不直接作为投放建议。", '']
lines += ['## 费用与执行边界', '',
          '- 成功请求：1 次免费地区列表、14 次 GetTop。联网获准前的地区列表尝试在本地网络层失败。',
          '- 卢布合同：GetTop 每 1,000 次 ₽20，单次 ₽0.02，本次估算 ₽0.28（含 VAT）。',
          '- 美元合同：每 1,000 次 $0.1639344，单次 $0.0001639344，本次估算 $0.0022950816（未含 VAT）。',
          '- 币种由签约主体决定；这是公开价估算，未读取账单核实实际扣款。',
          '- 未调用大模型、未创建云计算资源、未购买包月服务。关联词由同一次 GetTop 返回，无额外拓展请求。',
          '', '## 后续调研建议', '',
          '将品牌词和产品词分开研究。先查询其余不带 gobroad 的产品全称，再按实际投放地区过滤；DBS 等缩写需检查歧义。热门词可按价格、医院、评价、疾病与术后信息分类。搜索词仅代表搜索意图，不能据此认定客户提供相关治疗。',
          '', '## 官方依据', '',
          '- [GetTop 字段与统计口径](https://aistudio.yandex.ru/en/docs/search-api/api-ref/Wordstat/getTop)',
          '- [Wordstat 调用指南](https://aistudio.yandex.ru/en/docs/search-api/operations/wordstat-gettop)',
          '- [计费](https://aistudio.yandex.ru/ru/docs/search-api/pricing)',
          '- [认证](https://aistudio.yandex.ru/en/docs/search-api/api-ref/authentication)', '']
root.joinpath('REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
print(f'Report saved: {len(records)} keyword responses; {sum(not r["response"] for r in records.values())} empty responses.')
