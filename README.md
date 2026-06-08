# 课内有据（CourseTrace）

> **课内资料优先 · 回答可溯源 · 左上传右对话**

基于大语言模型与本地检索的**课程资料问答助手**。优先依据上传的讲义 / PPT / 文本作答，并在回答中标注**文件名与页码（或幻灯片序号）**，支持整页参考正文展示、协作学习与可选联网补充。

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
3. 小组复习时，**资料与对话难以共享**。

### 核心思路

| 原则 | 做法 |
|------|------|
| **课内优先** | 先检索已上传资料，再组织回答；相关度低时拒答或联网补充 |
| **可溯源** | 回答末尾给出 `[本地: 文件名 第 N 页]`；界面展示送入模型的**整页正文** |
| **按页理解** | PDF/PPT 按**一页一块**索引，减少表格、选项被截断 |
| **协作复习** | 邀请码创建协作空间，共享资料目录与对话记录 |
| **人机协同** | 支持对单页课件人工纠错；可选 DOI 参考文献解析（辅助功能） |

### 技术路线（简述）

```
上传资料 → 解析与分块 → TF-IDF 多路召回 → LLM 语义重排 → 拼接整页上下文 → DeepSeek 作答 → 引用标准化
```

---

## 三人分工

| 成员 | 主要负责 | 主要产出 |
|------|----------|----------|
| **成员 A · 开发与算法** | 检索与对话链路、Streamlit 界面、协作空间、引用与索引逻辑 | `app.py`、`src/retriever.py`、`src/chat.py`、`src/workspace.py` 等 |
| **成员 B · 论文与汇报** | 需求分析、系统架构说明、实验与对比、答辩 PPT / 演示脚本 | 课程报告、架构图、功能演示录屏 |
| **成员 C · 资料与评测** | 嵌入式等课程课件整理、典型问答用例、效果评测与问题反馈 | Demo 问题集、检索/回答样例、纠错样例 |

*具体姓名与学号见课程提交材料；本 README 不收录个人信息。*

---

## 功能一览

| 模块 | 说明 | 状态 |
|------|------|------|
| 多格式资料库 | PDF / PPTX / TXT / MD 上传与索引 | ✅ |
| 可溯源问答 | 页码/幻灯片引用 + 整页参考正文 | ✅ |
| 题型适配 | 概念、对比、推理、按页定位等 prompt 策略 | ✅ |
| LLM 语义重排 | 过滤跑题片段，提升召回质量 | ✅ |
| 联网补充 | 课内不足时检索网络并标注 URL | ✅ |
| 协作空间 | 邀请码加入，共享资料与会话 | ✅ |
| 人工纠错 | 按页修正课件内容并参与检索 | ✅ |
| 参考文献 DOI | 从文本/表格解析 DOI（可选工具） | ✅ |

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
├── app.py                 # Streamlit 主界面
├── assets/                # 布局样式与前端脚本
├── src/
│   ├── loaders.py         # PDF / PPT / 文本加载
│   ├── indexer.py         # 多文件索引
│   ├── retriever.py       # 检索与按页合并
│   ├── llm_rerank.py      # LLM 语义重排
│   ├── chat.py            # 对话与引用格式化
│   ├── workspace.py       # 协作空间
│   ├── corrections.py     # 人工纠错
│   ├── references.py      # 参考文献 / DOI
│   └── web_search.py      # 联网搜索
├── data/                  # 个人模式资料（本地，不入库）
├── workspaces/            # 协作空间数据（本地，不入库）
├── .env.example           # 环境变量示例
└── DEPLOY.md              # Streamlit Cloud 部署说明
```

---

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `OPENAI_API_KEY` | API 密钥（必填） | — |
| `OPENAI_API_BASE` | 兼容接口地址 | `https://api.deepseek.com/v1` |
| `MODEL_NAME` | 模型名称 | `deepseek-chat` |
| `ENABLE_WEB_SEARCH` | 课内不足时联网 | `true` |
| `ENABLE_WORKSPACE` | 协作空间 | `true` |
| `ENABLE_CORRECTIONS` | 人工纠错 | `true` |
| `ENABLE_LLM_RERANK` | LLM 重排 | `true` |
| `ENABLE_REFERENCES` | 参考文献 DOI 工具 | `true` |
| `PUBLIC_APP_URL` | 部署后的公开网址（用于生成协作分享链接） | 空 |

完整示例见 [`.env.example`](./.env.example) 与 [`.streamlit/secrets.toml.example`](./.streamlit/secrets.toml.example)。

---

## 协作空间（简要）

1. 左侧 **协作 → 创建空间**，获得 6 位邀请码  
2. 在**同一套已部署/已运行的实例**上，队友打开 `你的网址/?space=邀请码` 或手动输入邀请码加入  
3. 在协作空间的 **资料库** 中上传并索引课件（与个人模式目录相互独立）  
4. 使用 **同步消息** 拉取最新对话  

---

## 常见问题

| 现象 | 处理建议 |
|------|----------|
| 回答与课件不符 | 查看「课内参考资料」整页正文；尝试换问法或重建索引 |
| 引用格式异常 | 重启应用后再提问；旧会话中的历史格式会在加载时自动修复 |
| PPT 无文字 | 可能为图片型幻灯片，需含可复制文本 |
| 402 / API 错误 | 检查密钥与账户余额 |
| 协作邀请码无效 | 确认队友访问的是**同一部署地址**，而非各自本机 `localhost` |

---

## 小组协作文档

| 目录 | 说明 |
|------|------|
| [docs/TASKS.md](./docs/TASKS.md) | 成员 B/C 任务说明与群公告模板 |
| [docs/report.md](./docs/report.md) | 课程报告模板（B 填写） |
| [docs/architecture.md](./docs/architecture.md) | 系统架构图与说明（B 填写） |
| [docs/demo-script.md](./docs/demo-script.md) | 答辩演示脚本（B 准备） |
| [eval/test_cases.md](./eval/test_cases.md) | 测试问题集（C 填写，≥20 题） |
| [eval/results.md](./eval/results.md) | 评测结果与截图（C 填写） |
| [eval/collab_test.md](./eval/collab_test.md) | 协作空间联调记录（B+C） |

---

## 相关链接

- **仓库**：https://github.com/wyonna111/course-agent  
- **部署说明**：[DEPLOY.md](./DEPLOY.md)  

---

## 致谢

感谢课程提供的算法实践框架与嵌入式系统等相关课件；本项目使用 Streamlit、LangChain、scikit-learn、PyMuPDF 等开源组件。
