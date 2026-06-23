"""
eval/question_type_analysis.py
按问题类型分析系统性能差异。

问题分类：
- 事实性问题（定义、概念）
- 计算题（地址转换、补码、浮点数）
- 推理题（需要多步推理）
- 比较题（比较多个概念）

输出：
    eval/figures/performance_by_type.png — 各类型性能对比
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 问题类型关键词
TYPE_PATTERNS = {
    "计算题": [
        "计算", "地址", "转换", "补码", "反码", "浮点", "十进制", "二进制", "十六进制",
        "偏移量", "物理地址", "逻辑地址"
    ],
    "比较题": [
        "区别", "不同", "差异", "比较", "对比", "相同", "异同", "vs", "和"
    ],
    "推理题": [
        "为什么", "原因", "如何", "怎样", "过程", "步骤", "解释", "原理"
    ],
    "事实题": []  # 默认类别
}


def classify_question(question_text: str) -> str:
    """根据关键词分类问题类型"""
    for qtype, keywords in TYPE_PATTERNS.items():
        if qtype == "事实题":
            continue
        for kw in keywords:
            if kw in question_text:
                return qtype
    return "事实题"


def analyze_by_type():
    """按问题类型分析性能"""
    from eval.run_eval import load_questions, build_index, run_qa_simple, score_one
    from src.chat import get_llm
    from collections import defaultdict

    questions = load_questions()
    index = build_index()
    llm = get_llm()

    # 按类型分组
    results_by_type = defaultdict(list)

    for i, q in enumerate(questions):
        question_text = q["question"]
        qtype = classify_question(question_text)

        print(f"[{i+1}/{len(questions)}] [{qtype}] {question_text[:40]}...")

        answer, docs, elapsed = run_qa_simple(index, llm, question_text, [])
        sc = score_one(q, answer, docs, elapsed)

        results_by_type[qtype].append(sc)

    # 统计每个类型的平均指标
    summary = {}
    for qtype, scores in results_by_type.items():
        n = len(scores)
        summary[qtype] = {
            "count": n,
            "avg_score": round(sum(s["total_score"] for s in scores) / n, 4),
            "avg_keyword": round(sum(s["keyword_score"] for s in scores) / n, 4),
            "avg_citation": round(sum(s["citation_score"] for s in scores) / n, 4),
            "pass_rate": round(sum(1 for s in scores if s["total_score"] >= 0.6) / n, 4),
            "refuse_rate": round(sum(1 for s in scores if s["refused"]) / n, 4),
            "avg_elapsed_ms": round(sum(s["elapsed_ms"] for s in scores) / n),
        }

    # 保存结果
    output = ROOT / "eval" / "type_analysis.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到 {output}")
    return summary


def plot_performance_by_type(summary: dict):
    """绘制不同类型问题的性能对比"""
    import matplotlib.pyplot as plt
    import matplotlib
    import numpy as np

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12

    types = list(summary.keys())
    metrics = ["avg_score", "avg_keyword", "avg_citation", "pass_rate"]
    metric_labels = ["综合得分", "关键词命中", "引用正确", "通过率"]
    colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444']

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    for idx, (metric, label, color) in enumerate(zip(metrics, metric_labels, colors)):
        ax = axes[idx]
        values = [summary[t][metric] for t in types]
        bars = ax.bar(range(len(types)), values, color=color, alpha=0.8)

        # 添加数值标签
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{val:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.set_xticks(range(len(types)))
        ax.set_xticklabels(types, fontsize=11, fontweight='bold')
        ax.set_ylabel(label, fontsize=12, fontweight='bold')
        ax.set_title(f'{label}按问题类型分布', fontsize=13, fontweight='bold', pad=10)
        ax.set_ylim(0, 1.15)
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        ax.set_axisbelow(True)

    fig.suptitle('不同问题类型性能对比', fontsize=16, fontweight='bold', y=0.995)
    fig.tight_layout()

    out = ROOT / "eval" / "figures" / "performance_by_type.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"已保存：{out}")


def print_summary(summary: dict):
    """打印汇总表格"""
    print(f"\n{'='*90}")
    print(f"{'问题类型':<12} {'数量':>6} {'综合得分':>10} {'通过率':>10} {'拒答率':>10} {'响应时间':>12}")
    print("-" * 90)
    for qtype, stats in summary.items():
        print(f"{qtype:<12} {stats['count']:>6} "
              f"{stats['avg_score']:>10.4f} "
              f"{stats['pass_rate']:>9.1%} "
              f"{stats['refuse_rate']:>9.1%} "
              f"{stats['avg_elapsed_ms']:>11.0f}ms")
    print("=" * 90)


if __name__ == "__main__":
    summary = analyze_by_type()
    print_summary(summary)
    plot_performance_by_type(summary)
