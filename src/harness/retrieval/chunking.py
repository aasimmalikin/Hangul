"""Split text into overlapping chunks. Overlap keeps a sentence that straddles a
boundary from being lost. Chunk size is the highest-leverage RAG knob."""

def chunk_text(text: str, chunk_size: int = 120, overlap: int = 20)-> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap
    return chunks
