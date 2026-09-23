# 模块：sem_automation/ai/prompt_loader.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from sem_automation.core.paths import PROJECT_ROOT
from pathlib import Path


def load_prompt(prompt_name):
    """
    读取 prompts 目录下的 prompt 文件。
    支持自动识别 .md 或 .txt 后缀。
    优先级：如果同名文件都存在，优先读取 .md。
    """

    # 1. 定位项目根目录
    project_root = PROJECT_ROOT
    prompt_dir = project_root / "prompts"

    # 2. 定义可能的路径
    path_md = prompt_dir / f"{prompt_name}.md"
    path_txt = prompt_dir / f"{prompt_name}.txt"

    # 3. 按优先级检查文件是否存在
    if path_md.exists():
        return path_md.read_text(encoding="utf-8")
    elif path_txt.exists():
        return path_txt.read_text(encoding="utf-8")
    else:
        # 4. 如果都不存在，抛出明确错误
        raise FileNotFoundError(
            f"找不到 Prompt 文件：'{prompt_name}'。\n"
            f"请检查 prompts 目录下是否存在 {prompt_name}.md 或 {prompt_name}.txt"
        )


if __name__ == "__main__":
    # 测试：假设你有一个 company_profile.md 或者 company_profile.txt
    try:
        content = load_prompt("company_profile")
        print(f"成功读取内容 (前50字)：\n{content[:50]}...")
    except FileNotFoundError as e:
        print(e)
