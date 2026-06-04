"""本地 TF-IDF 检索（中文优化：字符 n-gram + 关键词兜底）"""

import re

from langchain_core.documents import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import (
    MAX_CHUNKS_PER_PAGE,
    MIN_RELEVANCE,
    RETRIEVE_POOL,
    TOP_K,
    TOP_K_RETRIEVE,
)
from src.page_lookup import (
    find_chunks_by_page,
    merge_docs_by_page,
    merge_page_chunks,
    page_key,
    page_lookup_meta,
    parse_page_lookup,
)
from src.query_utils import (
    assess_topic_coverage,
    build_retrieval_queries,
    extract_key_terms,
)
from src.rerank import rerank_chunks


def chunk_index_text(doc: Document) -> str:
    """用于检索的正文（不含 [本地:...] 位置标签）。"""
    raw = doc.metadata.get("raw_content")
    if raw:
        return raw
    text = doc.page_content or ""
    if text.startswith("[本地:"):
        parts = text.split("\n", 1)
        return parts[1].strip() if len(parts) > 1 else text
    return text.strip()


def _query_ngrams(query: str, min_n: int = 2, max_n: int = 4) -> set[str]:
    """从问句中提取中文/英文检索片段。"""
    query = re.sub(r"\s+", "", query.strip())
    grams: set[str] = set()
    if not query:
        return grams
    for n in range(min_n, max_n + 1):
        for i in range(len(query) - n + 1):
            g = query[i : i + n]
            if re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9]+", g):
                grams.add(g)
    if len(query) >= 2:
        grams.add(query[: min(8, len(query))])
    return grams


def keyword_overlap_score(query: str, text: str) -> float:
    """子串命中 + 技术关键词加权。"""
    grams = _query_ngrams(query)
    base = 0.0
    if grams:
        hits = sum(1 for g in grams if g in text)
        base = min(hits / max(len(grams), 1), 1.0) * 0.35
    terms = extract_key_terms(query)
    text_l = text.lower()
    term_bonus = 0.0
    for t in terms:
        if len(t) >= 2 and (t.lower() in text_l or t in text):
            term_bonus += 0.12 if len(t) >= 4 else 0.08
    return min(base + term_bonus, 0.55)


class TfidfRetriever:
    """本地检索；中文使用 char n-gram，避免默认分词导致相关度恒为 0。"""

    def __init__(self, chunks: list[Document]):
        if not chunks:
            raise ValueError("文档为空，无法建立索引")
        self.chunks = chunks
        texts = [chunk_index_text(c) for c in chunks]
        empty = sum(1 for t in texts if len(t) < 10)
        if empty == len(texts):
            raise ValueError("所有片段几乎为空，请检查 PDF/PPT 是否为扫描版或图片页")

        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            max_features=50000,
            sublinear_tf=True,
        )
        self.matrix = self.vectorizer.fit_transform(texts)
        self.stats = self._build_stats(chunks)

    @staticmethod
    def _build_stats(chunks: list[Document]) -> dict:
        files = sorted({c.metadata.get("source_name", "?") for c in chunks})
        sample = chunk_index_text(chunks[0])[:120] if chunks else ""
        return {
            "total_chunks": len(chunks),
            "files": files,
            "file_count": len(files),
            "sample_preview": sample,
        }

    def _page_key(self, doc: Document) -> str:
        name = doc.metadata.get("source_name", "")
        page = doc.metadata.get("page")
        return f"{name}::{page}"

    def _combined_scores(self, query: str) -> list[float]:
        q_vec = self.vectorizer.transform([query])
        tfidf = cosine_similarity(q_vec, self.matrix).flatten()
        combined = []
        for i, doc in enumerate(self.chunks):
            text = chunk_index_text(doc)
            kw = keyword_overlap_score(query, text)
            combined.append(float(tfidf[i]) + kw)
        return combined

    def similarity_search_with_score(
        self, query: str, k: int = TOP_K
    ) -> tuple[list[tuple[Document, float]], float]:
        sims = self._combined_scores(query)
        best_sim = float(max(sims)) if sims else 0.0
        ranked = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:RETRIEVE_POOL]

        results: list[tuple[Document, float]] = []
        page_hits: dict[str, int] = {}

        for i in ranked:
            if sims[i] <= 0:
                continue
            doc = self.chunks[i]
            pk = self._page_key(doc)
            if page_hits.get(pk, 0) >= MAX_CHUNKS_PER_PAGE:
                continue
            page_hits[pk] = page_hits.get(pk, 0) + 1
            results.append((doc, float(sims[i])))
            if len(results) >= k:
                break

        if len(results) < k:
            for i in ranked:
                if any(self.chunks[i] is r[0] for r in results):
                    continue
                if sims[i] <= 0:
                    continue
                results.append((self.chunks[i], float(sims[i])))
                if len(results) >= k:
                    break

        # 仍无命中时返回得分最高的若干条，交给大模型判断「资料是否提及」
        if not results and best_sim > 0:
            top_i = max(range(len(sims)), key=lambda i: sims[i])
            results.append((self.chunks[top_i], float(sims[top_i])))

        return results, best_sim

    def similarity_search_multi(
        self, question: str, k: int = TOP_K, llm=None
    ) -> tuple[list[tuple[Document, float]], float, list[dict]]:
        """
        多路召回 → 按本题意图重排 → 过滤跑题片段。
        若问句指定页码，优先按页码直查。
        """
        lookup = parse_page_lookup(question)
        if lookup:
            page_docs = find_chunks_by_page(
                self.chunks,
                lookup["page"],
                file_hint=lookup.get("file_hint"),
                is_slide=lookup.get("is_slide", False),
                indexed_files=self.stats.get("files", []),
            )
            if page_docs:
                merged = merge_page_chunks(page_docs)
                meta = page_lookup_meta(
                    lookup["page"], True, lookup.get("file_hint")
                )
                if merged.metadata.get("page_parts_merged", 1) > 1:
                    meta["llm_reason"] += (
                        f"（已合并 {merged.metadata['page_parts_merged']} 个切片为整页）"
                    )
                return [(merged, 0.95)], 0.95, [meta]
            meta = page_lookup_meta(lookup["page"], False, lookup.get("file_hint"))
            meta["llm_reason"] = (
                f"索引中未找到第 {lookup['page']} 页"
                "（请重新索引资料；PDF 页码若与课件不一致可试「幻灯片 N」）"
            )
            return [], 0.0, [meta]

        queries = build_retrieval_queries(question)
        merged: dict[int, tuple[Document, float]] = {}
        for q in queries:
            batch, _ = self.similarity_search_with_score(q, k=TOP_K_RETRIEVE)
            for doc, score in batch:
                doc_id = id(doc)
                if doc_id not in merged or score > merged[doc_id][1]:
                    merged[doc_id] = (doc, score)

        candidates = sorted(merged.values(), key=lambda x: x[1], reverse=True)[
            : RETRIEVE_POOL
        ]
        reranked = rerank_chunks(
            question, candidates, k=k, get_text=chunk_index_text, llm=llm
        )

        reranked_list = list(reranked)
        results = [(doc, display_score) for doc, display_score, _ in reranked_list]
        results = merge_docs_by_page(results)

        metas: list[dict] = []
        for mdoc, mscore in results:
            pk = page_key(mdoc)
            group = [
                (score, meta)
                for doc, score, meta in reranked_list
                if page_key(doc) == pk
            ]
            if group:
                _, best_meta = max(group, key=lambda x: x[0])
                meta = dict(best_meta)
            else:
                meta = {
                    "display_pct": int(round(mscore * 100)),
                    "cite_tier": "课件页",
                    "llm_reason": "",
                    "rerank_method": "heuristic",
                }
            meta["display_score"] = mscore
            meta["display_pct"] = int(round(mscore * 100))
            meta.setdefault("cite_tier", "课件页")
            parts = mdoc.metadata.get("page_parts_merged")
            if parts and parts > 1:
                hint = f"本页 {parts} 段已合并为整页"
                meta["llm_reason"] = (
                    f"{meta.get('llm_reason', '')} · {hint}".strip(" ·")
                )
            metas.append(meta)

        best_sim = results[0][1] if results else 0.0
        return results, best_sim, metas

    def similarity_search_multi_legacy(
        self, question: str, k: int = TOP_K
    ) -> tuple[list[tuple[Document, float]], float]:
        """兼容旧接口。"""
        docs, best, _ = self.similarity_search_multi(question, k=k)
        return docs, best

    def local_topic_match(self, question: str, docs: list[tuple[Document, float]]) -> dict:
        """判断检索片段是否覆盖问题核心概念（防止 PPT 有相关内容却误判联网）。"""
        if not docs:
            return {
                "strong": False,
                "term_ratio": 0.0,
                "best_sim": 0.0,
                "coverage": 0.0,
                "term_hits": 0,
                "phrase_hits": [],
                "terms": [],
            }
        corpus = "\n".join(chunk_index_text(d) for d, _ in docs)
        cov = assess_topic_coverage(question, corpus)
        best_sim = max(s for _, s in docs)

        # 检索分 + 概念覆盖 联合判定
        strong = cov["strong"] or (
            best_sim >= 0.10 and cov["term_hits"] >= 2
        ) or (
            best_sim >= 0.06 and len(cov["phrase_hits"]) >= 1
        )

        return {
            "strong": strong,
            "term_ratio": cov["term_ratio"],
            "best_sim": round(best_sim, 3),
            "coverage": cov["coverage"],
            "term_hits": cov["term_hits"],
            "phrase_hits": cov["phrase_hits"],
            "terms": cov["terms"],
        }

    def is_relevant(self, best_sim: float) -> bool:
        return best_sim >= MIN_RELEVANCE

    def debug_search(self, query: str, k: int = 4) -> dict:
        results, best, metas = self.similarity_search_multi(query, k=k)
        match = self.local_topic_match(query, results)
        hits = []
        for (doc, score), meta in zip(results, metas):
            hits.append(
                {
                    "score_pct": meta["display_pct"],
                    "raw": meta["raw_score"],
                    "location": doc.metadata.get("source_name"),
                    "preview": chunk_index_text(doc)[:120],
                    "boosts": meta.get("boosts", []),
                    "penalties": meta.get("penalties", []),
                    "filtered": meta.get("keep", True),
                }
            )
        return {
            "best_pct": int(round(best * 100)) if results else 0,
            "hits": hits,
            "topic_strong": match["strong"],
            "coverage": match.get("coverage", 0),
            "phrase_hits": match.get("phrase_hits", []),
        }
