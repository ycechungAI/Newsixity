"""External API integrations: RSS, content extraction, search, finance, ollama."""

from app.lib.integrations.rss import fetch_feed, fetch_all_feeds
from app.lib.integrations.content import fetch_article_content
from app.lib.integrations.search import extract_search_results
from app.lib.integrations.finance import (
    fetch_quote,
    fetch_quotes,
    fetch_chart,
    search_stocks,
    StockNotFoundError,
)
from app.lib.integrations.ollama import (
    is_ollama_available,
    get_available_models,
    summarize_article,
    generate_group_label,
    answer_research_question,
    OllamaUnavailableError,
    OllamaModelNotFoundError,
)

__all__ = [
    "fetch_feed",
    "fetch_all_feeds",
    "fetch_article_content",
    "extract_search_results",
    "fetch_quote",
    "fetch_quotes",
    "fetch_chart",
    "search_stocks",
    "StockNotFoundError",
    "is_ollama_available",
    "get_available_models",
    "summarize_article",
    "generate_group_label",
    "answer_research_question",
    "OllamaUnavailableError",
    "OllamaModelNotFoundError",
]
