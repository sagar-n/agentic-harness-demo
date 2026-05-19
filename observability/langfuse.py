"""Langfuse observability — traces, spans, and token tracking.

Enhanced with span support so every pipeline step is recorded.
"""

from __future__ import annotations

import time
from typing import Any

from config import settings


class Span:
    """A single observability span within a trace."""

    def __init__(
        self,
        name: str,
        parent: Any = None,
    ) -> None:
        self.name = name
        self.parent = parent
        self.status: str = "running"
        self.started_at = time.monotonic()
        self.completed_at: float | None = None
        self.output: Any = None
        self.error: str | None = None

    def end(self, status: str = "success", output: Any = None, error: str | None = None) -> None:
        self.completed_at = time.monotonic()
        self.status = status
        if output is not None:
            self.output = output
        if error is not None:
            self.error = error

    @property
    def duration_ms(self) -> float:
        end = self.completed_at or time.monotonic()
        return (end - self.started_at) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
        }


class LangfuseTracker:
    """Minimal Langfuse integration for observability.

    V1 provides a no-op stub that logs to console.
    When LANGNFUSE_ENABLED=true and keys are set, it will send real traces.

    Supports nested spans for per-step recording (FR8).
    """

    def __init__(self) -> None:
        self._enabled = settings.langfuse_enabled
        self._client: Any = None
        self._current_trace: Any = None
        self._spans: list[Span] = []

    async def initialize(self) -> None:
        """Initialize the Langfuse client if enabled."""
        if not self._enabled:
            return

        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except ImportError:
            print("[langfuse] langfuse package not installed. Run: pip install langfuse")
            self._enabled = False

    async def trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Create a new trace."""
        self._spans = []
        if self._enabled and self._client is not None:
            self._current_trace = self._client.start_observation(
                as_type="span",
                name=name,
                metadata=metadata,
            )
        else:
            print(f"[trace] {name} — metadata: {metadata}")
            self._current_trace = {"name": name, "metadata": metadata}
        return self._current_trace

    def start_span(self, name: str) -> Span:
        """Start a new span within the current trace."""
        span = Span(name=name, parent=self._current_trace)
        self._spans.append(span)
        if self._enabled and self._client is not None and self._current_trace is not None:
            try:
                langfuse_span = self._current_trace.start_observation(as_type="span", name=name)
                span._langfuse_span = langfuse_span  # type: ignore[attr-defined]
            except Exception:
                pass
        print(f"  [span start] {name}")
        return span

    def end_span(
        self,
        span: Span,
        status: str = "success",
        output: Any = None,
        error: str | None = None,
    ) -> None:
        """End a span with status and optional output."""
        span.end(status=status, output=output, error=error)
        langfuse_span = getattr(span, "_langfuse_span", None)
        if langfuse_span is not None:
            try:
                langfuse_span.update(
                    output=output,
                    level="ERROR" if status == "failed" else "DEFAULT",
                    status_message=error,
                )
                langfuse_span.end()
            except Exception:
                pass
        status_icon = "✔" if status == "success" else "✖" if status == "failed" else "⟳"
        duration = f"{span.duration_ms:.0f}ms"
        print(f"  [span end]   {span.name} — {status_icon} {status} ({duration})")

    def get_span_summary(self) -> list[dict[str, Any]]:
        """Return a summary of all completed spans for inclusion in verification."""
        return [s.to_dict() for s in self._spans]

    async def close(self) -> None:
        """Flush and close."""
        if self._current_trace is not None:
            try:
                self._current_trace.end()
            except Exception:
                pass
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:
                pass
