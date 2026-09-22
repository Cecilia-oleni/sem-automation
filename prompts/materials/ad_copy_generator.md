# PowerShell 运行：
# & "D:\sem自动化 - 副本\sem自动化 - 副本\.venv\Scripts\python.exe" -m modules.ad_copy_generator

from pathlib import Path
import argparse
import csv
import re

import pandas as pd

from modules.prompt_loader import load_prompt
from modules.llm_client import call_llm

OUTPUT_FIELDS = [
    "Campaign",
    "AdGroup",
    "AdType",
    "Index",
    "RussianText",
    "ChineseTranslation",
    "CharCount",
    "CharLimit",
    "Status",
    "Keywords",
    "Model",
    "Provider",
    "FinishReason",
]

def get_project_root():
    return Path(__file__).resolve().parent.parent

def get_output_dir(project_name):
    return get_project_root() / "outputs" / project_name

def read_text(path, label):
    if not path.exists():
        raise FileNotFoundError(f"找不到{label}：{path}")

    text = path.read_text(encoding="utf-8")

    if not text.strip():
        raise ValueError(f"{label}为空，无法继续：{path}")

    return text

def load_project_brief(project_name):
    path = get_output_dir(project_name) / "project_brief.md"
    return read_text(path, "项目资料分析 project_brief.md")

def load_negative_keywords(project_name):
    path = get_output_dir(project_name) / "negative_keywords.md"
    return read_text(path, "否词文件 negative_keywords.md")

def normalize_column_name(name):
    return str(name).strip().lower().replace(" ", "").replace("_", "").replace("-", "")

def find_column(df, aliases):
    normalized_map = {
        normalize_column_name(col): col
        for col in df.columns
    }

    for alias in aliases:
        key = normalize_column_name(alias)
        if key in normalized_map:
            return normalized_map[key]

    return None

def first_existing_path(paths):
    for path in paths:
        if path.exists():
            return path

    return paths[0]

def clean_cell(value):
    if pd.isna(value):
        return ""

    return str(value).strip()

def parse_label_value(text, prefixes):
    normalized = text.replace("：", ":").strip()
    lower_text = normalized.lower()

    for prefix in prefixes:
        lower_prefix = prefix.lower()
        if lower_text.startswith(lower_prefix):
            value = normalized[len(prefix):].strip(" :：\r\n\t")
            lines = [line.strip(" :：\t") for line in value.splitlines() if line.strip()]
            return lines[-1] if lines else ""

    return ""

def parse_manual_keyword_v2(path):
    raw_df = pd.read_excel(path, header=None)

    rows = []
    current_campaign = ""
    current_adgroup = ""

    for _, row in raw_df.iterrows():
        cells = [clean_cell(value) for value in row.tolist()]
        non_empty = [cell for cell in cells if cell]

        if not non_empty:
            continue

        for cell in non_empty:
            campaign = parse_label_value(cell, ["campaign"])
            if campaign:
                current_campaign = campaign
                current_adgroup = ""
                break

        for cell in non_empty:
            adgroup = parse_label_value(cell, ["ad_group_", "ad_group", "adgroup", "广告组"])
            if adgroup:
                current_adgroup = adgroup
                break

        if not current_campaign or not current_adgroup:
            continue

        keyword = cells[2] if len(cells) > 2 else ""
        if not keyword or keyword == current_adgroup:
            continue

        rows.append({
            "Campaign": current_campaign,
            "AdGroup": current_adgroup,
            "Keyword": keyword,
        })

    if not rows:
        raise ValueError(f"无法从人工分组表解析关键词数据：{path}")

    return pd.DataFrame(rows)

def load_keyword_v2(project_name):
    output_dir = get_output_dir(project_name)
    path = first_existing_path([
        output_dir / "keyword_v2.xlsx",
        output_dir / "keywords_v2.xlsx",
    ])

    if not path.exists():
        raise FileNotFoundError(
            f"找不到关键词文件 keyword_v2.xlsx 或 keywords_v2.xlsx：{path}"
        )

    df = pd.read_excel(path)

    column_config = {
        "Campaign": ["Campaign", "广告系列", "广告系列名称"],
        "AdGroup": ["AdGroup", "Ad Group", "广告组", "广告组名称"],
        "Keyword": ["Keyword", "关键词", "关键词（俄语/英文）", "关键词(俄语/英文)", "KeywordText"],
    }

    rename_map = {}

    for standard_name, aliases in column_config.items():
        actual_column = find_column(df, aliases)

        if actual_column is None:
            df = parse_manual_keyword_v2(path)
            rename_map = {}
            break

        rename_map[actual_column] = standard_name

    if rename_map:
        df = df.rename(columns=rename_map)

    df = df[["Campaign", "AdGroup", "Keyword"]].copy()
    df = df.dropna(subset=["Campaign", "AdGroup", "Keyword"])

    for col in ["Campaign", "AdGroup", "Keyword"]:
        df[col] = df[col].astype(str).str.strip()

    df = df[
        (df["Campaign"] != "")
        & (df["AdGroup"] != "")
        & (df["Keyword"] != "")
    ]

    if df.empty:
        raise ValueError("keyword_v2.xlsx 中没有可用关键词数据。")

    return df

def group_keywords(df):
    groups = []

    grouped = df.groupby(["Campaign", "AdGroup"], sort=False)

    for (campaign, adgroup), group in grouped:
        keywords = group["Keyword"].dropna().astype(str).str.strip().tolist()

        groups.append({
            "campaign": campaign,
            "adgroup": adgroup,
            "keywords": keywords,
        })

    return groups

def build_prompt(project_brief, negative_keywords, campaign, adgroup, keywords):
    prompt = load_prompt("ad_copy")

    replacements = {
        "project_brief": project_brief,
        "negative_keywords": negative_keywords,
        "campaign": campaign,
        "adgroup": adgroup,
        "keywords": "\n".join(keywords),
    }

    for key, value in replacements.items():
        prompt = prompt.replace("{{" + key + "}}", value or "")

    return prompt

def extract_content(result):
    if isinstance(result, str):
        return result

    if isinstance(result, dict) and "content" in result:
        return result["content"]

    if isinstance(result, dict) and "choices" in result:
        return result["choices"][0]["message"]["content"]

    raise TypeError(f"无法识别 LLM 返回结果：{type(result)}")

def parse_ad_copy(text):
    data = {}
    current_key = None

    pattern = re.compile(
        r"^(Headline[1-7](?:_CN)?|Description[1-3](?:_CN)?):\s*(.*)$"
    )

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        match = pattern.match(line)

        if match:
            current_key = match.group(1)
            data[current_key] = match.group(2).strip()
            continue

        if current_key:
            data[current_key] = (data[current_key] + " " + line).strip()

    return data

def make_rows(group, parsed, result_meta):
    rows = []
    keywords_text = " | ".join(group["keywords"])

    for index in range(1, 8):
        text = parsed.get(f"Headline{index}", "")
        cn = parsed.get(f"Headline{index}_CN", "")
        rows.append(make_row(group, "Headline", index, text, cn, 56, keywords_text, result_meta))

    for index in range(1, 4):
        text = parsed.get(f"Description{index}", "")
        cn = parsed.get(f"Description{index}_CN", "")
        rows.append(make_row(group, "Description", index, text, cn, 81, keywords_text, result_meta))

    return rows

def make_row(group, ad_type, index, text, cn, char_limit, keywords_text, result_meta):
    char_count = len(text)

    if not text:
        status = "MISSING"
    elif char_count > char_limit:
        status = "TOO_LONG"
    else:
        status = "OK"

    return {
        "Campaign": group["campaign"],
        "AdGroup": group["adgroup"],
        "AdType": ad_type,
        "Index": index,
        "RussianText": text,
        "ChineseTranslation": cn,
        "CharCount": char_count,
        "CharLimit": char_limit,
        "Status": status,
        "Keywords": keywords_text,
        "Model": result_meta.get("actual_model", ""),
        "Provider": result_meta.get("provider", ""),
        "FinishReason": result_meta.get("finish_reason", ""),
    }

def write_tsv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

def write_xlsx(path, rows):
    df = pd.DataFrame(rows, columns=OUTPUT_FIELDS)
    df.to_excel(path, index=False)

def write_raw(path, raw_sections):
    path.write_text("\n\n".join(raw_sections), encoding="utf-8")

def generate_ad_copy(
    project_name,
    provider=None,
    model=None,
    temperature=0.7,
    max_tokens=None,
    use_premium=None,
):
    output_dir = get_output_dir(project_name)

    project_brief = load_project_brief(project_name)
    negative_keywords = load_negative_keywords(project_name)
    keyword_df = load_keyword_v2(project_name)

    groups = group_keywords(keyword_df)

    result_path = output_dir / "ad_copy_results.tsv"
    xlsx_path = output_dir / "ad_copy_results.xlsx"
    raw_path = output_dir / "ad_copy_raw.md"

    all_rows = []
    raw_sections = []

    print(f"开始生成广告语：{project_name}")
    print(f"共发现 {len(groups)} 个广告组")

    for index, group in enumerate(groups, start=1):
        print("\n----------------")
        print(f"正在处理第 {index} 个广告组")
        print("Campaign:", group["campaign"])
        print("AdGroup:", group["adgroup"])
        print("Keywords:", len(group["keywords"]))

        prompt = build_prompt(
            project_brief=project_brief,
            negative_keywords=negative_keywords,
            campaign=group["campaign"],
            adgroup=group["adgroup"],
            keywords=group["keywords"],
        )

        result = call_llm(
            prompt=prompt,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            use_premium=use_premium,
        )

        content = extract_content(result)
        parsed = parse_ad_copy(content)
        rows = make_rows(group, parsed, result if isinstance(result, dict) else {})

        all_rows.extend(rows)

        raw_sections.append(
            f"# {group['campaign']} / {group['adgroup']}\n\n"
            f"## Keywords\n\n"
            + "\n".join(f"- {kw}" for kw in group["keywords"])
            + "\n\n## AI Output\n\n"
            + content
        )

        write_tsv(result_path, all_rows)
        write_xlsx(xlsx_path, all_rows)
        write_raw(raw_path, raw_sections)

        print(f"已保存阶段性结果：{result_path}")

    print("\n广告语生成完成")
    print(f"结构化结果：{result_path}")
    print(f"Excel 结果：{xlsx_path}")
    print(f"原始输出备份：{raw_path}")

    return all_rows

def main():
    parser = argparse.ArgumentParser(
        description="根据 keyword_v2.xlsx 按 Campaign + AdGroup 生成 Yandex 广告语。"
    )

    parser.add_argument("--project", help="项目名称")
    parser.add_argument("--model", help="指定模型名称")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--use-premium", action="store_true", default=None)

    args = parser.parse_args()

    project_name = args.project or input("请输入项目名称：").strip()

    generate_ad_copy(
        project_name=project_name,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        use_premium=args.use_premium,
    )

if __name__ == "__main__":
    main()
