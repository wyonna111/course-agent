"""
可视化脚本 - 生成完整实验报告的所有图表
包含5个关键可视化图表，字体加粗放大，适合论文展示

运行方式：
    python eval/plot_all_figures.py

生成的图表：
    1. baseline_comparison.png - 基线方法对比（时代演进）
    2. ablation_radar.png - 消融实验（模块贡献度雷达图）
    3. error_distribution.png - 错误分析（故障类型分布）
    4. hyperparam_sensitivity.png - 超参数敏感性曲线
    5. performance_efficiency.png - 性能vs效率散点图
"""

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from pathlib import Path

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 设置全局字体大小（加大）
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 13
plt.rcParams['ytick.labelsize'] = 13
plt.rcParams['legend.fontsize'] = 13
plt.rcParams['font.weight'] = 'bold'
plt.rcParams['axes.labelweight'] = 'bold'
plt.rcParams['axes.titleweight'] = 'bold'

# 创建输出目录
output_dir = Path("eval/figures")
output_dir.mkdir(parents=True, exist_ok=True)

# ============================================================================
# 图表 1：基线方法对比 - 时代演进图
# ============================================================================
def plot_baseline_comparison():
    """实验三：基线方法对比 - 时代演进分析"""
    fig, ax1 = plt.subplots(figsize=(16, 9))

    # 数据
    methods = ['TF-IDF\n(1994)', 'Vanilla RAG\n(2020)', 'RAG+Rerank\n(2023)',
               'Self-RAG\n(2023)', '完整系统\n(2024)']
    scores = [0.5950, 0.6580, 0.6950, 0.6890, 0.7411]
    pass_rates = [68, 78, 83, 82, 91]
    colors = ['#d9534f', '#5bc0de', '#f0ad4e', '#5cb85c', '#0275d8']

    # 柱状图 - 综合得分
    bars = ax1.bar(methods, scores, color=colors, alpha=0.85, edgecolor='black', linewidth=2.5)
    ax1.set_ylabel('综合得分', fontsize=22, fontweight='bold')
    ax1.set_ylim(0.5, 0.82)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.tick_params(axis='x', labelsize=16)
    ax1.tick_params(axis='y', labelsize=18)

    # 在柱状图中间标注数值 - 黑色文字
    for i, (bar, score) in enumerate(zip(bars, scores)):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height/2.,
                f'{score:.4f}', ha='center', va='center',
                fontsize=18, fontweight='bold', color='black')

    # 折线图 - 通过率（使用深蓝色）
    ax2 = ax1.twinx()
    line = ax2.plot(methods, pass_rates, 'o-', color='#1E3A8A', linewidth=4.5,
                    markersize=16, label='通过率', markeredgecolor='white', markeredgewidth=2.5)
    ax2.set_ylabel('通过率 (%)', fontsize=22, fontweight='bold', color='#1E3A8A')
    ax2.tick_params(axis='y', labelcolor='#1E3A8A', labelsize=18)
    ax2.set_ylim(60, 98)

    # 在折线上方标注数值 - 深蓝色
    for x, y in zip(range(len(methods)), pass_rates):
        ax2.text(x, y + 3.5, f'{y}%', ha='center', va='bottom',
                fontsize=20, fontweight='bold', color='#1E3A8A',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#1E3A8A', linewidth=2))

    # 添加图例
    ax1.legend(['综合得分'], loc='upper left', fontsize=17, framealpha=0.9)
    ax2.legend(['通过率'], loc='upper left', bbox_to_anchor=(0, 0.88), fontsize=17, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_dir / 'baseline_comparison.png', dpi=300, bbox_inches='tight')
    print("[OK] 已生成：实验三 - 基线方法对比图 (baseline_comparison.png)")
    plt.close()


# ============================================================================
# 图表 2：消融实验 - 模块贡献度雷达图
# ============================================================================
def plot_ablation_radar():
    """实验二：消融实验 - 模块贡献度分析"""
    fig = plt.figure(figsize=(16, 16))
    ax = fig.add_subplot(111, projection='polar')

    # 维度
    categories = ['综合得分', '通过率', '关键词\n命中率', '引用\n正确率', '低拒答率', '响应速度']
    N = len(categories)

    # 数据（归一化到0-1）
    # 完整系统
    full_system = [
        0.7411 / 0.8,      # 综合得分（归一化）
        0.91,              # 通过率
        0.7502 / 0.8,      # 关键词命中率
        0.4950 / 0.6,      # 引用正确率
        1 - 0.04,          # 低拒答率（反向）
        1 - (16204 / 30000)  # 响应速度（反向）
    ]

    # 去掉LLM重排
    no_rerank = [
        0.6596 / 0.8,
        0.71,
        0.6777 / 0.8,
        0.3350 / 0.6,
        1 - 0.07,
        1 - (28900 / 30000)
    ]

    # 去掉Self-RAG
    no_selfrag = [
        0.6457 / 0.8,
        0.75,
        0.6546 / 0.8,
        0.4350 / 0.6,
        1 - 0.17,
        1 - (19941 / 30000)
    ]

    # 基线系统
    baseline = [
        0.5950 / 0.8,
        0.68,
        0.6081 / 0.8,
        0.4200 / 0.6,
        1 - 0.25,
        1 - (12320 / 30000)
    ]

    # 角度
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    full_system += full_system[:1]
    no_rerank += no_rerank[:1]
    no_selfrag += no_selfrag[:1]
    baseline += baseline[:1]
    angles += angles[:1]

    # 绘制 - 加粗线条
    ax.plot(angles, full_system, 'o-', linewidth=5, label='完整系统', color='#0275d8', markersize=18)
    ax.fill(angles, full_system, alpha=0.2, color='#0275d8')

    ax.plot(angles, no_rerank, 's-', linewidth=4, label='去掉LLM重排', color='#f0ad4e', markersize=15)
    ax.plot(angles, no_selfrag, '^-', linewidth=4, label='去掉Self-RAG', color='#5cb85c', markersize=15)
    ax.plot(angles, baseline, 'D-', linewidth=4, label='基线系统', color='#d9534f', markersize=15)

    # 设置刻度标签 - 增大并加粗所有文字
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=24, fontweight='bold')
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=22, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.5, linewidth=1.5)

    # 图例 - 增大字体
    plt.legend(loc='upper right', bbox_to_anchor=(1.35, 1.08), fontsize=22, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_dir / 'ablation_radar.png', dpi=300, bbox_inches='tight')
    print("[OK] 已生成：实验二 - 消融实验雷达图 (ablation_radar.png)")
    plt.close()


# ============================================================================
# 图表 3：错误分析 - 故障类型分布饼图
# ============================================================================
def plot_error_distribution():
    """实验四：错误分析 - 故障类型分布"""
    fig, ax = plt.subplots(figsize=(15, 13))

    # 数据
    labels = ['检索失败\n33.3%', '生成错误\n22.2%', '推理错误\n22.2%',
              '重排错误\n11.1%', '边界情况\n11.1%']
    sizes = [33.3, 22.2, 22.2, 11.1, 11.1]
    colors = ['#d9534f', '#f0ad4e', '#5bc0de', '#5cb85c', '#9467bd']
    explode = (0.12, 0.06, 0.06, 0, 0)  # 突出显示检索失败

    # 绘制饼图 - 增大标签字体
    wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=labels, colors=colors,
                                       autopct='%1.1f%%', startangle=90,
                                       textprops={'fontsize': 24, 'fontweight': 'bold'},
                                       wedgeprops={'edgecolor': 'black', 'linewidth': 2.5})

    # 设置百分比文字样式 - 黑色加粗36号
    for autotext in autotexts:
        autotext.set_color('black')
        autotext.set_fontsize(36)
        autotext.set_fontweight('bold')

    # 添加图例说明 - 增大字体到20，移除原因说明
    legend_labels = [
        '检索失败 (33.3%)',
        '生成错误 (22.2%)',
        '推理错误 (22.2%)',
        '重排错误 (11.1%)',
        '边界情况 (11.1%)'
    ]
    ax.legend(legend_labels, loc='upper left', bbox_to_anchor=(0.82, 1), fontsize=20, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_dir / 'error_distribution.png', dpi=300, bbox_inches='tight')
    print("[OK] 已生成：实验四 - 错误分析饼图 (error_distribution.png)")
    plt.close()


# ============================================================================
# 图表 4：超参数敏感性曲线
# ============================================================================
def plot_hyperparam_sensitivity():
    """实验一：超参数调优 - 参数敏感性分析"""
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))

    # 子图1：TOP_K
    top_k_values = [3, 4, 5, 8]
    top_k_scores = [0.7411, 0.6825, 0.6745, 0.6880]
    top_k_pass_rates = [91, 88, 85, 78]

    ax1 = axes[0]
    ax1_twin = ax1.twinx()

    # 综合得分线 - 使用深蓝色
    line1 = ax1.plot(top_k_values, top_k_scores, 'o-', linewidth=4.5, markersize=16,
                     color='#1E3A8A', label='综合得分', markeredgecolor='white', markeredgewidth=2.5)
    # 通过率线 - 使用深橙色（不亮）
    line2 = ax1_twin.plot(top_k_values, top_k_pass_rates, 's-', linewidth=4.5, markersize=16,
                          color='#DC6803', label='通过率', markeredgecolor='white', markeredgewidth=2.5)

    # 在线上标注数值 - 加粗数字
    for x, y in zip(top_k_values, top_k_scores):
        ax1.text(x, y + 0.012, f'{y:.4f}', ha='center', va='bottom',
                fontsize=20, fontweight='bold', color='#1E3A8A')

    for x, y in zip(top_k_values, top_k_pass_rates):
        ax1_twin.text(x, y + 2, f'{y}%', ha='center', va='bottom',
                     fontsize=20, fontweight='bold', color='#DC6803')

    ax1.set_xlabel('TOP_K（送入LLM的片段数）', fontsize=18, fontweight='bold')
    ax1.set_ylabel('综合得分', fontsize=18, fontweight='bold', color='#1E3A8A')
    ax1_twin.set_ylabel('通过率 (%)', fontsize=18, fontweight='bold', color='#DC6803')
    ax1.tick_params(axis='y', labelcolor='#1E3A8A', labelsize=16)
    ax1_twin.tick_params(axis='y', labelcolor='#DC6803', labelsize=16)
    ax1.tick_params(axis='x', labelsize=16)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_ylim(0.65, 0.77)
    ax1_twin.set_ylim(72, 95)

    # 标注最优点
    ax1.scatter([3], [0.7411], s=500, color='gold', edgecolor='black', linewidth=3, zorder=5, marker='*')

    # 子图2：MIN_RELEVANCE
    min_rel_values = [0.02, 0.03, 0.05]
    min_rel_labels = ['0.02', '0.03', '0.05']
    min_rel_scores = [0.7411, 0.7065, 0.7395]
    min_rel_pass_rates = [91, 86, 90]

    ax2 = axes[1]
    ax2_twin = ax2.twinx()

    x_pos = np.arange(len(min_rel_values))
    line1 = ax2.plot(x_pos, min_rel_scores, 'o-', linewidth=4.5, markersize=16,
                     color='#1E3A8A', label='综合得分', markeredgecolor='white', markeredgewidth=2.5)
    line2 = ax2_twin.plot(x_pos, min_rel_pass_rates, 's-', linewidth=4.5, markersize=16,
                          color='#DC6803', label='通过率', markeredgecolor='white', markeredgewidth=2.5)

    # 在线上标注数值 - 加粗数字
    for x, y in zip(x_pos, min_rel_scores):
        ax2.text(x, y + 0.012, f'{y:.4f}', ha='center', va='bottom',
                fontsize=20, fontweight='bold', color='#1E3A8A')

    for x, y in zip(x_pos, min_rel_pass_rates):
        ax2_twin.text(x, y + 1.5, f'{y}%', ha='center', va='bottom',
                     fontsize=20, fontweight='bold', color='#DC6803')

    ax2.set_xlabel('MIN_RELEVANCE（相关性阈值）', fontsize=18, fontweight='bold')
    ax2.set_ylabel('综合得分', fontsize=18, fontweight='bold', color='#1E3A8A')
    ax2_twin.set_ylabel('通过率 (%)', fontsize=18, fontweight='bold', color='#DC6803')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(min_rel_labels, fontsize=16)
    ax2.tick_params(axis='y', labelcolor='#1E3A8A', labelsize=16)
    ax2_twin.tick_params(axis='y', labelcolor='#DC6803', labelsize=16)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_ylim(0.69, 0.76)
    ax2_twin.set_ylim(82, 94)

    # 标注最优点
    ax2.scatter([0], [0.7411], s=500, color='gold', edgecolor='black', linewidth=3, zorder=5, marker='*')

    # 子图3：TOP_K_RETRIEVE
    retrieve_values = [8, 10, 15]
    retrieve_scores = [0.7395, 0.7411, 0.7195]
    retrieve_times = [19860, 13491, 14097]

    ax3 = axes[2]
    ax3_twin = ax3.twinx()

    x_pos = np.arange(len(retrieve_values))
    line1 = ax3.plot(x_pos, retrieve_scores, 'o-', linewidth=4.5, markersize=16,
                     color='#1E3A8A', label='综合得分', markeredgecolor='white', markeredgewidth=2.5)
    line2 = ax3_twin.plot(x_pos, retrieve_times, 's-', linewidth=4.5, markersize=16,
                          color='#047857', label='响应时间', markeredgecolor='white', markeredgewidth=2.5)

    # 在线上标注数值 - 加粗数字
    for x, y in zip(x_pos, retrieve_scores):
        ax3.text(x, y + 0.012, f'{y:.4f}', ha='center', va='bottom',
                fontsize=20, fontweight='bold', color='#1E3A8A')

    for x, y in zip(x_pos, retrieve_times):
        ax3_twin.text(x, y + 800, f'{y}', ha='center', va='bottom',
                     fontsize=20, fontweight='bold', color='#047857')

    ax3.set_xlabel('TOP_K_RETRIEVE（初始召回数）', fontsize=18, fontweight='bold')
    ax3.set_ylabel('综合得分', fontsize=18, fontweight='bold', color='#1E3A8A')
    ax3_twin.set_ylabel('响应时间 (ms)', fontsize=18, fontweight='bold', color='#047857')
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(retrieve_values, fontsize=16)
    ax3.tick_params(axis='y', labelcolor='#1E3A8A', labelsize=16)
    ax3_twin.tick_params(axis='y', labelcolor='#047857', labelsize=16)
    ax3.grid(True, alpha=0.3, linestyle='--')
    ax3.set_ylim(0.71, 0.755)
    ax3_twin.set_ylim(12000, 21000)

    # 标注最优点
    ax3.scatter([1], [0.7411], s=500, color='gold', edgecolor='black', linewidth=3, zorder=5, marker='*')

    plt.tight_layout()
    plt.savefig(output_dir / 'hyperparam_sensitivity.png', dpi=300, bbox_inches='tight')
    print("[OK] 已生成：实验一 - 超参数敏感性曲线 (hyperparam_sensitivity.png)")
    plt.close()


# ============================================================================
# 图表 5：性能vs效率散点图
# ============================================================================
def plot_performance_efficiency():
    """实验三：基线方法对比 - 性能与效率权衡"""
    fig, ax = plt.subplots(figsize=(14, 10))

    # 数据
    methods = ['TF-IDF\nBaseline', 'Vanilla\nRAG', 'RAG+\nRerank', 'Self-\nRAG', '完整\n系统']
    response_times = [12320, 14500, 18200, 17200, 16204]
    scores = [0.5950, 0.6580, 0.6950, 0.6890, 0.7411]
    pass_rates = [68, 78, 83, 82, 91]  # 用于气泡大小
    colors = ['#d9534f', '#5bc0de', '#f0ad4e', '#5cb85c', '#0275d8']

    # 绘制散点图（气泡大小与通过率成正比）
    for i, (method, x, y, pr, color) in enumerate(zip(methods, response_times, scores, pass_rates, colors)):
        size = pr * 10  # 放大气泡
        ax.scatter(x, y, s=size, alpha=0.6, color=color, edgecolor='black', linewidth=2)
        # 标注方法名和通过率
        ax.annotate(f'{method}\n({pr}%)', xy=(x, y), xytext=(10, 10),
                   textcoords='offset points', fontsize=13, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor=color, alpha=0.7, edgecolor='black', linewidth=1.5))

    # 标注完整系统（突出显示）
    ax.scatter(response_times[-1], scores[-1], s=1000, alpha=0.3, color='gold', edgecolor='gold', linewidth=3)

    # 设置标签
    ax.set_xlabel('响应时间 (ms)', fontsize=18, fontweight='bold')
    ax.set_ylabel('综合得分', fontsize=18, fontweight='bold')
    ax.set_title('实验三：基线方法对比 - 性能与效率权衡分析\n(气泡大小 = 通过率)',
                fontsize=20, fontweight='bold', pad=20)
    ax.grid(True, alpha=0.3, linestyle='--')

    # 添加参考线
    ax.axhline(y=0.74, color='red', linestyle='--', linewidth=2, alpha=0.5, label='完整系统得分基准')
    ax.axvline(x=16204, color='blue', linestyle='--', linewidth=2, alpha=0.5, label='完整系统时间基准')

    # 图例
    ax.legend(fontsize=14, loc='lower right', framealpha=0.9)

    # 添加说明文字
    textstr = '✨ 完整系统特点：\n• 最高得分 (0.7411)\n• 最高通过率 (91%)\n• 响应时间适中 (16.2s)'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8, edgecolor='black', linewidth=2)
    ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=13, fontweight='bold',
            verticalalignment='top', bbox=props)

    plt.tight_layout()
    plt.savefig(output_dir / 'performance_efficiency.png', dpi=300, bbox_inches='tight')
    print("[OK] 已生成：实验三 - 性能效率散点图 (performance_efficiency.png)")
    plt.close()


# ============================================================================
# 主函数
# ============================================================================
def main():
    print("\n" + "="*70)
    print("开始生成完整实验报告的可视化图表")
    print("="*70 + "\n")

    # 生成所有图表
    plot_baseline_comparison()
    plot_ablation_radar()
    plot_error_distribution()
    plot_hyperparam_sensitivity()

    print("\n" + "="*70)
    print("[OK] 所有图表生成完成！")
    print(f"输出目录：{output_dir.absolute()}")
    print("="*70)
    print("\n生成的图表：")
    print("  1. baseline_comparison.png - 实验三：基线方法对比")
    print("  2. ablation_radar.png - 实验二：消融实验雷达图")
    print("  3. error_distribution.png - 实验四：错误分析饼图")
    print("  4. hyperparam_sensitivity.png - 实验一：超参数敏感性曲线")
    print("\n提示：所有图表已优化字体（加粗放大），适合论文展示\n")


if __name__ == "__main__":
    main()
