# 模块：sem_automation/materials/context/crawl.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path
from sem_automation.core.paths import PROJECT_ROOT, material_dir
from sem_automation.materials.context.website import resolve_website_urls_path
from sem_automation.readers.web_reader import read_seed_urls, crawl_website, build_markdown, write_csv

def get_project_root():
    return PROJECT_ROOT

def read_website(
    project_name: str,
    max_pages: int = 12,
    max_depth: int = 2,
    delay: float = 0.5,
    timeout: int = 15,
    max_chars_per_page: int = 20000,
    project_root: Path | None = None,
) -> dict:
    """
    网页读取模块的主业务函数。
    """
    project_root = project_root or get_project_root()
    output_dir = material_dir("outputs", project_name, project_root)

    url_file, url_source = resolve_website_urls_path(
        project_root=project_root,
        project_name=project_name,
    )

    if url_file is None:
        print(
            f"客户资料未提供网站，本项目跳过网页读取：{project_name}"
        )
        return {
            "project_name": project_name,
            "status": "skipped_no_website",
            "seed_urls": [],
            "pages": [],
            "links": [],
        }

    if url_source == "uploads_legacy":
        print(
            "提示：正在读取旧路径中的 website_urls.txt。\n"
            f"旧路径：{url_file}\n"
            "后续建议通过 main.py 生成到 outputs/项目名称/。"
        )
    else:
        print(f"网站入口文件：{url_file}")

    seed_urls = read_seed_urls(url_file)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"开始读取项目网站：{project_name}")
    print(f"入口网址数量：{len(seed_urls)}")
    print(f"最大页面数：{max_pages}")
    print(f"最大抓取深度：{max_depth}")

    pages, discovered_links, report_rows = crawl_website(
        seed_urls=seed_urls,
        max_pages=max_pages,
        max_depth=max_depth,
        delay=delay,
        timeout=timeout,
        max_chars_per_page=max_chars_per_page,
    )

    result = {
        "project_name": project_name,
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "seed_urls": seed_urls,
        "settings": {
            "max_pages": max_pages,
            "max_depth": max_depth,
            "delay": delay,
            "timeout": timeout,
            "max_chars_per_page": max_chars_per_page,
        },
        "summary": {
            "successful_pages": len(pages),
            "discovered_links": len(discovered_links),
            "report_rows": len(report_rows),
        },
        "pages": pages,
        "links": discovered_links,
    }

    json_path = output_dir / "website_pages.json"
    markdown_path = output_dir / "website_content.md"
    report_path = output_dir / "web_report.csv"

    json_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    markdown_path.write_text(
        build_markdown(project_name, pages),
        encoding="utf-8",
    )

    write_csv(report_path, report_rows)

    print("\n网页读取完成")
    print(f"成功页面数：{len(pages)}")
    print(f"发现内部链接数：{len(discovered_links)}")
    print(f"结构化数据：{json_path}")
    print(f"网页正文：{markdown_path}")
    print(f"读取报告：{report_path}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="读取客户网站并整理网页内容和内部链接。"
    )

    parser.add_argument(
        "--project",
        help="项目名称，对应 uploads 和 outputs 下的文件夹名称",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=30,
        help="最多成功读取多少个HTML页面，默认30",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="站内链接最大抓取深度，默认2",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="每次请求后的等待秒数，默认0.5",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="单个网页请求超时秒数，默认15",
    )
    parser.add_argument(
        "--max-chars-per-page",
        type=int,
        default=20000,
        help="每个页面最多保留的正文字符数，默认20000",
    )

    args = parser.parse_args()

    project_name = (
        args.project
        or input("请输入项目名称（须与 uploads 下的文件夹名完全一致）：").strip()
    )

    if not project_name:
        raise ValueError("项目名称不能为空。")

    if args.max_pages <= 0:
        raise ValueError("--max-pages 必须大于0。")

    if args.max_depth < 0:
        raise ValueError("--max-depth 不能小于0。")

    read_website(
        project_name=project_name,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay=args.delay,
        timeout=args.timeout,
        max_chars_per_page=args.max_chars_per_page,
    )


if __name__ == "__main__":
    main()
