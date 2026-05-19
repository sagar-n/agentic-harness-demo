"""Vision analyzer — sends chart screenshots to Ollama vision model."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from config import settings
from models import ChartAnalysis, SupportResistance


class ChartVisionAnalyzer:
    """Sends a TradingView screenshot to Qwen2.5-VL for structured analysis."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def analyze(self, image_bytes: bytes, symbol: str) -> ChartAnalysis:
        """Send a chart screenshot to the vision model and parse the response.

        Uses Ollama's vision API which accepts base64-encoded images in
        the chat payload.
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            f"You are a chart analyst. Analyze this TradingView chart for {symbol}.\n\n"
            f"Extract the following:\n"
            f"- trend (e.g. 'Bullish', 'Bearish', 'Sideways')\n"
            f"- support levels (array of prices)\n"
            f"- resistance levels (array of prices)\n"
            f"- RSI value (float or null)\n"
            f"- breakout probability (0.0 to 1.0)\n"
            f"- volume confidence (0.0 to 1.0)\n"
            f"- pattern name (e.g. 'flag', 'wedge', 'double top', or empty)\n"
            f"- notes (string)\n\n"
            f"Return ONLY valid JSON with keys: trend, support_resistance ({{support: [], resistance: []}}), "
            f"rsi, breakout_probability, volume_confidence, pattern, notes"
        )

        if settings.omlx_enabled:
            url = f"{settings.omlx_base_url}/v1/chat/completions"
            headers = {"Authorization": f"Bearer {settings.omlx_api_key}"}
            payload = {
                "model": settings.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}"
                                }
                            }
                        ]
                    }
                ],
                "stream": False,
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
        else:
            url = settings.ollama_chat_url
            headers = None
            payload = {
                "model": settings.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_b64],
                    }
                ],
                "stream": False,
                "options": {"temperature": 0.1},
                "format": "json",
            }

        try:
            import time
            print(f"    [llm-call] [ChartVisionAnalyzer] Calling vision model '{settings.vision_model}'...")
            start_time = time.monotonic()
            resp = await self.client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            if settings.omlx_enabled:
                raw = data["choices"][0]["message"]["content"]
            else:
                raw = data["message"]["content"]
            duration_ms = (time.monotonic() - start_time) * 1000
            print(f"    [llm-response] [ChartVisionAnalyzer] Received response in {duration_ms:.0f}ms")
            print(f"    [llm-content] [ChartVisionAnalyzer] Snippet: {raw[:150].strip()!r}...")

            parsed = json.loads(raw)

            # Handle nested support_resistance
            sr_data = parsed.get("support_resistance", {})
            if isinstance(sr_data, dict):
                support = sr_data.get("support", [])
                resistance = sr_data.get("resistance", [])
            else:
                support = []
                resistance = []

            return ChartAnalysis(
                trend=parsed.get("trend", ""),
                support_resistance=SupportResistance(
                    support=[float(s) for s in support if s],
                    resistance=[float(r) for r in resistance if r],
                ),
                rsi=float(parsed["rsi"]) if parsed.get("rsi") is not None else None,
                breakout_probability=float(parsed.get("breakout_probability", 0.0)),
                volume_confidence=float(parsed.get("volume_confidence", 0.0)),
                pattern=parsed.get("pattern", ""),
                notes=parsed.get("notes", ""),
            )

        except Exception as exc:
            print(f"    [llm-error] [ChartVisionAnalyzer] Failed: {exc}")
            # Return a fallback analysis so pipeline doesn't break
            return ChartAnalysis(
                trend="Unknown (vision analysis unavailable)",
                notes=f"Vision analysis error: {exc}",
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
