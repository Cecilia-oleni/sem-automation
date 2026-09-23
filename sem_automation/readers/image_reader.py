# 模块：sem_automation/readers/image_reader.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
def read_image(file_path):

    print(f"发现图片文件：{file_path.name}")

    return "[图片OCR暂未启用]"