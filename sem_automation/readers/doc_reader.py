# 模块：sem_automation/readers/doc_reader.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from docx import Document


def read_docx(file_path):

    print(f"正在读取Word：{file_path.name}")

    doc = Document(file_path)

    text = []

    # 段落
    for para in doc.paragraphs:
        if para.text.strip():
            text.append(para.text)

    # 表格
    for table in doc.tables:
        for row in table.rows:

            row_data = []

            for cell in row.cells:

                value = cell.text.strip()

                if value:
                    row_data.append(value)

            if row_data:
                text.append(" | ".join(row_data))

    result = "\n".join(text)

    print(f"读取完成，共 {len(result)} 个字符")

    return result