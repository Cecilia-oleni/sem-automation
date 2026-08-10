# & ".\.venv\Scripts\python.exe" pipeline.py



from __future__ import annotations

import argparse

from modules.pipeline_runner import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按文件依赖运行 SEM 投放前自动化工作流。",
    )
    parser.add_argument(
        "--project",
        help="项目名称，对应 uploads 和 outputs 下的文件夹名称。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示流程和人工断点，不调用 API、不发起网页请求、不写文件。",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_name = args.project or input("请输入项目名称：").strip()

    if not project_name:
        print("Pipeline 启动失败：项目名称不能为空。")
        return 2

    try:
        result = run_pipeline(project_name, dry_run=args.dry_run)
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
