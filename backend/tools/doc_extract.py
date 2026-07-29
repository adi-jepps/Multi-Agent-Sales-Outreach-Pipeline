"""
Extracts plain text from an uploaded campaign-agenda file (PDF or DOCX), so
it can be shown in an editable text area rather than trusted blindly.
"""

import io

import docx
import fitz  # pymupdf

_MAX_BYTES = 10 * 1024 * 1024  # 10MB


def extract_text(filename: str, content: bytes) -> str:
    name = (filename or "").lower()

    if len(content) > _MAX_BYTES:
        raise ValueError("File too large (max 10MB).")

    if name.endswith(".pdf"):
        text = _extract_pdf_text(content)
    elif name.endswith(".docx"):
        text = _extract_docx_text(content)
    else:
        raise ValueError("Only .pdf and .docx files are supported.")

    if not text.strip():
        raise ValueError(
            "No extractable text found in this file - it may be a scanned/image-only document."
        )

    return text


def _extract_pdf_text(content: bytes) -> str:
    try:
        with fitz.open(stream=content, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        raise ValueError(f"Could not read this PDF: {e}") from e


def _extract_docx_text(content: bytes) -> str:
    try:
        document = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as e:
        raise ValueError(f"Could not read this DOCX: {e}") from e
