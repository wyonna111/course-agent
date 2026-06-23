"""
eval/run_eval.py
对 eval/questions.json 中的题目跑系统，自动打分，输出结果到 eval/results.json。

用法：
    # 完整版（全部优化开启）
    python eval/run_eval.py --label full

    # 消融：关闭 LLM 重排
    ENABLE_LLM_RERANK=false python eval/run_eval.py --label no_rerank

    # 消融：关闭 Self-RAG
    ENABLE_SELF_RAG=false python eval/run_eval.py --label no_selfrag

    # 消融：TF-IDF 检索
    RETRIEVER_TYPE=tfidf python eval/run_eval.py --label tfidf

    # 基线：最简 RAG
    RETRIEVER_TYPE=tfidf ENABLE_LLM_RERANK=false ENABLE_SELF_RAG=false ENABLE_WEB_SEARCH=false python eval/run_eval.py --label baseline

结果追加写入 eval/results.json，每个 label 一条记录。
"""

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*wrong pointing object.*")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# 评测脚本本身只需要加载文档，若未设置 RETRIEVER_TYPE 则默认 tfidf
# （各消融组合的 RETRIEVER_TYPE 由命令行环境变量控制，不在这里覆盖）
if "RETRIEVER_TYPE" not in os.environ:
    os.environ["RETRIEVER_TYPE"] = "tfidf"

QUESTIONS_PATH = ROOT / "eval" / "questions.json"
RESULTS_PATH = ROOT / "eval" / "results.json"
DATA_DIR = ROOT / "data"

# ── 打分权重 ────────────────────────────────────────────────────
W_KEYWORD = 0.6   # 关键词命中率
W_CITATION = 0.2  # 引用页码正确
W_REFUSE = 0.2    # 未拒答（应该能答的题没说"未找到"）


def load_questions() -> list[dict]:
    if not QUESTIONS_PATH.exists():
        raise FileNotFoundError(f"题目文件不存在：{QUESTIONS_PATH}\n请先运行 gen_questions.py")
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_index():
    from src.indexer import DocumentIndex
    index = DocumentIndex()
    for path in sorted(DATA_DIR.iterdir()):
        if path.suffix.lower() in {".pdf", ".pptx", ".ppt", ".txt", ".md"}:
            index.add_file(path)
    return index


def score_one(question: dict, answer: str, docs: list, elapsed: float) -> dict:
    """对单道题打分，返回详细得分字典。"""
    keywords = [str(k).strip() for k in question.get("keywords", [])]
    sources = question.get("sources", [])  # v2: 支持多页来源
    if not sources:
        sources = [question.get("source", "")]  # 兼容旧版单页
    answer_lower = answer.lower()

    # 1. 关键词命中率
    if keywords:
        hits = sum(1 for kw in keywords if kw in answer)
        keyword_score = hits / len(keywords)
    else:
        keyword_score = 0.5

    # 2. 否定词惩罚（命中了关键词但答案否定）
    negation_words = ["不是", "不需要", "不用", "错误", "无需", "不应", "不能", "不会"]
    has_negation = any(neg in answer for neg in negation_words)
    if has_negation and keyword_score > 0.5:
        keyword_score *= 0.7

    # 3. 引用页码正确率（v2：支持多页，命中任意一页即满分）
    citation_score = 0.0
    if sources and docs:
        import re
        # 从所有 sources 提取页码关键词
        all_page_hints = []
        for src in sources:
            all_page_hints.extend(re.findall(r'第\d+页|幻灯片\s*\d+|第\d+张', src))

        if all_page_hints:
            # 检索到的片段的页码标签
            cited_pages = " ".join(d.page_content.split("\n")[0] for d, _ in docs if hasattr(d, 'page_content'))
            # 只要命中任意一个预期页码就满分
            page_hits = sum(1 for ph in all_page_hints if ph in cited_pages)
            citation_score = 1.0 if page_hits > 0 else 0.0
        else:
            citation_score = 0.5
    elif not docs:
        citation_score = 0.0
    else:
        citation_score = 0.5

    # 4. 拒答检测
    refuse_markers = ["未找到", "未提及", "无法回答", "资料中没有", "上传的资料", "没有相关"]
    refused = any(m in answer for m in refuse_markers)
    refuse_score = 0.0 if refused else 1.0

    # 综合得分
    total = (
        W_KEYWORD * keyword_score +
        W_CITATION * citation_score +
        W_REFUSE * refuse_score
    )

    return {
        "keyword_score": round(keyword_score, 3),
        "citation_score": round(citation_score, 3),
        "refuse_score": refuse_score,
        "total_score": round(total, 3),
        "refused": refused,
        "elapsed_ms": round(elapsed * 1000),
    }


def run_qa_simple(index, llm, question: str, history: list) -> tuple[str, list, float]:
    """调用系统 run_qa，返回 (answer, docs, elapsed_seconds)。"""
    # 动态 import，确保读取当前环境变量里的开关
    import importlib
    import src.config as cfg
    importlib.reload(cfg)

    from app import run_qa
    t0 = time.time()
    try:
        answer, docs, web_results, meta, rerank_metas = run_qa(index, llm, question, history)
    except Exception as e:
        answer = f"[ERROR] {e}"
        docs = []
    elapsed = time.time() - t0
    return answer, docs, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="本次实验标签，如 full / no_rerank / baseline")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题（调试用，0=全部）")
    args = parser.parse_args()

    questions = load_questions()
    if args.limit > 0:
        questions = questions[:args.limit]

    print(f"加载 {len(questions)} 道题目，标签：{args.label}")
    print("构建索引...")
    index = build_index()

    from src.chat import get_llm
    llm = get_llm()

    scores = []
    history = []  # 每道题独立，不传历史

    for i, q in enumerate(questions):
        question_text = q["question"]
        print(f"[{i+1:3d}/{len(questions)}] {question_text[:50]}...", end=" ")

        answer, docs, elapsed = run_qa_simple(index, llm, question_text, history)
        sc = score_one(q, answer, docs, elapsed)

        scores.append({
            "id": i + 1,
            "question": question_text,
            "answer": answer[:300],  # 截断节省空间
            "expected_keywords": q.get("keywords", []),
            "source": q.get("source", ""),
            "auto": q.get("auto", False),
            **sc,
        })

        status = "✓" if sc["total_score"] >= 0.6 else "✗"
        print(f"{status} {sc['total_score']:.2f} ({sc['elapsed_ms']}ms)")

    # 汇总统计
    n = len(scores)
    avg_total = sum(s["total_score"] for s in scores) / n
    avg_keyword = sum(s["keyword_score"] for s in scores) / n
    avg_citation = sum(s["citation_score"] for s in scores) / n
    avg_elapsed = sum(s["elapsed_ms"] for s in scores) / n
    refuse_rate = sum(1 for s in scores if s["refused"]) / n
    pass_rate = sum(1 for s in scores if s["total_score"] >= 0.6) / n

    summary = {
        "label": args.label,
        "n": n,
        "avg_score": round(avg_total, 4),
        "avg_keyword": round(avg_keyword, 4),
        "avg_citation": round(avg_citation, 4),
        "avg_elapsed_ms": round(avg_elapsed),
        "refuse_rate": round(refuse_rate, 4),
        "pass_rate": round(pass_rate, 4),
        # 当前环境变量快照（记录实验配置）
        "config": {
            "RETRIEVER_TYPE": os.getenv("RETRIEVER_TYPE", "tfidf"),
            "ENABLE_LLM_RERANK": os.getenv("ENABLE_LLM_RERANK", "true"),
            "ENABLE_SELF_RAG": os.getenv("ENABLE_SELF_RAG", "true"),
            "REASONING_MODEL_NAME": os.getenv("REASONING_MODEL_NAME", ""),
            "USE_LLM_REWRITE_QUERY": os.getenv("USE_LLM_REWRITE_QUERY", "true"),
            "ENABLE_WEB_SEARCH": os.getenv("ENABLE_WEB_SEARCH", "true"),
        },
        "details": scores,
    }

    # 读取已有结果，追加本次
    existing = []
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, encoding="utf-8") as f:
            existing = json.load(f)
    # 同标签覆盖
    existing = [r for r in existing if r["label"] != args.label]
    existing.append(summary)

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"标签：{args.label}")
    print(f"题目数：{n}")
    print(f"综合得分：{avg_total:.4f}  通过率（≥0.6）：{pass_rate:.1%}")
    print(f"关键词命中：{avg_keyword:.4f}  引用正确：{avg_citation:.4f}")
    print(f"平均响应时间：{avg_elapsed:.0f}ms  拒答率：{refuse_rate:.1%}")
    print(f"结果已写入 {RESULTS_PATH}")


if __name__ == "__main__":
    main()
