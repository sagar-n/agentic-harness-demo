"""Verifier Agent — cross-checks all evidence and produces a confidence score.

Enhanced to accept execution step records (FR8) and output validation
results for full workflow verification.
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from models import (
    ChartAnalysis,
    ExecutionStep,
    FinalReport,
    MarketContext,
    SentimentAnalysis,
    StepCheck,
    VerificationResult,
)

VERIFIER_PROMPT = """You are a verification agent for trading research. Your job is to:

1. Cross-check all signals for agreement/contradiction
2. Check news consistency with technical signals
3. Evaluate trend alignment across timeframes
4. Assess risk-reward ratio
5. Review step execution quality (did all pipeline steps complete?)
6. Review output validation results (structural checks)
7. Produce a confidence score (0.0 – 1.0)

Return the output as a JSON object with these keys:
- confidence_score (float 0-1)
- contradictions (list of {aspect, detail})
- missing_evidence (list of {aspect, detail})
- signal_agreement (string describing how well signals align)
- risk_reward_ratio (float or null)
- passed (boolean — true if confidence_score >= 0.6)
- step_checks (list of {step, agent, status, issue})
- output_validation (string summarizing structural validation)

Be critical. It's better to flag uncertainty than to be overconfident."""


class VerifierAgent(BaseAgent):
    """Verifies all collected evidence and returns a *VerificationResult*.

    In addition to signal cross-checking, this agent now also evaluates
    step execution records (observability spans) and output validation
    results to verify the *full workflow* completed correctly.
    """

    async def run(  # type: ignore[override]
        self,
        symbol: str,
        market: MarketContext | None = None,
        chart: ChartAnalysis | None = None,
        sentiment: SentimentAnalysis | None = None,
        retry_feedback: list[str] | None = None,
        step_records: list[dict[str, Any]] | None = None,
        output_validation_result: str = "",
    ) -> VerificationResult:
        context_parts = [f"Symbol: {symbol}"]

        if market:
            context_parts.append(f"Market Context: {market.model_dump_json(indent=2)}")
        if chart:
            context_parts.append(f"Chart Analysis: {chart.model_dump_json(indent=2)}")
        if sentiment:
            context_parts.append(
                f"Sentiment Analysis: {sentiment.model_dump_json(indent=2)}"
            )

        # FR8: Include step execution records (observability spans)
        if step_records:
            step_summary = "\n".join(
                f"  - {s.get('name', s.get('step', '?'))}: "
                f"{s.get('status', 'unknown')} "
                f"({s.get('duration_ms', '?')}ms)"
                for s in step_records
            )
            context_parts.append(
                f"Step Execution Records (observability spans):\n{step_summary}\n\n"
                f"Verify that all expected steps completed successfully. "
                f"Flag any step that failed, took too long, or produced errors."
            )

        # FR8: Include deterministic output validation results
        if output_validation_result:
            context_parts.append(
                f"Deterministic Output Validation:\n{output_validation_result}\n\n"
                f"Consider these structural checks when assessing overall confidence."
            )

        # FR7: Inject retry feedback so the verifier focuses on missing evidence
        if retry_feedback:
            feedback_str = "\n".join(f"  - {m}" for m in retry_feedback)
            context_parts.append(
                f"[Retry Feedback — Previous attempt flagged missing evidence:\n{feedback_str}\n"
                f"Please check if these gaps have been addressed.]"
            )

        prompt = f"{VERIFIER_PROMPT}\n\nEvidence:\n\n" + "\n\n".join(context_parts)

        result = await self.chat(
            [{"role": "user", "content": prompt}],
            response_format=VerificationResult,
        )
        return VerificationResult(**result)
