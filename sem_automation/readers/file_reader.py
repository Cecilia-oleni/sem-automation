# 模块：sem_automation/readers/file_reader.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' materials run --project '通亚' --dry-run
# 上述为离线预览；生成物料时去掉 --dry-run，按提示完成人工节点。
from sem_automation.readers.doc_reader import read_docx
from sem_automation.readers.excel_reader import read_excel
from sem_automation.readers.pdf_reader import read_pdf
from sem_automation.readers.image_reader import read_image


def read_file(file_path):

    suffix = file_path.suffix.lower()

    try:
        if suffix == ".docx":
            content = read_docx(file_path)

        elif suffix in [".xlsx", ".xls"]:
            content = read_excel(file_path)

        elif suffix == ".pdf":
            content = read_pdf(file_path)

        elif suffix in [".jpg", ".jpeg", ".png"]:
            read_image(file_path)
            return "", "跳过", "图片OCR暂未启用"

        else:
            print(f"暂不支持：{file_path.name}")
            return "", "不支持", f"暂不支持该文件类型：{suffix}"

        if content and content.strip():
            return content, "成功", "正常"
        else:
            return "", "空内容", "文件可读取，但未提取到文字，可能是扫描版PDF、图片型文件或空文件"

    except Exception as e:
        print(f"读取失败：{file_path.name}")
        print(f"错误原因：{e}")
        return "", "失败", str(e)