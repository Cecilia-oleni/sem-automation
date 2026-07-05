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