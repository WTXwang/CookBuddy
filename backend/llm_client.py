"""
LLM 客户端 —— 硅基流动 (SiliconFlow) OpenAI 兼容适配

每个 Agent 独立指定模型，直接传模型全名即可。
"""
import json
import base64
from typing import Optional
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from openai import OpenAI

import config


# ═══════════════════════════════════════════════════════════════
# LangChain ChatModel（供 Agent 节点使用）
# ═══════════════════════════════════════════════════════════════

def create_chat_llm(model: str = "",
                    temperature: float = config.LLM_TEMPERATURE) -> Optional[BaseChatModel]:
    """创建 LangChain ChatOpenAI 实例。model 为空或无 API key 时返回 None（纯规则降级）。"""
    if not model:
        return None
    api_key = config.SILICONFLOW_API_KEY.strip()
    if not api_key:
        return None

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=config.SILICONFLOW_BASE_URL,
        temperature=temperature,
        max_tokens=4096,
        timeout=config.LOOP_LLM_TIMEOUT,
    )


# ═══════════════════════════════════════════════════════════════
# 原生 OpenAI 客户端（多模态等非标准调用）
# ═══════════════════════════════════════════════════════════════

_client: Optional[OpenAI] = None


def _get_client() -> Optional[OpenAI]:
    global _client
    if _client is not None:
        return _client
    api_key = config.SILICONFLOW_API_KEY.strip()
    if not api_key:
        return None
    _client = OpenAI(
        api_key=api_key,
        base_url=config.SILICONFLOW_BASE_URL,
        timeout=config.LOOP_LLM_TIMEOUT,
    )
    return _client


# ═══════════════════════════════════════════════════════════════
# 便捷方法
# ═══════════════════════════════════════════════════════════════

def chat(prompt: str,
         system: Optional[str] = None,
         model: str = "",
         temperature: float = config.LLM_TEMPERATURE,
         response_format: Optional[str] = None) -> Optional[str]:
    """简单文本对话，返回模型回复文本。"""
    client = _get_client()
    if client is None or not model:
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=4096,
    )
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as e:
        print(f"[LLM Error] {e}")
        return None


def chat_json(prompt: str,
              system: Optional[str] = None,
              model: str = "") -> Optional[dict]:
    """文本对话，强制返回 JSON。"""
    text = chat(prompt, system=system, model=model, response_format="json")
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            print(f"[LLM JSON Parse Error] raw: {text[:500]}")
            return None


# ═══════════════════════════════════════════════════════════════
# 多模态：图片 → 食材识别
# ═══════════════════════════════════════════════════════════════

def image_to_ingredients(image_path: str,
                         model: str = "") -> Optional[dict]:
    """上传图片，识别其中的食材。model 为空时默认使用 config.VISION_MODEL。"""
    client = _get_client()
    if client is None:
        return None

    model = model or config.VISION_MODEL

    path = Path(image_path)
    if not path.exists():
        print(f"[Vision] 图片不存在: {image_path}")
        return None

    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = path.suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp",
                ".gif": "image/gif"}
    mime_type = mime_map.get(ext, "image/jpeg")

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张图片中的所有食材，返回 JSON 格式：{\"ingredients\": [...], \"quantities\": {...}, \"notes\": \"...\"}。只识别可食用食材，使用中文名称。"},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}"
                    }},
                ]
            }],
            temperature=0.1,
            max_tokens=2048,
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
        return json.loads(text.strip())
    except Exception as e:
        print(f"[Vision Error] {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# Guarded 版本 —— 自动重试 + 熔断 + 并发控制
# 使用 loop.py 对 chat/chat_json 进行运行时防护。
# 调用方将 chat_json 替换为 chat_json_guarded 即可无痛接入。
# ═══════════════════════════════════════════════════════════════

def chat_guarded(prompt: str,
                 system: Optional[str] = None,
                 model: str = "",
                 temperature: float = config.LLM_TEMPERATURE,
                 response_format: Optional[str] = None) -> Optional[str]:
    """带 Loop 保护的 chat：自动重试 + 熔断 + 并发控制。

    签名与 chat() 完全一致，调用方可直接替换。
    """
    from loop import retry_with_backoff

    return retry_with_backoff(
        chat,
        prompt,
        system=system,
        model=model,
        temperature=temperature,
        response_format=response_format,
    )


def chat_json_guarded(prompt: str,
                      system: Optional[str] = None,
                      model: str = "") -> Optional[dict]:
    """带 Loop 保护的 chat_json：自动重试 + 熔断 + 并发控制。

    签名与 chat_json() 完全一致，调用方可直接替换。
    """
    from loop import retry_with_backoff

    return retry_with_backoff(
        chat_json,
        prompt,
        system=system,
        model=model,
    )
