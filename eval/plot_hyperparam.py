"""
eval/plot_hyperparam.py
读取 eval/hyperparam_results.json，生成超参数实验对比图。

用法：
    python eval/plot_hyperparam.py

输出：
    eval/figures/hyperparam_top_k.png         — TOP_K 影响
    eval/figures/hyperparam_min_relevance.png — MIN_RELEVANCE 影响
    eval/figures/hyperparam_retrieve.png      — TOP_K_RETRIEVE 影响
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS_PATH = ROOT / "eval" / "hyperparam_results.json"
FIGURES_DIR = ROOT / "eval" / "figures"


def load_results() -> list[dict]:
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(f"结果文件不存在：{RESULTS_PATH}\n请先运行 run_hyperparam.py")
    with open(RESULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def plot_top_k(results: list[dict]):
    """TOP_K 参数影响曲线图"""
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.serif'] = ['Times New Roman', 'SimSun']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12

    # 筛选 TOP_K 实验组
    data = [r for r in results if r['label'].startswith('top_k_')]
    data = sorted(data, key=lambda r: r['config']['TOP_K'])

    x = [r['config']['TOP_K'] for r in data]
    scores = [r['avg_score'] for r in data]
    times = [r['avg_elapsed_ms'] / 1000 for r in data]  # 转为秒

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    line1 = ax1.plot(x, scores, 'o-', color='#3b82f6', linewidth=2.5,
                     markersize=8, label='综合得分', zorder=3)
    line2 = ax2.plot(x, times, 's--', color='#ef4444', linewidth=2.5,
                     markersize=8, label='响应时间 (s)', zorder=3)

    ax1.set_xlabel('TOP_K（检索片段数）', fontsize=13, fontweight='bold')
    ax1.set_ylabel('综合得分 (0–1)', fontsize=13, fontweight='bold', color='#3b82f6')
    ax2.set_ylabel('响应时间 (s)', fontsize=13, fontweight='bold', color='#ef4444')

    ax1.tick_params(axis='y', labelcolor='#3b82f6')
    ax2.tick_params(axis='y', labelcolor='#ef4444')
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.set_axisbelow(True)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=11, frameon=True)

    plt.title('超参数实验：TOP_K 对性能的影响', fontsize=15, fontweight='bold', pad=12)
    fig.tight_layout()

    out = FIGURES_DIR / "hyperparam_top_k.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  已保存：{out}")


def plot_min_relevance(results: list[dict]):
    """MIN_RELEVANCE 参数影响曲线图"""
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.serif'] = ['Times New Roman', 'SimSun']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12

    data = [r for r in results if r['label'].startswith('min_rel_')]
    data = sorted(data, key=lambda r: r['config']['MIN_RELEVANCE'])

    x = [r['config']['MIN_RELEVANCE'] for r in data]
    scores = [r['avg_score'] for r in data]
    refuse = [r['refuse_rate'] * 100 for r in data]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    line1 = ax1.plot(x, scores, 'o-', color='#10b981', linewidth=2.5,
                     markersize=8, label='综合得分', zorder=3)
    line2 = ax2.plot(x, refuse, 's--', color='#f59e0b', linewidth=2.5,
                     markersize=8, label='拒答率 (%)', zorder=3)

    ax1.set_xlabel('MIN_RELEVANCE（相关性阈值）', fontsize=13, fontweight='bold')
    ax1.set_ylabel('综合得分 (0–1)', fontsize=13, fontweight='bold', color='#10b981')
    ax2.set_ylabel('拒答率 (%)', fontsize=13, fontweight='bold', color='#f59e0b')

    ax1.tick_params(axis='y', labelcolor='#10b981')
    ax2.tick_params(axis='y', labelcolor='#f59e0b')
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.set_axisbelow(True)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=11, frameon=True)

    plt.title('超参数实验：MIN_RELEVANCE 对性能的影响', fontsize=15, fontweight='bold', pad=12)
    fig.tight_layout()

    out = FIGURES_DIR / "hyperparam_min_relevance.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  已保存：{out}")


def plot_retrieve(results: list[dict]):
    """TOP_K_RETRIEVE 参数影响曲线图"""
    import matplotlib.pyplot as plt
    import matplotlib

    matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    matplotlib.rcParams['font.serif'] = ['Times New Roman', 'SimSun']
    matplotlib.rcParams['font.family'] = 'sans-serif'
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 12

    data = [r for r in results if r['label'].startswith('retrieve_')]
    data = sorted(data, key=lambda r: r['config']['TOP_K_RETRIEVE'])

    x = [r['config']['TOP_K_RETRIEVE'] for r in data]
    scores = [r['avg_score'] for r in data]
    citation = [r['avg_citation'] for r in data]

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()

    line1 = ax1.plot(x, scores, 'o-', color='#8b5cf6', linewidth=2.5,
                     markersize=8, label='综合得分', zorder=3)
    line2 = ax2.plot(x, citation, 's--', color='#ec4899', linewidth=2.5,
                     markersize=8, label='引用正确率', zorder=3)

    ax1.set_xlabel('TOP_K_RETRIEVE（初始召回数）', fontsize=13, fontweight='bold')
    ax1.set_ylabel('综合得分 (0–1)', fontsize=13, fontweight='bold', color='#8b5cf6')
    ax2.set_ylabel('引用正确率 (0–1)', fontsize=13, fontweight='bold', color='#ec4899')

    ax1.tick_params(axis='y', labelcolor='#8b5cf6')
    ax2.tick_params(axis='y', labelcolor='#ec4899')
    ax1.grid(True, linestyle='--', alpha=0.3)
    ax1.set_axisbelow(True)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left', fontsize=11, frameon=True)

    plt.title('超参数实验：TOP_K_RETRIEVE 对性能的影响', fontsize=15, fontweight='bold', pad=12)
    fig.tight_layout()

    out = FIGURES_DIR / "hyperparam_retrieve.png"
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  已保存：{out}")


def print_summary_table(results: list[dict]):
    """打印汇总表格"""
    print(f"\n{'='*90}")
    print(f"{'配置':<20} {'综合得分':>8} {'通过率':>8} {'拒答率':>8} {'响应时间':>10}")
    print("-" * 90)
    for r in results:
        print(f"{r['label']:<20} "
              f"{r['avg_score']:>8.4f} "
              f"{r['pass_rate']:>7.1%} "
              f"{r['refuse_rate']:>7.1%} "
              f"{r['avg_elapsed_ms']:>9.0f}ms")
    print("=" * 90)


def main():
    results = load_results()

    if len(results) == 0:
        print("hyperparam_results.json 为空，请先运行 run_hyperparam.py")
        return

    print(f"读取到 {len(results)} 组超参数实验结果")
    print_summary_table(results)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    print("\n生成图表...")

    try:
        import matplotlib
        plot_top_k(results)
        plot_min_relevance(results)
        plot_retrieve(results)
        print(f"\n所有图表已保存到 {FIGURES_DIR}/")
    except ImportError:
        print("未安装 matplotlib，请运行：pip install matplotlib")


if __name__ == "__main__":
    main()
