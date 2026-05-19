"""Market context tool — analyzes macro conditions via LLM."""

from __future__ import annotations

from typing import Any

import httpx

from config import settings
from models import IndexData, MarketContext, SectorData


class MarketContextTool:
    """Generates market context (NIFTY, BankNifty, sectors, volatility) using LLM.

    V1 uses the reasoning model to simulate market context based on recent
    known conditions. In production, replace with a real market data API
    (e.g. Alpha Vantage, Yahoo Finance, Twelve Data).
    """

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=180.0)
        return self._client

    async def get_context(self, symbol: str, banknifty_analysis: ChartAnalysis) -> MarketContext:
        """Fetch market context for the given symbol's market, integrating actual BANKNIFTY trend."""
        prompt = (
            f"You are a market research analyst. Provide current market context for {symbol}.\n\n"
            f"Note that the actual BANKNIFTY index trend is visually analyzed as: '{banknifty_analysis.trend}' "
            f"with pattern '{banknifty_analysis.pattern}'.\n\n"
            f"Include:\n"
            f"- 3-4 relevant sector movements with name, change_pct, and strength ('strong'/'neutral'/'weak')\n"
            f"- market_breadth (e.g. 'Broadly positive', 'Mixed', 'Negative')\n"
            f"- volatility_index (VIX or India VIX approximate value)\n"
            f"- summary (2-3 sentence overview of macro environment based on the BANKNIFTY index trend)\n\n"
            f"Return ONLY valid JSON with keys: sectors (list of {{name, change_pct, strength}}), market_breadth, volatility_index, summary."
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

            print(f"    [llm-call] [MarketContextTool] Calling fast model '{settings.fast_model}'...")
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
            print(f"    [llm-response] [MarketContextTool] Received response in {duration_ms:.0f}ms")
            print(f"    [llm-content] [MarketContextTool] Snippet: {raw[:150].strip()!r}...")

            import json

            parsed = json.loads(raw)
            sectors_raw = parsed.get("sectors", [])

            def parse_float(val: Any) -> float:
                try:
                    return float(str(val).replace("%", "").strip())
                except (ValueError, TypeError):
                    return 0.0

            return MarketContext(
                banknifty_trend=banknifty_analysis.trend,
                banknifty_pattern=banknifty_analysis.pattern,
                banknifty_rsi=banknifty_analysis.rsi,
                comparison="",  # Updated later during coordination
                sectors=[
                    SectorData(
                        name=s.get("name", ""),
                        change_pct=parse_float(s.get("change_pct", 0.0)),
                        strength=s.get("strength", "neutral"),
                    )
                    for s in sectors_raw
                ],
                market_breadth=parsed.get("market_breadth", ""),
                volatility_index=parse_float(parsed.get("volatility_index", 0.0)),
                summary=parsed.get("summary", ""),
            )

        except Exception as exc:
            print(f"    [llm-error] [MarketContextTool] Failed: {exc}")
            return MarketContext(
                banknifty_trend=banknifty_analysis.trend,
                banknifty_pattern=banknifty_analysis.pattern,
                summary=f"Market context macro details unavailable: {exc}",
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
