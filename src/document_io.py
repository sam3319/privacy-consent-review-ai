import re
from io import BytesIO
from pathlib import Path

from docx import Document
from PIL import Image
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}
MAX_OCR_PAGES = 20


def _extract_ocr_text(content: bytes, extension: str) -> str:
    return "\n".join(page["text"] for page in _extract_ocr_pages(content, extension))


def _extract_ocr_pages(content: bytes, extension: str) -> list[dict]:
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError as error:
        raise ValueError(
            "OCR Python 패키지가 설치되지 않았습니다. requirements.txt를 다시 설치하세요."
        ) from error

    try:
        if extension == ".pdf":
            images = convert_from_bytes(
                content,
                dpi=200,
                first_page=1,
                last_page=MAX_OCR_PAGES,
            )
        else:
            images = [Image.open(BytesIO(content))]
        pages = []
        for index, image in enumerate(images, 1):
            text = pytesseract.image_to_string(image, lang="kor+eng")
            pages.append(
                {
                    "page": index,
                    "text": text,
                    "quality": estimate_text_quality(text),
                    "method": "ocr",
                }
            )
    except Exception as error:
        raise ValueError(
            "OCR 실행에 실패했습니다. Tesseract 한국어 언어팩과 PDF 변환 도구 설치를 확인하세요."
        ) from error

    if not any(page["text"].strip() for page in pages):
        raise ValueError("OCR에서 읽을 수 있는 텍스트를 찾지 못했습니다.")
    return pages


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg"}:
        return _extract_ocr_text(content, extension)
    return extract_text_with_details(filename, content)["text"]


def extract_text_with_details(filename: str, content: bytes) -> dict:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("지원 형식은 TXT, PDF, DOCX입니다.")

    if extension == ".txt":
        text = content.decode("utf-8-sig")
        pages = [_page_detail(1, text, "text")]
        return {"text": text, "pages": pages}
    if extension == ".pdf":
        reader = PdfReader(BytesIO(content))
        pages = [
            _page_detail(index, page.extract_text() or "", "pdf_text")
            for index, page in enumerate(reader.pages, 1)
        ]
        text = "\n".join(page["text"] for page in pages)
        if not text.strip():
            pages = _extract_ocr_pages(content, extension)
            text = "\n".join(page["text"] for page in pages)
        return {"text": text, "pages": pages}
    if extension in {".png", ".jpg", ".jpeg"}:
        pages = _extract_ocr_pages(content, extension)
        return {"text": pages[0]["text"], "pages": pages}

    document = Document(BytesIO(content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    return {"text": text, "pages": [_page_detail(1, text, "docx")]}


def estimate_text_quality(text: str) -> dict:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return {"score": 0, "label": "낮음"}
    readable = len(re.findall(r"[가-힣A-Za-z0-9]", compact))
    replacement = compact.count("�")
    symbol_noise = len(re.findall(r"[^\w가-힣.,:;()/%+-]", compact))
    score = max(
        0,
        min(
            100,
            round(
                readable / len(compact) * 100
                - replacement * 10
                - symbol_noise / len(compact) * 20
            ),
        ),
    )
    label = "높음" if score >= 80 else "보통" if score >= 55 else "낮음"
    return {"score": score, "label": label}


def _page_detail(page: int, text: str, method: str) -> dict:
    return {
        "page": page,
        "text": text,
        "quality": estimate_text_quality(text),
        "method": method,
    }
