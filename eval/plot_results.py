"""
eval/plot_results.py
读取 eval/results.json，生成消融实验对比图。

用法：
    python eval/plot_results.py

输出：
    eval/figures/ablation_scores.png   — 综合得分柱状图
    eval/figures/ablation_metrics.png  — 多指标对比图
    eval/figures/response_time.png     — 响应时间对比图
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS_PATH = ROOT / "eval" / "results.json"
FIGURES_DIR = ROOT / "eval" / "figures"

# 标签显示名称映射（在图中显示更友好的名字）
LABEL_NAMES = {
    "baseline":      "基线\n(TF-IDF only)",
    "tfidf":         "TF-IDF\n检索",
    "no_rerank":     "去掉\nLLM重排",
    "no_selfrag":    "去掉\nSelf-RAG",
    "no_reasoning":  "去掉\n推理模型",
    "no_rewrite":    "去掉\n查询改写",
    "full":          "完整系统\n(Ours)",
}

# 显示顺序（基线→逐步消融→完整）
PREFERRED_ORDER = [
    "baseline", "tfidf", "no_rerank", "no_selfrag",
    "no_reasoning", "no_rewrite", "full"
]


def load_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(f"结果文件不存在：{RESULTS_PATH}\n请先运行 run_eval.py")
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def sort_results(results: list[dict]) -> list[dict]:
    """按 PREFERRED_ORDER 排序，未知标签排最后。"""
    order_map = {label: i for i, label in enumerate(PREFERRED_ORDER)}
    return sorted(results, key=lambda r: order_map.get(r["label"], 999))


def plot_ablation_scores(results: list[dict]):
    """主图：综合得分 + 通过率柱状图（双 Y 轴）。"""
    import matplotlib.pyplot as plt
    import matplotlib
    from matplotlib import font_manager

    # 设置字体：英文用 Times New Roman，中文用 SimHei（黑体，Windows 自带）
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']  # 黑体优先
    matplotlib.rcParams['font.serif'] = ['Times New Roman', 'SimSun']
    matplotlib.rcParams['font.family'] = 'sans-serif'  # 改用无衬线字体避免中文不显示
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12
    matplotlib.rcParams['axes.labelsize'] = 13
    matplotlib.rcParams['xtick.labelsize'] = 11
    matplotlib.rcParams['ytick.labelsize'] = 11
    matplotlib.rcParams['legend.fontsize'] = 11
    matplotlib.rcParams['axes.titlesize'] = 15
    matplotlib.rcParams['axes.titleweight'] = 'bold'
    matplotlib.rcParams['axes.labelweight'] = 'bold'

    labels = [LABEL_NAMES.get(r["label"], r["label"]) for r in results]
    scores = [r["avg_score"] for r in results]
    pass_rates = [r["pass_rate"] * 100 for r in results]

    x = range(len(results))
    width = 0.38

    fig, ax1 = plt.subplots(figsize=(max(8, len(results) * 1.4), 5))
    ax2 = ax1.twinx()

    # 高亮最后一条（完整系统）
    colors = ["#94a3b8"] * (len(results) - 1) + ["#3b82f6"]
    bars1 = ax1.bar([xi - width/2 for xi in x], scores, width, color=colors,
                    label="综合得分", zorder=3)
    bars2 = ax2.bar([xi + width/2 for xi in x], pass_rates, width, color=colors,
                    alpha=0.55, label="通过率 (%)", zorder=3)

    # 数值标注
    for bar, val in zip(bars1, scores):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                 f"{val:.3f}", ha="center", va="bottom", fontsize=10, fontweight='bold')
    for bar, val in zip(bars2, pass_rates):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f"{val:.1f}%", ha="center", va="bottom", fontsize=10, fontweight='bold')

    ax1.set_ylabel("综合得分 (0–1)", fontsize=13, fontweight='bold')
    ax2.set_ylabel("通过率 (%)", fontsize=13, fontweight='bold')
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, fontsize=11, fontweight='bold')
    ax1.set_ylim(0, 1.1)
    ax2.set_ylim(0, 115)
    ax1.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax1.set_axisbelow(True)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=11, frameon=True)

    plt.title("消融实验：综合得分与通过率对比", fontsize=15, fontweight="bold", pad=12)
    fig.tight_layout()

    out = FIGURES_DIR / "ablation_scores.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")  # 提高 DPI 到 300
    plt.close()
    print(f"  已保存：{out}")


def plot_multi_metrics(results: list[dict]):
    """多指标雷达/分组柱状图。"""
    import matplotlib.pyplot as plt
    import matplotlib
    from matplotlib import font_manager

    # 设置字体
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.serif'] = ['Times New Roman', 'SimSun']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12
    matplotlib.rcParams['axes.labelsize'] = 13
    matplotlib.rcParams['xtick.labelsize'] = 11
    matplotlib.rcParams['ytick.labelsize'] = 11
    matplotlib.rcParams['legend.fontsize'] = 10
    matplotlib.rcParams['axes.titlesize'] = 15
    matplotlib.rcParams['axes.titleweight'] = 'bold'
    matplotlib.rcParams['axes.labelweight'] = 'bold'

    metrics = ["avg_keyword", "avg_citation", "pass_rate"]
    metric_labels = ["关键词命中率", "引用正确率", "通过率"]
    colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4"]

    x = range(len(metrics))
    width = 0.8 / len(results)

    fig, ax = plt.subplots(figsize=(9, 5))

    for i, r in enumerate(results):
        vals = [r.get(m, 0) for m in metrics]
        offset = (i - len(results)/2 + 0.5) * width
        bars = ax.bar([xi + offset for xi in x], vals, width * 0.9,
                      color=colors[i % len(colors)],
                      label=LABEL_NAMES.get(r["label"], r["label"]),
                      zorder=3)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.008,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=9, fontweight='bold')

    ax.set_xticks(list(x))
    ax.set_xticklabels(metric_labels, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 1.2)
    ax.set_ylabel("得分 (0–1)", fontsize=13, fontweight='bold')
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(fontsize=10, ncol=2, loc="upper right", frameon=True)
    plt.title("消融实验：多维指标对比", fontsize=15, fontweight="bold", pad=12)
    fig.tight_layout()

    out = FIGURES_DIR / "ablation_metrics.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  已保存：{out}")


def plot_response_time(results: list[dict]):
    """响应时间对比横向柱状图。"""
    import matplotlib.pyplot as plt
    import matplotlib
    from matplotlib import font_manager

    # 设置字体
    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.serif'] = ['Times New Roman', 'SimSun']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12
    matplotlib.rcParams['axes.labelsize'] = 13
    matplotlib.rcParams['xtick.labelsize'] = 11
    matplotlib.rcParams['ytick.labelsize'] = 11
    matplotlib.rcParams['axes.titlesize'] = 15
    matplotlib.rcParams['axes.titleweight'] = 'bold'
    matplotlib.rcParams['axes.labelweight'] = 'bold'

    labels = [LABEL_NAMES.get(r["label"], r["label"]).replace("\n", " ") for r in results]
    times = [r["avg_elapsed_ms"] for r in results]
    colors = ["#94a3b8"] * (len(results) - 1) + ["#3b82f6"]

    fig, ax = plt.subplots(figsize=(7, max(4, len(results) * 0.7)))
    bars = ax.barh(range(len(results)), times, color=colors, zorder=3)

    for bar, val in zip(bars, times):
        ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height()/2,
                f"{val:.0f}ms", va="center", fontsize=10, fontweight='bold')

    ax.set_yticks(range(len(results)))
    ax.set_yticklabels(labels, fontsize=11, fontweight='bold')
    ax.set_xlabel("平均响应时间 (ms)", fontsize=13, fontweight='bold')
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    plt.title("消融实验：平均响应时间对比", fontsize=15, fontweight="bold", pad=12)
    fig.tight_layout()

    out = FIGURES_DIR / "response_time.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  已保存：{out}")


def print_summary_table(results: list[dict]):
    """在终端打印汇总表格。"""
    print(f"\n{'='*80}")
    print(f"{'标签':<16} {'综合得分':>8} {'通过率':>8} {'关键词':>8} {'引用':>8} {'响应ms':>8} {'拒答率':>8}")
    print("-" * 80)
    for r in results:
        print(f"{r['label']:<16} "
              f"{r['avg_score']:>8.4f} "
              f"{r['pass_rate']:>7.1%} "
              f"{r['avg_keyword']:>8.4f} "
              f"{r['avg_citation']:>8.4f} "
              f"{r['avg_elapsed_ms']:>8.0f} "
              f"{r['refuse_rate']:>7.1%}")
    print("=" * 80)


def main():
    results = load_results()
    results = sort_results(results)

    if len(results) == 0:
        print("results.json 为空，请先运行 run_eval.py")
        return

    print(f"读取到 {len(results)} 组实验结果")
    print_summary_table(results)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print("\n生成图表...")

    try:
        import matplotlib
        plot_ablation_scores(results)
        plot_multi_metrics(results)
        plot_response_time(results)
        print(f"\n所有图表已保存到 {FIGURES_DIR}/")
    except ImportError:
        print("未安装 matplotlib，请运行：pip install matplotlib")


if __name__ == "__main__":
    main()
