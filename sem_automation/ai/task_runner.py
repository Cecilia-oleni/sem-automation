# 模块：sem_automation/ai/task_runner.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from sem_automation.core.paths import PROJECT_ROOT
from pathlib import Path

from sem_automation.ai.prompt_loader import load_prompt
from sem_automation.ai.llm_client import call_llm


def get_project_root():
    """
    获取项目根目录。
    当前文件位于 modules/ai_task_runner.py，
    所以 parent.parent 是项目根目录。
    """
    return PROJECT_ROOT


def extract_llm_content(result):
    """
    从 call_llm 的返回结果中提取 AI 正文内容。

    当前 llm_client.py 返回的是 dict，正文在 result["content"]。
    这里同时兼容 str 和 OpenAI 原始 choices 结构。
    """

    if isinstance(result, str):
        return result

    if isinstance(result, dict) and "content" in result:
        return result["content"]

    if isinstance(result, dict) and "choices" in result:
        return result["choices"][0]["message"]["content"]

    raise TypeError(
        f"无法识别 call_llm 返回结果类型：{type(result)}，内容：{result}"
    )


def run_ai_task(
    project_name,
    prompt_name,
    output_filename,
    replacements,
    provider=None,
    model=None,
    temperature=None,
    max_tokens=None,
    use_premium=None,
    output_dir=None,
):
    """
    通用 AI 任务执行器。

    project_name: 项目名称，对应 outputs/项目名
    prompt_name: prompt 文件名，不带 .md，例如 project_brief
    output_filename: 输出文件名，例如 project_brief.md
    replacements: prompt 中需要替换的变量，例如 {"raw_text": "..."}
    provider/model/use_premium: 可选模型控制
    temperature/max_tokens:
        - 如果传入具体值，则覆盖 .env
        - 如果不传，则由 llm_client.py 从 .env 读取
    """

    if output_dir is None:
        raise ValueError('业务调用方必须显式提供 output_dir')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result_path = output_dir / output_filename

    prompt_template = load_prompt(prompt_name)

    if not prompt_template.strip():
        raise ValueError(
            f"Prompt 文件为空：prompts/{prompt_name}.md\n"
            f"请检查该 prompt 文件是否已经填写内容。"
        )

    final_prompt = prompt_template

    for key, value in replacements.items():
        if value is None:
            value = ""

        if not isinstance(value, str):
            value = str(value)

        final_prompt = final_prompt.replace(
            "{{" + key + "}}",
            value
        )

    if not final_prompt.strip():
        raise ValueError(
            f"最终 prompt 为空，任务未执行。\n"
            f"prompt_name: {prompt_name}\n"
            f"请检查 prompts/{prompt_name}.md 以及 replacements 内容。"
        )

    print(f"正在执行 AI 任务：{prompt_name}")
    print(f"输出文件：{result_path}")
    print(f"最终 prompt 长度：{len(final_prompt)} 字符")

    result = call_llm(
        prompt=final_prompt,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        use_premium=use_premium
    )

    result_text = extract_llm_content(result)

    if not result_text.strip():
        raise ValueError(
            f"AI 返回内容为空，任务未保存。\n"
            f"prompt_name: {prompt_name}"
        )

    result_path.write_text(result_text, encoding="utf-8")

    print(f"AI 任务已完成，结果已保存：{result_path}")

    return result_text
