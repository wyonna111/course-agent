"""
ReAct Agent：用 OpenAI function calling 驱动工具选择。

工具：
  search_local  — 在课件资料库中检索相关片段
  search_web    — 联网搜索补充信息
  direct_answer — 直接回答（无需检索，适合闲聊/通识问题）

流程：
  LLM 根据问题自主决定调哪个工具 → 工具返回结果 → LLM 再次决策（最多 3 轮）→ 生成最终答案
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

if TYPE_CHECKING:
    from src.indexer import DocumentIndex

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_local",
            "description": "在已上传的课件资料库中检索与问题相关的片段，适合课程知识点、考题解析等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用于检索的查询词"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "联网搜索补充信息，适合资料库中没有、或需要最新信息的问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "direct_answer",
            "description": "直接回答，无需检索，适合问候、闲聊、通识性问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "选择直接回答的理由"},
                },
                "required": ["reason"],
            },
        },
    },
]

_AGENT_SYSTEM = """你是「课内有据」学习助手，通过调用工具回答学生问题。

策略：
1. 课程知识点、考题 → 优先调用 search_local
2. search_local 返回内容与问题无关，或需要补充 → 调用 search_web
3. 问候、闲聊、简单通识问题 → 调用 direct_answer
4. 获得足够信息后，直接输出最终答案，不要再调用工具

引用格式：文末写「引用：」并逐字复制参考资料开头的 [本地: 文件名 第N页] 标签。"""


def run_agent_qa(
    index: "DocumentIndex",
    llm,
    prompt: str,
    history: list[dict],
) -> dict:
    """
    ReAct Agent 主入口，返回与 run_qa 相同结构的 meta dict。
    """
    from src.chat import (
        chat_reply_web,
        format_context,
        get_reasoning_llm,
        normalize_answer_citations,
        _history_messages,
        SYSTEM_PROMPT_LOCAL,
        REFUSAL_TEMPLATE,
    )
    from src.web_search import search_web, format_web_context
    from src.config import ENABLE_WEB_SEARCH, REASONING_MODEL_NAME
    from src.corrections import apply_corrections_to_docs

    def _workspace_id():
        try:
            import streamlit as st
            return st.session_state.get("workspace_id")
        except Exception:
            return None

    # 工具执行函数
    def _exec_search_local(query: str):
        if not index.ready:
            return [], 0.0, "资料库为空，无法检索。"
        docs, best_sim, _ = index.retriever.similarity_search_multi(query, llm=llm)
        docs = apply_corrections_to_docs(docs, _workspace_id())
        if not docs:
            return [], 0.0, "未在课件中找到相关内容。"
        context = format_context(docs)
        return docs, best_sim, context

    def _exec_search_web(query: str):
        if not ENABLE_WEB_SEARCH:
            return [], "联网搜索已关闭。"
        results = search_web(query, max_results=5)
        if not results:
            return [], "联网搜索无结果。"
        return results, format_web_context(results)

    # 构建初始消息
    history_msgs = _history_messages(history)
    messages = [
        SystemMessage(content=_AGENT_SYSTEM),
        *history_msgs,
        HumanMessage(content=prompt),
    ]

    # 绑定工具到 LLM（辅助决策用普通模型）
    llm_with_tools = llm.bind_tools(_TOOLS)

    collected_docs = []
    collected_web = []
    best_sim = 0.0
    source_mode = "none"

    # ReAct 循环，最多 3 轮工具调用
    for _round in range(3):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None)
        if not tool_calls:
            # 没有工具调用，直接取最终答案
            answer = response.content or REFUSAL_TEMPLATE
            if collected_docs:
                answer = normalize_answer_citations(answer, [(d, 0) for d in collected_docs])
            break

        # 执行所有工具调用
        for tc in tool_calls:
            name = tc["name"]
            args = tc["args"] if isinstance(tc["args"], dict) else json.loads(tc["args"])
            tool_id = tc.get("id", name)

            if name == "search_local":
                docs, sim, content = _exec_search_local(args.get("query", prompt))
                collected_docs = docs
                best_sim = max(best_sim, sim)
                source_mode = "local"
                messages.append(ToolMessage(content=content, tool_call_id=tool_id))

            elif name == "search_web":
                results, content = _exec_search_web(args.get("query", prompt))
                collected_web = results
                if source_mode == "local":
                    source_mode = "hybrid"
                else:
                    source_mode = "web"
                messages.append(ToolMessage(content=content, tool_call_id=tool_id))

            elif name == "direct_answer":
                source_mode = "direct"
                messages.append(ToolMessage(content="直接回答模式。", tool_call_id=tool_id))

    else:
        # 超出轮次，强制生成
        final_response = llm.invoke(messages)
        answer = final_response.content or REFUSAL_TEMPLATE
        if collected_docs:
            answer = normalize_answer_citations(answer, [(d, 0) for d in collected_docs])

    return {
        "answer": answer,
        "docs": collected_docs,
        "web_results": collected_web,
        "best_sim": best_sim,
        "source_mode": source_mode,
        "topic_strong": False,
        "term_ratio": 0.0,
        "match_terms": [],
        "rerank_metas": [],
        "self_rag_skip": False,
        "agent_mode": True,
    }
