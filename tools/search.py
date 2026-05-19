"""News search tool — gathers company & market news (simulated / structured)."""

from __future__ import annotations

from typing import Any

import httpx

from config import settings
from models import NewsArticle, SentimentLabel


class NewsSearcher:
    """Retrieves news for a given symbol using available sources.

    In V1 this uses a simple web search via a local LLM call.
    In future this can be extended to use NewsAPI, Google News, etc.
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=180.0)
        return self._client

    async def search(self, symbol: str, max_articles: int = 5) -> list[NewsArticle]:
        """Search for recent news about *symbol*.

        Uses the Ollama fast model to generate plausible recent news
        summaries for demonstration purposes. Replace with a real API
        (NewsAPI, Alpha Vantage, etc.) in production.
        """
        prompt = (
            f"You are a financial news researcher. "
            f"Find {max_articles} recent news headlines for the stock {symbol}. "
            f"For each headline, provide:\n"
            f"- title\n"
            f"- source (real news source name)\n"
            f"- summary (1-2 sentences)\n"
            f"- sentiment (positive, negative, or neutral)\n"
            f"- relevance (float 0-1)\n\n"
            f"Return as a JSON list with keys: title, source, summary, sentiment, relevance."
        )

        try:
            import time
            if settings.omlx_enabled:
                url = f"{settings.omlx_base_url}/v1/chat/completions"
                headers = {"Authorization": f"Bearer {settings.omlx_api_key}"}
                payload = {
                    "model": settings.fast_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                }
            else:
                url = settings.ollama_chat_url
                headers = None
                payload = {
                    "model": settings.fast_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3},
                    "format": "json",
                }

            print(f"    [llm-call] [NewsSearcher] Calling fast model '{settings.fast_model}'...")
            start_time = time.monotonic()
            resp = await self.client.post(
                url,
                json=payload,
                headers=headers,
                timeout=180.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if settings.omlx_enabled:
                raw = data["choices"][0]["message"]["content"]
            else:
                raw = data["message"]["content"]
            duration_ms = (time.monotonic() - start_time) * 1000
            print(f"    [llm-response] [NewsSearcher] Received response in {duration_ms:.0f}ms")
            print(f"    [llm-content] [NewsSearcher] Snippet: {raw[:150].strip()!r}...")

            import json

            articles_data = json.loads(raw)
            if isinstance(articles_data, dict):
                articles_data = articles_data.get("articles", articles_data.get("news", [articles_data]))

            articles = []
            for item in articles_data[:max_articles]:
                articles.append(
                    NewsArticle(
                        title=item.get("title", f"News about {symbol}"),
                        source=item.get("source", "Unknown"),
                        summary=item.get("summary", ""),
                        sentiment=SentimentLabel(item.get("sentiment", "neutral")),
                        relevance=float(item.get("relevance", 0.5)),
                    )
                )
            return articles

        except Exception as exc:
            print(f"    [llm-error] [NewsSearcher] Failed: {exc}")
            # Return a fallback article so the pipeline doesn't break
            return [
                NewsArticle(
                    title=f"Market update for {symbol}",
                    source="MarketWire",
                    summary=f"Ongoing market activity for {symbol} in today's session.",
                    sentiment=SentimentLabel.neutral,
                    relevance=0.5,
                )
            ]

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
