"""
协作学习空间 — 邀请码加入，共享资料库与会话（无需注册账号）。

目录结构：
  workspaces/{邀请码}/
    meta.json      # 空间名、消息、时间戳
    data/          # 共享上传的资料
"""

from __future__ import annotations

import json
import random
import string
import time
from pathlib import Path
from typing import Any

from src.config import WORKSPACE_DIR
from src.chat_history import sanitize_chat_messages

# 易读邀请码字符（去掉 0/O、1/I/L）
_CODE_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_LEN = 6


class WorkspaceError(Exception):
    pass


def _meta_path(workspace_id: str) -> Path:
    return WORKSPACE_DIR / workspace_id.upper() / "meta.json"


def _data_dir(workspace_id: str) -> Path:
    return WORKSPACE_DIR / workspace_id.upper() / "data"


def normalize_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "")


def _generate_code() -> str:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    for _ in range(200):
        code = "".join(random.choices(_CODE_CHARS, k=_CODE_LEN))
        if not _meta_path(code).exists():
            return code
    raise WorkspaceError("无法生成唯一邀请码，请稍后重试")


def workspace_exists(workspace_id: str) -> bool:
    return _meta_path(normalize_code(workspace_id)).exists()


def get_workspace_data_dir(workspace_id: str) -> Path:
    wid = normalize_code(workspace_id)
    if not workspace_exists(wid):
        raise WorkspaceError(f"空间 {wid} 不存在")
    d = _data_dir(wid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_workspace(workspace_id: str) -> dict[str, Any]:
    wid = normalize_code(workspace_id)
    path = _meta_path(wid)
    if not path.exists():
        raise WorkspaceError(f"邀请码 {wid} 不存在，请向队友确认")
    meta = json.loads(path.read_text(encoding="utf-8"))
    meta["id"] = wid
    return meta


def save_workspace_meta(workspace_id: str, meta: dict[str, Any]) -> None:
    wid = normalize_code(workspace_id)
    path = _meta_path(wid)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta["id"] = wid
    meta["updated_at"] = time.time()
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def create_workspace(name: str = "复习小组") -> dict[str, Any]:
    """创建空间，返回含 invite_code 的 meta。"""
    wid = _generate_code()
    path = _meta_path(wid)
    path.parent.mkdir(parents=True, exist_ok=True)
    _data_dir(wid).mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "id": wid,
        "name": name.strip() or "复习小组",
        "invite_code": wid,
        "messages": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    save_workspace_meta(wid, meta)
    return meta


def join_workspace(workspace_id: str) -> dict[str, Any]:
    return load_workspace(workspace_id)


def load_workspace_messages(workspace_id: str) -> list[dict]:
    try:
        raw = load_workspace(workspace_id).get("messages", [])
    except WorkspaceError:
        return []
    from src.chat import repair_legacy_fragment_citations

    out: list[dict] = []
    for m in raw:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        item = dict(m)
        if item.get("role") == "assistant" and item.get("content"):
            item["content"] = repair_legacy_fragment_citations(item["content"])
        out.append(item)
    return out


def save_workspace_messages(workspace_id: str, messages: list[dict]) -> None:
    meta = load_workspace(workspace_id)
    meta["messages"] = sanitize_chat_messages(messages)
    save_workspace_meta(workspace_id, meta)


def append_workspace_message(workspace_id: str, message: dict) -> None:
    meta = load_workspace(workspace_id)
    msgs = meta.get("messages", [])
    msgs.extend(sanitize_chat_messages([message]))
    meta["messages"] = msgs
    save_workspace_meta(workspace_id, meta)


def list_workspace_files(workspace_id: str) -> list[str]:
    d = get_workspace_data_dir(workspace_id)
    return sorted(
        p.name
        for p in d.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".pptx", ".ppt", ".txt", ".md"}
    )
