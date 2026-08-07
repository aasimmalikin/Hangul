"""POST /upload — ingest a document into the caller's session index."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from harness.api.session import get_session_id
from harness.retrieval.upload_ingest import extract_text, chunk_text, UploadError, MAX_BYTES
from harness.retrieval.embeddings import get_embedder
from harness.retrieval.session_store import SessionVectorStore

router = APIRouter()
_session_store = SessionVectorStore()

@router.post("/upload")
async def upload(file:UploadFile = File(...), session_id:str = Depends(get_session_id)):
    data = b""
    while chunk:= await file.read(1024*1024):
        data+=chunk
        if len(data)>MAX_BYTES:
            raise HTTPException(status_code = 413, detail = "File too large")
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
        _session_store.add(session_id, ch, vector, source = file.filename or "upload")
    
    return {
        "session_id": session_id,
        "filename": file.filename,
        "chunks_indexed": len(chunks),
        "message": f"Indexed {len(chunks)} chunks from {file.filename}",
    }