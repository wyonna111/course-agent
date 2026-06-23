"""
eval/gen_questions.py (v2)
从已索引课件自动生成评测题目，保存到 eval/questions.json。

改进：先用种子问题检索，再让 LLM 基于检索结果出题，生成需要跨页回答的题目。

用法：
    python eval/gen_questions.py
"""

import json
import os
import random
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*wrong pointing object.*")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# 出题只需要读取文本内容，强制用 TF-IDF 避免下载 BGE 模型
os.environ["RETRIEVER_TYPE"] = "tfidf"

from src.indexer import DocumentIndex
from src.chat import get_llm

# ── 配置 ────────────────────────────────────────────────────────
TARGET_AUTO = 80          # 自动生成题目数量
OUTPUT_PATH = ROOT / "eval" / "questions.json"
MANUAL_PATH = ROOT / "eval" / "test_cases_manual.json"
DATA_DIR = ROOT / "data"

# 种子问题（覆盖各章节常见题型）
SEED_QUESTIONS = [
    "什么是冯诺依曼结构？",
    "固件和软件的区别是什么？",
    "原码、补码、反码有什么区别？",
    "IEEE754浮点数如何表示？",
    "8086的标志寄存器有哪些标志位？",
    "如何计算物理地址？",
    "堆栈指针SP的作用是什么？",
    "8086有哪些寻址方式？",
    "中断向量表如何存储？",
    "段寄存器的作用是什么？",
    "汇编语言中DB、DW、DD的区别？",
    "如何定义数组和字符串？",
    "LOOP指令的功能是什么？",
    "如何判断有符号数溢出？",
    "条件转移指令有哪些？",
    "存储器芯片容量如何计算？",
    "地址线和数据线的关系？",
    "ROM和RAM的区别？",
    "如何进行存储器扩展？",
    "奇偶地址对总线操作的影响？",
    "8253定时器工作方式有哪些？",
    "如何计算定时器初值？",
    "8255并行接口的工作方式？",
    "如何设置8255控制字？",
    "异步串行通信的帧格式？",
    "波特率如何影响传输速度？",
    "中断响应过程包括哪些步骤？",
    "可屏蔽中断和不可屏蔽中断的区别？",
    "DMA和中断有什么区别？",
    "指令周期、机器周期、时钟周期的关系？",
]

GEN_PROMPT = """你是出题老师。给你一组从课件检索到的相关片段，请出一道综合问答题。

要求：
1. 题目需要综合多个片段的信息才能完整回答（跨页综合题）
2. 优先出涉及计算、对比、步骤分析的题目
3. keywords 列出答案中必须出现的 4~7 个关键词或关键数字
4. sources 列出需要用到的所有片段的来源标签（从片段开头的 [本地: ...] 复制）
5. 只输出 JSON，不要任何额外文字

输出格式（严格 JSON）：
{
  "question": "题目内容",
  "answer": "标准答案（综合多个片段，100-150字）",
  "keywords": ["关键词1", "关键词2", "关键词3", "关键词4"],
  "sources": ["[本地: 文件名 第X页]", "[本地: 文件名 第Y页]"]
}

注意：如果片段内容不足以出一道有意义的题目，返回 {"skip": true}"""


def load_index() -> DocumentIndex:
    print("正在加载课件索引...")
    index = DocumentIndex()
    loaded = 0
    for path in sorted(DATA_DIR.iterdir()):
        if path.suffix.lower() in {".pdf", ".pptx", ".ppt", ".txt", ".md"}:
            index.add_file(path)
            loaded += 1
    if loaded == 0:
        raise RuntimeError(f"data/ 目录下没有课件文件，请先上传课件到 {DATA_DIR}")
    print(f"  已加载 {loaded} 个文件，共 {len(index.chunks)} 个 chunk")
    return index


def retrieve_for_seed(index: DocumentIndex, seed: str) -> list:
    """对种子问题检索，返回 top-4 片段。"""
    if not index.ready:
        return []
    docs, best_sim, _ = index.retriever.similarity_search_multi(seed, llm=None)
    return docs[:4]  # 取前4个片段


def format_retrieved_context(docs: list) -> str:
    """格式化检索片段，供 LLM 看着出题。"""
    parts = []
    for i, (doc, _) in enumerate(docs, 1):
        loc = doc.page_content.split("\n", 1)[0] if "\n" in doc.page_content else ""
        text = doc.metadata.get("raw_content", doc.page_content)
        parts.append(f"片段{i}：\n{loc}\n{text[:600]}")
    return "\n\n".join(parts)


def gen_one_question(llm, docs: list) -> dict | None:
    """基于检索片段出一道题，失败返回 None。"""
    if not docs:
        return None
    context = format_retrieved_context(docs)

    from langchain_core.messages import HumanMessage, SystemMessage
    try:
        resp = llm.invoke([
            SystemMessage(content=GEN_PROMPT),
            HumanMessage(content=f"检索到的片段：\n\n{context}"),
        ])
        raw = resp.content.strip()
        # 提取 JSON
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())

        # 跳过标记
        if data.get("skip"):
            return None

        # 基本校验
        if not data.get("question") or not data.get("answer") or not data.get("keywords"):
            return None

        # 如果 sources 缺失，自动从 docs 提取
        if not data.get("sources"):
            data["sources"] = [d.page_content.split("\n")[0] for d, _ in docs if d.page_content.startswith("[本地:")]

        data["auto"] = True
        return data
    except Exception as e:
        return None


def load_manual_questions() -> list[dict]:
    """加载人工题目。"""
    if not MANUAL_PATH.exists():
        return []
    with open(MANUAL_PATH, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  已加载 {len(data)} 道人工题目")
    return data


def main():
    random.seed(42)
    llm = get_llm()
    index = load_index()
    manual_qs = load_manual_questions()

    # 扩充种子池：从课件里再抽一些真实问题作为检索种子
    extended_seeds = list(SEED_QUESTIONS)

    print(f"\n开始生成 {TARGET_AUTO} 道自动题目...")
    print(f"使用 {len(extended_seeds)} 个种子问题进行检索出题")

    questions = list(manual_qs)
    success = 0
    fail = 0

    # 对每个种子问题检索并出题，直到满足数量
    for attempt in range(TARGET_AUTO * 3):  # 多跑几轮确保够数
        if success >= TARGET_AUTO:
            break

        seed = extended_seeds[attempt % len(extended_seeds)]
        print(f"  [{success+1}/{TARGET_AUTO}] 种子: {seed[:30]}...", end=" ")

        # 检索
        docs = retrieve_for_seed(index, seed)
        if not docs:
            print("无结果")
            fail += 1
            continue

        # 出题
        q = gen_one_question(llm, docs)
        if q:
            questions.append(q)
            success += 1
            print("✓")
        else:
            fail += 1
            print("✗")

        time.sleep(0.3)

    print(f"\n完成：成功 {success} 道，失败 {fail} 道，人工 {len(manual_qs)} 道")
    print(f"共 {len(questions)} 道题目写入 {OUTPUT_PATH}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print("done.")


if __name__ == "__main__":
    main()
