"""
eval/run_hyperparam.py
自动运行超参数实验，测试不同参数组合对性能的影响。

用法：
    python eval/run_hyperparam.py
"""

import json
import os
import sys
import warnings
from pathlib import Path

# 忽略警告信息
warnings.filterwarnings("ignore")
os.environ['PYTHONWARNINGS'] = 'ignore'

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 超参数网格
HYPERPARAMS = {
    "TOP_K": [3, 4, 5, 8],                    # 送入 LLM 的片段数
    "MIN_RELEVANCE": [0.02, 0.03, 0.05],      # 相关性阈值
    "TOP_K_RETRIEVE": [8, 10, 15],            # 初始召回数
}

# 固定配置（完整系统）
BASE_CONFIG = {
    "RETRIEVER_TYPE": "tfidf",
    "ENABLE_LLM_RERANK": "true",
    "ENABLE_SELF_RAG": "true",
    "REASONING_MODEL_NAME": "deepseek-reasoner",
    "USE_LLM_REWRITE_QUERY": "true",
    "ENABLE_WEB_SEARCH": "true",
}

RESULTS_PATH = ROOT / "eval" / "hyperparam_results.json"
QUESTIONS_PATH = ROOT / "eval" / "questions_quick.json"  # 使用10道精选题加速实验


def set_env(config: dict):
    """设置环境变量"""
    for k, v in config.items():
        os.environ[k] = str(v)


def save_incremental_result(result: dict):
    """增量保存结果，避免实验中断导致数据丢失"""
    try:
        # 读取已有结果
        if RESULTS_PATH.exists():
            with open(RESULTS_PATH, "r", encoding="utf-8") as f:
                results = json.load(f)
        else:
            results = []

        # 追加或更新当前结果
        label = result["label"]
        existing_idx = None
        for i, r in enumerate(results):
            if r["label"] == label:
                existing_idx = i
                break

        if existing_idx is not None:
            results[existing_idx] = result
        else:
            results.append(result)

        # 保存
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"[已保存] {label} 结果已写入 {RESULTS_PATH}")

    except Exception as e:
        print(f"[警告] 保存结果失败：{e}")


def run_one_config(label: str, config: dict) -> dict:
    """运行单组超参数配置"""
    print(f"\n{'='*60}")
    print(f"运行配置：{label}")
    print(f"  TOP_K={config.get('TOP_K', 4)}")
    print(f"  MIN_RELEVANCE={config.get('MIN_RELEVANCE', 0.03)}")
    print(f"  TOP_K_RETRIEVE={config.get('TOP_K_RETRIEVE', 10)}")
    print('='*60)

    # 动态修改 config.py（通过 reload 生效）
    set_env(config)

    # 重新加载配置模块
    import importlib
    import src.config as cfg
    for k in ['TOP_K', 'MIN_RELEVANCE', 'TOP_K_RETRIEVE']:
        if k in config:
            setattr(cfg, k, config[k])

    # 运行评测
    try:
        # 直接加载 questions_quick.json，不依赖 run_eval.py
        with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
            questions = json.load(f)

        print(f"加载了 {len(questions)} 道测试题")

        from eval.run_eval import build_index, run_qa_simple, score_one
        from src.chat import get_llm

        index = build_index()
        llm = get_llm()

        scores = []
        for i, q in enumerate(questions):
            question_text = q["question"]
            print(f"  [{i+1:3d}/{len(questions)}] {question_text[:40]}...", end=" ", flush=True)

            try:
                answer, docs, elapsed = run_qa_simple(index, llm, question_text, [])
                sc = score_one(q, answer, docs, elapsed)
                scores.append(sc)

                status = "✓" if sc["total_score"] >= 0.6 else "✗"
                print(f"{status} {sc['total_score']:.2f}")
            except Exception as e:
                print(f"ERROR: {str(e)[:50]}")
                # 发生错误时记录失败分数
                scores.append({
                    "total_score": 0.0,
                    "keyword_score": 0.0,
                    "citation_score": 0.0,
                    "elapsed_ms": 0,
                    "refused": True
                })

        # 汇总统计
        n = len(scores)
        result = {
            "label": label,
            "config": dict(config),
            "n": n,
            "avg_score": round(sum(s["total_score"] for s in scores) / n, 4),
            "avg_keyword": round(sum(s["keyword_score"] for s in scores) / n, 4),
            "avg_citation": round(sum(s["citation_score"] for s in scores) / n, 4),
            "avg_elapsed_ms": round(sum(s["elapsed_ms"] for s in scores) / n),
            "refuse_rate": round(sum(1 for s in scores if s["refused"]) / n, 4),
            "pass_rate": round(sum(1 for s in scores if s["total_score"] >= 0.6) / n, 4),
        }

        print(f"\n结果：综合得分 {result['avg_score']:.4f}  通过率 {result['pass_rate']:.1%}")

        # 立即保存当前结果（增量保存）
        save_incremental_result(result)

        return result

    except Exception as e:
        print(f"\n配置 {label} 运行失败：{e}")
        import traceback
        traceback.print_exc()
        # 返回失败结果
        return {
            "label": label,
            "config": dict(config),
            "n": 0,
            "avg_score": 0.0,
            "avg_keyword": 0.0,
            "avg_citation": 0.0,
            "avg_elapsed_ms": 0,
            "refuse_rate": 1.0,
            "pass_rate": 0.0,
            "error": str(e)
        }


def main():
    # 检查是否有未完成的实验
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            existing_results = json.load(f)
        completed_labels = {r["label"] for r in existing_results}
        print(f"\n检测到已完成 {len(completed_labels)} 个配置，将继续剩余实验")
        print(f"已完成：{', '.join(completed_labels)}")
    else:
        existing_results = []
        completed_labels = set()

    results = list(existing_results)  # 保留已有结果

    # 1. 测试 TOP_K（片段数量）
    print("\n" + "="*60)
    print("实验一：检索片段数量 (TOP_K)")
    print("="*60)
    for top_k in HYPERPARAMS["TOP_K"]:
        label = f"top_k_{top_k}"
        if label in completed_labels:
            print(f"\n跳过已完成的配置：{label}")
            continue

        config = {**BASE_CONFIG, "TOP_K": top_k}
        result = run_one_config(label, config)

        # 更新结果列表
        results = [r for r in results if r["label"] != label]  # 移除旧的
        results.append(result)

    # 2. 测试 MIN_RELEVANCE（相关性阈值）
    print("\n" + "="*60)
    print("实验二：相关性阈值 (MIN_RELEVANCE)")
    print("="*60)
    for min_rel in HYPERPARAMS["MIN_RELEVANCE"]:
        label = f"min_rel_{min_rel}"
        if label in completed_labels:
            print(f"\n跳过已完成的配置：{label}")
            continue

        config = {**BASE_CONFIG, "MIN_RELEVANCE": min_rel, "TOP_K": 4}
        result = run_one_config(label, config)

        results = [r for r in results if r["label"] != label]
        results.append(result)

    # 3. 测试 TOP_K_RETRIEVE（召回数）
    print("\n" + "="*60)
    print("实验三：初始召回数 (TOP_K_RETRIEVE)")
    print("="*60)
    for retrieve in HYPERPARAMS["TOP_K_RETRIEVE"]:
        label = f"retrieve_{retrieve}"
        if label in completed_labels:
            print(f"\n跳过已完成的配置：{label}")
            continue

        config = {**BASE_CONFIG, "TOP_K_RETRIEVE": retrieve, "TOP_K": 4}
        result = run_one_config(label, config)

        results = [r for r in results if r["label"] != label]
        results.append(result)

    # 最终保存（确保完整）
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"所有实验完成，结果保存至：{RESULTS_PATH}")
    print("="*60)

    # 打印汇总
    print("\n最优参数：")
    best = max(results, key=lambda r: r["avg_score"])
    print(f"  配置：{best['label']}")
    print(f"  综合得分：{best['avg_score']:.4f}")
    print(f"  通过率：{best['pass_rate']:.1%}")
    print(f"  参数：{best['config']}")


if __name__ == "__main__":
    main()
