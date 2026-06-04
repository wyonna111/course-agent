"""文档切分与索引管理（支持多文件累积）"""

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR
from src.loaders import load_documents, location_label
from src.retriever import TfidfRetriever


def split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )
    chunks: list[Document] = []
    for doc in docs:
        page = doc.metadata.get("page", 0)
        source_name = doc.metadata.get("source_name", "未知")
        doc_type = doc.metadata.get("doc_type", "file")
        # PDF/PPT 按页加载：一页一块，避免长页表格被截断导致分析全错
        if doc_type in ("pdf", "pptx"):
            pieces = [doc]
        else:
            pieces = splitter.split_documents([doc])
        for piece in pieces:
            piece.metadata["page"] = page
            piece.metadata["source_name"] = source_name
            piece.metadata["doc_type"] = doc_type
            if doc.metadata.get("display_page") is not None:
                piece.metadata["display_page"] = doc.metadata["display_page"]
            elif doc.metadata.get("slide") is not None:
                piece.metadata["display_page"] = doc.metadata["slide"]
            else:
                piece.metadata["display_page"] = int(page) + 1
            if doc_type == "pptx":
                piece.metadata["slide"] = doc.metadata.get("slide", int(page) + 1)
            raw = piece.page_content.strip()
            piece.metadata["raw_content"] = raw
            loc = location_label(piece.metadata)
            piece.page_content = f"{loc}\n{raw}"
            chunks.append(piece)
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
        self.retriever = TfidfRetriever(self.chunks)
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
