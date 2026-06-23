# 课内有据（CourseTrace）

> **课内资料优先 · 回答可溯源 · 智能检索增强**

基于大语言模型与语义检索的**课程资料问答助手**。优先依据上传的讲义 / PPT / 文本作答，并在回答中标注**文件名与页码（或幻灯片序号）**，支持整页参考正文展示、多模块协同优化与完整实验评测。

---

## 课程声明

本项目为**算法实践课程大作业**，由三人小组完成，仅用于课程学习、演示与答辩。

- **版权**：源代码归本小组所有；未经同意请勿直接用于提交其他课程作业或商业用途。
- **资料**：课件 PDF/PPT 等版权归原课程与出版社所有，本仓库**不包含**完整课件，使用者需自行准备合法授权的资料。
- **密钥**：`.env`、Streamlit Secrets 中的 API Key **请勿提交**至公开仓库；公开版仓库已通过 `.gitignore` 排除本地密钥与上传资料。

---

## 项目想法

### 背景与动机

专业课复习时，常见问题包括：

1. 问 AI 容易**脱离课件胡编**，难以核对依据；
2. 课件分散在多份 PDF/PPT 中，**翻页定位慢**；
3. 传统检索方法（TF-IDF）**语义理解不足**，难以匹配同义表达。

### 核心思路

| 原则 | 做法 |
|------|------|
| **课内优先** | 语义向量检索 + LLM 重排 + Self-RAG 反思机制，精准定位相关内容 |
| **可溯源** | 回答末尾给出 `[本地: 文件名 第 N 页]`；界面展示送入模型的**整页正文** |
| **按页理解** | PDF/PPT 按**一页一块**索引，减少表格、选项被截断 |
| **多模块协同** | BGE 语义检索 + LLM 重排 + Self-RAG + 推理模型 + 查询改写 + 联网补充 |
| **实验驱动** | 完整的测评系统（100 道题）+ 超参数调优 + 消融实验 + 基线对比 + 错误分析 |

### 技术路线（完整版）

```
上传资料 → 解析与分块 → BGE 语义向量检索 → LLM 语义重排 → Self-RAG 三阶段反思
         ↓
查询改写（多角度） → Top-K 片段拼接 → DeepSeek-Chat 生成 → DeepSeek-R1 推理增强
         ↓
引用标准化 → 联网补充（可选） → 最终回答
```

---

## 三人分工

| 成员 | 主要负责 | 主要产出 |
|------|----------|----------|
| **成员 A · 核心开发** | 系统架构与核心算法、测评系统与实验、前端界面 | `app.py`、`src/`、`eval/` |
| **成员 B · 论文撰写** | 需求分析、论文撰写、答辩准备 | 课程报告、演示材料 |
| **成员 C · 资料与论文** | 课件整理、测试用例标注、论文撰写 | 种子问题、课件资料 |

*具体姓名与学号见课程提交材料；本 README 不收录个人信息。*

---

## 功能一览

| 模块 | 说明 | 状态 |
|------|------|------|
| 语义向量检索 | BGE (BAAI/bge-small-zh-v1.5) 替代 TF-IDF，稠密向量检索 + 余弦相似度 | ✅ |
| LLM 语义重排 | DeepSeek-Chat 过滤低质量片段，提升召回精度 | ✅ |
| Self-RAG 反思 | 三阶段反思（检索必要性、片段相关性、答案充分性），闲聊跳过检索 | ✅ |
| 推理模型增强 | DeepSeek-R1 处理计算题（地址计算、浮点转换等） | ✅ |
| 查询改写 | LLM 生成多角度查询变体，提高召回全面性 | ✅ |
| 多模态图片理解 | Qwen-VL 提取 PDF/PPT 图片描述，支持用户上传图片提问 | ✅ |
| 可溯源问答 | 页码/幻灯片引用 + 整页参考正文 | ✅ |
| 联网补充 | 课内不足时检索网络并标注 URL | ✅ |
| 多格式资料库 | PDF / PPTX / TXT / MD 上传与索引 | ✅ |
| 完整测评系统 | 100 道题 + 自动评分 + 三维指标（关键词命中、引用正确、拒答率） | ✅ |

---

## 系统性能（实验结果）

基于 100 道嵌入式课程测试题的评测结果：

| 指标 | 完整系统 | TF-IDF 基线 | 提升幅度 |
|------|---------|-----------|---------|
| **综合得分** | 0.7411 | 0.5950 | +24.5% |
| **通过率** | 91% | 68% | +33.8% |
| **拒答率** | 4% | 25% | -84.0% |
| **关键词命中率** | 0.7502 | 0.6081 | +23.4% |
| **响应时间** | 16.2s | 12.3s | +31.5% |

**相比已发表方法的提升**：
- 相比 Vanilla RAG (NeurIPS 2020)：综合得分 +12.6%，通过率 +16.7%
- 相比 Self-RAG (NeurIPS 2023)：综合得分 +7.6%，通过率 +11.0%

---

## 快速开始（本地）

**环境**：Python 3.11+，OpenAI 兼容 API（默认 DeepSeek）。

```bash
git clone https://github.com/wyonna111/course-agent.git
cd course-agent

python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY

streamlit run app.py
```

浏览器打开提示的本地地址后：

1. 左侧 **资料库** 上传讲义 / PPT  
2. 点击 **解析并加入索引**  
3. 右侧输入问题；展开 **课内参考资料** 可查看整页正文  

公网部署（供队友仅浏览器访问）见 **[DEPLOY.md](./DEPLOY.md)**。

---

## 项目结构

```
course-agent/
├── app.py                        # Streamlit 主界面
├── assets/                       # 布局样式与前端脚本
├── src/
│   ├── loaders.py                # PDF / PPT / 文本加载
│   ├── indexer.py                # 多文件索引
│   ├── embedding_retriever.py    # BGE 语义向量检索
│   ├── llm_rerank.py             # LLM 语义重排
│   ├── chat.py                   # 对话链路与 Self-RAG 反思
│   ├── workspace.py              # 协作空间（已移除）
│   └── web_search.py             # 联网搜索
├── eval/                         # 完整测评系统
│   ├── gen_questions.py          # 测试集生成（20 → 100 道）
│   ├── run_eval.py               # 自动评测与打分
│   ├── run_hyperparam.py         # 超参数调优实验
│   ├── baseline_comparison.py    # 基线方法对比
│   ├── error_analysis.py         # 错误分析与分类
│   ├── plot_all_figures.py       # 生成 4 个高清图表
│   └── questions.json            # 100 道测试题（不入库）
├── data/                         # 资料库（本地，不入库）
├── .env.example                  # 环境变量示例
└── requirements.txt              # Python 依赖
```

---

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `OPENAI_API_KEY` | API 密钥（必填） | — |
| `OPENAI_API_BASE` | 兼容接口地址 | `https://api.deepseek.com/v1` |
| `MODEL_NAME` | 主模型名称 | `deepseek-chat` |
| `REASONING_MODEL_NAME` | 推理模型 | `deepseek-reasoner` |
| `ENABLE_WEB_SEARCH` | 联网补充 | `true` |
| `ENABLE_LLM_RERANK` | LLM 重排 | `true` |
| `ENABLE_SELF_RAG` | Self-RAG 反思 | `true` |
| `USE_LLM_REWRITE_QUERY` | 查询改写 | `true` |
| `TOP_K` | 送入 LLM 的片段数 | `3` |
| `MIN_RELEVANCE` | 最低相关性阈值 | `0.02` |
| `TOP_K_RETRIEVE` | 初始召回数 | `10` |

完整示例见 [`.env.example`](./.env.example)。

---

## 测评系统

### 测试集构建

- **种子问题**：标注 20 道题（含标准答案、关键词、来源页码）
- **自动扩展**：基于种子问题使用 LLM 生成 80 道题，扩展到 100 道
- **质量保证**：去重、人工审核、难度校准

### 评测指标

三维评分体系（自动化评测）：

- **关键词命中率**（60%）：答案包含标准答案关键词的比例
- **引用正确率**（20%）：检索片段来源页码正确的比例
- **未拒答率**（20%）：系统给出实质性答案的比例

### 运行测评

```bash
# 生成测试集（基于 20 道种子扩展到 100 道）
python eval/gen_questions.py

# 运行完整评测
python eval/run_eval.py

# 超参数调优实验
python eval/run_hyperparam.py

# 基线方法对比实验
python eval/baseline_comparison.py

# 生成实验可视化（4 个图表，300 DPI）
python eval/plot_all_figures.py
```

生成的可视化图表保存在 `eval/figures/` 目录。

---

## 常见问题

| 现象 | 处理建议 |
|------|----------|
| 回答与课件不符 | 查看「课内参考资料」整页正文；尝试换问法或重建索引 |
| 引用格式异常 | 重启应用后再提问；旧会话中的历史格式会在加载时自动修复 |
| 402 / API 错误 | 检查密钥与账户余额 |
| 测评运行缓慢 | 100 道题约需 30 分钟，可使用 `--limit` 参数测试前 N 道 |

---

## 技术栈

- **前端**：Streamlit
- **语义检索**：BGE (BAAI/bge-small-zh-v1.5)
- **大语言模型**：DeepSeek-Chat、DeepSeek-R1
- **文档解析**：PyMuPDF、python-pptx
- **向量检索**：scikit-learn
- **实验可视化**：matplotlib、numpy

---

## 相关链接

- **仓库**：https://github.com/wyonna111/course-agent  
- **部署说明**：[DEPLOY.md](./DEPLOY.md)  

---

## 致谢

感谢课程提供的算法实践框架与嵌入式相关课件；本项目使用 Streamlit、PyMuPDF、scikit-learn、matplotlib 等开源组件。特别感谢 DeepSeek 提供的 API 服务和 BAAI 提供的 BGE 中文语义模型。
