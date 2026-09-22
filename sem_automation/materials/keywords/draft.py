# 模块：sem_automation/materials/keywords/draft.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from sem_automation.core.paths import material_dir
#和 ai_analyzer.py 类似，但目标换成关键词初稿。
# 读取 raw_text.txt
# 读取 project_brief.md
# 截断原始文本
# 调 run_ai_task()
# 用 prompts/keyword_extract.md
# 输出 keyword_v1.md
# 用KEYWORD_RAW_TEXT_MAX_CHARS单独控制这一步的截断长度
# （和project_brief的PROJECT_BRIEF_MAX_CHARS是分开配置的，在为不同任务的"资料吃多少"做精细调节）



from sem_automation.core.paths import PROJECT_ROOT
from pathlib import Path

# 运行时直接在终端输入：
# .\.venv\Scripts\python.exe -m sem_automation.materials.keywords.draft
from sem_automation.ai.task_runner import run_ai_task
from sem_automation.materials.context.source_context import limit_source_context
from sem_automation.core.text_utils import get_env_int


def generate_keyword_v1(project_name, provider=None, model=None, use_premium=None, project_root=None):
    """
    读取 raw_text.txt 和 project_brief.md，
    调用 AI 生成第一版关键词方向与候选关键词 keyword_v1.md。
    """

    project_root = Path(project_root or PROJECT_ROOT)

    output_dir = material_dir("outputs", project_name, project_root)
    raw_text_path = output_dir / "raw_text.txt"
    project_brief_path = output_dir / "project_brief.md"

    if not raw_text_path.exists():
        raise FileNotFoundError(
            f"找不到 raw_text.txt：{raw_text_path}\n"
            f"请先运行 pipeline.py 完成本地资料与网站内容合并。"
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

    raw_text_for_ai = limit_source_context(
        text=raw_text,
        max_chars=max_chars,
        notice=f"【提示：原始资料较长，本次关键词生成按资料来源分配后最多参考 {max_chars} 个字符，并结合 project_brief.md。后续可通过分块分析功能处理完整资料。】"
    )

    return run_ai_task(
        project_name=project_name,
        output_dir=output_dir,
        prompt_name="materials/keyword_extract",
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
