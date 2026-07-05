from pathlib import Path

# 运行时直接在终端输入：
# .\.venv\Scripts\python.exe -m modules.negative_keyword_analyzer
# 不要使用右上角的播放按钮来启动代码，因为会找不到 modules 包

from modules.ai_task_runner import run_ai_task
from modules.text_utils import get_env_int, limit_text


def generate_negative_keywords(
    project_name,
    keyword_version="keyword_v1",
    provider=None,
    model=None,
    use_premium=None
):
    """
    读取 raw_text.txt、project_brief.md 以及指定版本的关键词文件，
    调用 AI 生成否词清单 negative_keywords.md。

    keyword_version: 指定参考哪个版本的关键词文件（不带 .md 后缀）。
        默认 "keyword_v1"（AI初版）。
        如已完成人工审核并另存为 keyword_v2.md，
        建议调用时传入 keyword_version="keyword_v2"，
        以确保否词清单基于人工确认过的关键词范围来判断。
    """

    project_root = Path(__file__).resolve().parent.parent

    output_dir = project_root / "outputs" / project_name
    raw_text_path = output_dir / "raw_text.txt"
    project_brief_path = output_dir / "project_brief.md"
    keyword_path = output_dir / f"{keyword_version}.md"

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

    if not keyword_path.exists():
        raise FileNotFoundError(
            f"找不到 {keyword_version}.md：{keyword_path}\n"
            f"请先完成关键词生成。若已完成人工审核，请将确认版另存为 keyword_v2.md，\n"
            f"并调用 generate_negative_keywords(project_name, keyword_version='keyword_v2')。"
        )

    raw_text = raw_text_path.read_text(encoding="utf-8")
    project_brief = project_brief_path.read_text(encoding="utf-8")
    keyword_content = keyword_path.read_text(encoding="utf-8")

    if not raw_text.strip():
        raise ValueError("raw_text.txt 是空的，无法生成否词清单。")

    if not project_brief.strip():
        raise ValueError("project_brief.md 是空的，无法生成否词清单。")

    if not keyword_content.strip():
        raise ValueError(f"{keyword_version}.md 是空的，无法生成否词清单。")

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
        "请输入要参考的关键词文件版本（不带.md，直接回车默认使用 keyword_v1；"
        "如已人工审核完成，建议输入 keyword_v2）："
    ).strip() or "keyword_v1"

    generate_negative_keywords(project_name, keyword_version=keyword_version)