"""
检索片段重排：优先 LLM 语义判断，失败时回退通用启发式（无题型注册表）。
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from src.config import ENABLE_LLM_RERANK
from src.llm_rerank import llm_rerank_chunks
from src.question_types import AnswerModeProfile, detect_answer_mode
from src.query_utils import assess_topic_coverage, extract_key_terms, term_overlap_ratio


def _heuristic_cite_tier(score: float, mode: AnswerModeProfile) -> str:
    if mode.rule_cite_tiers:
        if score >= 0.45:
            return "概念依据"
        if score >= 0.28:
            return "规则参考"
        return "弱相关"
    if score >= 0.45:
        return "直接命中"
    if score >= 0.28:
        return "部分相关"
    return "弱相关"


def _heuristic_score(
    question: str, chunk_text: str, raw_retrieval_score: float, mode: AnswerModeProfile
) -> dict:
    cov = assess_topic_coverage(question, chunk_text)
    raw_norm = min(float(raw_retrieval_score) / 1.15, 1.0)
    score = raw_norm * mode.raw_weight + float(cov["coverage"]) * mode.coverage_weight
    score = max(0.0, min(1.0, score))
    cite_tier = _heuristic_cite_tier(score, mode)

    if mode.rule_cite_tiers:
        keep = cite_tier in ("概念依据", "规则参考") or score >= 0.32
    else:
        keep = score >= 0.30

    return {
        "display_score": round(score, 3),
        "display_pct": int(round(score * 100)),
        "raw_score": round(raw_retrieval_score, 3),
        "coverage": cov["coverage"],
        "boosts": [],
        "penalties": [],
        "keep": keep,
        "cite_tier": cite_tier,
        "answer_mode": mode.id,
        "answer_mode_label": mode.label,
        "chunk_hint": mode.chunk_hint,
        "llm_reason": "",
        "rerank_method": "heuristic",
    }


def rerank_chunks(
    question: str,
    candidates: list[tuple],
    k: int = 4,
    min_keep: int = 2,
    get_text=None,
    llm: ChatOpenAI | None = None,
) -> list[tuple]:
    if get_text is None:
        raise ValueError("get_text 必须传入 chunk_index_text")

    mode = detect_answer_mode(question)

    scored: list[tuple] | None = None
    if ENABLE_LLM_RERANK and llm is not None:
        scored = llm_rerank_chunks(llm, question, candidates, get_text, mode)

    if scored is None:
        scored = []
        for doc, raw in candidates:
            text = get_text(doc)
            meta = _heuristic_score(question, text, raw, mode)
            scored.append((doc, meta["display_score"], meta))
        scored.sort(key=lambda x: x[1], reverse=True)

    kept = [x for x in scored if x[2]["keep"]]
    if len(kept) >= min_keep:
        result = kept[:k]
    else:
        result = scored[: max(min_keep, k)]

    if mode.filter_weak:
        filtered = [x for x in result if x[2]["cite_tier"] != "弱相关"]
        if filtered:
            cap = mode.max_cite or k
            result = filtered[:cap]

    return result
