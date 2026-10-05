import io

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED = {".txt", ".md", ".pdf", ".docx"}


def load_text(suffix: str, raw: bytes) -> str:
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(raw))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    elif suffix == ".docx":
        doc = DocxDocument(io.BytesIO(raw))
        text = "\n\n".join(p.text for p in doc.paragraphs)
    else:  # .txt, .md
        text = raw.decode("utf-8", errors="replace")
    return text.replace("\x00", "")