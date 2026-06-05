from io import BytesIO
from pathlib import Path

from docx import Document
from PIL import Image
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}
MAX_OCR_PAGES = 20


def _extract_ocr_text(content: bytes, extension: str) -> str:
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
        text = "\n".join(
            pytesseract.image_to_string(image, lang="kor+eng")
            for image in images
        )
    except Exception as error:
        raise ValueError(
            "OCR 실행에 실패했습니다. Tesseract 한국어 언어팩과 PDF 변환 도구 설치를 확인하세요."
        ) from error

    if not text.strip():
        raise ValueError("OCR에서 읽을 수 있는 텍스트를 찾지 못했습니다.")
    return text


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("지원 형식은 TXT, PDF, DOCX입니다.")

    if extension == ".txt":
        return content.decode("utf-8-sig")
    if extension == ".pdf":
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not text.strip():
            return _extract_ocr_text(content, extension)
        return text
    if extension in {".png", ".jpg", ".jpeg"}:
        return _extract_ocr_text(content, extension)

    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)
