#和 ai_analyzer.py 类似，但目标换成关键词初稿。
# 读取 raw_text.txt
# 读取 project_brief.md
# 截断原始文本
# 调 run_ai_task()
# 用 prompts/keyword_extract.md
# 输出 keyword_v1.md
# 用KEYWORD_RAW_TEXT_MAX_CHARS单独控制这一步的截断长度
# （和project_brief的PROJECT_BRIEF_MAX_CHARS是分开配置的，在为不同任务的"资料吃多少"做精细调节）


from pathlib import Path

# 运行时直接在终端输入：
# .\.venv\Scripts\python.exe -m modules.keyword_analyzer
from modules.ai_task_runner import run_ai_task
from modules.text_utils import get_env_int, limit_text


def generate_keyword_v1(project_name, provider=None, model=None, use_premium=None):
    """
    读取 raw_text.txt 和 project_brief.md，
    调用 AI 生成第一版关键词方向与候选关键词 keyword_v1.md。
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

    if not raw_text.strip():
        raise ValueError("raw_text.txt 是空的，无法生成关键词。")

    if not project_brief.strip():
        raise ValueError("project_brief.md 是空的，无法生成关键词。")

    max_chars = get_env_int("KEYWORD_RAW_TEXT_MAX_CHARS", default=15000)

    raw_text_for_ai = limit_text(
        text=raw_text,
        max_chars=max_chars,
        notice=f"【提示：原始资料较长，本次关键词生成仅参考前 {max_chars} 个字符，并结合 project_brief.md。后续可通过分块分析功能处理完整资料。】"
    )

    return run_ai_task(
        project_name=project_name,
        prompt_name="keyword_extract",
        output_filename="keyword_v1.md",
        replacements={
            "project_brief": project_brief,
            "raw_text": raw_text_for_ai
        },
        provider=provider,
        model=model,
        use_premium=use_premium
    )


if __name__ == "__main__":
    project_name = input("请输入项目名称：")
    generate_keyword_v1(project_name)