"""
Tools available to the research crew.

Kept separate from crew.py so tool choice/config can change (e.g. swapping
search providers) without touching agent/task wiring.
"""

import os

from crewai.tools import tool
from crewai_tools import ScrapeWebsiteTool
from serpapi import GoogleSearch

# Scrapes a given URL's text content - used for the company website and,
# where accessible, the LinkedIn page.
scrape_website_tool = ScrapeWebsiteTool()


@tool("Web Search")
def web_search_tool(query: str) -> str:
    """
    Search the web via SerpAPI and return the top results (title, link, snippet)
    as plain text. Use this for anything not sitting at a known URL - e.g. recent
    news about a company that isn't on its own website.
    """
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return "SERPAPI_API_KEY is not set - cannot perform web search."

    search = GoogleSearch({"q": query, "api_key": api_key, "num": 5})
    results = search.get_dict()

    organic_results = results.get("organic_results", [])
    if not organic_results:
        return "No search results found."

    formatted = []
    for r in organic_results[:5]:
        title = r.get("title", "")
        link = r.get("link", "")
        snippet = r.get("snippet", "")
        formatted.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}")

    return "\n\n".join(formatted)


# Note: LinkedIn company pages often block direct scraping without an
# authenticated session. ScrapeWebsiteTool will frequently come back empty
# or blocked for linkedin.com URLs - treat linkedin as a "best effort" source
# and lean on web_search_tool (e.g. "site:linkedin.com company_name") as the
# fallback.
research_tools = [scrape_website_tool, web_search_tool]

