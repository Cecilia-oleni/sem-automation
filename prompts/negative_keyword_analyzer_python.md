from pathlib import Path

# 运行时直接在终端输入：
# & "D:\sem自动化 - 副本\sem自动化 - 副本\.venv\Scripts\python.exe" -m modules.negative_keyword_analyzer
# 不要使用右上角的播放按钮来启动代码，因为会找不到 modules 包

from modules.ai_task_runner import run_ai_task
from modules.ad_copy_generator import group_keywords, load_keyword_v2
from modules.text_utils import get_env_int, limit_text


def format_keyword_v2_for_prompt(project_name):
    keyword_df = load_keyword_v2(project_name)
    groups = group_keywords(keyword_df)

    lines = [
        "【来源：keyword_v2.xlsx / keywords_v2.xlsx】",
        "以下关键词已按人工确认的 Campaign + AdGroup 结构整理，可作为否词判断的投放范围参考。",
    ]

    for group in groups:
        lines.append("")
        lines.append(f"## Campaign: {group['campaign']}")
        lines.append(f"### AdGroup: {group['adgroup']}")

        for keyword in group["keywords"]:
            lines.append(f"- {keyword}")

    return "\n".join(lines)


def load_keyword_reference(project_name, output_dir, keyword_version):
    keyword_version = (keyword_version or "auto").strip()
    keyword_stem = Path(keyword_version).stem
    keyword_suffix = Path(keyword_version).suffix.lower()

    if keyword_suffix == ".xlsx":
        if keyword_stem not in ["keyword_v2", "keywords_v2"]:
            keyword_path = output_dir / keyword_version
            if not keyword_path.exists():
                raise FileNotFoundError(f"找不到关键词 Excel 文件：{keyword_path}")

        return format_keyword_v2_for_prompt(project_name), keyword_version

    if keyword_suffix == ".md":
        keyword_path = output_dir / keyword_version
        if not keyword_path.exists():
            raise FileNotFoundError(f"找不到关键词 Markdown 文件：{keyword_path}")

        return keyword_path.read_text(encoding="utf-8"), keyword_path.name

    keyword_version = keyword_stem

    if keyword_version in ["auto", "keyword_v2", "keywords_v2"]:
        try:
            return format_keyword_v2_for_prompt(project_name), "keyword_v2.xlsx / keywords_v2.xlsx"
        except FileNotFoundError:
            if keyword_version in ["keyword_v2", "keywords_v2"]:
                keyword_path = output_dir / f"{keyword_version}.md"
                if not keyword_path.exists():
                    raise
            else:
                keyword_path = output_dir / "keyword_v1.md"
        except ValueError:
            if keyword_version != "auto":
                raise
            keyword_path = output_dir / "keyword_v1.md"
    else:
        keyword_path = output_dir / f"{keyword_version}.md"

    if not keyword_path.exists():
        raise FileNotFoundError(
            f"找不到关键词参考文件：{keyword_path}\n"
            f"建议优先准备 keyword_v2.xlsx；如果还没有人工确认版，请先使用 keyword_v1.md。"
        )

    return keyword_path.read_text(encoding="utf-8"), keyword_path.name


def generate_negative_keywords(
    project_name,
    keyword_version="auto",
    provider=None,
    model=None,
    use_premium=None
):
    """
    读取 raw_text.txt、project_brief.md 以及关键词参考文件，
    调用 AI 生成否词清单 negative_keywords.md。

    keyword_version:
        默认 "auto"，优先读取 keyword_v2.xlsx / keywords_v2.xlsx。
        如果没有人工确认版 Excel，则回退到 keyword_v1.md。
        也可以传入 "keyword_v1" 或其他不带 .md 后缀的文件名，读取对应 .md。
    """

    project_root = Path(__file__).resolve().parent.parent

    output_dir = project_root / "outputs" / project_name
    raw_text_path = output_dir / "raw_text.txt"
    project_brief_path = output_dir / "project_brief.md"

    if not raw_text_path.exists():
        raise FileNotFoundError(
            f"找不到 raw_text.txt：{raw_text_path}\n"
            f"请先运行 main.py 生成原始资料文本。"
        )

    if not project_brief_path.exists():
        raise FileNotFoundError(
            f"找不到 project_brief.md：{project_brief_path}\n"
            f"请先运行 ai_analyzer.py 生成项目资料初步分析。"
        )

    raw_text = raw_text_path.read_text(encoding="utf-8")
    project_brief = project_brief_path.read_text(encoding="utf-8")
    keyword_content, keyword_source = load_keyword_reference(
        project_name=project_name,
        output_dir=output_dir,
        keyword_version=keyword_version
    )

    if not raw_text.strip():
        raise ValueError("raw_text.txt 是空的，无法生成否词清单。")

    if not project_brief.strip():
        raise ValueError("project_brief.md 是空的，无法生成否词清单。")

    if not keyword_content.strip():
        raise ValueError(f"{keyword_source} 是空的，无法生成否词清单。")

    max_chars = get_env_int("NEGATIVE_KEYWORD_RAW_TEXT_MAX_CHARS", default=15000)

    raw_text_for_ai = limit_text(
        text=raw_text,
        max_chars=max_chars,
        notice=f"【提示：原始资料较长，本次否词生成仅参考前 {max_chars} 个字符，并结合 project_brief.md 与关键词清单。后续可通过分块分析功能处理完整资料。】"
    )

    return run_ai_task(
        project_name=project_name,
        prompt_name="negative_keyword",
        output_filename="negative_keywords.md",
        replacements={
            "project_brief": project_brief,
            "keyword_list": keyword_content,
            "raw_text": raw_text_for_ai
        },
        provider=provider,
        model=model,
        use_premium=use_premium
    )


if __name__ == "__main__":
    project_name = input("请输入项目名称：")
    keyword_version = input(
        "请输入要参考的关键词版本（直接回车自动优先使用 keyword_v2.xlsx；"
        "也可输入 keyword_v1 使用旧版 .md）："
    ).strip() or "auto"

    generate_negative_keywords(project_name, keyword_version=keyword_version)
