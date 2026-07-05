#不要用OpenRouter或DeepSeek处理图片（看图Token消耗极大）。
# 届时建议单独接入 阿里云视觉智能平台 或 Google Cloud Vision，按次计费更划算。


def read_image(file_path):

    print(f"发现图片文件：{file_path.name}")

    return "[图片OCR暂未启用]"