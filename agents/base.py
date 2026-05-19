"""Base agent with shared Ollama LLM interaction."""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from config import settings


class BaseAgent(ABC):
    """Abstract base for all agents that talk to an Ollama-hosted model."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 2,
    ) -> None:
        self.model = model or settings.reasoning_model
        self.temperature = temperature
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    # ── Public helpers ──────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, str]],
        response_format: type | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a chat request to Ollama and return the parsed response.

        If *response_format* is given the model is instructed to return valid
        JSON matching that Pydantic model and the output is parsed before
        being returned.
        """
        if settings.omlx_enabled:
            url = f"{settings.omlx_base_url}/v1/chat/completions"
            headers = {"Authorization": f"Bearer {settings.omlx_api_key}"}
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "temperature": kwargs.get("temperature", self.temperature),
            }
            if response_format is not None:
                payload["response_format"] = {"type": "json_object"}
        else:
            url = settings.ollama_chat_url
            headers = None
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.temperature),
                },
            }
            if response_format is not None:
                payload["format"] = "json"

        for attempt in range(1 + self.max_retries):
            try:
                print(f"    [llm-call] Calling reasoning model '{self.model}' (attempt {attempt + 1}/{1 + self.max_retries})...")
                start_time = time.monotonic()
                resp = await self.client.post(
                    url, json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                if settings.omlx_enabled:
                    raw = data["choices"][0]["message"]["content"]
                else:
                    raw = data["message"]["content"]
                duration_ms = (time.monotonic() - start_time) * 1000
                print(f"    [llm-response] Received response from '{self.model}' in {duration_ms:.0f}ms")
                print(f"    [llm-content] Content length: {len(raw)} chars | Snippet: {raw[:150].strip()!r}...")

                if response_format is not None:
                    try:
                        parsed = json.loads(raw)
                        validated = response_format(**parsed).model_dump()
                        return validated
                    except Exception as exc:
                        print(f"    [llm-error] JSON validation/decode failed: {exc}")
                        raise

                # Try to parse as JSON anyway
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"text": raw}

            except Exception as exc:
                print(f"    [llm-error] Attempt {attempt + 1} failed: {exc}")
                if attempt < self.max_retries:
                    wait = 1.0 * (attempt + 1)
                    print(f"    [llm-retry] Waiting {wait}s before retry...")
                    await asyncio.sleep(wait)
                    continue
                raise RuntimeError(
                    f"Agent {self.__class__.__name__} failed after "
                    f"{attempt + 1} attempts: {exc}"
                ) from exc

    async def generate(
        self, prompt: str, response_format: type | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Single-turn generate (wraps chat with a user message)."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, response_format=response_format, **kwargs)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent's primary task."""
        ...
