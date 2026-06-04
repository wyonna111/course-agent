"""从问句解析页码/幻灯片号，并在索引中按页定位。"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from langchain_core.documents import Document

from src.loaders import location_label

_PAGE_PATTERNS = (
    (r"第\s*(\d+)\s*页", False),
    (r"(\d+)\s*页", False),
    (r"page\s*(\d+)", False),
    (r"p\.?\s*(\d+)\b", False),
    (r"幻灯片\s*(\d+)", True),
    (r"第\s*(\d+)\s*张", True),
)


def parse_page_lookup(question: str) -> dict | None:
    """
    解析「第 N 页 / 幻灯片 N」类问句。
    返回 1-based 页码；is_slide 表示按幻灯片号而非 PDF 页码匹配。
    """
    q = question.strip()
    page_num: int | None = None
    is_slide = False

    for pat, slide in _PAGE_PATTERNS:
        m = re.search(pat, q, re.I)
        if m:
            page_num = int(m.group(1))
            is_slide = slide
            break

    if page_num is None:
        return None

    # 避免「10 页资料」等误触：需有明确页码查询意图
    intent = any(
        k in q
        for k in (
            "第",
            "页",
            "page",
            "幻灯",
            "该页",
            "这一页",
            "文件中",
            "PPT",
            "ppt",
            "PDF",
            "pdf",
            "答案",
            "内容",
            "讲",
            "题",
        )
    )
    if not intent:
        return None

    file_hint: str | None = None
    for m in re.finditer(
        r"[\u4e00-\u9fffA-Za-z0-9_\-\s]+\.(pdf|pptx|ppt)", q, re.I
    ):
        file_hint = m.group(0).strip()

    return {
        "page": page_num,
        "is_slide": is_slide,
        "file_hint": file_hint,
    }


def _file_match(name: str, hint: str | None) -> bool:
    if not hint:
        return True
    hint = hint.strip()
    if hint in name or name in hint:
        return True
    return SequenceMatcher(None, hint.lower(), name.lower()).ratio() >= 0.55


def find_chunks_by_page(
    chunks: list[Document],
    page_1based: int,
    *,
    file_hint: str | None = None,
    is_slide: bool = False,
    indexed_files: list[str] | None = None,
) -> list[Document]:
    """在已索引片段中查找指定页/幻灯片。"""
    if not file_hint and indexed_files and len(indexed_files) == 1:
        file_hint = indexed_files[0]

    hits: list[Document] = []
    for doc in chunks:
        meta = doc.metadata
        name = meta.get("source_name", "")
        if not _file_match(name, file_hint):
            continue

        doc_type = meta.get("doc_type", "")
        if is_slide or doc_type == "pptx":
            slide = meta.get("slide")
            if slide is None:
                slide = int(meta.get("page", 0)) + 1
            if int(slide) == page_1based:
                hits.append(doc)
        else:
            display = meta.get("display_page")
            if display is None:
                display = int(meta.get("page", 0)) + 1
            if int(display) == page_1based:
                hits.append(doc)
    return hits


def merge_page_chunks(chunks: list[Document]) -> Document:
    """同一页的多个切片合并为整页（长页曾被切分时必需）。"""
    if not chunks:
        raise ValueError("chunks 为空")
    if len(chunks) == 1:
        return chunks[0]

    def _raw(doc: Document) -> str:
        raw = doc.metadata.get("raw_content") or doc.page_content or ""
        if raw.startswith("[本地:"):
            raw = raw.split("\n", 1)[-1]
        return raw.strip()

    meta = dict(chunks[0].metadata)
    merged_raw = "\n".join(_raw(c) for c in chunks if _raw(c))
    meta["raw_content"] = merged_raw
    meta["page_parts_merged"] = len(chunks)
    loc = location_label(meta)
    return Document(page_content=f"{loc}\n{merged_raw}", metadata=meta)


def page_key(doc: Document) -> str:
    name = doc.metadata.get("source_name", "")
    page = doc.metadata.get("display_page")
    if page is None:
        page = int(doc.metadata.get("page", 0)) + 1
    slide = doc.metadata.get("slide")
    if doc.metadata.get("doc_type") == "pptx" and slide is not None:
        return f"{name}::slide::{slide}"
    return f"{name}::page::{page}"


def merge_docs_by_page(
    docs_with_scores: list[tuple[Document, float]],
) -> list[tuple[Document, float]]:
    """检索结果按「文件+页」合并，展示与送模均为整页正文。"""
    groups: dict[str, list[tuple[Document, float]]] = {}
    for doc, score in docs_with_scores:
        groups.setdefault(page_key(doc), []).append((doc, score))

    merged: list[tuple[Document, float]] = []
    for items in groups.values():
        best_score = max(s for _, s in items)
        if len(items) == 1:
            merged.append((items[0][0], best_score))
            continue
        docs_only = [d for d, _ in items]
        merged.append((merge_page_chunks(docs_only), best_score))

    merged.sort(key=lambda x: x[1], reverse=True)
    return merged


def page_lookup_meta(page: int, found: bool, file_hint: str | None = None) -> dict:
    return {
        "display_score": 0.95 if found else 0.0,
        "display_pct": 95 if found else 0,
        "raw_score": 1.0 if found else 0.0,
        "coverage": 1.0 if found else 0.0,
        "boosts": [],
        "penalties": [],
        "keep": found,
        "cite_tier": "直接命中" if found else "弱相关",
        "answer_mode": "page_lookup",
        "answer_mode_label": "页码定位",
        "chunk_hint": "",
        "llm_reason": (
            f"按问句页码直接定位第 {page} 页"
            + (f"（文件：{file_hint}）" if file_hint else "")
        ),
        "rerank_method": "page_lookup",
    }
