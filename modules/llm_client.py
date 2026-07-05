#接口层，统一管理所有AI模型和OpenRouter调用，可通过 .env 配置模型


#统一的 AI 大模型调用接口
# 核心设计思想是“封装与解耦”：上层业务代码只需要调用 call_llm 函数，而无需关心底层具体使用的是 OpenRouter、OpenAI 还是其他 AI 平台。
# 如果未来需要切换模型提供商或修改 API 密钥，只需更改 .env 配置文件，业务代码完全不需要改动。
import os
import requests

from dotenv import load_dotenv  

from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")   #环境变量加载，通过 python-dotenv 库自动读取项目根目录下的 .env 文件


def str_to_bool(value, default=False):
    """
    把 .env 里的 true / false 字符串转换成 Python 的布尔值。
    """
    if value is None:
        return default

    return value.strip().lower() in ["true", "1", "yes", "y"]


def get_openrouter_model(model=None, use_premium=None):
    """
    根据传入参数和 .env 配置，决定使用 OpenRouter 的便宜模型还是贵模型。
    优先级：
    1. 如果函数调用时传了 model，就直接用传入的 model
    2. 如果 USE_PREMIUM_MODEL=true，就用 OPENROUTER_PREMIUM_MODEL
    3. 否则用 OPENROUTER_CHEAP_MODEL
    """
    if model:
        return model

    if use_premium is None:
        use_premium = str_to_bool(os.getenv("USE_PREMIUM_MODEL"), default=False)

    if use_premium:
        return os.getenv("OPENROUTER_PREMIUM_MODEL")

    return os.getenv("OPENROUTER_CHEAP_MODEL")





#路由分发函数，定义了标准化的调用参数（如提示词 prompt、ai提供商provider、温度 temperature 等）
def call_llm(
    prompt,
    provider=None,
    model=None,
    system_prompt=None,
    temperature=None,  #控制模型生成文本时的随机性或创造性。目前是固定值，将来可改成动态，在生成广告语时调高到0.7-0.9。
    max_tokens=None,
    use_premium=None
):                                 
    """
    统一 AI 调用入口。

    上层业务代码只调用 call_llm，不直接关心底层用 OpenRouter、DeepSeek、OpenAI 还是其他平台。
    后续切换模型时，优先改 .env，不改业务代码。
    """

    provider = provider or os.getenv("DEFAULT_LLM_PROVIDER", "openrouter")

    temperature = temperature if temperature is not None else float(os.getenv("TEMPERATURE", 0.2))
    max_tokens = max_tokens if max_tokens is not None else int(os.getenv("MAX_TOKENS", 2000))


    if provider == "openrouter":
        # 接收底层返回的字典
        result_data = call_openrouter(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            use_premium=use_premium
        )
        # 直接返回即可，因为底层已经包含了 provider 和 model
        return result_data 

    else:
        raise ValueError(f"暂不支持的 provider：{provider}")   #如果传入不支持的 provider，会抛出 ValueError 异常。


def call_openrouter(
    prompt,
    model=None,
    system_prompt=None,
    temperature=None,
    max_tokens=None,
    use_premium=None
):
    """
    调用 OpenRouter。
    """

   #参数校验：从环境变量中提取 OPENROUTER_API_KEY、OPENROUTER_BASE_URL 和 DEFAULT_MODEL。
   # 如果缺少必要的密钥或模型名称，会立即抛出明确的错误提示。
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    timeout = int(os.getenv("REQUEST_TIMEOUT", 60))

    temperature = temperature if temperature is not None else float(os.getenv("TEMPERATURE", 0.2))
    max_tokens = max_tokens if max_tokens is not None else int(os.getenv("MAX_TOKENS", 3000))
    
    model = get_openrouter_model(model=model, use_premium=use_premium)

    if not api_key:
        raise ValueError("缺少 OPENROUTER_API_KEY，请检查 .env 文件")

    if not model:
        raise ValueError("缺少 OpenRouter 模型名称，请检查 OPENROUTER_CHEAP_MODEL / OPENROUTER_PREMIUM_MODEL")

    url = base_url.rstrip("/") + "/chat/completions"


    #构造请求消息 (Messages)：大模型 API 通常采用对话数组格式。
    # 如果传入了 system_prompt（系统提示词），会先将其作为 system 角色加入列表；然后将用户的 prompt 作为 user 角色加入列表。
    messages = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

     #构造 HTTP 请求：
     # Headers：包含 Bearer Token 鉴权信息、JSON 内容类型声明，以及一个自定义的 X-OpenRouter-Title 用于在 OpenRouter 后台标识应用名称。
     # Payload：包含目标模型、消息列表、temperature（控制输出随机性，值越低越确定）和 max_tokens（限制最大生成长度）。
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Title": "SEM Automation Workflow"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    print("正在调用 AI...")
    print("provider: openrouter")
    print("model:", model)

    #发送请求与异常处理：使用 requests.post 发送请求，并设置了 120 秒的超时时间。
    # 如果返回的 HTTP 状态码不是 200，会抛出包含错误码和响应文本前 1000 个字符的 RuntimeError，方便排查问题。
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter 调用失败：{response.status_code}\n"
            f"{response.text[:1000]}"
        )

    data = response.json()

     # 1. 提取内容
    content = data["choices"][0]["message"]["content"]
    
    # 2. 提取用量信息 (防止某些接口不返回 usage 导致报错，加个 get 或 try)
    usage = data.get("usage", {})

    # 3. 返回字典而不是纯字符串
    return {
        "platform": "openrouter",
        "provider": data.get("provider"),
        # 请求时指定
        "requested_model": model,
        # 实际执行
        "actual_model": data.get("model"),
        "content": content,
        "usage": usage,
        "finish_reason": data["choices"][0].get("finish_reason"),
        "raw": data
    }


#测试入口
if __name__ == "__main__":
    # 现在的 result 是一个字典
    result = call_llm(
        prompt="请用中文回答：你是谁？请用一句话回答。"
    )

    print("\nAI 回复：")
    # 1. 获取正文
    print(result["content"]) 
    
    # 假设 result 是你拿到的那个大字典
    usage = result.get("usage", {})

    print(f"模型: {result.get('actual_model', '未知模型')}")
    print(f"实际供应商: {result.get('provider', '未知供应商')}")
    print(f"输入: {usage.get('prompt_tokens')} tokens")
    print(f"输出: {usage.get('completion_tokens')} tokens")

    cost = usage.get("cost")
    if cost is not None:
        print(f"花费: ${cost:.6f}")
    else:
        print("花费: 未提供")