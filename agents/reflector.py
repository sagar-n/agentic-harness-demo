"""Reflector Agent — reviews the full execution trace and suggests improvements."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.base import BaseAgent


class Reflection(BaseModel):
    overall_quality: str = Field(description="Overall assessment of the output quality")
    weaknesses: list[str] = Field(description="Identified weaknesses")
    improvements: list[str] = Field(description="Suggestions for improvement")
    missing_data: list[str] = Field(description="Data that would have helped")


REFLECTOR_PROMPT = """You are a reflection agent. Review the entire execution trace and the final report.
Identify:
1. Weaknesses in the analysis
2. Missing data that would have helped
3. Suggestions for improving the next run
4. Overall quality assessment

Be honest and constructive. The goal is to improve the system."""


class ReflectorAgent(BaseAgent):
    """Reviews a completed execution and provides a *Reflection*."""

    async def run(  # type: ignore[override]
        self,
        query: str,
        execution_trace: dict[str, Any],
    ) -> Reflection:
        prompt = (
            f"{REFLECTOR_PROMPT}\n\n"
            f"Query: {query}\n"
            f"Execution trace:\n{execution_trace}"
        )
        result = await self.chat(
            [{"role": "user", "content": prompt}],
            response_format=Reflection,
        )
        return Reflection(**result)
