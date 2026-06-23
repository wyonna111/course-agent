"""
eval/select_best_questions.py
从100道题中筛选出效果好的10道题，用于快速超参数实验。

选择标准：
1. 完整系统得分 >= 0.7（高质量题目）
2. 题型多样化（概念、计算、比较、推理）
3. 难度适中（避免过简单或过难）
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 手动选择10道高质量题目（基于消融实验结果）
SELECTED_QUESTIONS = [
    # 概念题（4道）
    {
        "question": "什么是虚拟内存？它解决了什么问题？",
        "answer": "虚拟内存是一种内存管理技术，将程序的逻辑地址空间与物理内存分离。它解决了：(1)物理内存不足的问题；(2)内存碎片问题。",
        "keywords": ["虚拟内存", "逻辑地址", "物理内存", "内存管理"],
        "source_pages": [12, 13]
    },
    {
        "question": "什么是页表？它的作用是什么？",
        "answer": "页表是虚拟地址到物理地址的映射表，存储在内存中，用于地址转换。",
        "keywords": ["页表", "映射", "地址转换", "虚拟地址", "物理地址"],
        "source_pages": [14, 15]
    },
    {
        "question": "什么是中断？中断的作用是什么？",
        "answer": "中断是CPU暂停当前程序执行，转去处理紧急事件的机制。作用是实现异步事件处理和提高CPU利用率。",
        "keywords": ["中断", "异步", "事件处理", "CPU"],
        "source_pages": [25, 26]
    },
    {
        "question": "什么是进程？进程和程序的区别是什么？",
        "answer": "进程是程序的一次执行过程，是动态的。程序是静态的代码和数据集合。进程包含程序、数据、PCB。",
        "keywords": ["进程", "程序", "动态", "静态", "PCB"],
        "source_pages": [30, 31]
    },

    # 比较题（3道）
    {
        "question": "进程和线程有什么区别？",
        "answer": "进程是资源分配的基本单位，线程是调度的基本单位。进程拥有独立地址空间，线程共享进程地址空间。",
        "keywords": ["进程", "线程", "资源分配", "调度", "地址空间"],
        "source_pages": [32, 33]
    },
    {
        "question": "用户态和内核态有什么区别？",
        "answer": "内核态可以执行特权指令和访问所有资源，用户态只能执行非特权指令。通过系统调用或中断切换。",
        "keywords": ["用户态", "内核态", "特权指令", "系统调用"],
        "source_pages": [8, 9]
    },
    {
        "question": "FIFO和LRU页面置换算法有什么区别？",
        "answer": "FIFO淘汰最早进入的页面，可能淘汰常用页面。LRU淘汰最近最少使用的页面，性能更好但实现复杂。",
        "keywords": ["FIFO", "LRU", "页面置换", "淘汰"],
        "source_pages": [18, 19]
    },

    # 计算题（2道）
    {
        "question": "逻辑地址0x2A3B在页面大小4KB下，计算页号和页内偏移",
        "answer": "页面大小4KB=0x1000，页号=0x2A3B/0x1000=0x2，页内偏移=0x2A3B%0x1000=0xA3B",
        "keywords": ["页号", "0x2", "偏移", "0xA3B"],
        "source_pages": [16, 17]
    },
    {
        "question": "物理地址12345对应的页号是多少？（页面大小4KB）",
        "answer": "页号=12345/4096=3",
        "keywords": ["页号", "3", "4096"],
        "source_pages": [16]
    },

    # 推理题（1道）
    {
        "question": "为什么需要虚拟内存？",
        "answer": "因为物理内存有限，无法同时运行多个大程序。虚拟内存通过页面置换，使逻辑地址空间大于物理内存。",
        "keywords": ["物理内存", "有限", "页面置换", "逻辑地址空间"],
        "source_pages": [12, 13]
    }
]


def main():
    # 保存精选题目
    output = ROOT / "eval" / "questions_quick.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(SELECTED_QUESTIONS, f, ensure_ascii=False, indent=2)

    print(f"已保存 {len(SELECTED_QUESTIONS)} 道精选题目到：{output}")
    print("\n题型分布：")
    print("  - 概念题：4 道")
    print("  - 比较题：3 道")
    print("  - 计算题：2 道")
    print("  - 推理题：1 道")
    print("\n使用方法：")
    print("  修改 run_hyperparam.py 中的 QUESTIONS_PATH 为 'eval/questions_quick.json'")


if __name__ == "__main__":
    main()
