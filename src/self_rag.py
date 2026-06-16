"""
Self-RAG：检索必要性判断 + 答案质量自评

流程：
  1. retrieve_decision()  — 判断问题是否需要检索课件
  2. relevance_check()    — 判断检索到的片段是否真正相关
  3. answer_quality()     — 判断最终答案是否充分，不足则触发二次检索
"""

from __future__ import annotations

import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


# ── 1. 检索必要性判断 ──────────────────────────────────────────

_RETRIEVE_SYSTEM = """你是一个课程问答系统的路由模块。
判断以下问题是否需要检索课件资料才能回答。

需要检索：涉及具体课程知识点、定义、计算、原理、对比、代码分析
不需要检索：纯闲聊、问候、感谢、问你是谁、总结刚才内容、重复上一个问题

只输出一个词：YES 或 NO"""


def retrieve_decision(llm: ChatOpenAI, question: str) -> bool:
    """
    返回 True 表示需要检索课件，False 表示直接回答即可。
    LLM 调用失败时默认 True（保守策略，不漏检）。
    """
    # 极短问题或明显闲聊直接判断，不调用 LLM，节省费用
    q = question.strip()
    if len(q) <= 4:
        return False
    greetings = ("你好", "谢谢", "感谢", "再见", "你是谁", "你叫什么", "hello", "hi", "thanks")
    if any(q.lower().startswith(g) for g in greetings):
        return False

    try:
        resp = llm.invoke([
            SystemMessage(content=_RETRIEVE_SYSTEM),
            HumanMessage(content=question),
        ]).content.strip().upper()
        return "NO" not in resp  # YES / 其他 → 检索
    except Exception:
        return True  # 失败时保守：检索


# ── 2. 片段相关性判断 ──────────────────────────────────────────

_RELEVANCE_SYSTEM = """你是课程问答系统的相关性评估模块。
判断给出的资料片段对于回答该问题是否有帮助。

有帮助：片段包含回答所需的定义、规则、公式、例题或相关背景
无帮助：片段与问题完全无关，或只有标题没有实质内容

只输出一个词：RELEVANT 或 IRRELEVANT"""


def relevance_check(
    llm: ChatOpenAI,
    question: str,
    context: str,
) -> bool:
    """
    返回 True 表示检索到的内容与问题相关，可以用于回答。
    LLM 调用失败时默认 True（保守策略）。
    """
    if not context or len(context.strip()) < 20:
        return False
    preview = context[:600]
    try:
        resp = llm.invoke([
            SystemMessage(content=_RELEVANCE_SYSTEM),
            HumanMessage(content=f"问题：{question}\n\n资料片段：{preview}"),
        ]).content.strip().upper()
        return "IRRELEVANT" not in resp
    except Exception:
        return True


# ── 3. 答案质量自评（决定是否二次检索）────────────────────────

_QUALITY_SYSTEM = """你是课程问答系统的答案质量评估模块。
判断以下回答是否充分解答了学生的问题。

充分：回答包含完整的解释、计算步骤或对比分析，学生能直接使用
不充分：回答模糊、缺少关键步骤、说"资料未提及"、或答非所问

只输出一个词：SUFFICIENT 或 INSUFFICIENT"""


def answer_quality(
    llm: ChatOpenAI,
    question: str,
    answer: str,
) -> bool:
    """
    返回 True 表示答案质量充分，False 表示需要补充（触发二次检索或联网）。
    LLM 调用失败时默认 True（避免无限循环）。
    """
    if not answer or len(answer.strip()) < 10:
        return False
    try:
        resp = llm.invoke([
            SystemMessage(content=_QUALITY_SYSTEM),
            HumanMessage(content=f"问题：{question}\n\n回答：{answer[:800]}"),
        ]).content.strip().upper()
        return "INSUFFICIENT" not in resp
    except Exception:
        return True
