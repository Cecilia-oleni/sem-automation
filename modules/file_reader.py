from modules.doc_reader import read_docx
from modules.excel_reader import read_excel
from modules.pdf_reader import read_pdf
from modules.image_reader import read_image


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