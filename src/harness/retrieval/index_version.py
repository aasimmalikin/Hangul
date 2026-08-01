import hashlib

def index_version(*, chunk_size: int, overlap:int, embed_model: str, corpus_hash:str)->str:
    payload = f"{chunk_size}: {overlap}: {embed_model}: {corpus_hash}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]