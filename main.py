print("SEM助手启动成功")

# 导入库
import pandas
import docx
import openpyxl
from pypdf import PdfReader

print("依赖安装成功")


from pathlib import Path
import csv
from modules.file_reader import read_file


# 输入项目名称
PROJECT_NAME = input("请输入项目名称：")

# 项目路径
project_dir = Path("uploads") / PROJECT_NAME

# 检查项目是否存在
if not project_dir.exists():

    print(f"项目不存在：{PROJECT_NAME}")

    exit()

print(f"\n当前项目：{PROJECT_NAME}")


# 汇总所有文本
all_text = []

# 文件读取报告
file_reports = []


# 遍历项目文件，包括子文件夹
for file_path in project_dir.rglob("*"):

    if file_path.is_file():

        print(f"\n发现文件：{file_path.relative_to(project_dir)}")

        content, status, note = read_file(file_path)

        char_count = len(content)

        file_reports.append({
            "项目名称": PROJECT_NAME,
            "文件相对路径": str(file_path.relative_to(project_dir)),
            "文件名": file_path.name,
            "文件类型": file_path.suffix.lower(),
            "读取状态": status,
            "提取字符数": char_count,
            "备注": note
        })

        if status == "成功" and content:

            all_text.append(
                f"\n\n===== {file_path.relative_to(project_dir)} =====\n\n"
                + content
            )


# 合并文本
final_content = "\n".join(all_text)


# 输出目录
output_dir = Path("outputs") / PROJECT_NAME

output_dir.mkdir(
    parents=True,
    exist_ok=True
)


# 保存原始文本
with open(
    output_dir / "raw_text.txt",
    "w",
    encoding="utf-8"
) as f:

    f.write(final_content)


# 保存文件读取报告
report_path = output_dir / "file_report.csv"

with open(
    report_path,
    "w",
    encoding="utf-8-sig",
    newline=""
) as f:

    fieldnames = [
        "项目名称",
        "文件相对路径",
        "文件名",
        "文件类型",
        "读取状态",
        "提取字符数",
        "备注"
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames)

    writer.writeheader()

    writer.writerows(file_reports)


print(
    f"\n原始文本已保存：{output_dir / 'raw_text.txt'}"
)

print(
    f"\n文件读取报告已保存：{report_path}"
)

print(
    f"\n总共提取字符数：{len(final_content)}"
)

print(
    f"\n共扫描文件数：{len(file_reports)}"
)