"""Turn an uploaded file's bytes into clean text chunks, ready to embed."""

from io import BytesIO

MAX_BYTES = 10*1024*1024
ALLOWED = {".txt", ".md", ".pdf"}

class UploadError(Exception):
    """Raised for unsupported type or oversize upload; mapped to HTTP"""

def extract_text(filename:str, data: bytes)->str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise UploadError(f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED)}")
    if len(data) > MAX_BYTES:
        raise UploadError(f"File too large ({len(data)} bytes). Max {MAX_BYTES // (1024*1024)} MB.")

    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")

    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    

def chunk_text(text: str, size: int = 120, overlap: int = 20) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, start = [], 0
    step = max(1, size - overlap)
    while start < len(words):
        chunks.append(" ".join(words[start:start + size]))
        start += step
    return chunks
