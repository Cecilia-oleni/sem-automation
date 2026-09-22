# 模块：sem_automation/reporting/yutong/sync.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
# 该示例复用本地数据；详见 docs/月报操作说明.md。
"""Explicit history synchronization, with source checks, backups and rollback."""
import json
import os
from pathlib import Path
import shutil
import uuid
from sem_automation.core.runs import digest, write_json

def sync(manifest_path):
    manifest_path=Path(manifest_path).resolve()
    data=json.loads(manifest_path.read_text(encoding='utf-8'))
    run=manifest_path.parent.parent
    if data.get('schema')!='yutong_sync_v1' or data.get('status')!='completed' or data.get('client')!='yutong' or Path(data.get('run','')).resolve()!=run:
        raise ValueError('不是已完成的宇通运行清单')
    if manifest_path.parent.name!='_internal' or run.parent.name!='runs':raise ValueError('运行清单位置不正确')
    entries=data.get('entries',[])
    if len(entries)!=2:raise ValueError('同步清单必须包含两份历史表')
    config=json.loads((run/'_internal/resolved_config.json').read_text(encoding='utf-8'))
    if config.get('reportMonth')!=data.get('month') or config.get('client')!='yutong':raise ValueError('清单与本次周期配置不一致')
    expected={Path(config['paths'][key]).resolve() for key in ['countryHistory','ytdHistory']}
    if {Path(e['source']).resolve() for e in entries}!=expected:raise ValueError('同步目标与本次输入配置不一致')
    sources=[];candidates=[]
    for e in entries:
        source=Path(e['source']).resolve();candidate=Path(e['candidate']).resolve()
        if candidate.parent!=run/'history_candidates' or source==candidate or source.suffix!='.xlsx':raise ValueError('候选文件或源文件路径不正确')
        if not source.is_file() or digest(source)!=e['source_sha256']:raise ValueError(f'原表已变化或不存在，停止同步: {source}')
        if not candidate.is_file() or digest(candidate)!=e['candidate_sha256']:raise ValueError(f'候选文件已变化或不存在: {candidate}')
        sources.append(source);candidates.append(candidate)
    if len(set(sources))!=2 or len(set(candidates))!=2:raise ValueError('同步条目重复')
    lock=run/'_internal/sync.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('此运行正在同步或有未恢复的同步，请检查 sync 状态')
    os.close(fd)
    transaction=uuid.uuid4().hex
    backup_dir=run/'_internal/backups'/transaction
    staged=[];replaced=[];backups=[];keep_lock=False
    try:
        backup_dir.mkdir(parents=True)
        for i,(source,candidate) in enumerate(zip(sources,candidates)):
            if digest(source)!=entries[i]['source_sha256']:raise ValueError(f'原表已变化: {source}')
            backup=backup_dir/f'{i}-{source.name}'
            shutil.copy2(source,backup);backups.append(backup)
            if digest(backup)!=entries[i]['source_sha256']:raise ValueError('备份校验失败')
            temp=source.with_name(f'.{source.name}.{transaction}.pending')
            staged.append(temp);shutil.copy2(candidate,temp)
            if digest(temp)!=entries[i]['candidate_sha256']:raise ValueError('暂存候选校验失败')
        for i,source in enumerate(sources):
            if digest(source)!=entries[i]['source_sha256']:raise ValueError(f'原表已变化: {source}')
            os.replace(staged[i],source);replaced.append(i)
        write_json(run/'_internal/sync_result.json',{'status':'synced','backups':[str(p) for p in backups]})
        return backup_dir
    except Exception as exc:
        errors=[]
        for i in reversed(replaced):
            try:
                if digest(sources[i])!=entries[i]['candidate_sha256']:
                    raise RuntimeError(f'替换后源文件又被修改，不能自动回滚覆盖: {sources[i]}')
                recovery=sources[i].with_name(f'.{sources[i].name}.{transaction}.restore')
                shutil.copy2(backups[i],recovery);os.replace(recovery,sources[i])
            except Exception as restore_error:errors.append(str(restore_error))
        keep_lock=bool(errors)
        write_json(run/'_internal/sync_result.json',{'status':'recovery_required' if errors else 'rolled_back','error':str(exc),'recovery_errors':errors,'backups':[str(p) for p in backups]})
        if errors:raise RuntimeError(f'同步失败且自动恢复受阻；备份位于 {backup_dir}: {errors}') from exc
        raise
    finally:
        for temp in staged:
            if temp.exists():temp.unlink()
        if not keep_lock:lock.unlink(missing_ok=True)
