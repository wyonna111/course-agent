"""
课内有据 — Phase 1 基础版
左栏上传资料，右栏对话；支持 PDF / PPTX / TXT，多文件索引，回答带页码/幻灯片溯源。

运行：streamlit run app.py
"""

import base64
import html
import json
import os
from pathlib import Path

from urllib.parse import urlparse

import streamlit as st
from openai import APIStatusError

from src.chat import (
    REFUSAL_TEMPLATE,
    build_search_query,
    chat_reply_hybrid,
    chat_reply_local_with_retry,
    chat_reply_web,
    get_llm,
    repair_legacy_fragment_citations,
    retrieval_query_with_llm,
    should_fallback_to_web,
)
from src.config import (
    DATA_DIR,
    ENABLE_CORRECTIONS,
    ENABLE_REFERENCES,
    ENABLE_WEB_SEARCH,
    ENABLE_WORKSPACE,
    MIN_RELEVANCE,
    PUBLIC_APP_URL,
    REFERENCE_FETCH_META,
    UI_PANEL_HEIGHT,
    USE_LLM_REWRITE_QUERY,
)
from src.corrections import (
    CorrectionError,
    apply_correction_to_doc,
    apply_corrections_to_docs,
    chunk_source_key,
    delete_correction,
    get_correction,
    list_corrections_summary,
    save_correction,
)
from src.chat_history import (
    clear_personal_messages,
    load_personal_messages,
    save_personal_messages,
    sanitize_chat_messages,
)
from src.indexer import DocumentIndex
from src.loaders import location_label
from src.question_types import detect_answer_mode
from src.references import (
    linkify_dois_in_text,
    parse_references_from_file,
    parse_references_from_text,
    summarize_parse_results,
)
from src.retriever import chunk_index_text
from src.web_search import search_web
from src.workspace import (
    WorkspaceError,
    append_workspace_message,
    create_workspace,
    get_workspace_data_dir,
    join_workspace,
    load_workspace_messages,
    normalize_code,
    save_workspace_messages,
    workspace_exists,
)

LAYOUT_CSS_PATH = Path(__file__).resolve().parent / "assets" / "layout.css"
LOGO_SVG_PATH = Path(__file__).resolve().parent / "assets" / "logo.svg"


def _logo_html() -> str:
    if not LOGO_SVG_PATH.exists():
        return '<span class="ct-logo">📖</span>'
    encoded = base64.b64encode(LOGO_SVG_PATH.read_bytes()).decode("ascii")
    return f'<img class="ct-logo" src="data:image/svg+xml;base64,{encoded}" alt="" />'


def inject_layout_css() -> None:
    if LAYOUT_CSS_PATH.exists():
        css = LAYOUT_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


SPLITTER_JS_PATH = Path(__file__).resolve().parent / "assets" / "splitter.js"


def render_ui_scripts() -> None:
    """品牌顶栏 + 可拖分栏（页面底部注入，确保分栏 DOM 已渲染）。"""
    logo = _logo_html()
    inner = (
        f'{logo}<span class="ct-brand-name">课内有据</span>'
        f'<span class="ct-brand-slogan">课内资料优先 · 回答可溯源</span>'
    )
    splitter_js = ""
    if SPLITTER_JS_PATH.exists():
        splitter_js = SPLITTER_JS_PATH.read_text(encoding="utf-8")
    html = f"""
        <script>
        (() => {{
          const doc = window.parent.document;
          let bar = doc.getElementById("ct-brand-bar");
          if (!bar) {{
            bar = doc.createElement("div");
            bar.id = "ct-brand-bar";
            bar.className = "ct-brand-bar";
            bar.setAttribute("aria-label", "课内有据");
            doc.body.appendChild(bar);
          }}
          bar.innerHTML = {json.dumps(inner)};
        }})();
        {splitter_js}
        </script>
        """
    if hasattr(st, "iframe"):
        # st.iframe 不允许 height=0，用 content 自动收缩
        st.iframe(html, height="content")
    else:
        import streamlit.components.v1 as components

        components.html(html, height=0)


def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "doc_index" not in st.session_state:
        st.session_state.doc_index = DocumentIndex()
    if "auto_loaded" not in st.session_state:
        st.session_state.auto_loaded = False
    if "workspace_id" not in st.session_state:
        st.session_state.workspace_id = None
    if "workspace_name" not in st.session_state:
        st.session_state.workspace_name = ""
    if "member_name" not in st.session_state:
        st.session_state.member_name = ""
    if "_messages_loaded" not in st.session_state:
        st.session_state._messages_loaded = False
    for key in ("index_job_active", "rebuild_job_active", "ref_job_active", "qa_job_active"):
        if key not in st.session_state:
            st.session_state[key] = False


def is_app_busy() -> bool:
    return bool(
        st.session_state.get("index_job_active")
        or st.session_state.get("rebuild_job_active")
        or st.session_state.get("ref_job_active")
        or st.session_state.get("qa_job_active")
    )


def render_busy_banner() -> None:
    if not is_app_busy():
        return
    if st.session_state.get("qa_job_active"):
        msg = "正在思考并组织回答"
    elif st.session_state.get("index_job_active"):
        msg = "正在解析课件并建立索引"
    elif st.session_state.get("rebuild_job_active"):
        msg = "正在重建资料索引"
    elif st.session_state.get("ref_job_active"):
        msg = "正在解析参考文献"
    else:
        msg = "处理中"
    st.markdown(
        f'<div class="ct-busy-banner">⏳ <strong>{html.escape(msg)}</strong> · 请稍候，勿重复点击</div>',
        unsafe_allow_html=True,
    )


def ensure_messages_loaded() -> None:
    if st.session_state.get("_messages_loaded"):
        return
    wid = st.session_state.get("workspace_id")
    if wid and ENABLE_WORKSPACE:
        st.session_state.messages = load_workspace_messages(wid)
    else:
        st.session_state.messages = load_personal_messages()
    st.session_state._messages_loaded = True


def reset_messages_loaded_flag() -> None:
    st.session_state._messages_loaded = False


def active_data_dir() -> Path:
    """当前生效的资料目录：协作空间内用空间 data/，否则用全局 data/。"""
    wid = st.session_state.get("workspace_id")
    if wid and ENABLE_WORKSPACE:
        return get_workspace_data_dir(wid)
    return DATA_DIR


def sync_workspace_messages(force: bool = False) -> bool:
    """从磁盘拉取协作空间消息；有更新返回 True。"""
    wid = st.session_state.get("workspace_id")
    if not wid or not ENABLE_WORKSPACE:
        return False
    disk = load_workspace_messages(wid)
    session = st.session_state.messages
    if force or sanitize_chat_messages(disk) != sanitize_chat_messages(session):
        st.session_state.messages = disk
        return True
    return False


def persist_messages() -> None:
    wid = st.session_state.get("workspace_id")
    if wid and ENABLE_WORKSPACE:
        save_workspace_messages(wid, st.session_state.messages)
    else:
        save_personal_messages(st.session_state.messages)


def rebuild_index_for_context(index: DocumentIndex) -> None:
    """按当前模式（个人/协作）从对应 data 目录重建索引。"""
    data_dir = active_data_dir()
    if not data_dir.exists():
        index.chunks = []
        index.indexed_files = []
        index.retriever = None
        return
    has_files = any(
        p.is_file() and p.suffix.lower() in {".pdf", ".pptx", ".ppt", ".txt", ".md"}
        for p in data_dir.iterdir()
    )
    if not has_files:
        index.chunks = []
        index.indexed_files = []
        index.retriever = None
        return
    index.rebuild_from_data_dir(data_dir)


def try_join_from_url() -> None:
    """支持分享链接 ?space=邀请码 一键加入。"""
    if not ENABLE_WORKSPACE or st.session_state.get("workspace_id"):
        return
    code = st.query_params.get("space")
    if not code:
        return
    code = normalize_code(code)
    if workspace_exists(code):
        meta = join_workspace(code)
        st.session_state.workspace_id = meta["id"]
        st.session_state.workspace_name = meta.get("name", "")
        st.session_state.messages = meta.get("messages", [])
        st.session_state.auto_loaded = False
        st.session_state._messages_loaded = True


def enter_workspace(workspace_id: str, name: str = "") -> None:
    st.session_state.workspace_id = workspace_id
    st.session_state.workspace_name = name
    st.session_state.messages = load_workspace_messages(workspace_id)
    st.session_state.auto_loaded = False
    reset_messages_loaded_flag()
    st.session_state._messages_loaded = True


def leave_workspace() -> None:
    st.session_state.workspace_id = None
    st.session_state.workspace_name = ""
    st.session_state.messages = load_personal_messages()
    st.session_state.auto_loaded = False
    reset_messages_loaded_flag()
    st.session_state._messages_loaded = True


def try_auto_load_index(index: DocumentIndex):
    """启动时若当前资料目录里已有文件，自动建索引。"""
    if st.session_state.auto_loaded and index.ready:
        return
    data_dir = active_data_dir()
    if not data_dir.exists():
        st.session_state.auto_loaded = True
        return
    has_files = any(
        p.is_file() and p.suffix.lower() in {".pdf", ".pptx", ".ppt", ".txt", ".md"}
        for p in data_dir.iterdir()
    )
    if has_files:
        try:
            index.rebuild_from_data_dir(data_dir)
        except Exception:
            pass
    st.session_state.auto_loaded = True


def render_web_sources(web_results: list[dict]):
    with st.expander("🌐 本轮参考的网络来源", expanded=True):
        for i, r in enumerate(web_results, 1):
            title = r.get("title") or "（无标题）"
            url = r.get("url", "")
            st.markdown(f"**{i}. {title}**")
            if url:
                st.markdown(f"[网络: {url}]({url})")
            snippet = r.get("snippet", "")
            if snippet:
                st.caption(snippet[:400])


def current_workspace_id() -> str | None:
    return st.session_state.get("workspace_id")


def run_qa(index: DocumentIndex, llm, prompt: str, history: list[dict]):
    """先查本地资料，不足则联网 + DeepSeek 整理并附 URL。"""
    if USE_LLM_REWRITE_QUERY:
        search_q = retrieval_query_with_llm(llm, prompt, history)
    else:
        search_q = build_search_query(prompt, history)

    docs, best_sim = [], 0.0
    rerank_metas: list[dict] = []
    topic_info = {"strong": False, "term_ratio": 0.0, "best_sim": 0.0, "terms": []}

    if index.ready:
        docs, best_sim, rerank_metas = index.retriever.similarity_search_multi(
            prompt, llm=llm
        )
        docs = apply_corrections_to_docs(docs, current_workspace_id())
        topic_info = index.retriever.local_topic_match(prompt, docs)

    local_answer: str | None = None
    web_results: list[dict] = []
    source_mode = "none"
    topic_strong = topic_info.get("strong", False)

    # 1) 本地有匹配 → 先按课件回答（主题匹配时带重试）
    if docs and best_sim > 0:
        local_answer = chat_reply_local_with_retry(
            llm, prompt, docs, history, topic_strong=topic_strong
        )

    # 2) 判断是否需要联网（资料主题已匹配时不因 LLM 误报而联网）
    answer_mode = detect_answer_mode(prompt)
    need_web = ENABLE_WEB_SEARCH and should_fallback_to_web(
        best_sim, local_answer or "", topic_strong=topic_strong
    )
    if answer_mode.skip_web_if_strong and topic_strong:
        need_web = False

    if need_web:
        web_results = search_web(prompt, max_results=5)

    # 3) 组织最终回答
    if web_results and not topic_strong:
        if local_answer and not should_fallback_to_web(
            best_sim, local_answer, topic_strong=False
        ):
            answer = chat_reply_hybrid(llm, prompt, docs, web_results, history)
            source_mode = "hybrid"
        else:
            answer = chat_reply_web(llm, prompt, web_results, history)
            source_mode = "web"
    elif local_answer:
        answer = local_answer
        source_mode = "local"
    elif docs and best_sim > 0:
        answer = local_answer or REFUSAL_TEMPLATE
        source_mode = "local"
    else:
        answer = REFUSAL_TEMPLATE
        source_mode = "none"

    meta = {
        "best_sim": best_sim,
        "source_mode": source_mode,
        "web_count": len(web_results),
        "topic_strong": topic_strong,
        "term_ratio": topic_info.get("term_ratio", 0),
        "match_terms": topic_info.get("terms", []),
        "match_phrases": topic_info.get("phrase_hits", []),
        "coverage": topic_info.get("coverage", 0),
        "question_mode": answer_mode.id,
        "question_mode_label": answer_mode.label,
    }
    return answer, docs, web_results, meta, rerank_metas


def render_correction_form(doc, form_prefix: str, frag_idx: int) -> None:
    """针对单个资料页提交/更新纠错。"""
    if not ENABLE_CORRECTIONS:
        return
    wid = current_workspace_id()
    skey = chunk_source_key(doc.metadata)
    existing = get_correction(skey, wid)
    raw = doc.metadata.get("raw_content") or chunk_index_text(doc)
    loc = location_label(doc.metadata)

    with st.expander("✏️ 纠错此页课件", expanded=False):
        if doc.metadata.get("corrected"):
            st.caption("当前显示的是**已纠错**版本；可继续修改下方内容。")
        with st.form(f"corr_form_{form_prefix}_{frag_idx}"):
            corrected = st.text_area(
                "正确内容（将替代该页原文参与检索与作答）",
                value=existing["text"] if existing else raw[:2000],
                height=140,
            )
            note = st.text_input(
                "纠错说明（可选）",
                value=(existing or {}).get("note", ""),
                placeholder="例如：课件印刷错误，应为…",
            )
            if st.form_submit_button("保存纠错", use_container_width=True):
                try:
                    save_correction(
                        skey,
                        corrected,
                        source_name=doc.metadata.get("source_name", ""),
                        page_label=loc,
                        original_preview=raw,
                        note=note,
                        author=st.session_state.get("member_name", ""),
                        workspace_id=wid,
                    )
                    st.success("纠错已保存，后续问答将优先采用此内容")
                    st.rerun()
                except CorrectionError as e:
                    st.error(str(e))
        if existing and st.button(
            "撤销此页纠错",
            key=f"del_corr_{form_prefix}_{frag_idx}",
            use_container_width=True,
        ):
            delete_correction(skey, wid)
            st.rerun()


def build_source_previews(
    docs_with_scores: list,
    rerank_metas: list[dict] | None = None,
) -> list[dict]:
    """保存可序列化的课内参考页，刷新对话后仍可查看完整正文。"""
    previews: list[dict] = []
    for i, (doc, score) in enumerate(docs_with_scores):
        meta = rerank_metas[i] if rerank_metas and i < len(rerank_metas) else {}
        previews.append(
            {
                "location": location_label(doc.metadata),
                "text": chunk_index_text(doc),
                "score_pct": meta.get("display_pct", int(round(score * 100))),
                "cite_tier": meta.get("cite_tier", "课件页"),
                "llm_reason": meta.get("llm_reason", ""),
                "corrected": bool(doc.metadata.get("corrected")),
            }
        )
    return previews


def render_sources(
    docs_with_scores: list | None = None,
    rerank_metas: list[dict] | None = None,
    form_key_prefix: str = "src",
    source_previews: list[dict] | None = None,
):
    if source_previews:
        with st.expander(
            f"📎 课内参考资料（{len(source_previews)} 页 · 完整正文）",
            expanded=True,
        ):
            st.caption("以下为当时送入模型的整页课件内容（已保存于对话记录）。")
            for i, sp in enumerate(source_previews, 1):
                st.markdown(
                    f"**{sp['location']}** · 本题相关度 **{sp.get('score_pct', 0)}%** · "
                    f"{sp.get('cite_tier', '课件页')}"
                )
                if sp.get("corrected"):
                    st.caption("✏️ 本页已人工纠错")
                if sp.get("llm_reason"):
                    st.caption(sp["llm_reason"])
                full_text = sp.get("text", "")
                view_h = min(560, max(140, len(full_text) // 2))
                st.text_area(
                    "课件正文",
                    value=full_text,
                    height=view_h,
                    disabled=True,
                    key=f"src_prev_{form_key_prefix}_{i}",
                    label_visibility="collapsed",
                )
                if i < len(source_previews):
                    st.divider()
        return

    docs_with_scores = docs_with_scores or []
    wid = current_workspace_id()
    docs_with_scores = apply_corrections_to_docs(docs_with_scores, wid)

    if not docs_with_scores:
        return

    with st.expander(
        f"📎 课内参考资料（{len(docs_with_scores)} 页 · 完整正文）",
        expanded=True,
    ):
        st.caption(
            "优先使用你上传的讲义/PPT；以下为送入模型的**整页**内容，"
            "相关度由检索 + 语义重排得出。"
        )
        for i, (doc, score) in enumerate(docs_with_scores, 1):
            loc = location_label(doc.metadata)
            meta = (rerank_metas[i - 1] if rerank_metas and i <= len(rerank_metas) else {})
            tier = meta.get("cite_tier", "课件页")
            pct = meta.get("display_pct", int(round(score * 100)))
            st.markdown(f"**{loc}** · 本题相关度 **{pct}%** · {tier}")
            if doc.metadata.get("corrected"):
                st.caption("✏️ 本页已人工纠错，以下以纠错正文为准")
            if meta.get("chunk_hint"):
                st.caption(meta["chunk_hint"])
            elif meta.get("llm_reason"):
                method = "LLM 语义" if meta.get("rerank_method") == "llm" else "检索"
                st.caption(f"{method}：{meta['llm_reason']}")
            full_text = chunk_index_text(doc)
            view_h = min(560, max(140, len(full_text) // 2))
            st.text_area(
                "课件正文",
                value=full_text,
                height=view_h,
                disabled=True,
                key=f"src_body_{form_key_prefix}_{i}",
                label_visibility="collapsed",
            )
            render_correction_form(doc, form_key_prefix, i)
            if i < len(docs_with_scores):
                st.divider()


def _app_base_url() -> str:
    """协作分享用的站点根地址：线上优先用当前访问 URL，避免 Secrets 里旧域名。"""
    try:
        current = getattr(st.context, "url", None) or ""
        if current and not current.startswith(("http://localhost", "http://127.0.0.1")):
            parts = urlparse(current)
            if parts.scheme and parts.netloc:
                return f"{parts.scheme}://{parts.netloc}".rstrip("/")
    except Exception:
        pass
    return PUBLIC_APP_URL


def render_workspace_panel():
    """协作空间：邀请码创建 / 加入，共享会话与资料。"""
    if not ENABLE_WORKSPACE:
        st.info("协作空间未开启（.env ENABLE_WORKSPACE=true）")
        return

    wid = st.session_state.get("workspace_id")

    st.session_state.member_name = st.text_input(
        "你的昵称（可选）",
        value=st.session_state.member_name,
        placeholder="例如：小明",
        key="member_name_input",
    )

    if wid:
        st.success(f"已加入：**{st.session_state.workspace_name or wid}**")
        st.markdown(f"邀请码：`{wid}`")
        base = _app_base_url()
        if base:
            share = f"{base}/?space={wid}"
            st.markdown(f"**分享给队友：** [{share}]({share})")
            st.caption("队友用浏览器打开上方链接即可，无需安装代码。")
        else:
            st.caption("把邀请码发给队友；公网部署后会自动显示完整分享链接。")
            st.caption(f"链接格式：`你的网址/?space={wid}`")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 同步消息", use_container_width=True):
                sync_workspace_messages(force=True)
                st.rerun()
        with c2:
            if st.button("退出空间", use_container_width=True):
                leave_workspace()
                rebuild_index_for_context(st.session_state.doc_index)
                if "space" in st.query_params:
                    del st.query_params["space"]
                st.rerun()
        return

    tab_create, tab_join = st.tabs(["创建空间", "加入空间"])
    with tab_create:
        ws_name = st.text_input("空间名称", placeholder="例如：嵌入式期中复习", key="ws_create_name")
        if st.button("创建并获取邀请码", type="primary", use_container_width=True):
            meta = create_workspace(ws_name or "复习小组")
            enter_workspace(meta["id"], meta.get("name", ""))
            rebuild_index_for_context(st.session_state.doc_index)
            st.query_params["space"] = meta["id"]
            st.rerun()
    with tab_join:
        code = st.text_input("输入邀请码", placeholder="6 位，如 A3K9M2", key="ws_join_code")
        if st.button("加入空间", use_container_width=True):
            try:
                meta = join_workspace(code)
                enter_workspace(meta["id"], meta.get("name", ""))
                rebuild_index_for_context(st.session_state.doc_index)
                st.query_params["space"] = meta["id"]
                st.rerun()
            except WorkspaceError as e:
                st.error(str(e))


def render_left_panel(index: DocumentIndex):
    tab_data, tab_ws, tab_more = st.tabs(["📁 资料库", "👥 协作", "⚙️ 更多"])

    with tab_data:
        _render_data_tab(index)

    with tab_ws:
        render_workspace_panel()

    with tab_more:
        render_references_panel()
        render_corrections_panel()
        if st.button("清空对话", use_container_width=True, key="clear_chat_btn"):
            st.session_state.messages = []
            persist_messages()
            if not st.session_state.get("workspace_id"):
                clear_personal_messages()
            st.rerun()
        st.caption(
            f"联网搜索：{'已开启' if ENABLE_WEB_SEARCH else '已关闭（.env ENABLE_WEB_SEARCH=true）'}"
        )
        with st.expander("✅ 功能一览"):
            st.markdown(
                "- ~~联网补充~~ ✅\n"
                "- ~~协作空间~~ ✅\n"
                "- ~~人工纠错~~ ✅\n"
                "- ~~论文参考文献 / DOI~~ ✅"
            )


def _render_data_tab(index: DocumentIndex):
    data_dir = active_data_dir()
    in_ws = bool(st.session_state.get("workspace_id"))
    busy = is_app_busy()

    if st.session_state.get("index_job_active"):
        _execute_index_job(index, data_dir)
        return

    if st.session_state.get("rebuild_job_active"):
        _execute_rebuild_job(index, data_dir, in_ws)
        return

    if in_ws:
        st.caption("协作空间**共享**资料，队友上传的文件所有人可检索。")
    else:
        st.caption("支持 PDF、PPTX、TXT/MD；可多次上传，自动合并索引。")

    uploaded = st.file_uploader(
        "上传课程资料",
        type=["pdf", "pptx", "ppt", "txt", "md"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="course_file_uploader",
        disabled=busy,
    )

    if st.button(
        "解析并加入索引",
        type="primary",
        use_container_width=True,
        disabled=busy,
    ):
        if not uploaded:
            st.error("请先选择至少一个文件")
        else:
            st.session_state.index_job_files = [
                {"name": f.name, "data": f.getvalue()} for f in uploaded
            ]
            st.session_state.index_job_active = True
            st.rerun()

    rebuild_label = "重建空间资料索引" if in_ws else "从 data/ 目录重建全部索引"
    if st.button(
        rebuild_label,
        use_container_width=True,
        key="rebuild_index_btn",
        disabled=busy,
    ):
        st.session_state.rebuild_job_active = True
        st.rerun()

    st.markdown("**已索引文件**")
    if index.indexed_files:
        for name in index.indexed_files:
            st.markdown(f"- `{name}`")
        if index.retriever:
            st.caption(
                f"共 {index.retriever.stats['file_count']} 个文件 · "
                f"{index.retriever.stats['total_chunks']} 个片段"
            )
            with st.expander("🔍 检索调试（可选）"):
                test_q = st.text_input("试一句检索", placeholder="例如：UART 是什么")
                if st.button("测试检索", use_container_width=True) and test_q.strip():
                    dbg = index.retriever.debug_search(test_q.strip())
                    st.write(
                        f"最高本题相关度：**{dbg.get('best_pct', 0)}%** · "
                        f"概念覆盖：**{dbg.get('coverage', 0)}** · "
                        f"主题匹配：**{'是' if dbg.get('topic_strong') else '否'}**"
                    )
                    if dbg.get("phrase_hits"):
                        st.caption(f"命中短语：{', '.join(dbg['phrase_hits'])}")
                    for h in dbg["hits"]:
                        pen = f" ⚠️{h['penalties']}" if h.get("penalties") else ""
                        st.caption(
                            f"{h['score_pct']}% (raw {h['raw']}) · "
                            f"{h['location']}{pen} · {h['preview']}…"
                        )
    else:
        st.info("尚未上传资料")


def _execute_index_job(index: DocumentIndex, data_dir: Path) -> None:
    files = st.session_state.pop("index_job_files", []) or []
    results: list[dict] = []
    errors: list[str] = []
    try:
        with st.status("正在解析并加入索引…", expanded=True) as status:
            status.write(f"共 **{len(files)}** 个文件，请勿关闭页面或重复点击。")
            data_dir.mkdir(parents=True, exist_ok=True)
            for i, item in enumerate(files, 1):
                name = item["name"]
                status.write(f"({i}/{len(files)}) 正在处理 `{name}` …")
                save_path = data_dir / name
                save_path.write_bytes(item["data"])
                try:
                    results.append(index.add_file(save_path))
                except Exception as e:
                    errors.append(f"{name}: {e}")
            if results:
                total = index.retriever.stats["total_chunks"] if index.retriever else 0
                status.update(
                    label=f"索引完成：{len(results)} 个文件，{total} 个片段",
                    state="complete",
                )
            elif errors:
                status.update(label="索引失败", state="error")
            else:
                status.update(label="未处理任何文件", state="error")
    finally:
        st.session_state.index_job_active = False

    for err in errors:
        st.warning(err)
    if results:
        total = index.retriever.stats["total_chunks"] if index.retriever else 0
        st.success(
            f"已索引 {len(results)} 个文件，共 {total} 个片段（对话记录已保留）"
        )
    st.rerun()


def _execute_rebuild_job(index: DocumentIndex, data_dir: Path, in_ws: bool) -> None:
    label = "重建空间资料索引" if in_ws else "从 data/ 目录重建全部索引"
    try:
        with st.status(f"正在{label}…", expanded=True) as status:
            status.write("正在扫描目录并重建检索索引，请稍候…")
            info = index.rebuild_from_data_dir(data_dir)
            status.update(
                label=f"重建完成：{info['rebuilt_files']} 个文件",
                state="complete",
            )
        st.success(
            f"已重建 {info['rebuilt_files']} 个文件（对话记录已保留）"
        )
    except Exception as e:
        st.error(str(e))
    finally:
        st.session_state.rebuild_job_active = False
    st.rerun()


def render_references_panel():
    if not ENABLE_REFERENCES:
        return

    if st.session_state.get("ref_job_active"):
        _execute_ref_parse_job()
        return

    busy = is_app_busy()

    with st.expander("📚 论文 DOI 工具（可选，与课内问答无关）", expanded=False):
        st.caption(
            "仅用于解析文末 References 里的 DOI 链接。"
            "**日常提问请用右侧对话**，系统会优先检索你上传的讲义/PPT。"
        )
        ref_file = st.file_uploader(
            "参考文献 PDF/TXT",
            type=["pdf", "txt", "md"],
            key="ref_bib_upload",
            label_visibility="collapsed",
            disabled=busy,
        )
        ref_text = st.text_area(
            "或直接粘贴参考文献文本",
            height=120,
            placeholder="References\n[1] Author A. Title. doi:10.xxxx/...",
            key="ref_bib_text",
            disabled=busy,
        )
        fetch_meta = st.checkbox(
            "联网：CrossRef 补全标题 / 无 DOI 时尝试书目检索（需联网）",
            value=REFERENCE_FETCH_META,
            key="ref_fetch_meta",
        )
        hide_table = st.checkbox(
            "隐藏「表格行」（MOF 对比表等，本身不是文献）",
            value=True,
            key="ref_hide_table",
        )

        if st.button(
            "解析参考文献",
            use_container_width=True,
            key="ref_parse_btn",
            disabled=busy,
        ):
            if ref_file is None and not ref_text.strip():
                st.warning("请上传文件或粘贴参考文献文本")
            else:
                job: dict = {"fetch_meta": fetch_meta}
                if ref_file is not None:
                    job["file"] = {"name": ref_file.name, "data": ref_file.getvalue()}
                else:
                    job["text"] = ref_text
                st.session_state.ref_job_payload = job
                st.session_state.ref_job_active = True
                st.rerun()

        rows = st.session_state.get("parsed_references") or []
        if hide_table:
            rows = [r for r in rows if r.get("entry_type") != "table_row"]
        if not rows:
            return

        for i, row in enumerate(rows, 1):
            preview = row.get("preview") or row.get("entry", "")
            title = row.get("title") or ""
            year = row.get("year")
            doi = row.get("doi")
            url = row.get("url", "")
            status = row.get("status") or ""
            entry_type = row.get("entry_type", "")

            head = f"**[{i}]** "
            if title:
                meta = title
                if year:
                    meta += f" ({year})"
                head += meta
            else:
                head += preview[:120] + ("…" if len(preview) > 120 else "")

            if doi and url:
                src = row.get("source", "")
                hint = "检索匹配" if src == "crossref_search" else "DOI"
                head += f" · [{hint}]({url})"
            elif entry_type == "table_row":
                head += " · _表格行（非文献）_"
            else:
                head += " · _无 DOI_"

            st.markdown(head)
            if status:
                st.caption(status)
            if title and preview:
                st.caption(preview[:200] + ("…" if len(preview) > 200 else ""))
            authors = row.get("authors") or []
            if authors:
                st.caption("作者：" + "；".join(authors[:4]))
            score = row.get("crossref_score")
            if score is not None and doi:
                st.caption(f"CrossRef 匹配度：{score:.1f}")
            st.divider()


def _execute_ref_parse_job() -> None:
    job = st.session_state.pop("ref_job_payload", {}) or {}
    fetch_meta = job.get("fetch_meta", REFERENCE_FETCH_META)
    rows: list[dict] = []
    try:
        with st.status("正在解析参考文献…", expanded=True) as status:
            if job.get("file"):
                f = job["file"]
                status.write(f"正在读取 `{f['name']}` …")
                tmp = Path("_ref_upload") / f["name"]
                tmp.parent.mkdir(exist_ok=True)
                tmp.write_bytes(f["data"])
                if fetch_meta:
                    status.write("正在识别 DOI，并联网查询 CrossRef…")
                rows = parse_references_from_file(tmp, fetch_meta=fetch_meta)
            elif job.get("text"):
                status.write("正在解析粘贴的文本…")
                if fetch_meta:
                    status.write("正在识别 DOI，并联网查询 CrossRef…")
                rows = parse_references_from_text(job["text"], fetch_meta=fetch_meta)
            st.session_state.parsed_references = rows
            if rows:
                stats = summarize_parse_results(rows)
                status.update(
                    label=(
                        f"解析完成：{stats['total']} 条，"
                        f"{stats['with_doi']} 条有 DOI"
                    ),
                    state="complete",
                )
            else:
                status.update(label="未解析到条目", state="error")
    except Exception as e:
        st.error(f"解析失败：{e}")
    finally:
        st.session_state.ref_job_active = False

    if rows:
        stats = summarize_parse_results(rows)
        st.success(
            f"共 {stats['total']} 条 · {stats['with_doi']} 条有 DOI · "
            f"{stats['table_rows']} 条疑似表格行 · {stats['citations']} 条像文献"
        )
    st.rerun()


def render_corrections_panel():
    if not ENABLE_CORRECTIONS:
        return
    wid = current_workspace_id()
    items = list_corrections_summary(wid)
    scope = "协作空间" if wid else "个人"
    with st.expander(f"✏️ 纠错记录 · {scope}（{len(items)}）", expanded=False):
        if not items:
            st.caption("在右侧回答的「资料片段」下可提交纠错；保存后全员/后续问答生效。")
            return
        for i, item in enumerate(items):
            st.markdown(f"**{item['source_name']}** · {item['page_label']}")
            if item.get("author"):
                st.caption(f"提交：{item['author']}")
            if item.get("note"):
                st.caption(f"说明：{item['note']}")
            st.text(item["preview"] + ("…" if len(item["preview"]) >= 80 else ""))
            if st.button("删除", key=f"panel_del_corr_{i}_{item['key']}", use_container_width=True):
                delete_correction(item["key"], wid)
                st.rerun()
            st.divider()


def _render_sticky_question(user_msg: dict) -> None:
    author = user_msg.get("author", "")
    author_html = f" · {html.escape(author)}" if author else ""
    q_text = html.escape(user_msg.get("content", "")).replace("\n", "<br/>")
    st.markdown(
        f'<div class="ct-qa-turn"><div class="ct-qa-sticky-q">'
        f'<span class="ct-q-label">问{author_html}</span>'
        f'<span class="ct-q-text">{q_text}</span></div>',
        unsafe_allow_html=True,
    )


def _render_assistant_message(msg: dict, idx: int) -> None:
    meta = msg.get("_meta") or {}
    with st.chat_message("assistant"):
        st.markdown(linkify_dois_in_text(repair_legacy_fragment_citations(msg["content"])))

        mode = meta.get("source_mode")
        if mode == "web":
            st.caption(
                f"📌 上传资料未覆盖（本地相关度 {meta.get('best_sim', 0):.3f}），"
                f"已联网检索 {meta.get('web_count', 0)} 条。"
            )
        elif mode == "hybrid":
            st.caption(
                f"📌 本地 + 网络综合回答（本地相关度 {meta.get('best_sim', 0):.3f}）。"
            )
        elif mode == "local":
            pct = int(round(meta.get("best_sim", 0) * 100))
            prompt_hint = st.session_state.messages[idx - 1]["content"] if idx > 0 else ""
            amode = detect_answer_mode(prompt_hint)
            cap = amode.ui_caption.format(pct=pct)
            if amode.id == "direct" and meta.get("topic_strong"):
                cap += f"，概念覆盖 {meta.get('coverage', 0):.0%}"
            if amode.id == "direct":
                cap += "）"
            st.caption(f"{cap} · 题型：{amode.label}")

        if msg.get("sources"):
            render_sources(
                msg["sources"],
                msg.get("rerank_metas"),
                form_key_prefix=f"msg{idx}",
            )
        elif msg.get("source_previews"):
            render_sources(
                source_previews=msg["source_previews"],
                form_key_prefix=f"msg{idx}",
            )
        if msg.get("web_sources"):
            render_web_sources(msg["web_sources"])
    st.markdown("</div>", unsafe_allow_html=True)


def render_chat_messages(index: DocumentIndex) -> None:
    sync_workspace_messages()

    web_hint = "资料不足自动联网" if ENABLE_WEB_SEARCH else "未开启联网"
    st.markdown(
        f"""
        <div class="ct-chat-header">
          <p class="ct-chat-title">💬 对话</p>
          <p class="ct-chat-sub">TF-IDF + DeepSeek · {html.escape(web_hint)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    msgs = st.session_state.messages
    i = 0
    while i < len(msgs):
        msg = msgs[i]
        if msg["role"] == "user":
            _render_sticky_question(msg)
            if i + 1 < len(msgs) and msgs[i + 1]["role"] == "assistant":
                _render_assistant_message(msgs[i + 1], i + 1)
                i += 2
            else:
                st.markdown("</div>", unsafe_allow_html=True)
                i += 1
        elif msg["role"] == "assistant":
            st.markdown('<div class="ct-qa-turn">', unsafe_allow_html=True)
            _render_assistant_message(msg, i)
            i += 1
        else:
            i += 1

    if not msgs:
        if index.ready:
            hint = "在下方输入问题开始对话。滚动长回答时，题目会悬浮在顶部方便对照。"
        elif ENABLE_WEB_SEARCH:
            hint = "尚未索引本地资料，可直接提问（将尝试联网回答）。"
        else:
            hint = "请先在左侧「资料库」上传讲义/PPT 并点击「解析并加入索引」。"
        st.markdown(f'<div class="ct-empty-hint">{html.escape(hint)}</div>', unsafe_allow_html=True)

    if st.session_state.get("qa_job_active"):
        st.markdown(
            '<div class="ct-thinking">⏳ <strong>正在思考中…</strong> '
            "检索课内资料并组织回答，请勿重复发送。</div>",
            unsafe_allow_html=True,
        )


def _execute_qa_job(index: DocumentIndex, llm) -> None:
    """异步两阶段：先展示「思考中」，再执行检索与作答。"""
    messages = st.session_state.messages
    if not messages or messages[-1].get("role") != "user":
        st.session_state.qa_job_active = False
        st.rerun()
        return

    prompt = messages[-1]["content"]
    history = messages[:-1]

    try:
        with st.status("🧠 正在思考中…", expanded=True) as status:
            status.write("📂 正在检索课内资料…")
            answer, docs, web_results, meta, rerank_metas = run_qa(
                index, llm, prompt, history
            )
            mode = meta.get("source_mode", "none")
            if mode == "web":
                status.write("🌐 课内资料不足，正在联网检索…")
            elif mode == "hybrid":
                status.write("🔗 正在综合课内资料与网络来源…")
            else:
                status.write("✍️ 正在根据课件组织回答…")
            status.update(label="回答完成", state="complete")

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "sources": docs if docs else [],
                "source_previews": build_source_previews(docs, rerank_metas) if docs else [],
                "web_sources": web_results,
                "rerank_metas": rerank_metas,
                "_meta": meta,
            }
        )
        persist_messages()
    except APIStatusError as e:
        if e.status_code == 402:
            st.error("API 余额不足（402）。请充值或更换 API Key。")
        else:
            st.error(f"API 调用失败：{e}")
    except Exception as e:
        st.error(f"处理失败：{e}")
    finally:
        st.session_state.qa_job_active = False

    st.rerun()


def process_chat_input(index: DocumentIndex, llm) -> None:
    if st.session_state.get("qa_job_active"):
        _execute_qa_job(index, llm)
        return

    busy = is_app_busy()
    can_chat = (index.ready or ENABLE_WEB_SEARCH) and not busy
    if busy:
        placeholder = "资料正在处理中，请稍候再提问…"
    elif index.ready or ENABLE_WEB_SEARCH:
        placeholder = "输入问题，Enter 发送（多轮对话）"
    else:
        placeholder = "请先在左侧「资料库」上传并索引资料…"
    prompt = st.chat_input(placeholder, disabled=not can_chat)
    if not prompt:
        return

    user_msg: dict = {"role": "user", "content": prompt}
    if st.session_state.get("member_name"):
        user_msg["author"] = st.session_state.member_name.strip()
    st.session_state.messages.append(user_msg)
    persist_messages()
    st.session_state.qa_job_active = True
    st.rerun()


def _scroll_panel():
    """固定高度可滚动面板（Streamlit ≥1.33 支持 height 参数）。"""
    try:
        return st.container(height=UI_PANEL_HEIGHT, border=False)
    except TypeError:
        return st.container()


def main():
    st.set_page_config(
        page_title="课内有据",
        page_icon="📖",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_layout_css()
    init_session()
    try_join_from_url()
    ensure_messages_loaded()
    index: DocumentIndex = st.session_state.doc_index
    try_auto_load_index(index)

    if not os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY") == "你的密钥":
        st.error("请复制 `.env.example` 为 `.env` 并填写 `OPENAI_API_KEY`")
        st.stop()

    render_busy_banner()

    llm = get_llm()

    left, right = st.columns([22, 78], gap="small")
    with left:
        with _scroll_panel():
            render_left_panel(index)
    with right:
        with _scroll_panel():
            render_chat_messages(index)

    process_chat_input(index, llm)
    render_ui_scripts()


if __name__ == "__main__":
    main()
