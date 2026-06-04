"""个人模式下的对话记录持久化（协作空间仍用 workspace meta）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import CHAT_HISTORY_PATH

# 个人模式与协作空间共用：可 JSON 序列化的消息字段
MESSAGE_DISK_KEYS = (
    "role",
    "content",
    "author",
    "web_sources",
    "rerank_metas",
    "_meta",
    "source_previews",
)


def sanitize_chat_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只持久化可 JSON 序列化的字段（对话正文 + 参考页预览等）。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.get("role") not in ("user", "assistant"):
            continue
        item: dict[str, Any] = {"role": m["role"], "content": m.get("content", "")}
        for key in MESSAGE_DISK_KEYS[2:]:
            if m.get(key):
                item[key] = m[key]
        if m.get("author"):
            item["author"] = m["author"]
        out.append(item)
    return out


def load_personal_messages() -> list[dict[str, Any]]:
    if not CHAT_HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(CHAT_HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [m for m in data if isinstance(m, dict) and m.get("role") in ("user", "assistant")]


def save_personal_messages(messages: list[dict[str, Any]]) -> None:
    CHAT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHAT_HISTORY_PATH.write_text(
        json.dumps(sanitize_chat_messages(messages), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_personal_messages() -> None:
    if CHAT_HISTORY_PATH.exists():
        CHAT_HISTORY_PATH.unlink()
