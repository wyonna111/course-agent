"""
eval/baseline_comparison.py
基线方法对比实验 - 对比时代演进的 RAG 方法

对比方案（按时间顺序）：
1. TF-IDF Baseline (1994) - 传统信息检索方法（对照组）
2. Vanilla RAG (2020) - Lewis et al., 基础 RAG 方法
3. RAG + LLM Rerank (2023) - 工业界常用增强方法
4. Self-RAG (2023) - Asai et al., 学术界最新方法
5. 完整系统 (2024) - 本工作，多模块协同优化

用法：
    python eval/baseline_comparison.py
"""

import json
import os
import sys
import warnings
from pathlib import Path

# 忽略所有 warning（包括 PDF 解析的 warning）
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINE_CONFIGS = [
    {
        "label": "tfidf_baseline",
        "name": "TF-IDF Baseline (1994)",
        "year": 1994,
        "reference": "传统信息检索方法",
        "description": "关键词检索 + LLM生成（无语义理解）",
        "config": {
            "RETRIEVER_TYPE": "tfidf",
            "ENABLE_LLM_RERANK": "false",
            "ENABLE_SELF_RAG": "false",
            "USE_LLM_REWRITE_QUERY": "false",
            "ENABLE_WEB_SEARCH": "false",
            "REASONING_MODEL_NAME": "",
        }
    },
    {
        "label": "vanilla_rag",
        "name": "Vanilla RAG (2020)",
        "year": 2020,
        "reference": "Lewis et al., Retrieval-Augmented Generation, NeurIPS 2020",
        "description": "语义向量检索 + 单次生成（基础RAG）",
        "config": {
            "RETRIEVER_TYPE": "semantic",
            "ENABLE_LLM_RERANK": "false",
            "ENABLE_SELF_RAG": "false",
            "USE_LLM_REWRITE_QUERY": "false",
            "ENABLE_WEB_SEARCH": "false",
            "REASONING_MODEL_NAME": "",
        }
    },
    {
        "label": "rag_rerank",
        "name": "RAG + LLM Rerank (2023)",
        "year": 2023,
        "reference": "工业界常用增强方法",
        "description": "语义检索 + LLM重排序 + 生成",
        "config": {
            "RETRIEVER_TYPE": "semantic",
            "ENABLE_LLM_RERANK": "true",
            "ENABLE_SELF_RAG": "false",
            "USE_LLM_REWRITE_QUERY": "false",
            "ENABLE_WEB_SEARCH": "false",
            "REASONING_MODEL_NAME": "",
        }
    },
    {
        "label": "self_rag",
        "name": "Self-RAG (2023)",
        "year": 2023,
        "reference": "Asai et al., Self-RAG: Learning to Retrieve, Generate, and Critique, NeurIPS 2023",
        "description": "语义检索 + 自我反思机制",
        "config": {
            "RETRIEVER_TYPE": "semantic",
            "ENABLE_LLM_RERANK": "false",
            "ENABLE_SELF_RAG": "true",
            "USE_LLM_REWRITE_QUERY": "false",
            "ENABLE_WEB_SEARCH": "false",
            "REASONING_MODEL_NAME": "",
        }
    },
    {
        "label": "ours_full",
        "name": "完整系统 (2024)",
        "year": 2024,
        "reference": "本工作：多模块协同优化",
        "description": "语义检索 + LLM重排 + Self-RAG + 推理模型 + 查询改写 + 联网补充",
        "config": {
            "RETRIEVER_TYPE": "semantic",
            "ENABLE_LLM_RERANK": "true",
            "ENABLE_SELF_RAG": "true",
            "USE_LLM_REWRITE_QUERY": "true",
            "ENABLE_WEB_SEARCH": "true",
            "REASONING_MODEL_NAME": "deepseek-reasoner",
        }
    },
]


def set_env(config: dict):
    for k, v in config.items():
        os.environ[k] = str(v)


def run_baseline(baseline: dict) -> dict:
    """运行单个基线配置"""
    label = baseline["label"]
    name = baseline["name"]
    config = baseline["config"]

    print(f"\n{'='*70}")
    print(f"运行：{name}")
    print(f"年份：{baseline['year']}")
    print(f"参考：{baseline['reference']}")
    print(f"说明：{baseline['description']}")
    print('='*70)

    set_env(config)

    # 重新加载配置
    import importlib
    import src.config as cfg
    importlib.reload(cfg)

    from eval.run_eval import load_questions, build_index, run_qa_simple, score_one
    from src.chat import get_llm

    questions = load_questions()
    index = build_index()
    llm = get_llm()

    scores = []
    for i, q in enumerate(questions):
        question_text = q["question"]
        print(f"  [{i+1:3d}/{len(questions)}] {question_text[:40]}...", end=" ")

        answer, docs, elapsed = run_qa_simple(index, llm, question_text, [])
        sc = score_one(q, answer, docs, elapsed)
        scores.append(sc)

        status = "✓" if sc["total_score"] >= 0.6 else "✗"
        print(f"{status} {sc['total_score']:.2f}")

    n = len(scores)
    result = {
        "label": label,
        "name": name,
        "year": baseline["year"],
        "reference": baseline["reference"],
        "n": n,
        "avg_score": round(sum(s["total_score"] for s in scores) / n, 4),
        "avg_keyword": round(sum(s["keyword_score"] for s in scores) / n, 4),
        "avg_citation": round(sum(s["citation_score"] for s in scores) / n, 4),
        "avg_elapsed_ms": round(sum(s["elapsed_ms"] for s in scores) / n),
        "refuse_rate": round(sum(1 for s in scores if s["refused"]) / n, 4),
        "pass_rate": round(sum(1 for s in scores if s["total_score"] >= 0.6) / n, 4),
    }

    print(f"\n【结果】")
    print(f"  综合得分：{result['avg_score']:.4f}")
    print(f"  通过率：{result['pass_rate']:.1%}")
    print(f"  拒答率：{result['refuse_rate']:.1%}")
    print(f"  响应时间：{result['avg_elapsed_ms']:.0f}ms")
    return result


def load_existing_results(output_file: Path) -> dict:
    """加载已有的结果（如果存在）"""
    if output_file.exists():
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            completed = {r["label"]: r for r in data}
            print(f"\n✅ 发现已保存的结果，包含 {len(completed)} 个方法")
            for label in completed:
                print(f"  - {completed[label]['name']} 已完成")
            return completed
        except Exception as e:
            print(f"⚠️  加载已有结果失败：{e}")
    return {}


def save_results(results: list, output_file: Path):
    """保存结果到文件"""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 结果已保存至：{output_file}")


def main():
    output = ROOT / "eval" / "baseline_comparison_results.json"

    # 加载已有结果
    completed = load_existing_results(output)
    results = list(completed.values())

    print("\n" + "="*70)
    print("基线方法对比实验 - 时代演进分析")
    print("="*70)
    print(f"测试集：100 道课程问答题")
    print(f"对比方法：{len(BASELINE_CONFIGS)} 种（1994 → 2024）")
    print("="*70)

    for i, baseline in enumerate(BASELINE_CONFIGS, 1):
        label = baseline["label"]

        # 跳过已完成的方法
        if label in completed:
            print(f"\n[{i}/{len(BASELINE_CONFIGS)}] ⏭️  跳过已完成：{baseline['name']}")
            continue

        print(f"\n[{i}/{len(BASELINE_CONFIGS)}] 开始测试：{baseline['name']}")

        try:
            result = run_baseline(baseline)
            results.append(result)

            # 每完成一个方法就保存一次
            save_results(results, output)

        except KeyboardInterrupt:
            print(f"\n\n⚠️  用户中断，已保存当前进度")
            save_results(results, output)
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ 运行失败：{e}")
            print(f"已保存其他方法的结果")
            save_results(results, output)
            raise

    # 最终保存
    save_results(results, output)

    print(f"\n{'='*70}")
    print(f"✅ 基线对比完成，结果保存至：{output}")
    print("="*70)

    # 打印汇总表（按时间排序）
    print(f"\n{'='*70}")
    print("基线方法对比汇总表（按时间演进）")
    print("="*70)
    print(f"\n{'方法':<28} {'年份':>6} {'得分':>8} {'通过率':>8} {'拒答率':>8} {'时间':>10}")
    print("-" * 70)
    for r in results:
        print(f"{r['name']:<28} {r['year']:>6} {r['avg_score']:>8.4f} {r['pass_rate']:>7.1%} {r['refuse_rate']:>7.1%} {r['avg_elapsed_ms']:>9.0f}ms")

    # 计算提升幅度
    print(f"\n{'='*70}")
    print("相比基线的提升幅度")
    print("="*70)
    baseline_score = results[0]['avg_score']  # TF-IDF 作为基线
    ours_score = results[-1]['avg_score']  # 完整系统

    for r in results[1:]:
        improvement = (r['avg_score'] - baseline_score) / baseline_score * 100
        print(f"{r['name']:<28} 提升 {improvement:>6.1f}%")

    print(f"\n💡 关键发现：")
    print(f"  • 完整系统相比传统方法提升 {(ours_score - baseline_score) / baseline_score * 100:.1f}%")
    print(f"  • 完整系统相比 Vanilla RAG 提升 {(ours_score - results[1]['avg_score']) / results[1]['avg_score'] * 100:.1f}%")
    print(f"  • 多模块协同优化优于单一优化方法")


if __name__ == "__main__":
    main()
