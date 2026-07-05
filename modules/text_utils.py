import os
from pathlib import Path

from dotenv import load_dotenv


def get_project_root():
    """
    获取项目根目录。
    当前文件位于 modules/text_utils.py，
    所以 parent.parent 是项目根目录。
    """
    return Path(__file__).resolve().parent.parent


# 明确加载项目根目录下的 .env
project_root = get_project_root()
load_dotenv(project_root / ".env")


def get_env_int(name, default=None):
    """
    从 .env 读取整数配置。
    如果没有配置、为空、格式错误，则返回 default。
    """

    value = os.getenv(name)

    if value is None or value == "":
        return default

    try:
        return int(value)
    except ValueError:
        print(f"警告：环境变量 {name}={value} 不是有效整数，将使用默认值 {default}")
        return default


def limit_text(text, max_chars=None, notice=None):
    """
    按 max_chars 限制文本长度。

    max_chars:
    - None：不截断
    - 0 或负数：不截断
    - 正整数：超过该长度则截断

    notice:
    - 如果发生截断，在文本末尾追加提示。
    """

    if max_chars is None:
        return text

    if max_chars <= 0:
        return text

    if len(text) <= max_chars:
        return text

    limited_text = text[:max_chars]

    if notice:
        limited_text += "\n\n" + notice

    return limited_text