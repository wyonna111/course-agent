"""
LLM 语义重排：判断资料片段对「回答本题」的帮助程度。

替代 per-topic 关键词注册表 — 新题型无需改代码。
"""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import LLM_RERANK_MAX_CHUNKS, LLM_RERANK_PREVIEW_CHARS
from src.loaders import location_label
from src.question_types import AnswerModeProfile, detect_answer_mode

VALID_TIERS = frozenset(
    {"概念依据", "规则参考", "直接命中", "部分相关", "弱相关"}
)

SYSTEM = """你是课程资料检索重排助手。根据学生问题和资料片段，判断该片段对回答问题的帮助程度。

评分原则（务必遵守）：
1. **概念应用题**：课件中的规则、定义、公式、**同类例题**均可高分；资料不必含题目中的具体数字或变量名。
2. **对比/推理题**：含相关定义或规则即可，不要求写出最终答案。
3. **直接题**：需与问题主题直接相关；完全跑题给低分。
4. 区分「同类知识的不同章节」与「完全无关主题」（如问汇编变量分配时，通用字长概念页应低于汇编例题页）。

只输出 JSON 数组，不要 markdown 或其它文字。每项格式：
{"idx": 1, "score": 85, "tier": "概念依据", "reason": "一句话说明"}

tier 只能是：概念依据、规则参考、直接命中、部分相关、弱相关
score 为 0-100 整数。"""


def _extract_json_array(text: str) -> list[dict]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return []


def _normalize_tier(tier: str, score: int, rule_cite: bool) -> str:
    tier = (tier or "").strip()
    if tier in VALID_TIERS:
        return tier
    if rule_cite:
        if score >= 55:
            return "概念依据"
        if score >= 35:
            return "规则参考"
        return "弱相关"
    if score >= 60:
        return "直接命中"
    if score >= 35:
        return "部分相关"
    return "弱相关"


def llm_rerank_chunks(
    llm: ChatOpenAI,
    question: str,
    candidates: list[tuple],
    get_text,
    mode: AnswerModeProfile | None = None,
) -> list[tuple] | None:
    """
    用 LLM 对候选片段打分。成功返回 [(doc, score_0_1, meta), ...]；失败返回 None。
    """
    if not candidates:
        return []

    mode = mode or detect_answer_mode(question)
    batch = candidates[:LLM_RERANK_MAX_CHUNKS]

    parts = []
    for i, (doc, raw) in enumerate(batch, 1):
        loc = location_label(doc.metadata)
        preview = get_text(doc)[:LLM_RERANK_PREVIEW_CHARS].replace("\n", " ")
        parts.append(f"[{i}] {loc}\n检索分={raw:.3f}\n{preview}")

    user = (
        f"答题模式：{mode.label}（{mode.id}）\n"
        f"模式说明：{mode.rerank_hint}\n\n"
        f"学生问题：\n{question}\n\n"
        f"资料片段（共 {len(batch)} 条）：\n\n"
        + "\n\n".join(parts)
    )

    try:
        resp = llm.invoke(
            [SystemMessage(content=SYSTEM), HumanMessage(content=user)]
        ).content
    except Exception:
        return None

    items = _extract_json_array(resp)
    if not items:
        return None

    by_idx: dict[int, dict] = {}
    for item in items:
        try:
            idx = int(item.get("idx", 0))
            by_idx[idx] = item
        except (TypeError, ValueError):
            continue

    scored: list[tuple] = []
    for i, (doc, raw) in enumerate(batch, 1):
        item = by_idx.get(i, {})
        try:
            score_pct = int(item.get("score", 0))
        except (TypeError, ValueError):
            score_pct = 0
        score_pct = max(0, min(100, score_pct))
        tier = _normalize_tier(str(item.get("tier", "")), score_pct, mode.rule_cite_tiers)
        reason = str(item.get("reason", "")).strip()[:120]

        keep = tier != "弱相关" or score_pct >= 30
        if mode.rule_cite_tiers:
            keep = tier in ("概念依据", "规则参考") or score_pct >= 40

        meta = {
            "display_score": round(score_pct / 100, 3),
            "display_pct": score_pct,
            "raw_score": round(float(raw), 3),
            "coverage": None,
            "boosts": [],
            "penalties": [],
            "keep": keep,
            "cite_tier": tier,
            "answer_mode": mode.id,
            "answer_mode_label": mode.label,
            "chunk_hint": mode.chunk_hint,
            "llm_reason": reason,
            "rerank_method": "llm",
        }
        scored.append((doc, score_pct / 100, meta))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
