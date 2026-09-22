# 模块：sem_automation/materials/context/brief.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from sem_automation.core.paths import material_dir
# 业务层：负责"这个具体任务要读哪个输入文件、限制多少字符、调用哪个prompt、输出文件名叫什么"，然后把这些参数丢给run_ai_task
# 目前只负责 project_brief 业务
# 业务封装层，负责“项目初步分析”
# 找 outputs/项目名/raw_text.txt
# 截断过长文本
# 调 run_ai_task()
# 用 prompts/project_brief.md
# 输出 project_brief.md



from sem_automation.core.paths import PROJECT_ROOT
from pathlib import Path

# 运行时直接在终端输入：
# .\.venv\Scripts\python.exe -m sem_automation.materials.context.brief
# 不要使用右上角的播放按钮来启动代码，因为会找不到 modules 包

from sem_automation.ai.task_runner import run_ai_task
from sem_automation.materials.context.source_context import limit_source_context
from sem_automation.core.text_utils import get_env_int


def analyze_project_brief(project_name, provider=None, model=None, use_premium=None, project_root=None):
    """
    读取 raw_text.txt，调用 AI，生成项目资料初步分析 project_brief.md。
    """

    project_root = Path(project_root or PROJECT_ROOT)

    output_dir = material_dir("outputs", project_name, project_root)
    raw_text_path = output_dir / "raw_text.txt"

    if not raw_text_path.exists():
        raise FileNotFoundError(
            f"找不到 raw_text.txt：{raw_text_path}\n"
            f"请先运行 pipeline.py 完成本地资料与网站内容合并。"
        )

    raw_text = raw_text_path.read_text(encoding="utf-8")

    if not raw_text.strip():
        raise ValueError("raw_text.txt 是空的，无法进行 AI 分析。")

    max_chars = get_env_int("PROJECT_BRIEF_MAX_CHARS", default=30000)

    raw_text_for_ai = limit_source_context(
        text=raw_text,
        max_chars=max_chars,
        notice=f"【提示：原始资料较长，本次按资料来源分配后最多参考 {max_chars} 个字符。后续可通过分块分析功能处理完整资料。】"
    )

    return run_ai_task(
        project_name=project_name,
        output_dir=output_dir,
        prompt_name="materials/project_brief",
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
