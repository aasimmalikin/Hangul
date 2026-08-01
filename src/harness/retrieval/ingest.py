"""Read text files -> chunk -> embed -> save the index."""

import asyncio
import sys
import hashlib
from pathlib import Path

from harness.retrieval.chunking import chunk_text
from harness.retrieval.embeddings import get_embedder
from harness.retrieval.index_version import index_version
from harness.retrieval.store import VectorStore

CHUNK_SIZE = 120
OVERLAP = 20

async def ingest(doc_dir: str, index_path: str = "data/index.json")->None:
    embedder = get_embedder()
    store = VectorStore(Path(index_path))
    files = sorted(Path(doc_dir).glob("*.txt"))
    corpus = "".join(f.read_text()for f in files)
    corpus_hash = hashlib.sha256(corpus.encode()).hexdigest()[:12]

    n = 0
    for f in files:
        for chunk in chunk_text(f.read_text(), chunk_size = CHUNK_SIZE, overlap = OVERLAP):
            embedding = await embedder.embed(chunk)
            store.add(text = chunk, source = f.name, embedding = embedding)
            n += 1
    store.save()

    ver = index_version(chunk_size = CHUNK_SIZE, overlap = OVERLAP, embed_model = embedder.model, corpus_hash= corpus_hash)
    print(f"ingested {n} chunks from {len(files)} files -> {index_path}")
    print(f"index_version: {ver}")

if __name__ == "__main__":
    asyncio.run(ingest(sys.argv[1] if len(sys.argv) > 1 else "docs"))
