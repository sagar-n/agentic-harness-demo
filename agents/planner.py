"""Planner Agent — decomposes user intent into an execution plan."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from agents.base import BaseAgent
from models import Intent


class PlanStep(BaseModel):
    step_id: str = Field(description="Unique step identifier, e.g. 'step_1'")
    agent: str = Field(
        description="Agent or tool to use: market_context, chart_analysis, news, sentiment, verifier"
    )
    description: str = Field(description="What this step should accomplish")
    depends_on: list[str] = Field(default_factory=list)

    @field_validator("step_id", mode="before")
    @classmethod
    def coerce_step_id(cls, v: Any) -> str:
        return str(v)

    @field_validator("depends_on", mode="before")
    @classmethod
    def coerce_depends_on(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(item) for item in v]
        return [str(v)] if v is not None else []


class Plan(BaseModel):
    intent: Any = Field(description="The interpreted intent")
    steps: list[PlanStep] = Field(description="Ordered list of steps to execute")


PLANNER_PROMPT = """You are a trading research planner. Given a user query, produce a structured plan.

Available agents:
- **market_context** — NIFTY/BankNifty trend, sector movement, volatility
- **chart_analysis** — TradingView chart screenshot → trend, S/R, RSI, patterns
- **news** — Company & macro news retrieval
- **sentiment** — Sentiment scoring from collected news
- **verifier** — Cross-check all signals, contradictions, confidence

Rules:
1. Always include market_context first to set the macro backdrop.
2. chart_analysis runs concurrently with news.
3. sentiment depends on news.
4. verifier always runs last.
5. Add dependencies so that the runner can parallelize correctly.

Return a JSON object with keys: intent, steps.
Each step has: step_id, agent, description, depends_on.
"""


class PlannerAgent(BaseAgent):
    """Produces a structured *Plan* from an Intent."""

    async def run(self, intent: Intent, context: str = "") -> Plan:  # type: ignore[override]
        prompt_parts = [
            f"User query: {intent.raw_query}",
            f"Parsed intent: symbol={intent.symbol}, timeframe={intent.timeframe.value}, "
            f"analysis_type={intent.analysis_type.value}",
        ]
        if context:
            prompt_parts.append(f"\nAdditional context:\n{context}")
        prompt_parts.append("\n" + PLANNER_PROMPT)

        prompt = "\n".join(prompt_parts)

        result = await self.chat(
            [{"role": "user", "content": prompt}],
            response_format=Plan,
        )
        return Plan(**result)
