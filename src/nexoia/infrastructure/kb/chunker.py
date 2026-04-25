from __future__ import annotations

import tiktoken


class TextChunker:
    """Token-aware text chunker using cl100k_base encoding."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self._enc = tiktoken.get_encoding("cl100k_base")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        tokens = self._enc.encode(text)
        chunks: list[str] = []
        i = 0
        while i < len(tokens):
            end = min(i + self._chunk_size, len(tokens))
            chunk_tokens = tokens[i:end]
            chunks.append(self._enc.decode(chunk_tokens))
            if end == len(tokens):
                break
            i += self._chunk_size - self._overlap
        return chunks
