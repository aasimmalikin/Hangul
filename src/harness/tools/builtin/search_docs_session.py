"""Factory for a session-aware search_docs tool. Searches the caller's uploaded
documents first (per-session store), falling back to the global built-in index."""

from harness.retrieval.embeddings import get_embedder
from harness.retrieval.store import VectorStore
from harness.tools.base import Tool
from harness.api.routes.upload import _session_store

_global_store = VectorStore(path="data/index.json")
_global_store.load()


def make_search_docs_tool(session_id: str) -> Tool:
    async def search_docs(query: str, k: int = 3) -> str:
        emb = await get_embedder().embed(query)

        # 1. the session's uploaded documents, if any
        if _session_store.has_docs(session_id):
            hits = _session_store.search(session_id, emb, k=k)
            if hits:
                return "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)

        # 2. fall back to the global built-in index
        if _global_store.records:
            hits = _global_store.search(query_emb=emb, top_k=k)
            return "\n\n".join(f"[{r['source']}] {r['text']}" for _sim, r in hits)

        return "No documents available to search."

    return Tool(
        name="search_docs",
        description="Search the user's uploaded documents (or the built-in docs) "
                    "for passages relevant to a query. Use this for questions about "
                    "the user's documents.",
        parameter={
            "type": "object",
            "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
            "required": ["query"],
        },
        handler=search_docs,
    )
