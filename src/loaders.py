"""多格式文档加载：PDF / PPT / TXT"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from src.config import MIN_TEXT_LEN


def _load_pdf(file_path: Path) -> list[Document]:
    docs = PyPDFLoader(str(file_path)).load()
    result: list[Document] = []
    for d in docs:
        text = (d.page_content or "").strip()
        page = d.metadata.get("page", len(result))
        if len(text) < MIN_TEXT_LEN:
            text = text or "（本页未提取到可检索文字，可能为图片或空白页）"
        d.page_content = text
        d.metadata["doc_type"] = "pdf"
        d.metadata["source_name"] = file_path.name
        d.metadata["display_page"] = int(page) + 1
        result.append(d)

    if len(result) >= 2:
        return result

    try:
        import fitz

        pdf = fitz.open(str(file_path))
        docs = []
        for i, page in enumerate(pdf):
            text = (page.get_text() or "").strip()
            if len(text) < MIN_TEXT_LEN:
                text = text or "（本页未提取到可检索文字，可能为图片或空白页）"
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "page": i,
                        "display_page": i + 1,
                        "source": str(file_path),
                        "source_name": file_path.name,
                        "doc_type": "pdf",
                    },
                )
            )
        pdf.close()
        if docs:
            return docs
    except ImportError:
        pass

    if not docs:
        raise ValueError(
            f"{file_path.name} 几乎读不到文字（可能是扫描版 PDF）。"
            "请换可复制文字的 PDF 或导出为 .txt"
        )
    for d in docs:
        d.metadata.setdefault("doc_type", "pdf")
        d.metadata.setdefault("source_name", file_path.name)
    return docs


def _load_pptx(file_path: Path) -> list[Document]:
    try:
        from pptx import Presentation
    except ImportError as e:
        raise ImportError("请安装 python-pptx：pip install python-pptx") from e

    prs = Presentation(str(file_path))
    docs: list[Document] = []
    for i, slide in enumerate(prs.slides):
        parts: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                parts.append(shape.text.strip())
        text = "\n".join(parts).strip()
        if len(text) < MIN_TEXT_LEN:
            text = text or "（本幻灯片未提取到可检索文字，可能为图片页）"
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "page": i,
                    "slide": i + 1,
                    "display_page": i + 1,
                    "source": str(file_path),
                    "source_name": file_path.name,
                    "doc_type": "pptx",
                },
            )
        )
    if not docs:
        raise ValueError(f"{file_path.name} 中未读到有效文字（可能多为图片幻灯片）")
    return docs


def _load_text(file_path: Path) -> list[Document]:
    docs = TextLoader(str(file_path), encoding="utf-8").load()
    for d in docs:
        d.metadata["doc_type"] = "text"
        d.metadata["source_name"] = file_path.name
        d.metadata["page"] = 0
    return docs


def load_documents(file_path: Path) -> list[Document]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(file_path)
    if suffix in {".pptx", ".ppt"}:
        return _load_pptx(file_path)
    if suffix in {".txt", ".md"}:
        return _load_text(file_path)
    raise ValueError(f"不支持的格式：{suffix}，目前支持 PDF / PPTX / TXT / MD")


def location_label(meta: dict) -> str:
    """生成可溯源位置标签，供引用展示。"""
    name = meta.get("source_name") or Path(meta.get("source", "未知文件")).name
    doc_type = meta.get("doc_type", "file")
    if doc_type == "pptx":
        slide = meta.get("slide") or int(meta.get("page", 0)) + 1
        return f"[本地: {name} 幻灯片 {slide}]"
    page = meta.get("page")
    if page is not None:
        return f"[本地: {name} 第 {int(page) + 1} 页]"
    return f"[本地: {name}]"
