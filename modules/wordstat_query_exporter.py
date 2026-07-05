# .\.venv\Scripts\python.exe -m modules.wordstat_query_exporter  #默认清洗模式
# .\.venv\Scripts\python.exe -m modules.wordstat_query_exporter --project xxx  #指定项目名称
# .\.venv\Scripts\python.exe -m modules.wordstat_query_exporter --project xxx --copy-only   #跳过清洗模式


from pathlib import Path
import argparse
import re


def get_project_root():
    """
    获取项目根目录。
    当前文件位于 modules/wordstat_query_exporter.py，
    所以 parent.parent 是项目根目录。
    """
    return Path(__file__).resolve().parent.parent


def clean_keyword_line(line):
    """
    清洗单行关键词。

    处理内容：
    - 去掉 Markdown 项目符号
    - 去掉编号
    - 去掉反引号
    - 去掉中文括号/英文括号中的说明
    - 去掉冒号后的解释
    - 去掉多余空格
    """

    original_line = line
    line = line.strip()

    if not line:
        return ""

    # 跳过 Markdown 标题、代码块
    if line.startswith("#"):
        return ""

    if line.startswith("```"):
        return ""

    # 去掉 Markdown 列表符号
    line = re.sub(r"^\s*[-*+]\s+", "", line)

    # 去掉编号，例如 1. xxx / 1、xxx / 1) xxx
    line = re.sub(r"^\s*\d+[\.、)]\s*", "", line)

    # 去掉 Markdown inline code 反引号
    line = line.replace("`", "").strip()

    # 如果有中文冒号，且前面明显是标签，则取冒号后内容
    # 例如：关键词：камера распознавания номеров
    if "：" in line:
        left, right = line.split("：", 1)
        if len(left) <= 10:
            line = right.strip()

    # 如果有英文冒号，且前面明显是标签，则取冒号后内容
    if ":" in line:
        left, right = line.split(":", 1)
        if len(left) <= 15 and re.search(r"[A-Za-z\u4e00-\u9fff]", left):
            line = right.strip()

    # 去掉中文括号说明，例如 камера（车牌识别摄像头）
    line = re.sub(r"（.*?）", "", line)

    # 去掉英文括号说明，例如 camera (competitor)
    line = re.sub(r"\(.*?\)", "", line)

    # 去掉行尾常见说明
    line = line.replace("需人工确认", "")
    line = line.replace("竞品", "")
    line = line.replace("客户品牌", "")
    line = line.replace("品牌词", "")

    # 去掉多余分隔符
    line = line.strip(" -—–：:；;，,。.")

    # 合并多余空格
    line = re.sub(r"\s+", " ", line).strip()

    return line


def is_review_needed_line(line):
    """
    判断这一行是否需要单独放入 review_needed 文件。
    例如包含竞品、需人工确认等标记。
    """

    markers = [
        "竞品",
        "需人工确认",
        "不确定",
        "maybe",
        "competitor",
        "confirm"
    ]

    lower_line = line.lower()

    return any(marker.lower() in lower_line for marker in markers)


def export_copy_only(input_path, output_path):
    """
    跳过清洗模式。
    只去掉空行，保留用户已经整理好的关键词。
    """

    text = input_path.read_text(encoding="utf-8")

    lines = []
    seen = set()

    for line in text.splitlines():
        cleaned = line.strip()

        if not cleaned:
            continue

        if cleaned in seen:
            continue

        seen.add(cleaned)
        lines.append(cleaned)

    output_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"已使用 copy-only 模式导出：{output_path}")
    print(f"共导出 {len(lines)} 个关键词。")


def export_cleaned(input_path, output_path, review_needed_path):
    """
    默认清洗模式。
    输出：
    - wordstat_query_list.txt：普通关键词
    - wordstat_query_review_needed.txt：竞品/需人工确认关键词
    """

    text = input_path.read_text(encoding="utf-8")

    keywords = []
    review_needed = []

    seen_keywords = set()
    seen_review = set()

    for line in text.splitlines():
        raw_line = line.strip()

        if not raw_line:
            continue

        cleaned = clean_keyword_line(raw_line)

        if not cleaned:
            continue

        if is_review_needed_line(raw_line):
            if cleaned not in seen_review:
                seen_review.add(cleaned)
                review_needed.append(cleaned)
        else:
            if cleaned not in seen_keywords:
                seen_keywords.add(cleaned)
                keywords.append(cleaned)

    output_path.write_text("\n".join(keywords), encoding="utf-8")
    review_needed_path.write_text("\n".join(review_needed), encoding="utf-8")

    print(f"已导出 Wordstat 查询清单：{output_path}")
    print(f"普通关键词数量：{len(keywords)}")

    print(f"已导出需人工确认关键词：{review_needed_path}")
    print(f"需人工确认关键词数量：{len(review_needed)}")


def main():
    parser = argparse.ArgumentParser(
        description="从 keyword_v1_reviewed.md 导出 Wordstat 查询关键词清单。"
    )

    parser.add_argument(
        "--project",
        help="项目名称。如果不传，则运行后手动输入。"
    )

    parser.add_argument(
        "--copy-only",
        action="store_true",
        help="跳过清洗，只去掉空行并直接复制到 wordstat_query_list.txt。"
    )

    args = parser.parse_args()

    project_name = args.project

    if not project_name:
        project_name = input("请输入项目名称：").strip()

    project_root = get_project_root()
    output_dir = project_root / "outputs" / project_name

    input_path = output_dir / "keyword_v1_reviewed.md"
    output_path = output_dir / "wordstat_query_list.txt"
    review_needed_path = output_dir / "wordstat_query_review_needed.txt"

    if not input_path.exists():
        raise FileNotFoundError(
            f"找不到 keyword_v1_reviewed.md：{input_path}\n"
            f"请先人工审核 keyword_v1.md，并保存为 keyword_v1_reviewed.md。"
        )

    if args.copy_only:
        export_copy_only(
            input_path=input_path,
            output_path=output_path
        )
    else:
        export_cleaned(
            input_path=input_path,
            output_path=output_path,
            review_needed_path=review_needed_path
        )


if __name__ == "__main__":
    main()