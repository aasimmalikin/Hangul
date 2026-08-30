"""POST /upload — ingest a document into the caller's session index."""
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from harness.api.session import get_session_id
from harness.api.auth import get_current_user
from harness.retrieval.upload_ingest import extract_text, chunk_text, UploadError, MAX_BYTES
from harness.retrieval.embeddings import get_embedder
from harness.retrieval.session_store import SessionVectorStore

router = APIRouter()
_session_store = SessionVectorStore()
_SESSIONS_ROOT  = Path("data/sessions")

def _safe_session_dir(user_id: str)->Path:
    """Return and create this session's folder guarding against path tricks."""
    safe = "".join(c for c in user_id if c.isalnum() or c in "-_")
    d = _SESSIONS_ROOT/safe
    d.mkdir(parents = True, exist_ok = True)
    return d

@router.post("/upload")
async def upload(file:UploadFile = File(...), user: dict = Depends(get_current_user)):
    data = b""
    while chunk:= await file.read(1024*1024):
        data+=chunk
        if len(data)>MAX_BYTES:
            raise HTTPException(status_code = 413, detail = "File too large")
    
    filename = file.filename or "upload"

    try:
        text = extract_text(file.filename or "upload", data)
    except UploadError as e:
        raise HTTPException(status_code = 400, detail = str(e))
    
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(status_code = 400, detail = "No readable text found in the file")
    
    embedder = get_embedder()
    for ch in chunks:
        vector = await embedder.embed(ch)
        _session_store.add(user["user_id"], ch, vector, source = file.filename or "upload")
    
    safe_name = Path(filename).name
    session_dir = _safe_session_dir(user["user_id"])
    (session_dir/safe_name).write_bytes(data)
    
    return {
        "session_id": user["user_id"],
        "filename": file.filename,
        "chunks_indexed": len(chunks),
        "mcp_path": f"{session_dir.name}/{safe_name}",
        "message": f"Indexed {len(chunks)} chunks from {file.filename}",
    }