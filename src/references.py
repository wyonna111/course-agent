"""
论文参考文献解析：从 PDF/文本提取条目，识别 DOI 并生成可点击链接。

DOI = Digital Object Identifier（数字对象唯一标识符），形如 10.xxxx/......
仅当文本里出现该串，或通过 CrossRef 书目检索匹配到文献时，才会给出 DOI 链接。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from src.config import (
    CROSSREF_MAILTO,
    REFERENCE_CROSSREF_MIN_SCORE,
    REFERENCE_CROSSREF_SEARCH,
    REFERENCE_FETCH_TIMEOUT,
)

# doi.org 或裸 DOI
_DOI_PATTERN = re.compile(
    r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?"
    r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
    re.I,
)

_REF_MARKERS = (
    "references",
    "bibliography",
    "参考文献",
    "引用文献",
    "参考资料",
)

_ENTRY_SPLITTERS = re.compile(
    r"(?:\n\s*)"
    r"(?="
    r"\[\d+\]\s*"
    r"|\d+\.\s+[A-Z\u4e00-\u9fff]"
    r"|\(\d+\)\s*"
    r")",
    re.MULTILINE,
)

# 表格 / 数据行特征（MOF 对比表等）
_TABLE_UNIT = re.compile(
    r"g/g|mL/g\.?day|L/kg\.?day|kg\.?day|mg/g|wt%|cm\s*[-−]",
    re.I,
)
_MOF_NAME = re.compile(r"\b(?:MIL|MOF|UiO|ZIF|HKUST|CAU|DUT)[-\s]?\d+", re.I)
_CITATION_HINT = re.compile(
    r"et\s+al\.?|\(\d{4}\)|,\s*\d{4}[\.;,]|"
    r"journal|review|letters|proceedings|conference|"
    r"university|press|vol\.|pp\.|arxiv|ISBN",
    re.I,
)


def extract_doi(text: str) -> str | None:
    dois = extract_dois(text)
    return dois[0] if dois else None


def extract_dois(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _DOI_PATTERN.finditer(text or ""):
        doi = m.group(1).rstrip(".,;)")
        key = doi.lower()
        if key not in seen:
            seen.add(key)
            out.append(doi)
    return out


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi.strip()}"


def classify_entry(entry: str) -> str:
    """
    条目类型：
    - table_row：表格/数据行（如 MOF 吸附量对比），不是参考文献
    - citation：像文献著录
    - unknown：无法判断
    """
    text = (entry or "").strip()
    if not text:
        return "unknown"
    if extract_doi(text):
        return "citation"
    if _looks_like_table_row(text):
        return "table_row"
    if _CITATION_HINT.search(text):
        return "citation"
    # 长条目、含作者式大写开头，偏文献
    if len(text) > 60 and re.search(r"[A-Z][a-z]+,\s+[A-Z]", text):
        return "citation"
    if _MOF_NAME.search(text) and len(re.findall(r"\d+\.?\d*", text)) >= 4:
        return "table_row"
    return "unknown"


def _looks_like_table_row(entry: str) -> bool:
    nums = len(re.findall(r"\d+\.?\d*", entry))
    dashes = entry.count("–") + entry.count("—") + entry.count(" - ")
    has_unit = bool(_TABLE_UNIT.search(entry))
    has_mof = bool(_MOF_NAME.search(entry))
    has_cite = bool(_CITATION_HINT.search(entry))

    if has_cite and not has_unit:
        return False
    if has_unit and nums >= 3:
        return True
    if has_mof and nums >= 5 and dashes >= 1:
        return True
    if nums >= 6 and dashes >= 2 and not has_cite:
        return True
    return False


def entry_status_label(entry_type: str, doi: str | None, source: str) -> str:
    if doi:
        if source == "crossref_search":
            return "通过 CrossRef 检索匹配到 DOI"
        return "文中含 DOI"
    if entry_type == "table_row":
        return "疑似表格行（非参考文献，不含 DOI）"
    if entry_type == "citation":
        return "像文献条目，但文中未写 DOI，检索也未命中"
    return "未识别 DOI（请粘贴 References/参考文献 原文）"


def _slice_reference_body(text: str) -> str:
    lower = text.lower()
    best_idx = -1
    for marker in _REF_MARKERS:
        idx = lower.rfind(marker.lower())
        if idx != -1 and idx > best_idx:
            best_idx = idx
    if best_idx == -1:
        return text
    body = text[best_idx:]
    lines = body.split("\n", 1)
    return lines[1] if len(lines) > 1 else body


def split_reference_entries(text: str) -> list[str]:
    body = _slice_reference_body(text).strip()
    if not body:
        return []

    parts = _ENTRY_SPLITTERS.split(body)
    entries: list[str] = []
    for p in parts:
        p = re.sub(r"^\[\d+\]\s*", "", p.strip())
        p = re.sub(r"^\d+\.\s*", "", p.strip())
        p = re.sub(r"^\(\d+\)\s*", "", p.strip())
        if len(p) >= 15:
            entries.append(p)

    if len(entries) >= 2:
        return entries

    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if len(b.strip()) >= 20]
    if len(blocks) >= 2:
        return blocks

    lines = [ln.strip() for ln in body.splitlines() if len(ln.strip()) >= 20]
    return lines if lines else ([body] if len(body) >= 20 else [])


def _crossref_headers() -> dict[str, str]:
    ua = "CourseTrace/1.0"
    if CROSSREF_MAILTO:
        ua += f" (mailto:{CROSSREF_MAILTO})"
    return {"User-Agent": ua, "Accept": "application/json"}


def fetch_crossref_metadata(doi: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(doi, safe="/")
    url = f"https://api.crossref.org/works/{encoded}"
    req = urllib.request.Request(url, headers=_crossref_headers())
    try:
        with urllib.request.urlopen(req, timeout=REFERENCE_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return {}

    return _parse_crossref_message(data.get("message", {}), fallback_doi=doi)


def _parse_crossref_message(msg: dict[str, Any], *, fallback_doi: str = "") -> dict[str, Any]:
    title = (msg.get("title") or [""])[0]
    authors = []
    for a in msg.get("author") or []:
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)
    year = None
    for key in ("published-print", "published-online", "created", "issued"):
        parts = (msg.get(key) or {}).get("date-parts", [[]])
        if parts and parts[0]:
            year = parts[0][0]
            break
    container = (msg.get("container-title") or [""])[0]
    doi = msg.get("DOI") or fallback_doi
    return {
        "title": title,
        "authors": authors[:6],
        "year": year,
        "container": container,
        "doi": doi,
        "score": msg.get("score"),
    }


def search_crossref_bibliographic(entry: str) -> dict[str, Any]:
    """无 DOI 时，用 CrossRef 书目检索尝试匹配文献。"""
    if not REFERENCE_CROSSREF_SEARCH:
        return {}
    query = re.sub(r"^\[\d+\]\s*", "", entry.strip())[:280]
    params = urllib.parse.urlencode(
        {"query.bibliographic": query, "rows": "3", "select": "DOI,title,author,score,container-title,issued"}
    )
    url = f"https://api.crossref.org/works?{params}"
    req = urllib.request.Request(url, headers=_crossref_headers())
    try:
        with urllib.request.urlopen(req, timeout=REFERENCE_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return {}

    items = data.get("message", {}).get("items") or []
    if not items:
        return {}
    best = items[0]
    score = float(best.get("score") or 0)
    if score < REFERENCE_CROSSREF_MIN_SCORE:
        return {"score": score, "rejected": True}
    meta = _parse_crossref_message(best)
    meta["score"] = score
    return meta


def resolve_reference_entry(
    entry: str, *, fetch_meta: bool = True
) -> dict[str, Any]:
    entry_type = classify_entry(entry)
    doi = extract_doi(entry)
    source = "doi" if doi else "none"

    result: dict[str, Any] = {
        "entry": entry.strip(),
        "preview": entry.strip().replace("\n", " ")[:240],
        "entry_type": entry_type,
        "doi": doi,
        "url": doi_url(doi) if doi else "",
        "source": source,
        "title": "",
        "authors": [],
        "year": None,
        "container": "",
        "crossref_score": None,
        "status": entry_status_label(entry_type, doi, source),
    }

    if doi and fetch_meta:
        meta = fetch_crossref_metadata(doi)
        if meta:
            result.update(
                {
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", []),
                    "year": meta.get("year"),
                    "container": meta.get("container", ""),
                    "source": "doi+crossref",
                    "status": entry_status_label(entry_type, doi, "doi+crossref"),
                }
            )
        return result

    # 表格行不做 CrossRef 检索（避免误匹配）
    if entry_type == "table_row" or not fetch_meta:
        return result

    if entry_type in ("citation", "unknown") and REFERENCE_CROSSREF_SEARCH:
        meta = search_crossref_bibliographic(entry)
        if meta.get("doi") and not meta.get("rejected"):
            doi = meta["doi"]
            result.update(
                {
                    "doi": doi,
                    "url": doi_url(doi),
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", []),
                    "year": meta.get("year"),
                    "container": meta.get("container", ""),
                    "crossref_score": meta.get("score"),
                    "source": "crossref_search",
                    "status": entry_status_label(entry_type, doi, "crossref_search"),
                }
            )

    return result


def parse_references_from_text(
    text: str, *, fetch_meta: bool = True
) -> list[dict[str, Any]]:
    entries = split_reference_entries(text)
    if not entries and text.strip():
        dois = extract_dois(text)
        entries = [f"DOI: {d}" for d in dois]
    return [resolve_reference_entry(e, fetch_meta=fetch_meta) for e in entries]


def parse_references_from_upload(
    text: str, *, fetch_meta: bool = True
) -> list[dict[str, Any]]:
    """兼容上传 Word/docx/doc 文档的解析入口。"""
    return parse_references_from_text(text, fetch_meta=fetch_meta)


def parse_references_from_doc(path: Path, *, fetch_meta: bool = True) -> list[dict[str, Any]]:
    """直接从 .doc/.docx 路径解析，优先复用现有的富文本读取逻辑。"""
    text = load_text_from_file(path)
    return parse_references_from_text(text, fetch_meta=fetch_meta)


def load_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz

            doc = fitz.open(str(path))
            parts = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(parts)
        except ImportError:
            from langchain_community.document_loaders import PyPDFLoader

            docs = PyPDFLoader(str(path)).load()
            return "\n".join(d.page_content for d in docs)
    if suffix in {".doc", ".docx"}:
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return path.read_text(encoding="utf-8", errors="ignore")
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_references_from_file(
    path: Path, *, fetch_meta: bool = True
) -> list[dict[str, Any]]:
    text = load_text_from_file(path)
    return parse_references_from_text(text, fetch_meta=fetch_meta)


def linkify_dois_in_text(text: str) -> str:
    def _repl(m: re.Match) -> str:
        doi = m.group(1).rstrip(".,;)")
        return f"[doi:{doi}]({doi_url(doi)})"

    return _DOI_PATTERN.sub(_repl, text)


def summarize_parse_results(rows: list[dict[str, Any]]) -> dict[str, int]:
    doi_n = sum(1 for r in rows if r.get("doi"))
    table_n = sum(1 for r in rows if r.get("entry_type") == "table_row")
    cite_n = sum(1 for r in rows if r.get("entry_type") == "citation")
    return {
        "total": len(rows),
        "with_doi": doi_n,
        "table_rows": table_n,
        "citations": cite_n,
    }
