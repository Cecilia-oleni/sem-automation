#直接终端运行 .\.venv\Scripts\python.exe -m modules.wordstat_query_exporter

from pathlib import Path
import argparse
import re


def get_project_root():
    return Path(__file__).resolve().parent.parent


def clean_keyword(line: str) -> str:
    """
    极简清洗：
    只做格式清理，不做任何语义判断
    """

    if not line:
        return ""

    line = line.strip()

    # 跳过 markdown
    if line.startswith("#") or line.startswith("```"):
        return ""

    # 去列表符号
    line = re.sub(r"^\s*[-*+]\s+", "", line)

    # 去编号
    line = re.sub(r"^\s*\d+[\.、)]\s*", "", line)

    # 去反引号
    line = line.replace("`", "")

    # 去中文括号
    line = re.sub(r"（.*?）", "", line)

    # 去英文括号
    line = re.sub(r"\(.*?\)", "", line)

    # 去中文说明关键词（轻量）
    line = line.replace("需人工确认", "")
    line = line.replace("竞品", "")
    line = line.replace("品牌词", "")
    line = line.replace("客户品牌", "")

    # 去多余符号
    line = line.strip(" -—–：:；;，,。. ")

    # 合并空格
    line = re.sub(r"\s+", " ", line).strip()

    return line


def export(input_path, output_path):
    """
    单输出模式（最简版本）
    """

    text = input_path.read_text(encoding="utf-8")

    seen = set()
    result = []

    for line in text.splitlines():

        cleaned = clean_keyword(line)

        if not cleaned:
            continue

        if cleaned in seen:
            continue

        seen.add(cleaned)
        result.append(cleaned)

    output_path.write_text("\n".join(result), encoding="utf-8")

    print("✅ Wordstat 清洗完成")
    print(f"关键词数量：{len(result)}")
    print(f"输出文件：{output_path}")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--project", help="项目名称")

    args = parser.parse_args()

    project_name = args.project or input("请输入项目名称：").strip()

    root = get_project_root()
    base = root / "outputs" / project_name

    input_path = base / "keyword_v1_reviewed.md"
    output_path = base / "wordstat_query_list.txt"

    if not input_path.exists():
        raise FileNotFoundError(f"找不到文件: {input_path}")

    export(input_path, output_path)


if __name__ == "__main__":
    main()