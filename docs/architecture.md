# 系统架构说明（成员 B 填写）

> B 可据此图用 draw.io / ProcessOn 重绘为 `architecture.png` 放入答辩 PPT。  
> 下方 Mermaid 图可在 GitHub 或支持 Mermaid 的编辑器中直接预览。

---

## 总体架构

```mermaid
flowchart TB
    subgraph 用户层
        U[浏览器 · Streamlit UI]
    end

    subgraph 应用层["应用层 app.py"]
        UP[资料库上传]
        CH[对话问答]
        WS[协作空间]
        CR[人工纠错]
        RF[参考文献 DOI]
    end

    subgraph 核心层["核心层 src/"]
        LD[loaders.py<br/>PDF/PPT/TXT 解析]
        IX[indexer.py<br/>按页索引]
        RT[retriever.py<br/>TF-IDF 多路召回]
        RR[llm_rerank.py<br/>LLM 语义重排]
        QT[question_types.py<br/>题型判定]
        CT[chat.py<br/>作答与引用格式化]
        WB[web_search.py<br/>联网补充]
    end

    subgraph 外部服务
        LLM[DeepSeek API]
        WEB[DuckDuckGo 搜索]
        CRREF[CrossRef API]
    end

    subgraph 存储
        DATA[(data/ 个人资料)]
        WSP[(workspaces/ 协作数据)]
    end

    U --> UP & CH & WS & CR & RF
    UP --> LD --> IX --> RT
    CH --> RT --> RR --> QT --> CT
    CT --> LLM
    RT --> WB --> WEB
    WB --> CT
    RF --> CRREF
    IX --> DATA
    WS --> WSP
    CR --> WSP
```

---

## 问答链路（单次提问）

```mermaid
sequenceDiagram
    participant 用户
    participant app.py
    participant retriever
    participant llm_rerank
    participant chat
    participant DeepSeek

    用户->>app.py: 输入问题
    app.py->>retriever: TF-IDF 多路召回
    retriever->>llm_rerank: Top-K 候选片段
    llm_rerank->>DeepSeek: 语义打分重排
    DeepSeek-->>llm_rerank: 相关度与理由
    llm_rerank-->>app.py: 过滤后整页上下文
    alt 课内相关度不足且开启联网
        app.py->>app.py: web_search 检索网络
    end
    app.py->>chat: 组织 prompt + 历史
    chat->>DeepSeek: 生成回答
    DeepSeek-->>chat: 带引用格式的回答
    chat-->>app.py: 回答 + 参考资料
    app.py-->>用户: 展示回答与整页正文
```

---

## 模块说明表 【B 可补充】

| 模块 | 文件 | 职责 |
|------|------|------|
| 界面 | `app.py` | Streamlit 双栏布局、上传、对话、协作 |
| 加载 | `loaders.py` | PDF/PPT/TXT 解析，按页元数据 |
| 索引 | `indexer.py` | 多文件累积索引、重建 |
| 检索 | `retriever.py` | TF-IDF、多 query 召回、按页合并 |
| 重排 | `llm_rerank.py` | LLM 过滤跑题片段 |
| 对话 | `chat.py` | Prompt 策略、引用格式化 |
| 协作 | `workspace.py` | 邀请码、共享目录、消息同步 |
| 纠错 | `corrections.py` | 按页修正并参与检索 |
| 联网 | `web_search.py` | 课内不足时补充网络来源 |

---

## 部署架构（可选，答辩用）

```mermaid
flowchart LR
    GH[GitHub 仓库] -->|Deploy Key| SC[Streamlit Cloud]
    SC --> APP[streamlit.app 公网地址]
    APP --> U1[成员 A 浏览器]
    APP --> U2[成员 B 浏览器]
    APP --> U3[成员 C 浏览器]
    SC --> SEC[Streamlit Secrets<br/>API Key 等]
```

填写说明：若已部署，在图中标注实际 App 地址。
