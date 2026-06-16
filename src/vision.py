"""
多模态图片理解：提取课件图片 → 调用视觉 LLM → 生成中文描述

支持的视觉模型（需在 .env 配置对应的 VISION_API_BASE 和 VISION_API_KEY）：
  - qwen-vl-plus / qwen-vl-max（阿里云百炼，国内可用，推荐）
  - gpt-4o（需境外网络）

调用入口：describe_image(image_bytes) → str
"""

from __future__ import annotations

import base64
import os


_VISION_MODEL = os.getenv("VISION_MODEL_NAME", "")

# 视觉模型可以单独配置 API 地址和 Key，不填则复用文本模型的配置
_VISION_API_BASE = os.getenv(
    "VISION_API_BASE",
    os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1"),
)
_VISION_API_KEY = os.getenv(
    "VISION_API_KEY",
    os.getenv("OPENAI_API_KEY", ""),
)


def _get_vision_client():
    from openai import OpenAI
    return OpenAI(api_key=_VISION_API_KEY, base_url=_VISION_API_BASE)


_DESCRIBE_PROMPT = (
    "这是一张课件中的图片。请用简洁的中文描述图片的主要内容，"
    "重点说明图中的技术概念、结构关系、数据流向或关键标注。"
    "如果是电路图、时序图、结构框图、引脚图等，请指出图的类型并描述核心信息。"
    "控制在150字以内。"
)


def describe_image(image_bytes: bytes, mime: str = "image/png") -> str:
    """
    将图片字节传给视觉模型，返回中文描述。
    失败时返回空字符串，不抛异常。
    """
    if not image_bytes or not _VISION_MODEL:
        return ""
    try:
        client = _get_vision_client()
        b64 = base64.b64encode(image_bytes).decode()
        resp = client.chat.completions.create(
            model=_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                        {"type": "text", "text": _DESCRIBE_PROMPT},
                    ],
                }
            ],
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # 开发阶段打印错误，方便排查
        import sys
        print(f"[vision] describe_image 失败: {e}", file=sys.stderr)
        return ""


def is_vision_enabled() -> bool:
    """当 VISION_MODEL_NAME 非空且包含视觉模型关键词时启用。"""
    if not _VISION_MODEL:
        return False
    model = _VISION_MODEL.lower()
    return any(k in model for k in ("vl", "vision", "4o", "claude", "qwen"))
