"""web_search: query the live internet via Tavily. Complements search_docs —
that searches YOUR documents (closed corpus); this searches the OPEN web."""
import asyncio
from tavily import AsyncTavilyClient
from harness.config import get_settings
from harness.tools.base import Tool

_client: AsyncTavilyClient | None = None


def get_client() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=get_settings().tavily_api_key)
    return _client


def _format(results: list[dict]) -> str:
    if not results:
        return "No web results found"
    return "\n\n".join(
        f"[{r['title']}] ({r['url']})\n{r['content']}" for r in results
    )


async def web_search(query: str, max_results: int = 3) -> str:
    # Retry transient failures INSIDE the tool (fast, with backoff) so a flaky
    # network does not turn into agent-level retry loops that inflate steps.
    last_err = None
    for attempt in range(3):
        try:
            resp = await asyncio.wait_for(
                get_client().search(query=query, max_results=max_results),
                timeout=15,
            )
            return _format(resp.get("results", []))
        except Exception as e:
            last_err = e
            if attempt < 2:
                await asyncio.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s backoff
    # All retries failed — return a CLEAR, distinct signal so the agent knows
    # the tool is unavailable (not that it found nothing) and does not just
    # retry the same call.
    return (
        "WEB_SEARCH_UNAVAILABLE: the web search service could not be reached "
        f"after 3 attempts ({type(last_err).__name__}). Do not retry web_search; "
        "answer from available information or say you cannot access the web right now."
    )


WEB_SEARCH_TOOL = Tool(
    name="web_search",
    description="Search the live web for current information. Use for recent events, "
                "news, or anything not in the user's own documents. Cite the source URLs.",
    parameter={
        "type": "object",
        "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
        "required": ["query"],
    },
    handler=web_search,
)
