"""
语义向量检索（替代 TF-IDF）

使用 BAAI/bge-small-zh-v1.5 对文档和问句编码，
余弦相似度打分，接口与 TfidfRetriever 完全兼容。

首次使用时会自动下载模型（约 90MB），之后缓存在本地。
"""

from __future__ import annotations

import numpy as np
from langchain_core.documents import Document

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
)
from src.rerank import rerank_chunks
from src.retriever import chunk_index_text


def _load_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError(
            "请安装 sentence-transformers：pip install sentence-transformers"
        ) from e

    # 使用清华 HuggingFace 镜像（国内高速访问）
    import os
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    return SentenceTransformer("BAAI/bge-small-zh-v1.5")


def _cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a: (dim,)  b: (n, dim)  → (n,)"""
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return (b_norm @ a_norm).astype(float)


class EmbeddingRetriever:
    """
    向量语义检索；接口与 TfidfRetriever 完全兼容，
    可通过 RETRIEVER_TYPE=embedding 无缝切换。
    """

    # bge 系列建议在查询前加前缀以提升检索效果
    QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

    def __init__(self, chunks: list[Document]):
        if not chunks:
            raise ValueError("文档为空，无法建立索引")
        self.chunks = chunks
        self._model = _load_model()

        texts = [chunk_index_text(c) for c in chunks]
        # 批量编码，normalize=True 方便直接点积算余弦
        self._embeddings: np.ndarray = self._model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
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

    def _scores(self, query: str) -> np.ndarray:
        q_vec = self._model.encode(
            [self.QUERY_PREFIX + query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        # embeddings 已 normalize，直接点积 = 余弦相似度
        return self._embeddings @ q_vec

    def similarity_search_with_score(
        self, query: str, k: int = TOP_K
    ) -> tuple[list[tuple[Document, float]], float]:
        sims = self._scores(query)
        best_sim = float(sims.max()) if len(sims) > 0 else 0.0
        ranked = np.argsort(sims)[::-1][:RETRIEVE_POOL].tolist()

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

        if not results and best_sim > 0:
            top_i = int(np.argmax(sims))
            results.append((self.chunks[top_i], float(sims[top_i])))

        return results, best_sim

    def similarity_search_multi(
        self, question: str, k: int = TOP_K, llm=None
    ) -> tuple[list[tuple[Document, float]], float, list[dict]]:
        """多路召回 → 重排 → 合并；接口与 TfidfRetriever.similarity_search_multi 相同。"""
        # 页码旁路（不变）
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
                meta = page_lookup_meta(lookup["page"], True, lookup.get("file_hint"))
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

        # 多路召回
        queries = build_retrieval_queries(question)
        merged_dict: dict[int, tuple[Document, float]] = {}
        for q in queries:
            batch, _ = self.similarity_search_with_score(q, k=TOP_K_RETRIEVE)
            for doc, score in batch:
                doc_id = id(doc)
                if doc_id not in merged_dict or score > merged_dict[doc_id][1]:
                    merged_dict[doc_id] = (doc, score)

        candidates = sorted(merged_dict.values(), key=lambda x: x[1], reverse=True)[
            :RETRIEVE_POOL
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

    def local_topic_match(self, question: str, docs: list[tuple[Document, float]]) -> dict:
        """与 TfidfRetriever 接口相同。"""
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

        # 语义向量得分普遍比 TF-IDF 高，strong 阈值略微调高
        strong = cov["strong"] or (
            best_sim >= 0.55 and cov["term_hits"] >= 1
        ) or (
            best_sim >= 0.45 and len(cov["phrase_hits"]) >= 1
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
        return best_sim >= 0.40  # 向量相似度阈值略高于 TF-IDF

    def debug_search(self, query: str, k: int = 4) -> dict:
        results, best, metas = self.similarity_search_multi(query, k=k)
        match = self.local_topic_match(query, results)
        hits = []
        for (doc, score), meta in zip(results, metas):
            hits.append(
                {
                    "score_pct": meta["display_pct"],
                    "location": doc.metadata.get("source_name"),
                    "preview": chunk_index_text(doc)[:120],
                }
            )
        return {
            "best_pct": int(round(best * 100)) if results else 0,
            "hits": hits,
            "topic_strong": match["strong"],
            "coverage": match.get("coverage", 0),
            "phrase_hits": match.get("phrase_hits", []),
        }
