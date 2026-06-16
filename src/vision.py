"""
多模态图片理解：提取课件图片 → 调用视觉 LLM → 生成中文描述

支持两种后端：
  - deepseek-vl2（国内可访问，通过 OPENAI_API_BASE 配置）
  - gpt-4o（需境外网络）

调用入口：describe_image(image_bytes) → str
"""

from __future__ import annotations

import base64
import os


def _get_vision_client():
    """复用项目已有的 API 配置。"""
    from openai import OpenAI
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1"),
    )


_VISION_MODEL = os.getenv("VISION_MODEL_NAME", os.getenv("MODEL_NAME", "deepseek-chat"))

_DESCRIBE_PROMPT = (
    "这是一张课件中的图片。请用简洁的中文描述图片的主要内容，"
    "重点说明图中的技术概念、结构关系、数据流向或关键标注。"
    "如果是电路图、时序图、结构框图、引脚图等，请指出图的类型并描述核心信息。"
    "控制在150字以内。"
)


def describe_image(image_bytes: bytes, mime: str = "image/png") -> str:
    """
    将图片字节传给视觉模型，返回中文描述。
    失败时返回空字符串，不抛异常（避免因图片影响整体索引）。
    """
    if not image_bytes:
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
    except Exception:
        return ""


def is_vision_enabled() -> bool:
    """检查当前模型是否支持视觉（名称包含 vl / vision / 4o / claude）。"""
    model = _VISION_MODEL.lower()
    return any(k in model for k in ("vl", "vision", "4o", "claude", "qwen"))
