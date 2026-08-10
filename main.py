from __future__ import annotations

import csv
from pathlib import Path

from modules.file_reader import read_file
from modules.website_url_extractor import (
    extract_client_website_urls,
    update_website_urls_file,
)


PROJECT_ROOT = Path(__file__).resolve().parent


def collect_project_data(project_name: str) -> dict:
    """读取项目资料，并生成本地分析阶段的标准输出文件。"""
    project_name = (project_name or "").strip()
    if not project_name:
        raise ValueError("项目名称不能为空。")

    project_dir = PROJECT_ROOT / "uploads" / project_name
    if not project_dir.exists() or not project_dir.is_dir():
        raise FileNotFoundError(f"项目不存在：{project_dir}")

    print(f"\n当前项目：{project_name}")

    all_text: list[str] = []
    file_reports: list[dict] = []
    source_documents: list[dict] = []

    for file_path in project_dir.rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(project_dir)
        print(f"\n发现文件：{relative_path}")

        content, status, note = read_file(file_path)
        char_count = len(content)

        file_reports.append({
            "项目名称": project_name,
            "文件相对路径": str(relative_path),
            "文件名": file_path.name,
            "文件类型": file_path.suffix.lower(),
            "读取状态": status,
            "提取字符数": char_count,
            "备注": note,
        })

        if status == "成功" and content:
            source_documents.append({
                "source": str(relative_path),
                "content": content,
            })
            all_text.append(f"\n\n===== {relative_path} =====\n\n{content}")

    final_content = "\n".join(all_text)
    output_dir = PROJECT_ROOT / "outputs" / project_name
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_text_path = output_dir / "raw_text.txt"
    raw_text_path.write_text(final_content, encoding="utf-8")

    report_path = output_dir / "file_report.csv"
    fieldnames = [
        "项目名称",
        "文件相对路径",
        "文件名",
        "文件类型",
        "读取状态",
        "提取字符数",
        "备注",
    ]
    with report_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(file_reports)

    website_records = extract_client_website_urls(source_documents)
    website_url_status = update_website_urls_file(
        output_dir=output_dir,
        records=website_records,
    )

    website_urls_path = output_dir / "website_urls.txt"
    if website_url_status == "written":
        print(f"\n已提取客户网站：{website_urls_path}")
        for record in website_records:
            print(f"- {record['url']}（来源：{record['source']}）")
    elif website_url_status == "removed_stale":
        print("\n客户资料中未识别到网站，已移除上次自动生成的网址文件。")
    elif website_url_status == "preserved_manual":
        print("\n客户资料中未识别到网站；现有人工 website_urls.txt 已保留，请人工复核。")
    else:
        print("\n客户资料中未识别到网站，本项目不生成 website_urls.txt。")

    print(f"\n原始文本已保存：{raw_text_path}")
    print(f"文件读取报告已保存：{report_path}")
    print(f"总共提取字符数：{len(final_content)}")
    print(f"共扫描文件数：{len(file_reports)}")

    generated_files = [raw_text_path, report_path]
    if website_urls_path.exists():
        generated_files.append(website_urls_path)

    return {
        "project_name": project_name,
        "project_dir": project_dir,
        "output_dir": output_dir,
        "raw_text_path": raw_text_path,
        "report_path": report_path,
        "website_urls_path": website_urls_path if website_urls_path.exists() else None,
        "website_url_status": website_url_status,
        "website_records": website_records,
        "generated_files": generated_files,
        "file_count": len(file_reports),
        "character_count": len(final_content),
    }


def main() -> None:
    print("SEM助手启动成功")
    project_name = input("请输入项目名称：").strip()
    collect_project_data(project_name)


if __name__ == "__main__":
    main()
