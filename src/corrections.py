"""
人工纠错：用户对课件某页提交修正，后续检索与作答优先采用纠错版。

存储：
  个人模式  → data/corrections.json
  协作空间  → workspaces/{邀请码}/corrections.json
"""

from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.config import DATA_DIR, ENABLE_CORRECTIONS, WORKSPACE_DIR
from src.loaders import location_label


class CorrectionError(Exception):
    pass


def chunk_source_key(metadata: dict) -> str:
    """按「文件 + 页/幻灯片」定位，与 MAX_CHUNKS_PER_PAGE=1 一致。"""
    name = metadata.get("source_name") or metadata.get("source") or "unknown"
    page = metadata.get("page", metadata.get("slide", 0))
    return f"{name}::p{page}"


def _corrections_path(workspace_id: str | None = None) -> Path:
    if workspace_id:
        return WORKSPACE_DIR / workspace_id.upper() / "corrections.json"
    return DATA_DIR / "corrections.json"


def load_corrections(workspace_id: str | None = None) -> dict[str, dict]:
    if not ENABLE_CORRECTIONS:
        return {}
    path = _corrections_path(workspace_id)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_all(data: dict[str, dict], workspace_id: str | None = None) -> None:
    path = _corrections_path(workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_correction(
    source_key: str,
    corrected_text: str,
    *,
    source_name: str = "",
    page_label: str = "",
    original_preview: str = "",
    note: str = "",
    author: str = "",
    workspace_id: str | None = None,
) -> dict:
    if not ENABLE_CORRECTIONS:
        raise CorrectionError("纠错功能未开启（.env ENABLE_CORRECTIONS=true）")
    text = corrected_text.strip()
    if not text:
        raise CorrectionError("纠错正文不能为空")
    data = load_corrections(workspace_id)
    data[source_key] = {
        "text": text,
        "note": note.strip(),
        "source_name": source_name,
        "page_label": page_label,
        "original_preview": original_preview[:400],
        "author": author.strip(),
        "updated_at": time.time(),
    }
    _save_all(data, workspace_id)
    return data[source_key]


def delete_correction(source_key: str, workspace_id: str | None = None) -> bool:
    data = load_corrections(workspace_id)
    if source_key not in data:
        return False
    del data[source_key]
    _save_all(data, workspace_id)
    return True


def get_correction(source_key: str, workspace_id: str | None = None) -> dict | None:
    return load_corrections(workspace_id).get(source_key)


def apply_correction_to_doc(
    doc: Document, workspace_id: str | None = None
) -> Document:
    """若该页有纠错，返回带纠错正文的副本；否则原样返回。"""
    if not ENABLE_CORRECTIONS:
        return doc
    key = chunk_source_key(doc.metadata)
    corr = get_correction(key, workspace_id)
    if not corr:
        return doc
    if doc.metadata.get("corrected"):
        return doc

    meta = deepcopy(doc.metadata)
    meta["corrected"] = True
    meta["correction_note"] = corr.get("note", "")
    meta["correction_author"] = corr.get("author", "")
    raw = corr["text"]
    meta["raw_content"] = raw
    loc = location_label(meta)
    note = corr.get("note", "")
    header = f"{loc}\n[已人工纠错"
    if note:
        header += f"：{note}"
    header += "]\n"
    return Document(page_content=header + raw, metadata=meta)


def apply_corrections_to_docs(
    docs_with_scores: list[tuple], workspace_id: str | None = None
) -> list[tuple]:
    return [
        (apply_correction_to_doc(doc, workspace_id), score)
        for doc, score in docs_with_scores
    ]


def list_corrections_summary(workspace_id: str | None = None) -> list[dict[str, Any]]:
    data = load_corrections(workspace_id)
    items = []
    for key, c in data.items():
        items.append(
            {
                "key": key,
                "source_name": c.get("source_name", key.split("::")[0]),
                "page_label": c.get("page_label", ""),
                "note": c.get("note", ""),
                "author": c.get("author", ""),
                "preview": c.get("text", "")[:80],
                "updated_at": c.get("updated_at", 0),
            }
        )
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return items
