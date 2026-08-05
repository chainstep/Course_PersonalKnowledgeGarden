from __future__ import annotations

from ..models import EncryptedPDFError, OCRNotSupportedError
from .chunker import TextPart


def extract_pdf(data: bytes) -> list[TextPart]:
    import fitz

    document = fitz.open(stream=data, filetype="pdf")
    if document.is_encrypted:
        raise EncryptedPDFError("encrypted PDFs are not supported")
    parts: list[TextPart] = []
    for page_number in range(len(document)):
        page = document[page_number]
        blocks = page.get_text("blocks", sort=True)
        text = "\n\n".join(str(block[4]).strip() for block in blocks if str(block[4]).strip())
        if not text.strip():
            continue
        heading = None
        for line in text.splitlines():
            if len(line.strip()) < 120 and (line.strip().istitle() or line.strip().startswith("#")):
                heading = line.strip().lstrip("# ")
                break
        parts.append(TextPart(text, page_number + 1, heading))
    if not parts:
        raise OCRNotSupportedError("image-only PDF detected; OCR is not supported")
    return parts
