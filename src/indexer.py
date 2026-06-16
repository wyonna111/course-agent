"""文档切分与索引管理（支持多文件累积）"""

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR, RETRIEVER_TYPE
from src.loaders import load_documents, location_label
from src.retriever import TfidfRetriever

# 自适应切分阈值
_SHORT_PAGE = 300    # 低于此值：整页保留，内容太少切了没意义
_LONG_PAGE = 800     # 超过此值：需要切分，避免长页占满 context window
_OVERLAP_LONG = 80   # 长页切分时的重叠字符数


def _make_retriever(chunks: list[Document]):
    if RETRIEVER_TYPE == "embedding":
        from src.embedding_retriever import EmbeddingRetriever
        return EmbeddingRetriever(chunks)
    return TfidfRetriever(chunks)


def _adaptive_split(text: str) -> list[str]:
    """
    自适应切分：根据页面文字密度决定切分策略。

    短页（<300字）  → 整页不切，保留完整上下文
    中等页（300-800字）→ 整页不切，内容量适中
    长页（>800字）  → 按段落/句号语义切分，块大小动态调整为页长的 1/2
    """
    length = len(text)
    if length <= _LONG_PAGE:
        return [text]

    # 长页：块大小取页长一半（上限 CHUNK_SIZE），让每块有实质内容
    adaptive_size = min(length // 2, CHUNK_SIZE)
    adaptive_overlap = min(_OVERLAP_LONG, adaptive_size // 6)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=adaptive_size,
        chunk_overlap=adaptive_overlap,
        separators=["\n\n", "\n", "。", "；", "！", "？", " ", ""],
    )
    pieces = splitter.split_text(text)
    # 过滤掉切出来的过短碎片（<50字），合并到前一块
    merged: list[str] = []
    for p in pieces:
        if len(p) < 50 and merged:
            merged[-1] = merged[-1] + p
        else:
            merged.append(p)
    return merged if merged else [text]


def split_documents(docs: list[Document]) -> list[Document]:
    chunks: list[Document] = []
    for doc in docs:
        page = doc.metadata.get("page", 0)
        source_name = doc.metadata.get("source_name", "未知")
        doc_type = doc.metadata.get("doc_type", "file")
        raw_text = doc.page_content.strip()

        if doc_type in ("pdf", "pptx"):
            # PDF/PPT：自适应切分——短页整页保留，长页按语义切分
            pieces_text = _adaptive_split(raw_text)
        else:
            # TXT/MD：仍用固定大小切分
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                separators=["\n\n", "\n", "。", "！", "？", " ", ""],
            )
            pieces_text = splitter.split_text(raw_text) or [raw_text]

        for piece_text in pieces_text:
            meta = dict(doc.metadata)
            meta["page"] = page
            meta["source_name"] = source_name
            meta["doc_type"] = doc_type
            meta["raw_content"] = piece_text
            meta["chunk_len"] = len(piece_text)  # 记录实际块长，便于调试
            if doc.metadata.get("display_page") is not None:
                meta["display_page"] = doc.metadata["display_page"]
            elif doc.metadata.get("slide") is not None:
                meta["display_page"] = doc.metadata["slide"]
            else:
                meta["display_page"] = int(page) + 1
            if doc_type == "pptx":
                meta["slide"] = doc.metadata.get("slide", int(page) + 1)
            loc = location_label(meta)
            chunk = Document(
                page_content=f"{loc}\n{piece_text}",
                metadata=meta,
            )
            chunks.append(chunk)
    return chunks


class DocumentIndex:
    """管理已上传文件的向量索引。"""

    def __init__(self):
        self.chunks: list[Document] = []
        self.indexed_files: list[str] = []
        self.retriever: TfidfRetriever | None = None

    def add_file(self, file_path: Path) -> dict:
        page_docs = load_documents(file_path)
        new_chunks = split_documents(page_docs)
        # 同一文件重复上传则替换旧块
        name = file_path.name
        if name in self.indexed_files:
            self.chunks = [c for c in self.chunks if c.metadata.get("source_name") != name]
            self.indexed_files.remove(name)
        self.chunks.extend(new_chunks)
        self.indexed_files.append(name)
        self.retriever = _make_retriever(self.chunks)
        return {
            "file": name,
            "new_chunks": len(new_chunks),
            **self.retriever.stats,
        }

    def rebuild_from_data_dir(self, data_dir: Path | None = None) -> dict:
        root = data_dir if data_dir is not None else DATA_DIR
        root.mkdir(parents=True, exist_ok=True)
        self.chunks = []
        self.indexed_files = []
        added = 0
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix.lower() in {
                ".pdf",
                ".pptx",
                ".ppt",
                ".txt",
                ".md",
            }:
                self.add_file(path)
                added += 1
        if not self.retriever:
            raise ValueError(f"{root} 目录下没有可解析的文件")
        return {"rebuilt_files": added, **self.retriever.stats}

    @property
    def ready(self) -> bool:
        return self.retriever is not None
