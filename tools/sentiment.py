"""Sentiment analyzer — scores news/articles for sentiment."""

from __future__ import annotations

from typing import Any

import httpx

from config import settings
from models import NewsArticle, SentimentAnalysis, SentimentLabel


class SentimentAnalyzer:
    """Aggregates sentiment from a list of news articles."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def analyze(self, articles: list[NewsArticle]) -> SentimentAnalysis:
        """Analyze sentiment across a list of articles.

        Uses the fast model to produce a composite score when multiple
        articles are present; otherwise aggregates the individual labels.
        """
        if not articles:
            return SentimentAnalysis(
                overall=SentimentLabel.neutral,
                score=0.0,
                summary="No articles to analyze.",
            )

        # Simple aggregation: average the sentiment scores
        sentiment_map = {
            SentimentLabel.positive: 1.0,
            SentimentLabel.neutral: 0.0,
            SentimentLabel.negative: -1.0,
        }

        total = 0.0
        for article in articles:
            total += sentiment_map.get(article.sentiment, 0.0)

        avg_score = total / len(articles)

        if avg_score > 0.2:
            overall = SentimentLabel.positive
        elif avg_score < -0.2:
            overall = SentimentLabel.negative
        else:
            overall = SentimentLabel.neutral

        positive_count = sum(
            1 for a in articles if a.sentiment == SentimentLabel.positive
        )
        negative_count = sum(
            1 for a in articles if a.sentiment == SentimentLabel.negative
        )

        summary = (
            f"Positive: {positive_count}, Neutral: {len(articles) - positive_count - negative_count}, "
            f"Negative: {negative_count}. "
            f"Composite score: {avg_score:+.2f}"
        )

        return SentimentAnalysis(
            overall=overall,
            score=round(avg_score, 2),
            articles=articles,
            summary=summary,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
