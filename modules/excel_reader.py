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