# 暂空，目前先手动划分结构，未来可能会在这里接入ai来划分关键词结构
# 本文件内目前只有数据清洗功能
# 数据标准化层（Data Normalization）

# #KEYWORD_V2_STRUCTURE = {
#     "high_intent": [],
#     "mid_intent": [],
#     "low_intent": [],
#     "industry_terms": [],
#     "competitor_terms": [],
#     "negative_candidates": []
# }


# 默认运行： .\.venv\Scripts\python.exe -m modules.keyword_v2_builder
# 指定项目：.\.venv\Scripts\python.exe -m modules.keyword_v2_builder --project 星纵物联
# 按搜索量降序排列： .\.venv\Scripts\python.exe -m modules.keyword_v2_builder --project 星纵物联 --sort-volume


from pathlib import Path
import argparse
import csv
import re


def get_project_root():
    """
    获取项目根目录。
    当前文件位于 modules/keyword_v2_builder.py，
    所以 parent.parent 是项目根目录。
    """
    return Path(__file__).resolve().parent.parent


def clean_volume(volume_text):
    """
    清洗 Wordstat 搜索量。

    示例：
    "2 311" -> 2311
    "5 013" -> 5013
    "12 456" -> 12456
    "803" -> 803
    """

    if volume_text is None:
        return None

    volume_text = str(volume_text).strip()

    if not volume_text:
        return None

    # 只保留数字，去掉空格、逗号、特殊符号等
    digits = re.sub(r"[^\d]", "", volume_text)

    if not digits:
        return None

    return int(digits)


def clean_keyword(keyword):
    """
    清洗关键词字段。
    只做轻量格式处理，不做语义判断。
    """

    if keyword is None:
        return ""

    keyword = str(keyword).strip()

    # 去掉 markdown 列表符号
    keyword = re.sub(r"^\s*[-*+]\s+", "", keyword)

    # 去掉编号，例如 1. xxx / 1、xxx / 1) xxx
    keyword = re.sub(r"^\s*\d+[\.、)]\s*", "", keyword)

    # 去掉反引号
    keyword = keyword.replace("`", "")

    # 合并多余空格
    keyword = re.sub(r"\s+", " ", keyword).strip()

    # 去掉行尾多余符号
    keyword = keyword.strip(" -—–：:；;，,。.")

    return keyword


def is_header_line(line):
    """
    判断是否是表头行。
    """

    normalized = line.strip().lower()

    header_patterns = [
        "keyword volume",
        "keyword\tvolume",
        "keyword | volume",
        "关键词 搜索量",
        "关键词\t搜索量",
        "关键词 | 搜索量",
        "词 搜索量",
        "词\t搜索量",
    ]

    return normalized in header_patterns


def parse_wordstat_line(line):
    """
    解析一行 Wordstat 手动数据。

    支持几种常见格式：

    1. tab 分隔：
       камера распознавания номеров    2 311

    2. 竖线分隔：
       камера распознавания номеров | 2 311

    3. 多空格分隔：
       камера распознавания номеров    2 311

    4. 普通尾部数字：
       камера распознавания номеров 2 311
    """

    original_line = line
    line = line.strip()

    if not line:
        return None

    if line.startswith("#") or line.startswith("```"):
        return None

    if is_header_line(line):
        return None

    keyword = ""
    volume_raw = ""

    # 1. 优先处理 tab
    if "\t" in line:
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) >= 2:
            keyword = parts[0]
            volume_raw = parts[-1]

    # 2. 再处理竖线
    elif "|" in line:
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 2:
            keyword = parts[0]
            volume_raw = parts[-1]

    # 3. 再处理多个空格
    else:
        parts = re.split(r"\s{2,}", line)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) >= 2:
            keyword = parts[0]
            volume_raw = parts[-1]
        else:
            # 4. 最后兜底：匹配行尾搜索量
            # 例如：камера распознавания номеров 2 311
            match = re.match(
                r"^(?P<keyword>.+?)\s+(?P<volume>\d[\d\s]*\d|\d)$",
                line
            )

            if match:
                keyword = match.group("keyword")
                volume_raw = match.group("volume")

    keyword = clean_keyword(keyword)
    volume = clean_volume(volume_raw)

    if not keyword or volume is None:
        return {
            "success": False,
            "raw_line": original_line,
            "reason": "无法解析关键词或搜索量"
        }

    return {
        "success": True,
        "keyword": keyword,
        "volume": volume,
        "raw_line": original_line
    }


def write_output_with_skipped(output_path, rows, skipped):
    """
    写入清洗结果。

    文件结构：
    1. 前半部分：清洗成功的数据，TSV格式
    2. 中间空 5 行
    3. 末尾：无法解析的原始行
    """

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["keyword", "volume"],
            delimiter="\t"
        )

        writer.writeheader()
        writer.writerows(rows)

        if skipped:
            # 和上面成功数据隔 5 行
            f.write("\n\n\n\n\n")
            f.write("# 无法解析的原始行\n")
            f.write("# 请人工检查这些行的格式，必要时手动补充到上方数据区。\n")

            for line in skipped:
                f.write(str(line).strip() + "\n")


def clean_wordstat_results(input_path, output_path, sort_by_volume=False):
    """
    清洗 Wordstat 手动查询结果。

    输入：
    wordstat_results_manual.txt

    输出：
    wordstat_results_cleaned.tsv

    注意：
    无法解析的行不再单独保存为文件，
    而是追加在 wordstat_results_cleaned.tsv 末尾。
    """

    text = input_path.read_text(encoding="utf-8")

    rows = []
    skipped = []
    seen = set()

    for line in text.splitlines():
        parsed = parse_wordstat_line(line)

        if parsed is None:
            continue

        if not parsed.get("success"):
            skipped.append(parsed["raw_line"])
            continue

        keyword = parsed["keyword"]
        volume = parsed["volume"]

        # 去重：同一个关键词只保留第一次出现
        if keyword in seen:
            continue

        seen.add(keyword)

        rows.append({
            "keyword": keyword,
            "volume": volume
        })

    if sort_by_volume:
        rows.sort(key=lambda x: x["volume"], reverse=True)

    write_output_with_skipped(
        output_path=output_path,
        rows=rows,
        skipped=skipped
    )

    print("Wordstat 数据清洗完成")
    print(f"成功解析关键词数：{len(rows)}")
    print(f"无法解析行数：{len(skipped)}")
    print(f"输出文件：{output_path}")

    if skipped:
        print("无法解析的行已追加到输出文件末尾。")


def main():
    parser = argparse.ArgumentParser(
        description="清洗 Wordstat 手动查询结果，为 keyword_v2 手动分组做准备。"
    )

    parser.add_argument(
        "--project",
        help="项目名称。如果不传，则运行后手动输入。"
    )

    parser.add_argument(
        "--sort-volume",
        action="store_true",
        help="按搜索量从高到低排序。默认保留原始顺序。"
    )

    args = parser.parse_args()

    project_name = args.project

    if not project_name:
        project_name = input("请输入项目名称：").strip()

    project_root = get_project_root()
    output_dir = project_root / "outputs" / project_name

    input_path = output_dir / "wordstat_results_manual.txt"
    output_path = output_dir / "wordstat_results_cleaned.tsv"

    if not input_path.exists():
        raise FileNotFoundError(
            f"找不到 wordstat_results_manual.txt：{input_path}\n"
            f"请先手动查询 Wordstat 搜索量，并保存为 wordstat_results_manual.txt。"
        )

    clean_wordstat_results(
        input_path=input_path,
        output_path=output_path,
        sort_by_volume=args.sort_volume
    )


if __name__ == "__main__":
    main()