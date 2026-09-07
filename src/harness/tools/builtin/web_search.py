"""web_search: query the live internet via Tavily. Complements search_docs —
that searches YOUR documents (closed corpus); this searches the OPEN web."""
from tavily import AsyncTavilyClient
from harness.config import get_settings
from harness.tools.base import Tool


def _format(results: list[dict]) -> str:
    if not results:
        return "No web results found"
    return "\n\n".join(
        f"[{r['title']}] ({r['url']})\n{r['content']}" for r in results
    )


async def web_search(query: str, max_results: int = 3) -> str:
    try:
        client = AsyncTavilyClient(api_key=get_settings().tavily_api_key)
        resp = await client.search(query=query, max_results=max_results)
        return _format(resp.get("results", []))
    except Exception as e:
        return (
            "WEB_SEARCH_UNAVAILABLE: the web search service could not be reached "
            f"({type(e).__name__}). Do not retry web_search; answer from available "
            "information or say you cannot access the web right now."
        )


WEB_SEARCH_TOOL = Tool(
    name="web_search",
    description="Search the live web. Use it only when the answer depends on current "
                "or external information the user's own material would not contain -- "
                "recent events, news, prices, public facts. Check search_docs first for "
                "anything about the user's documents. Cite the source URL of every "
                "result you use.",
    parameter={
        "type": "object",
        "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
        "required": ["query"],
    },
    handler=web_search,
)
