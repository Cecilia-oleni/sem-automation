# 模块：sem_automation/cli/materials.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
from __future__ import annotations

import argparse

from sem_automation.materials.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按文件依赖运行 SEM 投放前自动化工作流。",
    )
    parser.add_argument('--wordstat-mode', choices=['api','manual'], default='api', help='默认 API；manual 为旧人工流程')
    parser.add_argument('--wordstat-region', action='append', help='地区ID，可重复；all 表示全部，覆盖项目配置')
    parser.add_argument('--review-file', help='明确选择种子审核 Excel/CSV')
    parser.add_argument('--keywords-file', help='明确选择最终分组 Excel/CSV')
    parser.add_argument(
        "--project",
        help="项目名称，对应 uploads 和 outputs 下的文件夹名称。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示流程和人工断点，不调用 API、不发起网页请求、不写文件。",
    )
    parser.add_argument(
        "--website",
        action="append",
        default=[],
        metavar="URL",
        help=(
            "显式指定客户网站，可重复传入；该列表会覆盖项目现有的 "
            "website_urls.txt。网址必须以 http:// 或 https:// 开头。"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_name = args.project or input("请输入项目名称：").strip()

    if not project_name:
        print("Pipeline 启动失败：项目名称不能为空。")
        return 2

    try:
        result = run_pipeline(
            project_name,
            dry_run=args.dry_run,
            website_urls=args.website,
            wordstat_mode=args.wordstat_mode, regions=args.wordstat_region,
            review_file=args.review_file, keywords_file=args.keywords_file,
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"Pipeline 启动失败：{error}")
        return 2
    except KeyboardInterrupt:
        print("\nPipeline 已由用户中断，可重新运行后从已有文件继续。")
        return 130
    except Exception as error:
        print(f"Pipeline 发生未预期错误：{error}")
        return 1

    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
