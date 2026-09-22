# 模块：sem_automation/readers/pdf_reader.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from pypdf import PdfReader


def read_pdf(file_path):

    print(f"正在读取PDF：{file_path.name}")

    reader = PdfReader(file_path)

    text = []

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text.append(page_text)

    result = "\n".join(text)

    print(f"读取完成，共 {len(result)} 个字符")

    return result