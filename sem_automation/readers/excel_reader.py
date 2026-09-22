# 模块：sem_automation/readers/excel_reader.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
import pandas as pd


def read_excel(file_path):

    print(f"正在读取Excel：{file_path.name}")

    text = []

    excel_file = pd.ExcelFile(file_path)

    for sheet_name in excel_file.sheet_names:

        text.append(f"\n===== Sheet: {sheet_name} =====\n")

        df = pd.read_excel(file_path, sheet_name=sheet_name)
        df = df.fillna("")

        text.append(df.to_string(index=False))

    result = "\n".join(text)

    print(f"读取完成，共 {len(result)} 个字符")

    return result