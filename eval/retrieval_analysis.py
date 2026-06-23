"""
eval/retrieval_analysis.py
分析检索质量：召回率、准确率、排序效果。

输出：
    eval/figures/recall_at_k.png       — Recall@K 曲线
    eval/figures/precision_at_k.png    — Precision@K 曲线
    eval/figures/rerank_improvement.png — 重排前后对比
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def analyze_retrieval_quality():
    """
    分析检索质量指标。
    需要修改 retrieval 逻辑记录重排前后的排序。
    """
    from eval.run_eval import load_questions, build_index
    from src.chat import get_llm
    from src.retriever import semantic_search, tfidf_search
    import src.config as cfg

    questions = load_questions()
    index = build_index()

    recall_at_k = {k: [] for k in [1, 3, 5, 10]}
    precision_at_k = {k: [] for k in [1, 3, 5, 10]}
    rerank_changes = []

    for i, q in enumerate(questions):
        question = q["question"]
        source_pages = set(q.get("source_pages", []))

        print(f"[{i+1}/{len(questions)}] {question[:50]}...")

        # 初始检索（记录前 10 个结果）
        if cfg.RETRIEVER_TYPE == "semantic":
            results = semantic_search(index, question, top_k=10)
        else:
            results = tfidf_search(index, question, top_k=10)

        retrieved_pages = [r.get("page", -1) for r in results]

        # 计算 Recall@K 和 Precision@K
        for k in [1, 3, 5, 10]:
            top_k_pages = set(retrieved_pages[:k])
            hits = len(top_k_pages & source_pages)

            recall = hits / len(source_pages) if source_pages else 0
            precision = hits / k if k > 0 else 0

            recall_at_k[k].append(recall)
            precision_at_k[k].append(precision)

        # 重排效果分析（需要记录重排前后的顺序）
        # 这里简化为：检查第一个相关文档的排名变化
        if source_pages:
            before_rank = next((i for i, p in enumerate(retrieved_pages) if p in source_pages), -1)
            # 假设重排后相关文档排名提升（这里需要实际实现重排逻辑）
            # after_rank = ...
            # rerank_changes.append((before_rank, after_rank))

    # 计算平均值
    avg_recall = {k: sum(vals) / len(vals) for k, vals in recall_at_k.items()}
    avg_precision = {k: sum(vals) / len(vals) for k, vals in precision_at_k.items()}

    return avg_recall, avg_precision, rerank_changes


def plot_recall_precision():
    """绘制 Recall@K 和 Precision@K 曲线"""
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12

    # 模拟数据（实际运行时替换为真实数据）
    k_values = [1, 3, 5, 10]
    recall = [0.25, 0.52, 0.68, 0.85]
    precision = [0.90, 0.75, 0.62, 0.48]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Recall@K
    ax1.plot(k_values, recall, 'o-', color='#3b82f6', linewidth=2.5, markersize=8)
    ax1.set_xlabel('K（检索片段数）', fontsize=13, fontweight='bold')
    ax1.set_ylabel('Recall@K', fontsize=13, fontweight='bold')
    ax1.set_title('召回率曲线', fontsize=15, fontweight='bold', pad=12)
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.set_xticks(k_values)

    for x, y in zip(k_values, recall):
        ax1.text(x, y + 0.02, f'{y:.2f}', ha='center', fontsize=11, fontweight='bold')

    # Precision@K
    ax2.plot(k_values, precision, 's-', color='#10b981', linewidth=2.5, markersize=8)
    ax2.set_xlabel('K（检索片段数）', fontsize=13, fontweight='bold')
    ax2.set_ylabel('Precision@K', fontsize=13, fontweight='bold')
    ax2.set_title('准确率曲线', fontsize=15, fontweight='bold', pad=12)
    ax2.grid(True, linestyle='--', alpha=0.3)
    ax2.set_xticks(k_values)

    for x, y in zip(k_values, precision):
        ax2.text(x, y + 0.02, f'{y:.2f}', ha='center', fontsize=11, fontweight='bold')

    fig.tight_layout()
    out = ROOT / "eval" / "figures" / "recall_precision.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"已保存：{out}")


def plot_rerank_effect():
    """绘制重排效果对比"""
    import matplotlib.pyplot as plt
    import matplotlib
    import numpy as np

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12

    # 模拟数据：重排前后第一个相关文档的排名分布
    positions_before = [3, 5, 7, 2, 9, 4, 6, 8, 1, 10]
    positions_after = [1, 1, 2, 1, 3, 1, 2, 4, 1, 5]

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(positions_before))
    width = 0.35

    bars1 = ax.bar(x - width/2, positions_before, width, label='重排前', color='#94a3b8')
    bars2 = ax.bar(x + width/2, positions_after, width, label='重排后', color='#3b82f6')

    ax.set_ylabel('相关文档排名', fontsize=13, fontweight='bold')
    ax.set_xlabel('问题编号', fontsize=13, fontweight='bold')
    ax.set_title('LLM 重排对检索排序的改善', fontsize=15, fontweight='bold', pad=12)
    ax.set_xticks(x)
    ax.set_xticklabels([f'Q{i+1}' for i in x])
    ax.legend(fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)
    ax.invert_yaxis()  # 排名越小越好

    fig.tight_layout()
    out = ROOT / "eval" / "figures" / "rerank_improvement.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"已保存：{out}")


if __name__ == "__main__":
    print("生成检索质量分析图表...")
    plot_recall_precision()
    plot_rerank_effect()
    print("\n图表生成完成！")
    print("注意：当前使用模拟数据，需要修改 retrieval 逻辑记录实际检索排序。")
