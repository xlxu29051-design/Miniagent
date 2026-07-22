"""Mock web-search tool: deterministic canned results (reproducible tests)."""
from __future__ import annotations

from typing import Any, Dict, List

from .base import Tool, ToolError, ToolRegistry

_CANNED: Dict[str, List[Dict[str, str]]] = {
    "python": [{"title": "Welcome to Python.org", "url": "https://python.org",
                "snippet": "Python is a programming language that lets you work quickly."}],
    "agent": [{"title": "LLM agents explained", "url": "https://example.com/agents",
               "snippet": "An agent loops: observe, think, act with tools, then answer."}],
}


def _default_results(query: str) -> List[Dict[str, str]]:
    return [{"title": f"Result about '{query}'",
             "url": f"https://example.com/search?q={query.replace(' ', '+')}",
             "snippet": f"This is a mock search result summarising information about {query}."}]


def search(query: str, top_k: int = 3) -> Dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise ToolError("query must be a non-empty string")
    if not isinstance(top_k, int) or top_k < 1:
        raise ToolError("top_k must be a positive integer")
    q = query.lower().strip()
    hits: List[Dict[str, str]] = []
    for key, results in _CANNED.items():
        if key in q:
            hits.extend(results)
    if not hits:
        hits = _default_results(query)
    return {"query": query, "results": hits[:top_k]}


def register(registry: ToolRegistry) -> None:
    registry.register(Tool(
        name="search",
        description="Search the web for information about a topic (mocked). "
        "Returns a list of results with title, url and snippet.",
        parameters={"type": "object",
                    "properties": {"query": {"type": "string", "description": "The search query."},
                                   "top_k": {"type": "integer",
                                             "description": "Max results (default 3)."}},
                    "required": ["query"]},
        func=search))