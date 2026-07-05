# 业务层：负责"这个具体任务要读哪个输入文件、限制多少字符、调用哪个prompt、输出文件名叫什么"，然后把这些参数丢给run_ai_task
# 目前只负责 project_brief 业务
# 业务封装层，负责“项目初步分析”
# 找 outputs/项目名/raw_text.txt
# 截断过长文本
# 调 run_ai_task()
# 用 prompts/project_brief.md
# 输出 project_brief.md


from pathlib import Path

# 运行时直接在终端输入：
# .\.venv\Scripts\python.exe -m modules.ai_analyzer
# 不要使用右上角的播放按钮来启动代码，因为会找不到 modules 包

from modules.ai_task_runner import run_ai_task
from modules.text_utils import get_env_int, limit_text


def analyze_project_brief(project_name, provider=None, model=None, use_premium=None):
    """
    读取 raw_text.txt，调用 AI，生成项目资料初步分析 project_brief.md。
    """

    project_root = Path(__file__).resolve().parent.parent

    output_dir = project_root / "outputs" / project_name
    raw_text_path = output_dir / "raw_text.txt"

    if not raw_text_path.exists():
        raise FileNotFoundError(
            f"找不到 raw_text.txt：{raw_text_path}\n"
            f"请先运行 main.py 生成原始资料文本。"
        )

    raw_text = raw_text_path.read_text(encoding="utf-8")

    if not raw_text.strip():
        raise ValueError("raw_text.txt 是空的，无法进行 AI 分析。")

    max_chars = get_env_int("PROJECT_BRIEF_MAX_CHARS", default=30000)

    raw_text_for_ai = limit_text(
        text=raw_text,
        max_chars=max_chars,
        notice=f"【提示：原始资料较长，本次仅分析前 {max_chars} 个字符。后续可通过分块分析功能处理完整资料。】"
    )

    return run_ai_task(
        project_name=project_name,
        prompt_name="project_brief",
        output_filename="project_brief.md",
        replacements={
            "raw_text": raw_text_for_ai
        },
        provider=provider,
        model=model,
        use_premium=use_premium
    )


if __name__ == "__main__":
    project_name = input("请输入项目名称：")
    analyze_project_brief(project_name)