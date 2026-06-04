"""全局配置（Phase 2 功能通过环境变量开关，默认关闭）"""

import os
from pathlib import Path

from src.env_bootstrap import bootstrap_env

bootstrap_env()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = BASE_DIR / "workspaces"
CHAT_HISTORY_PATH = DATA_DIR / "chat_history.json"

# 文本切分
CHUNK_SIZE = 500
CHUNK_OVERLAP = 60
MIN_TEXT_LEN = 30

# 检索
TOP_K = 4  # 送入大模型的片段数（重排过滤后）
TOP_K_RETRIEVE = 10  # 每路 query 先召回条数
RETRIEVE_POOL = 40
MAX_CHUNKS_PER_PAGE = 1
MIN_RELEVANCE = 0.03

# 对话
MAX_HISTORY_TURNS = 6
UI_PANEL_HEIGHT = int(os.getenv("UI_PANEL_HEIGHT", "700"))

# Phase 2 开关（联网搜索默认开启）
ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true"
ENABLE_CORRECTIONS = os.getenv("ENABLE_CORRECTIONS", "true").lower() == "true"
ENABLE_WORKSPACE = os.getenv("ENABLE_WORKSPACE", "true").lower() == "true"
USE_LLM_REWRITE_QUERY = os.getenv("USE_LLM_REWRITE_QUERY", "false").lower() == "true"
ENABLE_LLM_RERANK = os.getenv("ENABLE_LLM_RERANK", "true").lower() == "true"
LLM_RERANK_MAX_CHUNKS = int(os.getenv("LLM_RERANK_MAX_CHUNKS", "12"))
LLM_RERANK_PREVIEW_CHARS = int(os.getenv("LLM_RERANK_PREVIEW_CHARS", "700"))

# Phase 3：参考文献 / DOI
ENABLE_REFERENCES = os.getenv("ENABLE_REFERENCES", "true").lower() == "true"
CROSSREF_MAILTO = os.getenv("CROSSREF_MAILTO", "").strip()
REFERENCE_FETCH_TIMEOUT = int(os.getenv("REFERENCE_FETCH_TIMEOUT", "8"))
REFERENCE_FETCH_META = os.getenv("REFERENCE_FETCH_META", "true").lower() == "true"
REFERENCE_CROSSREF_SEARCH = os.getenv("REFERENCE_CROSSREF_SEARCH", "true").lower() == "true"
REFERENCE_CROSSREF_MIN_SCORE = float(os.getenv("REFERENCE_CROSSREF_MIN_SCORE", "28"))

# 部署后填公开网址，协作页会生成完整分享链接（可选）
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
