"""联网搜索：本地资料不足时补充网络结果并附 URL"""

import logging

from src.config import ENABLE_WEB_SEARCH

logger = logging.getLogger(__name__)

_DDGS_CLS = None
try:
    from ddgs import DDGS as _DDGS_CLS  # 新版包名
except ImportError:
    try:
        from duckduckgo_search import DDGS as _DDGS_CLS
    except ImportError:
        pass


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    返回 [{"title": str, "url": str, "snippet": str}, ...]
    使用 DuckDuckGo 文本搜索（pip install ddgs，无需额外 API Key）。
    """
    if not ENABLE_WEB_SEARCH:
        return []
    if _DDGS_CLS is None:
        logger.warning("请安装搜索依赖：pip install ddgs")
        return []

    try:
        ddgs = _DDGS_CLS()
        raw = list(ddgs.text(query, max_results=max_results))
        results = []
        for r in raw:
            url = r.get("href") or r.get("link") or ""
            if not url:
                continue
            results.append(
                {
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("body", r.get("snippet", "")),
                }
            )
        return results
    except Exception as e:
        logger.warning("联网搜索失败: %s", e)
        return []


def format_web_context(results: list[dict]) -> str:
    if not results:
        return ""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[网络片段{i} | {r.get('url', '')}]\n"
            f"标题：{r.get('title', '')}\n"
            f"{r.get('snippet', '')}"
        )
    return "\n\n".join(parts)
