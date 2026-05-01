# tests/unit/infrastructure/kb/test_text_extractor.py
import pytest

from shared.adapters.kb.text_extractor import TextExtractor


def test_extract_plain_text():
    extractor = TextExtractor()
    content = b"Hello, world!"
    result = extractor.extract(content, "text/plain")
    assert result == "Hello, world!"


def test_extract_markdown():
    extractor = TextExtractor()
    content = b"# Title\n\nParagraph."
    result = extractor.extract(content, "text/markdown")
    assert "Title" in result
    assert "Paragraph" in result


def test_unsupported_mime_raises():
    extractor = TextExtractor()
    with pytest.raises(ValueError, match="Unsupported mime_type"):
        extractor.extract(b"data", "image/png")
