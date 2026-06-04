"""对话与检索查询逻辑"""

import os
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import MAX_HISTORY_TURNS, MIN_RELEVANCE, USE_LLM_REWRITE_QUERY
from src.loaders import location_label
from src.addressing_ref import REF_8086_ADDRESSING, is_addressing_table_page
from src.question_types import detect_answer_mode
from src.retriever import chunk_index_text
from src.web_search import format_web_context

# 作答风格：默认细致；课件有误时仅禁止纠结式表述
ANSWER_STYLE = """
【作答风格】
1. **细致、完整**：逐条写清寻址方式判断、物理地址计算过程与结论。
2. 多指令判错题：先逐条分析 → **错误项汇总** → 对照选项 → **文末写一次「答案：X」**（不要开头预告又与文末矛盾）。
3. 课件/选项与严格判断不一致时：点明 1 句即可，**不要**「可能、再检查、再看、矛盾」式反复改口。
4. **[已人工纠错]** 以纠错正文为准。
5. 文末单独一行「引用：」，**逐字复制**参考资料开头的 **[本地: 文件名 第N页]** 或 **[本地: 文件名 幻灯片 N]**；**禁止**写「片段1」「片段2」或省略 [本地: ] 前缀。"""


def _compose_style() -> str:
    return ANSWER_STYLE


SYSTEM_PROMPT_LOCAL = f"""你是「课内有据」学习助手。你必须依据提供的**课程资料片段**回答。

规则：
1. 综合片段作答；**[已人工纠错]** 片段以纠错正文为准。
2. 资料有定义/规则时据此推理，勿因未逐字出现结论就说「未找到」。
3. 仅当片段与问题**完全无关**时才写「上传的资料中未找到相关信息」。

{_compose_style()}"""


SYSTEM_PROMPT_CONCEPT_APPLY = f"""你是「课内有据」学习助手。这是**概念应用题**，需按课件规则/例题自行演算。

规则：
1. 提取规则或同类例题做法；**[已人工纠错]** 以纠错正文为准。
2. 分步演算，步骤完整；若要求画图，用文字或 ASCII 示意。
3. 禁止写「资料未找到」。

{_compose_style()}"""


SYSTEM_PROMPT_LOCAL_APPLY = f"""你是「课内有据」学习助手。资料片段**已包含**答题所需概念，请直接作答。

规则：
1. 提取定义/规则，推理过程写完整；禁止「未找到/无法回答」。

{_compose_style()}"""


SYSTEM_PROMPT_COMPARE = f"""你是「课内有据」学习助手。这是**对比题**。

规则：
1. 先概括核心差异，再分点或表格对比，双方都要写全。
2. 资料只覆盖一方时据实说明，再基于已有内容对比。

{_compose_style()}"""


SYSTEM_PROMPT_REASONING = f"""你是「课内有据」学习助手。这是**推理题**。

规则：
1. 先结论，再按逻辑链逐步推理，每步写清依据。
2. 禁止因资料未写最终结论就说「未找到」。

{_compose_style()}"""


SYSTEM_PROMPT_PAGE_LOOKUP = f"""你是「课内有据」学习助手。下方片段即学生指定的**该页完整正文**（按页码定位，含表格与选项）。

规则：
1. **严格依据该页表格中的 DS/SS/寄存器初值与每条指令**逐条分析，不要编造页外数据。
2. 多指令判错题：逐条分析 → 错误项汇总 → 对照选项 → 文末「答案：X」。
3. 禁止说「片段未包含该页」。

{_compose_style()}"""


PROMPT_BY_ID = {
    "local": SYSTEM_PROMPT_LOCAL,
    "concept_apply": SYSTEM_PROMPT_CONCEPT_APPLY,
    "local_apply": SYSTEM_PROMPT_LOCAL_APPLY,
    "compare": SYSTEM_PROMPT_COMPARE,
    "reasoning": SYSTEM_PROMPT_REASONING,
    "page_lookup": SYSTEM_PROMPT_PAGE_LOOKUP,
}


SYSTEM_PROMPT_WEB = f"""你是「课内有据」学习助手。上传资料未覆盖，请据**网络检索**作答。

规则：
1. 开头一句说明来源为网络资料。
2. 不要编造检索中没有的内容。

{_compose_style()}
引用格式：[网络: URL]"""


SYSTEM_PROMPT_HYBRID = f"""你是「课内有据」学习助手。结合**课程资料**与**网络检索**作答。

规则：
1. 与课程直接相关的内容优先采用资料，写全分析过程；冲突以资料为准。
2. 网络部分仅作补充。

{_compose_style()}"""


# 本地回答出现这些表述时，触发联网补充
INSUFFICIENT_MARKERS = (
    "未找到相关",
    "未找到相关信息",
    "上传的资料中未找到",
    "资料中未提及",
    "资料中未涉及",
    "资料未提及",
    "均未包含",
    "没有包含",
    "没有提到",
    "无法回答",
    "无法区分",
    "未覆盖",
    "不包含相关",
    "没有相关",
)


REFUSAL_TEMPLATE = (
    "上传的资料与网络检索均未找到足够信息。\n\n"
    "建议：\n"
    "1. 换种问法或补充关键词；\n"
    "2. 确认相关讲义/PPT 已上传并重新索引；\n"
    "3. 检查网络连接或稍后重试联网搜索。"
)


def get_llm() -> ChatOpenAI:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "你的密钥":
        raise ValueError("请在 .env 中填写 OPENAI_API_KEY")
    return ChatOpenAI(
        api_key=key,
        base_url=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1"),
        model=os.getenv("MODEL_NAME", "deepseek-chat"),
        temperature=0.25,
    )


def is_insufficient_local_answer(text: str) -> bool:
    """判断本地资料回答是否表示「资料里没有」。"""
    if not text:
        return True
    t = text.strip()
    return any(m in t for m in INSUFFICIENT_MARKERS)


def should_fallback_to_web(
    best_sim: float,
    local_answer: str | None,
    topic_strong: bool = False,
) -> bool:
    """
    是否应联网补充。
    topic_strong=True 表示检索片段与问题关键词高度匹配，即使 LLM 误报「未找到」也不联网。
    """
    if topic_strong:
        return best_sim <= 0
    if local_answer and is_insufficient_local_answer(local_answer):
        return True
    if best_sim < MIN_RELEVANCE:
        return True
    return False


def format_context(docs_with_scores: list) -> str:
    """送入模型的资料块：以 [本地: …] 为唯一溯源标签，不用「片段N」。"""
    parts = []
    for doc, _score in docs_with_scores:
        loc = location_label(doc.metadata)
        body = chunk_index_text(doc)
        parts.append(f"{loc}\n{body}")
    parts.append(
        "【引用格式】文末「引用：」须逐字复制上文各段开头的 [本地: …] 标签，"
        "禁止使用「片段1」「片段2」等编号。"
    )
    return "\n\n".join(parts)


def repair_legacy_fragment_citations(text: str) -> str:
    """
    修复旧版回答中的「片段N」引用（协作空间历史里常见）。
    例：[片段1] 某.pdf 第17页 → [本地: 某.pdf 第17页]
    """
    if not text or "片段" not in text:
        return text

    def _to_local(m: re.Match) -> str:
        body = m.group(1).strip()
        if body.startswith("[本地:"):
            return m.group(0)
        return f"[本地: {body}]"

    text = re.sub(r"\[?片段\d+\]?\s*([^\[；\n]+)", _to_local, text)
    return text


def build_citation_line(docs_with_scores: list) -> str:
    seen: list[str] = []
    for doc, _ in docs_with_scores:
        loc = location_label(doc.metadata)
        if loc not in seen:
            seen.append(loc)
    if not seen:
        return ""
    return "引用：" + "；".join(seen)


def normalize_answer_citations(answer: str, docs_with_scores: list) -> str:
    """去掉模型生成的引用行，统一替换为标准 [本地: …] 格式。"""
    if not docs_with_scores or not (answer or "").strip():
        return repair_legacy_fragment_citations(answer)
    import re

    line = build_citation_line(docs_with_scores)
    if not line:
        return repair_legacy_fragment_citations(answer)

    text = answer.rstrip()
    for i, (doc, _) in enumerate(docs_with_scores, 1):
        loc = location_label(doc.metadata)
        text = re.sub(rf"\[?片段{i}\]?", loc, text)

    lines = text.rstrip().split("\n")
    while lines and re.match(r"^引用[：:]", lines[-1].strip()):
        lines.pop()
    text = "\n".join(lines).rstrip()
    return f"{text}\n\n{line}"


def build_search_query(question: str, history: list[dict]) -> str:
    if USE_LLM_REWRITE_QUERY:
        return question
    recent_user = [m["content"] for m in history if m["role"] == "user"]
    if recent_user:
        return f"{recent_user[-1]} {question}"
    return question


def retrieval_query_with_llm(
    llm: ChatOpenAI, question: str, history: list[dict]
) -> str:
    recent = history[-MAX_HISTORY_TURNS:]
    lines = []
    for m in recent:
        role = "学生" if m["role"] == "user" else "助手"
        lines.append(f"{role}：{m['content'][:300]}")
    dialog = "\n".join(lines) if lines else "（无）"
    messages = [
        SystemMessage(
            content="根据对话历史，把「当前问题」改写成适合在课程讲义里检索的一句中文问句。"
            "只输出这一句话，不要解释。"
        ),
        HumanMessage(content=f"对话历史：\n{dialog}\n\n当前问题：{question}"),
    ]
    return llm.invoke(messages).content.strip()


def _history_messages(history: list[dict]) -> list:
    """送入 LLM 的历史：去掉旧式「片段N」以免污染新回答的引用格式。"""
    recent = history[-MAX_HISTORY_TURNS:]
    dialog = []
    for m in recent:
        if m["role"] == "user":
            dialog.append(HumanMessage(content=m["content"]))
        else:
            content = repair_legacy_fragment_citations(m.get("content", ""))
            dialog.append(AIMessage(content=content))
    return dialog


def _build_user_content(
    question: str, context: str, docs_with_scores: list
) -> str:
    parts = [f"参考资料：\n{context}"]
    corpus = context
    if is_addressing_table_page(corpus):
        parts.append(REF_8086_ADDRESSING)
        parts.append(
            "【重要】请仅根据参考资料中**该页完整表格**逐条判断；"
            "每条须写出物理地址计算式（若涉及内存访问）。"
        )
    parts.append(f"学生当前问题：{question}")
    return "\n\n".join(parts)


def _pick_local_system(
    question: str, force_apply: bool, docs_with_scores: list | None = None
) -> str:
    mode = detect_answer_mode(question)
    if force_apply:
        return PROMPT_BY_ID["local_apply"]
    return PROMPT_BY_ID.get(mode.prompt_id, SYSTEM_PROMPT_LOCAL)


def chat_reply_local(
    llm: ChatOpenAI,
    question: str,
    docs_with_scores: list,
    history: list[dict],
    *,
    force_apply: bool = False,
) -> str:
    context = format_context(docs_with_scores)
    system = _pick_local_system(question, force_apply, docs_with_scores)
    messages = [
        SystemMessage(content=system),
        *_history_messages(history),
        HumanMessage(content=_build_user_content(question, context, docs_with_scores)),
    ]
    raw = llm.invoke(messages).content
    return normalize_answer_citations(raw, docs_with_scores)


def chat_reply_local_with_retry(
    llm: ChatOpenAI,
    question: str,
    docs_with_scores: list,
    history: list[dict],
    topic_strong: bool,
) -> str:
    """先正常答；概念应用题用专用 prompt；误报未找到时用更强 prompt 重答。"""
    answer = chat_reply_local(llm, question, docs_with_scores, history)
    if (
        detect_answer_mode(question).skip_web_if_strong is False
        and topic_strong
        and is_insufficient_local_answer(answer)
    ):
        answer = chat_reply_local(
            llm, question, docs_with_scores, history, force_apply=True
        )
    return answer


def chat_reply_web(
    llm: ChatOpenAI,
    question: str,
    web_results: list[dict],
    history: list[dict],
) -> str:
    context = format_web_context(web_results)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT_WEB),
        *_history_messages(history),
        HumanMessage(
            content=f"网络检索结果：\n{context}\n\n学生当前问题：{question}"
        ),
    ]
    return llm.invoke(messages).content


def chat_reply_hybrid(
    llm: ChatOpenAI,
    question: str,
    docs_with_scores: list,
    web_results: list[dict],
    history: list[dict],
) -> str:
    local_ctx = format_context(docs_with_scores)
    web_ctx = format_web_context(web_results)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT_HYBRID),
        *_history_messages(history),
        HumanMessage(
            content=(
                f"课程资料：\n{local_ctx}\n\n"
                f"网络检索：\n{web_ctx}\n\n"
                f"学生当前问题：{question}"
            )
        ),
    ]
    raw = llm.invoke(messages).content
    return normalize_answer_citations(raw, docs_with_scores)


# 兼容旧名
chat_reply = chat_reply_local
