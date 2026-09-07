from harness.retrieval.embeddings import get_embedder
from harness.retrieval.store import VectorStore
from harness.tools.base import Tool

_store = VectorStore(path = "data/index.json")
_store.load()

async def search_docs(query:str, k:int = 3)->str:
    if not _store.records:
        return "No documents have been ingested yet."
    emb = await get_embedder().embed(query)
    hits = _store.search(query_emb = emb, top_k = k)
    return "\n\n".join(f"[{r['source']}] {r['text']}" for _sim, r in hits)

SEARCH_DOCS_TOOL = Tool(
    name = "search_docs",
    description="Search the user's document library for passages relevant to a "
                  "query. This is the only way to reach that library -- the "
                  "filesystem tools cannot see it. Use it for any question about "
                  "what the documents say, including when the user names a "
                  "document by title. Cite the [source] shown with each passage.",
    
    parameter = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
        "required": ["query"],
    },
    handler = search_docs
)