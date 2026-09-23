# 终端输入：python sem.py materials wordstat query --project '通亚'
# 整理已有查询：python sem.py materials wordstat organize --project '通亚'
"""Complete seed collection, validated AI enrichment and deterministic fair selection."""
import hashlib
import json
import time
import re
from pathlib import Path
from sem_automation.core.paths import PROJECT_ROOT, material_dir
from sem_automation.integrations.yandex.wordstat.client import WordstatClient, save_json, file_lock
from sem_automation.materials.keywords.tables import key, choose_file, seeds_from_table, REVIEW_NAMES, FIELDS, write_tables


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def settings(project, root, regions=None):
    path = material_dir('uploads', project, root)/'wordstat.json'
    cfg = json.loads(path.read_text('utf-8-sig')) if path.exists() else {}
    chosen = regions if regions is not None else cfg.get('regions', [])
    if chosen == ['all']:
        chosen = []
    if not isinstance(chosen, list) or len(chosen) > 100 or any(not str(r).isdigit() for r in chosen):
        raise ValueError('Wordstat regions 必须是地区ID列表；全部地区为 [] 或命令 --wordstat-region all')
    return {'regions': sorted(set(map(str, chosen))), 'devices':['DEVICE_ALL'], 'numPhrases':30}


def inputs(project, *, root=PROJECT_ROOT, review_file=None, regions=None):
    output = material_dir('outputs', project, root)
    source = choose_file(output, REVIEW_NAMES, review_file)
    if source is None:
        raise FileNotFoundError('请审核 keywords_v1.xlsx，另存 keywords_v1_reviewed.xlsx 或 .csv')
    seeds = seeds_from_table(source)
    cfg = settings(project, root, regions)
    # CN edits do not require a paid query; changes of Russian text or parameters do.
    task = fingerprint({'phrases':[r['keywords'] for r in seeds], 'settings':cfg, 'schema':1})
    return output, seeds, cfg, task


def query(project, *, root=PROJECT_ROOT, review_file=None, regions=None, client=None, report=print, dry_run=False, refresh=False):
    output, seeds, cfg, task = inputs(project, root=root, review_file=review_file, regions=regions)
    report(f'Wordstat：{len(seeds)} 个种子；地区 {cfg["regions"] or "全部"}；全部设备；所有种子均会查询。')
    if dry_run:
        return {'task':task, 'seeds':len(seeds), 'settings':cfg, 'dry_run':True}
    internal = output/'_internal/wordstat'
    with file_lock(internal/'task.lock'):
        current = internal/'current.json'
        previous = json.loads(current.read_text('utf-8')) if current.exists() else {}
        if previous.get('task') == task and not refresh:
            generation = previous['generation']
        else:
            generation = f'{time.time_ns()}'
        run = internal/task/generation
        save_json(current, {'task':task, 'generation':generation})
        state = {'task':task, 'settings':cfg, 'status':'running', 'total':len(seeds), 'completed':0}
        save_json(run/'status.json', state)
        records = []
        try:
            for i, seed in enumerate(seeds):
                phrase = seed['keywords']
                path = run/'responses'/f'{fingerprint(phrase)}.json'
                if path.exists():
                    record = json.loads(path.read_text('utf-8'))
                else:
                    if client is None:
                        client = WordstatClient(root)
                    data = client.top_requests(phrase, cfg['regions'])
                    record = {'phrase':phrase, 'time':time.time(), 'response':data}
                    # Validate platform shapes and counts before committing completion.
                    build_candidates([record], [seed])
                    save_json(path, record)
                records.append(record)
                state['completed'] = i + 1
                save_json(run/'status.json', state)
                report(f'Wordstat 已完成 {i+1}/{len(seeds)}：{phrase}')
            save_json(run/'collected.json', {'seeds':seeds, 'records':records, 'settings':cfg, 'task':task})
            state['status'] = 'completed'
            save_json(run/'status.json', state)
        except BaseException as exc:
            state.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=str(exc))
            save_json(run/'status.json', state)
            raise
        return run


def count(value):
    if value is None:
        return None
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError('Wordstat 搜索量应为非负整数或缺失')
    return int(value)


def build_candidates(records, seeds):
    seed_map = {key(s['keywords']):s for s in seeds}
    candidates = {}
    for record in sorted(records, key=lambda r:(r['time'], r['phrase'])):
        response = record['response']
        if not isinstance(response, dict):
            raise ValueError('Wordstat response 必须是对象')
        entries = [(record['phrase'], response.get('totalCount'), 'seed')]
        for kind in ('results', 'associations'):
            items = response.get(kind, [])
            if not isinstance(items, list):
                raise ValueError(f'Wordstat {kind} 必须是数组')
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get('phrase'), str) or not item['phrase'].strip():
                    raise ValueError('Wordstat 扩展词结构异常')
                entries.append((item['phrase'], item.get('count'), kind))
        for phrase, volume, kind in entries:
            normalized = key(phrase)
            row = candidates.setdefault(normalized, {'keywords':phrase, 'sources':[], 'observations':[], 'volume':None, 'seed':normalized in seed_map})
            volume = count(volume)
            origin = key(record['phrase'])
            if origin not in row['sources']:
                row['sources'].append(origin)
            row['observations'].append({'seed':record['phrase'], 'kind':kind, 'volume':volume, 'time':record['time']})
            if kind == 'seed':
                row['own_volume'] = volume
                row['keywords'] = seed_map.get(normalized, {}).get('keywords', phrase)
            elif volume is not None:
                row['volume'] = volume
    for normalized, row in candidates.items():
        if 'own_volume' in row:
            row['volume'] = row.pop('own_volume')
        row['sources'].sort()
        row['keywords_CN'] = seed_map.get(normalized, {}).get('keywords_CN', '')
    return dict(sorted(candidates.items()))


def fair_select(candidates, *, limit=600, per_seed=30):
    seeds = sorted(k for k,v in candidates.items() if v['seed'])
    if len(seeds) > limit:
        raise ValueError('种子超过最终上限')
    rank = {'high':0, 'medium':1, 'low':2}
    def order(k):
        row = candidates[k]
        return (rank[row['relevance']], -row['score'], -(row['volume'] if row['volume'] is not None else -1), k)
    queues = {}
    for seed in seeds:
        queues[seed] = sorted((k for k,v in candidates.items() if not v['seed'] and seed in v['sources'] and v['relevance'] != 'low'), key=order)[:per_seed]
    selected = list(seeds)
    seen = set(seeds)
    for level in ('high','medium'):
        working = {s:[k for k in queues[s] if candidates[k]['relevance'] == level] for s in seeds}
        while len(selected) < limit:
            added = False
            for seed in seeds:
                while working[seed] and working[seed][0] in seen:
                    working[seed].pop(0)
                if working[seed]:
                    k = working[seed].pop(0)
                    selected.append(k); seen.add(k); added = True
                    if len(selected) == limit:
                        break
            if not added:
                break
    return selected, queues


def ask_json(prompt):
    from sem_automation.ai.llm_client import call_llm
    result = call_llm(prompt=prompt, temperature=0, max_tokens=6500)
    text = result['content'].strip()
    if text.startswith('```'):
        text = text.split('\n',1)[1].rsplit('```',1)[0]
    return json.loads(text)


def organize(project, *, root=PROJECT_ROOT, review_file=None, regions=None, ai=None, writer=None, overwrite=False):
    from sem_automation.ai.prompt_loader import load_prompt
    output, seeds, cfg, task = inputs(project, root=root, review_file=review_file, regions=regions)
    internal = output/'_internal/wordstat'
    with file_lock(internal/'task.lock'):
        current = json.loads((internal/'current.json').read_text('utf-8'))
        if current['task'] != task:
            raise ValueError('审核词表或地区已变化，请先运行 wordstat query')
        run = internal/task/current['generation']
        if json.loads((run/'status.json').read_text('utf-8'))['status'] != 'completed':
            raise ValueError('仍有种子未完成查询，请先续跑 query')
        collected = json.loads((run/'collected.json').read_text('utf-8'))
        candidates = build_candidates(collected['records'], seeds)
        if sum(v['seed'] for v in candidates.values()) != len(seeds):
            raise ValueError('原始响应缺少种子，不能生成完整结果')
        brief = (output/'project_brief.md').read_text('utf-8')
        prompt = load_prompt('materials/wordstat_enrich')
        model_cfg = _model_identity()
        revision = fingerprint({'seeds':seeds, 'candidates':candidates, 'brief':brief, 'prompt':prompt, 'model':model_cfg})
        ai_dir = run/'ai'/revision
        if (output/'wordstat_results.xlsx').exists() or (output/'wordstat_results.csv').exists():
            delivered = internal/'delivery.json'
            previous = json.loads(delivered.read_text('utf-8')) if delivered.exists() else {}
            if not overwrite:
                if previous.get('revision') == revision and all((output/f'wordstat_results.{ext}').exists() for ext in ('xlsx','csv')):
                    return output/'wordstat_results.xlsx'
                raise ValueError('已有 Wordstat 结果。确认备份人工修改后，加 --overwrite 生成新结果。')
        ai = ai or ask_json
        state_path = ai_dir/'status.json'
        save_json(state_path, {'status':'running'})
        try:
            taxonomy_path = ai_dir/'taxonomy.json'
            if taxonomy_path.exists():
                taxonomy = json.loads(taxonomy_path.read_text('utf-8'))
            else:
                taxonomy = ai('根据项目资料制定简洁的中文广告系列和广告组列表。只返回 JSON 数组，每项只有 campaign、adgroup 两个非空中文名称。同一业务使用统一名称。\n资料：'+brief+'\n种子：'+json.dumps(seeds,ensure_ascii=False))
                if not isinstance(taxonomy,list) or not taxonomy or any(not isinstance(r,dict) or set(r) != {'campaign','adgroup'} or not all(isinstance(v,str) and re.search(r'[\u3400-\u9fff]',v) for v in r.values()) for r in taxonomy):
                    raise ValueError('AI 分组目录格式不正确')
                save_json(taxonomy_path, taxonomy)
            groups = {(r['campaign'],r['adgroup']) for r in taxonomy}
            keys = sorted(candidates)
            for start in range(0,len(keys),20):
                batch_keys = keys[start:start+20]
                batch = [{'id':k,'keywords':candidates[k]['keywords'], 'seed':candidates[k]['seed']} for k in batch_keys]
                path = ai_dir/f'batch-{start:05d}.json'
                if path.exists():
                    result = json.loads(path.read_text('utf-8'))
                else:
                    result = ai(prompt.replace('{{brief}}',brief).replace('{{groups}}',json.dumps(taxonomy,ensure_ascii=False)).replace('{{candidates}}',json.dumps(batch,ensure_ascii=False)))
                validate_enrichment(result, batch_keys, groups)
                save_json(path, result)
                for item in result:
                    row = candidates[item['id']]
                    old_cn = row['keywords_CN']
                    row.update({k:v for k,v in item.items() if k != 'id'})
                    if row['seed'] and old_cn:
                        row['keywords_CN'] = old_cn
            selected, queues = fair_select(candidates)
            rows = [{f:candidates[k].get(f) for f in FIELDS} for k in selected]
            chosen = set(selected)
            eligible = {k for q in queues.values() for k in q}
            for k,row in candidates.items():
                row['selection'] = 'selected' if k in chosen else 'low_relevance' if row['relevance'] == 'low' else 'per_seed_limit' if k not in eligible else 'global_limit'
            save_json(ai_dir/'audit.json', {'settings':cfg, 'candidates':candidates, 'per_seed_candidates':queues, 'selected':selected})
            (writer or write_tables)(output/'wordstat_results', FIELDS, rows, root=root)
            save_json(internal/'delivery.json', {'revision':revision,'task':task,'generated_at':time.time(),'run':str(run.relative_to(output)), 'audit':str((ai_dir/'audit.json').relative_to(output)), 'rows':len(rows), 'unknown_volume':sum(r['volume'] is None for r in rows), 'settings':cfg})
            save_json(state_path, {'status':'completed','rows':len(rows)})
            print(f'Wordstat 整理完成：{len(seeds)} 个种子，{len(rows)-len(seeds)} 个扩展词；空白搜索量表示未返回，不是0。')
            return output/'wordstat_results.xlsx'
        except BaseException as exc:
            save_json(state_path, {'status':'failed','error':str(exc)})
            raise


def _model_identity():
    from sem_automation.ai.llm_client import get_openrouter_model
    import os
    return {'provider':os.getenv('DEFAULT_LLM_PROVIDER','openrouter'),'model':get_openrouter_model()}


def validate_enrichment(rows, expected, groups):
    fields = {'id','campaign','adgroup','keywords_CN','relevance','score','reason'}
    if not isinstance(rows,list) or len(rows) != len(expected):
        raise ValueError('AI 返回条数与候选不符，未生成最终表；可续跑整理')
    seen = set()
    for row in rows:
        if not isinstance(row,dict) or set(row) != fields or row.get('id') not in expected or row['id'] in seen:
            raise ValueError('AI 返回漏词、重复词、虚构词或多余字段')
        seen.add(row['id'])
        if (row['campaign'],row['adgroup']) not in groups or row['relevance'] not in ('high','medium','low'):
            raise ValueError('AI 分组或相关性不符合约定')
        if type(row['score']) is not int or not 0 <= row['score'] <= 100 or not isinstance(row['keywords_CN'],str) or not re.search(r'[\u3400-\u9fff]',row['keywords_CN']) or not isinstance(row['reason'],str):
            raise ValueError('AI 评分、翻译或理由缺失')
