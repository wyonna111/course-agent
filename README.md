# 课内有据 — 课程资料可溯源答疑 Agent

> **课内资料优先 · 回答可溯源 · 左上传右对话**

## 快速开始

```powershell
cd "d:\HuaweiMoveData\Users\Wyonn\Desktop\算法实践大作业\course-agent"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
copy .env.example .env
# 编辑 .env 填入 DeepSeek / OpenAI 兼容 API Key
streamlit run app.py
```

浏览器打开后：

1. **左侧**上传 PDF / PPTX / TXT（可多个文件）
2. 点击 **「解析并加入索引」**
3. **右侧**像聊天一样提问，回答末尾带「引用：文件名 + 页码/幻灯片」

## 功能路线图

| 阶段 | 功能 | 状态 |
|------|------|------|
| **Phase 1** | 多格式上传、多文件索引、可溯源问答、低相关度拒答 | ✅ 当前 |
| Phase 2 | 联网补充（带 URL）、人工纠错 | 🔜 `src/web_search.py` `src/corrections.py` |
| Phase 2 | 多人共享学习空间 | 🔜 `src/workspace.py` |
| Phase 3 | 论文参考文献 DOI 链接 | 🔜 `src/references.py` |

## 项目结构

```
course-agent/
├── app.py              # Streamlit 主界面
├── src/
│   ├── config.py       # 配置与 Phase 开关
│   ├── loaders.py      # PDF / PPT / TXT 加载
│   ├── indexer.py      # 多文件索引管理
│   ├── retriever.py    # TF-IDF 检索
│   ├── chat.py         # 大模型对话
│   ├── web_search.py   # Phase 2 联网（桩）
│   ├── corrections.py  # Phase 2 纠错（桩）
│   ├── workspace.py    # Phase 2 协作（桩）
│   └── references.py   # Phase 3 文献链接（桩）
├── data/               # 上传的资料（自动创建）
└── .env                # API 密钥（勿提交）
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | 必填，DeepSeek 等兼容密钥 |
| `OPENAI_API_BASE` | 默认 `https://api.deepseek.com/v1` |
| `MODEL_NAME` | 默认 `deepseek-chat` |
| `ENABLE_WEB_SEARCH` | Phase 2，默认 `false` |
| `ENABLE_WORKSPACE` | Phase 2，默认 `false` |

## 常见问题

| 问题 | 处理 |
|------|------|
| 回答瞎编 | 先看「本轮参考的资料片段」；相关度太低会自动拒答 |
| PPT 读不到字 | 可能是图片型幻灯片，需含可复制文字 |
| 扫描版 PDF | 换可复制文字版或 .txt |
| 402 错误 | API 余额不足，请充值 |

## 三人分工提示

- **开发**：Phase 2 从 `web_search.py` / `workspace.py` 开始接
- **论文+汇报**：用 Phase 1 demo 录屏与截图
- **资料+Demo**：整理嵌入式课件、写 10 个 demo 用例
