"""
答题模式判定 — 仅看问句结构，不维护 per-topic 注册表。

片段相关度、引用 tier 由 LLM 语义重排（llm_rerank.py）决定；
新增课程题型无需改代码，只需上传资料。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

_HEX_RE = re.compile(r"[0-9A-Fa-f]+H")
_NUM_RE = re.compile(r"\d+\.\d+|\d{2,}")
_CODE_STMT_RE = re.compile(
    r"\b(DB|DW|DD|DUP|MOV|ADD|SUB|ORG|EQU|PROC|ENDP)\b|VAR\d+",
    re.I,
)


def has_concrete_instance(text: str) -> bool:
    """题目是否给出具体实例（数字、代码式语句、字符串字面量等）。"""
    if _HEX_RE.search(text) or _NUM_RE.search(text):
        return True
    if re.search(r"'[^']+'", text):
        return True
    if _CODE_STMT_RE.search(text):
        return True
    return False


def has_apply_intent(text: str) -> bool:
    return any(
        k in text
        for k in (
            "各为多少",
            "多少",
            "转换为",
            "换算",
            "对应",
            "求",
            "计算",
            "表示",
            "化为",
            "写出",
            "分配",
            "画出",
            "编程",
            "实现",
        )
    )


def has_compare_intent(text: str) -> bool:
    return any(
        k in text
        for k in ("区别", "对比", "不同", "优缺点", "相比较", "差异", "异同")
    )


def has_reasoning_intent(text: str) -> bool:
    return any(
        k in text
        for k in (
            "要不要",
            "需要",
            "几个",
            "是否",
            "能否",
            "为什么",
            "怎样",
            "如何",
            "是不是",
            "能不能",
        )
    )


@dataclass(frozen=True)
class AnswerModeProfile:
    id: str
    label: str
    priority: int
    match: Callable[[str], bool]
    raw_weight: float
    coverage_weight: float
    rule_cite_tiers: bool
    filter_weak: bool
    max_cite: int | None
    skip_web_if_strong: bool
    prompt_id: str
    ui_caption: str
    chunk_hint: str
    rerank_hint: str


from src.page_lookup import parse_page_lookup


def _match_page_lookup(q: str) -> bool:
    return parse_page_lookup(q) is not None


def _match_concept_apply(q: str) -> bool:
    """具体实例 + 演算/画图/分配类要求 → 概念应用（不限定学科）。"""
    return has_apply_intent(q) and has_concrete_instance(q)


def _match_compare(q: str) -> bool:
    return has_compare_intent(q)


def _match_reasoning(q: str) -> bool:
    if _match_concept_apply(q):
        return False
    return has_reasoning_intent(q)


ANSWER_MODES: tuple[AnswerModeProfile, ...] = (
    AnswerModeProfile(
        id="concept_apply",
        label="概念应用",
        priority=100,
        match=_match_concept_apply,
        raw_weight=0.25,
        coverage_weight=0.45,
        rule_cite_tiers=True,
        filter_weak=True,
        max_cite=3,
        skip_web_if_strong=True,
        prompt_id="concept_apply",
        ui_caption=(
            "📐 **概念应用题**：按课件规则/例题演算；"
            "引用为**规则或同类例题依据**（非题目原句）。规则匹配度最高 {pct}%。"
        ),
        chunk_hint="📐 概念应用：此页提供规则或同类例题，非现成答案。",
        rerank_hint=(
            "概念应用题：资料含同类定义、换算规则、公式或例题即可高分，"
            "不要求出现题目中的具体数字、变量名或语句。"
        ),
    ),
    AnswerModeProfile(
        id="page_lookup",
        label="页码定位",
        priority=95,
        match=_match_page_lookup,
        raw_weight=0.10,
        coverage_weight=0.10,
        rule_cite_tiers=False,
        filter_weak=False,
        max_cite=2,
        skip_web_if_strong=True,
        prompt_id="page_lookup",
        ui_caption="📄 **按页码定位**：已直接读取指定页内容。匹配度 {pct}%。",
        chunk_hint="",
        rerank_hint="按页码定位，无需语义重排。",
    ),
    AnswerModeProfile(
        id="compare",
        label="对比分析",
        priority=80,
        match=_match_compare,
        raw_weight=0.30,
        coverage_weight=0.55,
        rule_cite_tiers=False,
        filter_weak=False,
        max_cite=None,
        skip_web_if_strong=True,
        prompt_id="compare",
        ui_caption="⚖️ **对比题**：引用为对比依据页。最高相关度 {pct}%。",
        chunk_hint="⚖️ 对比题：此页提供一方或对比维度的概念依据。",
        rerank_hint="对比题：含任一方定义、特点或对比维度即可给中等以上分数。",
    ),
    AnswerModeProfile(
        id="reasoning",
        label="概念推理",
        priority=60,
        match=_match_reasoning,
        raw_weight=0.32,
        coverage_weight=0.52,
        rule_cite_tiers=False,
        filter_weak=False,
        max_cite=None,
        skip_web_if_strong=True,
        prompt_id="reasoning",
        ui_caption="🧩 **推理题**：需据资料定义推导结论。最高相关度 {pct}%。",
        chunk_hint="🧩 推理题：此页提供定义或规则，需结合题目推理。",
        rerank_hint="推理题：含相关定义/规则即可高分，不要求资料写出最终结论。",
    ),
    AnswerModeProfile(
        id="direct",
        label="直接检索",
        priority=0,
        match=lambda _q: True,
        raw_weight=0.35,
        coverage_weight=0.50,
        rule_cite_tiers=False,
        filter_weak=False,
        max_cite=None,
        skip_web_if_strong=False,
        prompt_id="local",
        ui_caption="📌 基于上传资料（最高相关度 {pct}%",
        chunk_hint="",
        rerank_hint="直接检索：资料需与问题主题直接相关。",
    ),
)


def detect_answer_mode(question: str) -> AnswerModeProfile:
    for mode in sorted(ANSWER_MODES, key=lambda m: m.priority, reverse=True):
        if mode.match(question):
            return mode
    return ANSWER_MODES[-1]


def question_mode(question: str) -> str:
    return detect_answer_mode(question).id


def is_concept_application_question(question: str) -> bool:
    return detect_answer_mode(question).id == "concept_apply"
