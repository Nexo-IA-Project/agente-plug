from __future__ import annotations

from typing import ClassVar


class TextExtractor:
    """Extracts plain text from uploaded document bytes."""

    SUPPORTED_TYPES: ClassVar[set[str]] = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    }

    def extract(self, content: bytes, mime_type: str) -> str:
        if mime_type == "application/pdf":
            return self._extract_pdf(content)
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self._extract_docx(content)
        elif mime_type in ("text/plain", "text/markdown"):
            return content.decode("utf-8", errors="ignore")
        raise ValueError(f"Unsupported mime_type: {mime_type}")

    def _extract_pdf(self, content: bytes) -> str:
        import io

        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_docx(self, content: bytes) -> str:
        import io

        from docx import Document as DocxDocument

        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
