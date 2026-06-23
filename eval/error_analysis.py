"""
eval/error_analysis.py
分析系统常见故障模式，找出典型失败案例。

用法：
    python eval/error_analysis.py

输出：
    eval/error_cases.json  — 失败案例分类
    eval/figures/error_distribution.png — 错误类型分布图
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 故障类型定义
ERROR_TYPES = {
    "retrieval_miss": "检索失败（未召回相关片段）",
    "rerank_error": "重排错误（相关片段排序过低）",
    "generation_error": "生成错误（理解片段但答错）",
    "reasoning_error": "推理错误（需要多步计算但推理失败）",
    "format_error": "格式错误（答案不完整或格式不对）",
    "refusal_error": "错误拒答（课件中有答案但系统拒答）",
}


def analyze_failures():
    """
    从 run_eval.py 生成的详细日志中分析失败案例。
    需要先修改 run_eval.py 保存每题的详细结果。
    """
    from eval.run_eval import load_questions, build_index, run_qa_simple, score_one
    from src.chat import get_llm

    questions = load_questions()
    index = build_index()
    llm = get_llm()

    failures = []

    for i, q in enumerate(questions):
        question_text = q["question"]
        print(f"[{i+1}/{len(questions)}] {question_text[:50]}...")

        answer, docs, elapsed = run_qa_simple(index, llm, question_text, [])
        sc = score_one(q, answer, docs, elapsed)

        # 记录失败案例（得分 < 0.6）
        if sc["total_score"] < 0.6:
            # 分析失败原因
            error_type = classify_error(q, answer, docs, sc)

            failures.append({
                "question": question_text,
                "expected_answer": q.get("answer", ""),
                "actual_answer": answer,
                "retrieved_pages": [d.get("page", -1) for d in docs],
                "source_pages": q.get("source_pages", []),
                "score": sc["total_score"],
                "error_type": error_type,
                "keyword_score": sc["keyword_score"],
                "citation_score": sc["citation_score"],
            })

    # 保存结果
    output = ROOT / "eval" / "error_cases.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=2)

    print(f"\n找到 {len(failures)} 个失败案例，已保存到 {output}")
    return failures


def classify_error(question, answer, docs, score):
    """
    根据症状分类错误类型。
    """
    # 拒答
    if score["refused"]:
        return "refusal_error"

    # 检索失败（召回的页码完全不对）
    if score["citation_score"] == 0.0:
        return "retrieval_miss"

    # 生成错误（检索对了但关键词不匹配）
    if score["citation_score"] >= 0.5 and score["keyword_score"] < 0.3:
        # 检查是否是计算题
        if any(kw in question["question"] for kw in ["计算", "地址", "转换", "补码", "浮点"]):
            return "reasoning_error"
        return "generation_error"

    # 重排错误（部分召回但排序不好）
    if score["citation_score"] > 0 and score["citation_score"] < 0.5:
        return "rerank_error"

    # 格式错误（其他情况）
    return "format_error"


def plot_error_distribution(failures):
    """绘制错误类型分布图"""
    import matplotlib.pyplot as plt
    import matplotlib
    from collections import Counter

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12

    # 统计错误类型
    error_counts = Counter(f["error_type"] for f in failures)

    # 中文标签
    labels = [ERROR_TYPES.get(k, k) for k in error_counts.keys()]
    values = list(error_counts.values())
    colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899']

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(range(len(labels)), values, color=colors[:len(labels)])

    # 添加数值标签
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                f"{val} ({val/len(failures)*100:.1f}%)",
                va='center', fontsize=11, fontweight='bold')

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=12, fontweight='bold')
    ax.set_xlabel('失败案例数量', fontsize=13, fontweight='bold')
    ax.set_title(f'系统故障模式分析（共 {len(failures)} 个失败案例）',
                 fontsize=15, fontweight='bold', pad=12)
    ax.grid(axis='x', linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)

    fig.tight_layout()
    out = ROOT / "eval" / "figures" / "error_distribution.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"已保存：{out}")


def print_typical_cases(failures, n=3):
    """打印每种错误类型的典型案例"""
    from collections import defaultdict

    grouped = defaultdict(list)
    for f in failures:
        grouped[f["error_type"]].append(f)

    print("\n" + "="*80)
    print("典型失败案例")
    print("="*80)

    for error_type, cases in grouped.items():
        print(f"\n## {ERROR_TYPES.get(error_type, error_type)}（共 {len(cases)} 例）\n")
        for case in cases[:n]:
            print(f"问题：{case['question']}")
            print(f"回答：{case['actual_answer'][:100]}...")
            print(f"得分：{case['score']:.2f}")
            print("-" * 60)


if __name__ == "__main__":
    failures = analyze_failures()
    plot_error_distribution(failures)
    print_typical_cases(failures)
