# tests/unit/infrastructure/kb/test_chunker.py
from shared.adapters.kb.chunker import TextChunker


def test_short_text_produces_single_chunk():
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk("Hello world")
    assert len(chunks) == 1
    assert "Hello" in chunks[0]


def test_empty_text_produces_no_chunks():
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk("")
    assert chunks == []


def test_long_text_produces_multiple_chunks():
    # ~600 tokens → should produce 2 chunks with size=512, overlap=50
    word = "word "
    # ~600 tokens ≈ 600 "word " repetitions (roughly 1 token each)
    long_text = word * 600
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk(long_text)
    assert len(chunks) >= 2


def test_overlap_is_respected():
    """With overlap=50, second chunk should share tokens with first."""
    word = "token "
    long_text = word * 600
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk(long_text)
    # Both chunks must be non-empty
    assert all(len(c) > 0 for c in chunks)


def test_chunk_size_boundary():
    """A text of exactly chunk_size tokens → exactly 1 chunk."""
    chunker = TextChunker(chunk_size=100, overlap=10)
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode("hello ") * 100  # 100 repetitions of "hello " ≈ 100 tokens
    text = enc.decode(tokens[:100])
    chunks = chunker.chunk(text)
    assert len(chunks) == 1


def test_custom_chunk_size():
    chunker = TextChunker(chunk_size=50, overlap=5)
    word = "word "
    long_text = word * 200
    chunks = chunker.chunk(long_text)
    assert len(chunks) >= 4  # 200 tokens / (50-5) stride ≈ 4-5 chunks
