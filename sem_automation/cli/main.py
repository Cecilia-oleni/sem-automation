# 模块：sem_automation/cli/main.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
"""Single command dispatcher; help and material dry-run have no side effects."""
import argparse
from pathlib import Path
from sem_automation.core.paths import PROJECT_ROOT

def parser():
    p = argparse.ArgumentParser(description='SEM：物料工作流与客户报告')
    families = p.add_subparsers(dest='family', required=True)
    materials = families.add_parser('materials', help='生成物料，保留人工审核节点').add_subparsers(dest='action', required=True)
    from sem_automation.cli.materials import build_parser
    materials.add_parser('run', parents=[build_parser()], add_help=False)
    reports = families.add_parser('reports', help='生成通用、安琪或宇通月报').add_subparsers(dest='kind', required=True)
    s = reports.add_parser('standard', help='通用 Direct + Metrika 报告')
    s.add_argument('--client', required=True, type=Path)
    s.add_argument('--month'); s.add_argument('--date-from'); s.add_argument('--date-to')
    s.add_argument('--source', choices=['existing','api'], default='existing')
    s.add_argument('--data-dir', type=Path, help='existing 模式必填；包含 _internal 原始数据的目录')
    s.add_argument('--enrich', action='store_true', help='显式联网补充历史数据')
    s.add_argument('--internal-only', action='store_true'); s.add_argument('--node')
    a = reports.add_parser('angel-yeast', help='安琪专用：数据计算及三份 Excel')
    a.add_argument('--config', type=Path, default=PROJECT_ROOT/'config/angel_yeast_direct_monthly.json')
    a.add_argument('--month', required=True)
    a.add_argument('--reuse-raw', type=Path, help='原始 JSON 路径；复制到新运行目录后重建')
    a.add_argument('--skip-translation', action='store_true'); a.add_argument('--skip-calibration', action='store_true'); a.add_argument('--node')
    y = reports.add_parser('yutong', help='宇通 Yandex 月报；sync 为独立历史表同步')
    y.add_argument('action', nargs='?', choices=['sync'])
    y.add_argument('--config', type=Path); y.add_argument('--month'); y.add_argument('--node')
    y.add_argument('--manifest', type=Path)
    y.add_argument('--check-only', action='store_true', help='只检查输入与历史期间，不生成文件')
    return p

def main(argv=None):
    p=parser(); args=p.parse_args(argv)
    try:
        if args.family == 'materials':
            from sem_automation.materials.pipeline import run_pipeline
            project = args.project or input('请输入项目名称：').strip()
            result=run_pipeline(project, dry_run=args.dry_run, website_urls=args.website)
            return 1 if result.get('failed') else 0
        if args.kind == 'angel-yeast':
            from sem_automation.reporting.angel_yeast.pipeline import run_report
            result=run_report(config=args.config, month=args.month, reuse_raw=args.reuse_raw, skip_translation=args.skip_translation, skip_calibration=args.skip_calibration, node=args.node)
        elif args.kind == 'standard':
            from sem_automation.reporting.standard.pipeline import run_report, load_client
            from sem_automation.reporting.common.dates import date_range
            from sem_automation.core.runs import new_run, write_json, tidy_run
            if args.source=='existing' and not args.data_dir:
                raise ValueError('existing 模式需要 --data-dir，避免误用旧月份数据')
            start,end,_=date_range(args.month,args.date_from,args.date_to)
            client,*_=load_client(args.client)
            run=new_run(client['slug'],'standard',args.month or f'{start}_{end}')
            try:
                result=run_report(client_path=args.client,start=start,end=end,source=args.source,enrich=args.enrich,node=args.node,data_dir=args.data_dir,output_dir=run/'deliverables',customer_copy=not args.internal_only,run_dir=run)
                tidy_run(run)
                write_json(run/'_internal/status.json',{'status':'completed'})
            except Exception as exc:
                write_json(run/'_internal/status.json',{'status':'failed','error':str(exc)})
                raise
        elif args.action=='sync':
            if not args.manifest:raise ValueError('sync 必须指定 --manifest')
            from sem_automation.reporting.yutong.sync import sync
            result=sync(args.manifest)
        else:
            if not args.config or not args.month:raise ValueError('宇通报告必须指定 --config 和 --month')
            from sem_automation.reporting.yutong.pipeline import run_report
            result=run_report(config_path=args.config,month=args.month,node=args.node,check_only=args.check_only)
        print(f'完成：{result}')
        return 0
    except KeyboardInterrupt:
        print('已中断，可修正输入后重新运行。');return 130
    except Exception as exc:
        print(f'执行失败：{exc}');return 1
