"""PDF text extraction, OCR fallback and page-preserving Markdown conversion."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    method: str
    confidence: float | None = None


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    path: Path
    pages: list[PageText]
    markdown: str
    quality: str
    warnings: list[str]


def _clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _ocr_page(image) -> tuple[str, float | None]:
    try:
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "扫描 PDF 需要 rapidocr==3.9.1 和 onnxruntime；请先安装 requirements.txt。"
        ) from exc

    model_dir = os.getenv("RAPIDOCR_MODEL_DIR")
    offline = os.getenv("RAPIDOCR_OFFLINE", "0").lower() in {"1", "true", "yes"}
    if offline:
        if not model_dir or not Path(model_dir).is_dir():
            raise RuntimeError("RAPIDOCR_OFFLINE=1 时必须配置存在的 RAPIDOCR_MODEL_DIR")
        expected = {
            "PP-OCRv6_det_small.onnx",
            "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
            "PP-OCRv6_rec_small.onnx",
        }
        missing = [name for name in expected if not (Path(model_dir) / name).is_file()]
        if missing:
            raise RuntimeError(f"离线 OCR 模型缺失：{', '.join(missing)}")
    params = {"Global.model_root_dir": model_dir} if model_dir else None
    result = RapidOCR(params=params)(image)
    texts: list[str] = []
    scores: list[float] = []
    if hasattr(result, "txts"):
        texts = [str(item) for item in (result.txts or [])]
        scores = [float(item) for item in (getattr(result, "scores", None) or [])]
    elif isinstance(result, tuple) and result:
        rows = result[0] or []
        for row in rows:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                texts.append(str(row[1]))
                if len(row) >= 3:
                    scores.append(float(row[2]))
    elif isinstance(result, list):
        for row in result:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                texts.append(str(row[1]))
                if len(row) >= 3:
                    scores.append(float(row[2]))
    confidence = sum(scores) / len(scores) if scores else None
    return _clean_text(" ".join(texts)), confidence


def parse_pdf(path: Path, document_id: str | None = None, *, ocr_dpi: int = 200) -> ParsedDocument:
    """Parse a PDF one page at a time and retain the source page number."""
    path = path.resolve()
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"只支持 PDF 输入：{path.name}")
    if not path.is_file():
        raise FileNotFoundError(path)

    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("缺少 pdfplumber，请安装 requirements.txt。") from exc

    pages: list[PageText] = []
    warnings: list[str] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = _clean_text(page.extract_text())
            if len(re.sub(r"\s", "", text)) >= 30:
                pages.append(PageText(number, text, "text", 1.0))
                continue

            try:
                import pypdfium2 as pdfium
                pdf_doc = pdfium.PdfDocument(str(path))
                pdf_page = pdf_doc[number - 1]
                bitmap = pdf_page.render(scale=ocr_dpi / 72)
                image = bitmap.to_pil()
                ocr_text, confidence = _ocr_page(image)
                text = ocr_text or text
                pages.append(PageText(number, text, "ocr", confidence))
            except Exception as exc:  # OCR is a recoverable page-level failure.
                warnings.append(f"第 {number} 页 OCR 失败：{type(exc).__name__}")
                pages.append(PageText(number, text, "text-fallback", None))

    if not pages:
        raise ValueError("PDF 未解析出任何页面")
    ocr_pages = sum(item.method == "ocr" for item in pages)
    low_confidence = any(item.confidence is not None and item.confidence < 0.80 for item in pages)
    quality = "low" if warnings or low_confidence else ("medium" if ocr_pages else "high")
    doc_id = document_id or hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    markdown = "\n\n".join(
        f"## Page {item.page}\n\n{item.text or '[本页未识别到文字]'}"
        for item in pages
    )
    return ParsedDocument(doc_id, path, pages, markdown, quality, warnings)


def stage_input(source: Path, input_root: Path, *, document_id: str | None = None) -> tuple[str, Path]:
    """Copy a user-selected PDF into the controlled workspace input directory."""
    source = source.expanduser().resolve()
    if source.suffix.lower() != ".pdf" or not source.is_file():
        raise ValueError("输入必须是存在的 PDF 文件")
    input_root = input_root.resolve()
    input_root.mkdir(parents=True, exist_ok=True)
    doc_id = document_id or hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:12]
    destination = (input_root / f"{doc_id}{source.suffix.lower()}").resolve()
    if input_root not in destination.parents:
        raise ValueError("非法输入路径")
    if source != destination:
        import shutil
        shutil.copy2(source, destination)
    return doc_id, destination
