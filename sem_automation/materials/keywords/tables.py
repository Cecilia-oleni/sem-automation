# 终端输入：python sem.py materials wordstat prepare --project '通亚'
"""Human-reviewed bilingual tables and a single final-keyword reader."""
import csv
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path
import pandas as pd
from sem_automation.core.paths import PROJECT_ROOT
from sem_automation.integrations.yandex.wordstat.client import save_json

FINAL_NAMES = ('keywords_v2.xlsx', 'keywords_v2.csv', 'keyword_v2.xlsx', 'keyword_v2.csv')
REVIEW_NAMES = ('keywords_v1_reviewed.xlsx', 'keywords_v1_reviewed.csv')
FIELDS = ['campaign', 'adgroup', 'keywords', 'volume', 'keywords_CN']


def key(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', str(text))).strip().casefold()


def choose_file(directory, names, explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    found = [Path(directory)/n for n in names if (Path(directory)/n).is_file()]
    if len(found) > 1:
        raise ValueError('发现多个候选文件，请用 --review-file 或 --keywords-file 明确选择：' + ', '.join(p.name for p in found))
    return found[0] if found else None


def read_table(path):
    path = Path(path)
    if path.suffix.lower() == '.csv':
        try:
            df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            raise ValueError('CSV 请另存为 CSV UTF-8，或直接使用 .xlsx') from None
    elif path.suffix.lower() == '.xlsx':
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
    else:
        raise ValueError('人工词表仅支持 .xlsx 或 UTF-8 .csv')
    df.columns = [str(c).strip() for c in df.columns]
    if any(str(c).startswith('Unnamed:') for c in df.columns):
        df = df.loc[:, [not str(c).startswith('Unnamed:') for c in df.columns]]
    if df.columns.duplicated().any():
        raise ValueError('词表存在重复列名')
    for col in df:
        df[col] = df[col].map(lambda v: v[1:] if isinstance(v,str) and v.startswith(("'=", "'+", "'-", "'@")) else v)
    return df


def seeds_from_table(path):
    df = read_table(path)
    if not {'keywords', 'keywords_CN'} <= set(df.columns):
        raise ValueError('审核表第一行必须包含 keywords、keywords_CN 两列')
    rows = {}
    for number, row in enumerate(df.to_dict('records'), 2):
        phrase, cn = str(row['keywords']).strip(), str(row['keywords_CN']).strip()
        if not phrase and not cn:
            continue
        if not phrase or re.search(r'[\u3400-\u9fff]', phrase) or len(phrase) > 400:
            raise ValueError(f'第 {number} 行关键词为空、含中文或超过400字符；中文请放 keywords_CN 列')
        normalized = key(phrase)
        item = {'keywords': phrase, 'keywords_CN': cn}
        if normalized in rows and rows[normalized]['keywords_CN'] != cn:
            raise ValueError(f'重复关键词中文说明不一致：{phrase}')
        rows[normalized] = min(rows.get(normalized, item), item, key=lambda r:r['keywords'])
    if not rows or len(rows) > 600:
        raise ValueError(f'审核种子去重后为 {len(rows)} 个；必须为1–600个，请人工缩减后再查询')
    return [rows[k] for k in sorted(rows)]


def write_tables(base, fields, rows, *, root=PROJECT_ROOT, preview=False):
    """Write machine CSV and an Office-friendly XLSX using the shared Node runtime."""
    base = Path(base)
    payload = base.parent/'_internal'/f'{base.name}_table.json'
    save_json(payload, {'fields':fields, 'rows':rows})
    runtime = Path(root)/'config/runtime.local.json'
    cfg = json.loads(runtime.read_text('utf-8')) if runtime.exists() else {}
    node = cfg.get('node') or shutil.which('node')
    if not node:
        raise RuntimeError('Excel 导出需要 Node.js，请配置 config/runtime.local.json')
    args = [node, str(PROJECT_ROOT/'sem_automation/materials/keywords/table_workbook.mjs'), str(payload), str(base.with_suffix('.xlsx'))]
    if preview:
        args.append(str(base.with_suffix('.png')))
    subprocess.run(args, cwd=PROJECT_ROOT, check=True)
    temp = base.with_suffix('.csv.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            # Neutralize spreadsheet formulas from model/API text. Reader removes the prefix.
            writer.writerow({f: ("'" + str(row[f]) if isinstance(row.get(f), str) and str(row[f]).startswith(('=', '+', '-', '@')) else row.get(f)) for f in fields})
    temp.replace(base.with_suffix('.csv'))


def parse_draft(text):
    """Only parse the explicit final bilingual table, never narrative headings."""
    rows = []
    active = False
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells == ['keywords', 'keywords_CN']:
            active = True
            continue
        if not active:
            continue
        if len(cells) != 2:
            if rows:
                break
            continue
        if all(re.fullmatch(r':?-+:?', c) for c in cells):
            continue
        if cells[0] and cells[1] and not re.search(r'[\u3400-\u9fff]', cells[0]):
            rows.append(dict(zip(['keywords', 'keywords_CN'], cells)))
        else:
            raise ValueError('初稿中俄表格格式有误，请修正 keywords、keywords_CN 两列')
    if not rows:
        raise ValueError('旧初稿没有标准中俄表格。请在末尾补 keywords | keywords_CN 两列表格，或直接准备审核版 Excel/CSV。')
    return rows


def prepare_review(directory, *, root=PROJECT_ROOT, force=False):
    directory = Path(directory)
    if (directory/'keywords_v1.xlsx').exists() and not force:
        return directory/'keywords_v1.xlsx'
    rows = parse_draft((directory/'keyword_v1.md').read_text('utf-8'))
    write_tables(directory/'keywords_v1', ['keywords', 'keywords_CN'], rows, root=root)
    return directory/'keywords_v1.xlsx'


def load_final(directory, explicit=None):
    path = choose_file(directory, FINAL_NAMES, explicit)
    if path is None:
        raise FileNotFoundError('请准备 keywords_v2.xlsx 或 keywords_v2.csv（兼容 keyword_v2.xlsx）')
    df = read_table(path)
    aliases = {
        'Campaign':['campaign','广告系列','广告系列名称'],
        'AdGroup':['adgroup','广告组','广告组名称'],
        'Keyword':['keyword','keywords','关键词','关键词（俄语/英文）','关键词(俄语/英文)','keywordtext'],
    }
    norm = lambda x: str(x).strip().lower().replace('_','').replace(' ','').replace('-','')
    cols = {norm(c):c for c in df.columns}
    mapping = {}
    for target, names in aliases.items():
        source = next((cols[norm(n)] for n in names if norm(n) in cols), None)
        if source is None:
            if path.suffix == '.xlsx':
                # Preserve the legacy hand-grouped block format only for legacy XLSX.
                from sem_automation.materials.ads.generator import parse_manual_keyword_v2
                df = parse_manual_keyword_v2(path)
                break
            raise ValueError(f'最终词表缺少 {target} 列：{path}')
        mapping[source] = target
    else:
        df = df.rename(columns=mapping)
    df = df[['Campaign','AdGroup','Keyword']].fillna('').astype(str)
    for col in df:
        df[col] = df[col].str.strip().map(lambda v:v[1:] if v.startswith(("'=", "'+", "'-", "'@")) else v)
    df = df.loc[(df != '').any(axis=1)]
    if df.empty or (df == '').any().any():
        raise ValueError('最终词表为空，或有关键词未填写 campaign / adgroup / keywords')
    return df.drop_duplicates().reset_index(drop=True)


def verify_final_review(directory, final):
    """A previously reviewed file cannot silently approve a newly generated selection."""
    import hashlib
    directory, final = Path(directory), Path(final)
    metadata = directory/'_internal/wordstat/delivery.json'
    approval = directory/'_internal/wordstat/final_review.json'
    delivered = json.loads(metadata.read_text('utf-8'))
    previous = json.loads(approval.read_text('utf-8')) if approval.exists() else {}
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    changed_file = previous.get('sha256') != digest or previous.get('mtime_ns') != final.stat().st_mtime_ns
    if previous.get('revision') != delivered['revision']:
        if (previous and not changed_file) or (not previous and final.stat().st_mtime < delivered['generated_at']):
            raise ValueError('Wordstat 结果已更新，请重新审核并保存 keywords_v2，再继续生成否词和广告语。')
    save_json(approval, {'revision':delivered['revision'],'sha256':digest,'mtime_ns':final.stat().st_mtime_ns,'file':final.name})
