from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("지원 형식은 TXT, PDF, DOCX입니다.")

    if extension == ".txt":
        return content.decode("utf-8-sig")
    if extension == ".pdf":
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)

