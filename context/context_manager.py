"""Context Manager — enriches agent prompts with contextual information."""

from __future__ import annotations

from typing import Any

from context.memory import MemoryStore


class ContextManager:
    """Gathers context from memory and system state to augment prompts."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store = store or MemoryStore()

    async def enrich(
        self,
        query: str,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Return contextual data that can be injected into prompts."""
        context: dict[str, Any] = {"query": query}

        # Past executions for the same symbol
        if symbol:
            past = self._store.get_by_symbol(symbol, limit=3)
            if past:
                context["past_analyses"] = [
                    {
                        "date": p["created_at"],
                        "bias": p["bias"],
                        "confidence": p["confidence"],
                    }
                    for p in past
                ]

        # Recent overall executions
        recent = self._store.get_recent(limit=5)
        context["recent_executions"] = len(recent)

        return context

    def format_context_prompt(self, context: dict[str, Any]) -> str:
        """Format context dict into a prompt prefix string."""
        parts = []
        if "past_analyses" in context:
            parts.append("Previous analyses for this symbol:")
            for p in context["past_analyses"]:
                parts.append(
                    f"  - {p['date']}: Bias={p['bias']}, Confidence={p['confidence']}"
                )
        if "recent_executions" in context:
            parts.append(
                f"Total recent analyses: {context['recent_executions']}"
            )
        return "\n".join(parts)
