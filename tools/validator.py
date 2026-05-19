"""Output validator — deterministic structural checks on the FinalReport.

No LLM calls. Pure Pydantic validation of data structure, completeness,
and internal consistency.
"""

from __future__ import annotations

from typing import Any

from models import (
    Bias,
    ExecutionStep,
    FinalReport,
    StepCheck,
)


class OutputValidator:
    """Performs deterministic validation of the FinalReport and step execution.

    All checks are pure logic — no LLM calls. This ensures the system
    can always catch basic structural issues regardless of model output.
    """

    @staticmethod
    def validate_report(report: FinalReport) -> list[str]:
        """Check the FinalReport for structural completeness.

        Returns a list of issues found (empty = all passed).
        """
        issues: list[str] = []

        # ── Required fields ──────────────────────────────────────────
        if not report.symbol:
            issues.append("Report symbol is empty")
        if not report.generated_at:
            issues.append("Report generated_at timestamp is missing")

        # ── Confidence bounds ────────────────────────────────────────
        if not (0.0 <= report.confidence <= 1.0):
            issues.append(f"Confidence {report.confidence} out of range [0, 1]")

        # ── Bias validity ────────────────────────────────────────────
        valid_biases = {b.value for b in Bias}
        bias_str = report.bias.value if hasattr(report.bias, "value") else str(report.bias)
        if bias_str not in valid_biases:
            issues.append(f"Invalid bias value: {bias_str}")

        # ── Evidence presence ────────────────────────────────────────
        if not report.evidence:
            issues.append("No evidence collected — report may lack supporting data")

        # ── Detailed analysis ────────────────────────────────────────
        if not report.detailed_analysis:
            issues.append("Detailed analysis is empty")
        else:
            expected_keys = {"intent", "plan", "market_context", "chart_analysis", "sentiment", "verification"}
            missing_keys = expected_keys - set(report.detailed_analysis.keys())
            if missing_keys:
                issues.append(f"Detailed analysis missing keys: {', '.join(sorted(missing_keys))}")

        return issues

    @staticmethod
    def validate_steps(steps: list[ExecutionStep]) -> list[StepCheck]:
        """Check that all execution steps completed successfully.

        Returns a list of StepCheck objects for inclusion in verification.
        """
        checks: list[StepCheck] = []

        for step in steps:
            if step.status == "success":
                checks.append(StepCheck(
                    step=step.step,
                    agent=step.agent,
                    status="success",
                ))
            elif step.status == "failed":
                checks.append(StepCheck(
                    step=step.step,
                    agent=step.agent,
                    status="failed",
                    issue=step.error or "Step failed without error detail",
                ))
            elif step.status == "retry":
                checks.append(StepCheck(
                    step=step.step,
                    agent=step.agent,
                    status="success",
                    issue=f"Succeeded after {step.retry_count} retries",
                ))
            else:
                checks.append(StepCheck(
                    step=step.step,
                    agent=step.agent,
                    status="failed",
                    issue=f"Step ended with unexpected status: {step.status}",
                ))

        return checks

    @staticmethod
    def all_steps_passed(steps: list[ExecutionStep]) -> bool:
        """Quick check: did all steps complete successfully?"""
        return all(s.status == "success" for s in steps)

    @staticmethod
    def format_validation_report(
        report_issues: list[str],
        step_checks: list[StepCheck],
    ) -> str:
        """Format validation results into a human-readable string."""
        parts: list[str] = []

        # Step checks
        failed_steps = [c for c in step_checks if c.status == "failed"]
        parts.append(f"Steps: {len(step_checks)} total, {len(failed_steps)} failed")
        for c in step_checks:
            icon = "✔" if c.status == "success" else "✖"
            parts.append(f"  {icon} {c.step} ({c.agent})")
            if c.issue:
                parts.append(f"     {c.issue}")

        # Report issues
        if report_issues:
            parts.append(f"\nReport issues ({len(report_issues)}):")
            for issue in report_issues:
                parts.append(f"  ⚠ {issue}")
        else:
            parts.append("\nReport structure: ✔ All checks passed")

        return "\n".join(parts)
