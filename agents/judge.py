"""Judge Agent — uses LLM to verify the final output using trace logs/spans."""

from __future__ import annotations

from typing import Any
from agents.base import BaseAgent
from models import FinalReport, JudgeResult

JUDGE_PROMPT = """You are an independent QA auditor. Your primary task is to verify if the system followed the required research workflow or if it skipped steps/falsified execution. LLM agents can sometimes lie or hallucinate conclusions without actually performing the work. You must audit the execution trace logs to ensure all required steps were actually executed and that their actual outputs were used in the final report.

The accuracy of the trading prediction or final trade recommendation itself is NOT your concern (it is completely fine if the final trading recommendation/bias is wrong). Your concern is strictly:
1. Execution Verification: Did the agent actually run all the planned steps (intent classification, planning, market context chart capture/analysis, stock chart capture/analysis, news search, news sentiment scoring) in the trace logs?
2. Output Lineage: Does the final report utilize the actual outputs returned by the tools in the trace logs? If a step failed (e.g. returned an error or empty output) but the final report pretends it succeeded with real data, flag this as a mismatch.
3. Tool Usage Integrity: Did the agent bypass any tool or fabricate results?

Analyze the provided final report and the execution steps trace.
Return your verdict as a JSON object with these keys:
- workflow_verified (boolean)
- evaluation_notes (string summarizing your validation reasoning)
- mismatches_found (list of strings describing any errors/discrepancies found, or empty list if none)
- steps_verified_count (integer count of successful execution steps)
"""

class JudgeAgent(BaseAgent):
    """Audits the coordinator's final report against execution trace logs."""

    async def run(
        self,
        report: FinalReport,
        step_records: list[dict[str, Any]],
    ) -> JudgeResult:
        context_parts = []
        
        # Format the final report
        context_parts.append(f"FINAL REPORT:\n{report.model_dump_json(indent=2)}")
        
        # Format the execution steps / spans
        step_summary = "\n".join(
            f"  - Step: {s.get('name', s.get('step', '?'))}\n"
            f"    Status: {s.get('status', 'unknown')}\n"
            f"    Duration: {s.get('duration_ms', '?')}ms\n"
            f"    Output: {s.get('output', None)}\n"
            f"    Error: {s.get('error', None)}"
            for s in step_records
        )
        context_parts.append(f"EXECUTION TRACE LOG / SPANS:\n{step_summary}")
        
        prompt = f"{JUDGE_PROMPT}\n\nTrace Data:\n\n" + "\n\n".join(context_parts)
        
        result = await self.chat(
            [{"role": "user", "content": prompt}],
            response_format=JudgeResult,
        )
        return JudgeResult(**result)
