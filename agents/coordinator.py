"""Coordinator Agent — orchestrates the research pipeline end-to-end.

Includes:
- FR1: Intent classifier
- FR4: Market context generation
- FR3: Chart vision analysis (via Qwen2.5-VL)
- FR5: News & sentiment
- FR6: Verification layer (now checks step records + output validation)
- FR7: Retry engine (confidence < threshold -> re-run)
- FR8: Observability (every step recorded as a span)
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agents.base import BaseAgent
from agents.planner import Intent, PlannerAgent, Plan
from agents.verifier import VerifierAgent
from agents.judge import JudgeAgent
from config import settings
from context.context_manager import ContextManager
from context.memory import MemoryStore
from models import (
    AnalysisType,
    ChartAnalysis,
    ExecutionStep,
    FinalReport,
    MarketContext,
    SentimentAnalysis,
    Timeframe,
    TradeSuggestion,
)
from observability.langfuse import LangfuseTracker, Span
from tools.market import MarketContextTool
from tools.screenshot import ScreenshotCapture
from tools.search import NewsSearcher
from tools.sentiment import SentimentAnalyzer
from tools.validator import OutputValidator
from tools.vision import ChartVisionAnalyzer


class IntentResponse(BaseModel):
    symbol: str = Field(description="Stock symbol, e.g. RELIANCE, AAPL")
    timeframe: str = Field(description="intraday, short_term, or swing")
    analysis_type: str = Field(description="technical, fundamental, sentiment, or full")


INTENT_PROMPT = """Extract the trading intent from the user query.

Return a JSON object with:
- symbol: the stock symbol (uppercase)
- timeframe: "intraday", "short_term", or "swing"
- analysis_type: "technical", "fundamental", "sentiment", or "full"

If the query is ambiguous, make reasonable defaults (intraday, full)."""


class CoordinatorAgent(BaseAgent):
    """Main orchestrator. Receives a query, runs the full pipeline with retry."""

    def __init__(
        self,
        browser_headless: bool | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._browser_headless = browser_headless if browser_headless is not None else settings.browser_headless
        self._planner = PlannerAgent(model=self.model)
        self._verifier = VerifierAgent(model=self.model)
        self._judge = JudgeAgent(model=self.model)
        self._validator = OutputValidator()
        self._tools_initialized = False
        self._market_tool: MarketContextTool | None = None
        self._vision_analyzer: ChartVisionAnalyzer | None = None
        self._news_searcher: NewsSearcher | None = None
        self._sentiment_analyzer: SentimentAnalyzer | None = None
        self._screenshot: ScreenshotCapture | None = None
        self._context_mgr: ContextManager | None = None
        self._store: MemoryStore | None = None
        self._observability: LangfuseTracker | None = None
        # Track spans for current execution
        self._spans: list[Span] = []

    # ── Lazy initialisation ──────────────────────────────────────────────

    async def _ensure_tools(self) -> None:
        if self._tools_initialized:
            return
        self._market_tool = MarketContextTool()
        self._vision_analyzer = ChartVisionAnalyzer()
        self._news_searcher = NewsSearcher()
        self._sentiment_analyzer = SentimentAnalyzer()
        self._screenshot = ScreenshotCapture()
        self._store = MemoryStore()
        self._context_mgr = ContextManager(self._store)
        self._observability = LangfuseTracker()
        await self._observability.initialize()
        self._tools_initialized = True

    # ── Span helpers ─────────────────────────────────────────────────────

    def _start_step_span(self, name: str) -> Span:
        """Create both an ExecutionStep and an observability span."""
        assert self._observability is not None
        span = self._observability.start_span(name)
        self._spans.append(span)
        return span

    def _end_step_span(
        self,
        span: Span,
        status: str = "success",
        output: Any = None,
        error: str | None = None,
    ) -> None:
        """Complete a step span."""
        assert self._observability is not None
        self._observability.end_span(span, status=status, output=output, error=error)

    # ── Intent classifier (FR1) ──────────────────────────────────────────

    async def classify_intent(self, query: str) -> Intent:
        """Extract structured intent from a free-text query."""
        result = await self.chat(
            [{"role": "user", "content": f"{INTENT_PROMPT}\n\nQuery: {query}"}],
            response_format=IntentResponse,
        )
        return Intent(
            symbol=result["symbol"],
            timeframe=Timeframe(result["timeframe"]),
            analysis_type=AnalysisType(result["analysis_type"]),
            raw_query=query,
        )

    # ── Market context (FR4) ─────────────────────────────────────────────

    async def _gather_market_context(self, symbol: str) -> MarketContext:
        """Gather macro market context using actual BANKNIFTY chart analysis."""
        assert self._market_tool is not None
        assert self._vision_analyzer is not None
        assert self._screenshot is not None

        span = self._start_step_span("market_context")
        try:
            from browser.tradingview import TradingViewBrowser
            print("    [market_context] Navigating to NSE:BANKNIFTY chart...")
            async with TradingViewBrowser(headless=self._browser_headless) as tv:
                await tv.search_symbol("NSE:BANKNIFTY")
                await tv.set_timeframe("1D")
                image_bytes = await tv.capture_screenshot()
                
                path = await self._screenshot.save(image_bytes, "BANKNIFTY", label="chart")
                print(f"    [market_context] Saved BANKNIFTY chart to {path}")
                
                print("    [market_context] Analyzing BANKNIFTY chart with vision model...")
                banknifty_analysis = await self._vision_analyzer.analyze(image_bytes, "NSE:BANKNIFTY")
                print(f"    [market_context] BANKNIFTY trend detected: {banknifty_analysis.trend}")

            result = await self._market_tool.get_context(symbol, banknifty_analysis)
            self._end_step_span(span, output=result.model_dump())
            return result
        except Exception as exc:
            self._end_step_span(span, status="failed", error=str(exc))
            raise

    # ── Chart vision analysis (FR3) ──────────────────────────────────────

    async def _analyse_chart(self, symbol: str) -> tuple[ChartAnalysis, str | None]:
        """Capture a TradingView screenshot and analyse it with the vision model.

        Returns (analysis, screenshot_path_or_none).
        """
        assert self._vision_analyzer is not None
        assert self._screenshot is not None

        from browser.tradingview import TradingViewBrowser

        span = self._start_step_span("chart_analysis")
        screenshot_path = None
        try:
            async with TradingViewBrowser(headless=self._browser_headless) as tv:
                await tv.search_symbol(symbol)
                await tv.set_timeframe("1D")
                image_bytes = await tv.capture_screenshot()

                path = await self._screenshot.save(image_bytes, symbol, label="chart")
                screenshot_path = str(path)

                analysis = await self._vision_analyzer.analyze(image_bytes, symbol)
                self._end_step_span(span, output=analysis.model_dump())
                return analysis, screenshot_path
        except Exception as exc:
            fallback = ChartAnalysis(
                trend="Unknown (chart capture unavailable)",
                notes=f"Chart analysis error: {exc}",
            )
            self._end_step_span(span, status="failed" if "Unknown" in fallback.trend else "success",
                              output=fallback.model_dump(), error=str(exc))
            return fallback, None

    # ── News & sentiment (FR5) ───────────────────────────────────────────

    async def _gather_news_and_sentiment(
        self, symbol: str
    ) -> tuple[list[Any], SentimentAnalysis]:
        """Gather news and analyse sentiment."""
        assert self._news_searcher is not None
        assert self._sentiment_analyzer is not None

        news_span = self._start_step_span("news_search")
        try:
            articles = await self._news_searcher.search(symbol)
            self._end_step_span(news_span, output={"count": len(articles)})
        except Exception as exc:
            articles = []
            self._end_step_span(news_span, status="failed", error=str(exc))

        sentiment_span = self._start_step_span("sentiment_analysis")
        try:
            sentiment = await self._sentiment_analyzer.analyze(articles)
            self._end_step_span(sentiment_span, output=sentiment.model_dump())
        except Exception as exc:
            from models import SentimentLabel
            sentiment = type('obj', (object,), {
                'overall': SentimentLabel.neutral,
                'score': 0.0,
                'articles': articles,
                'summary': f'Error: {exc}',
                'model_dump': lambda: {'overall': 'neutral', 'score': 0.0}
            })()
            self._end_step_span(sentiment_span, status="failed", error=str(exc))

        return articles, sentiment

    # ── Comparison step ──────────────────────────────────────────────────

    async def _compare_charts(self, symbol: str, stock_chart: ChartAnalysis, market: MarketContext) -> str:
        """Compare the stock chart analysis with the BANKNIFTY index chart analysis."""
        prompt = (
            f"You are a quantitative researcher comparing a stock against its index.\n\n"
            f"Stock: {symbol}\n"
            f"Stock Chart Trend: {stock_chart.trend}\n"
            f"Stock Chart Pattern: {stock_chart.pattern}\n"
            f"Stock Chart RSI: {stock_chart.rsi}\n"
            f"Stock Chart Breakout Probability: {stock_chart.breakout_probability}\n\n"
            f"Index: BANKNIFTY\n"
            f"Index Chart Trend: {market.banknifty_trend}\n"
            f"Index Chart Pattern: {market.banknifty_pattern}\n"
            f"Index Chart RSI: {market.banknifty_rsi}\n\n"
            f"Compare the stock relative to the index. Determine:\n"
            f"1. Is the stock outperforming or underperforming the index?\n"
            f"2. Are the chart patterns in agreement or contradiction?\n"
            f"3. Provide a brief 1-2 sentence comparison summary.\n\n"
            f"Return a clean text paragraph summarizing this comparison."
        )
        
        result = await self.chat(
            [{"role": "user", "content": prompt}],
        )
        return result.get("text", str(result))

    # ── Retry Engine (FR7) ───────────────────────────────────────────────

    async def _run_with_retry(
        self,
        intent: Intent,
        plan: Plan,
    ) -> dict[str, Any]:
        """Execute the plan steps and retry if confidence is below threshold.

        Each step execution is recorded as an observability span (FR8).
        The final verification includes step records and output validation.
        """
        assert self._verifier is not None

        max_retries = settings.max_retries
        symbol = intent.symbol

        market: MarketContext | None = None
        chart: ChartAnalysis | None = None
        sentiment: SentimentAnalysis | None = None
        screenshot_path: str | None = None

        missing_evidence_feedback: list[str] = []
        span_boundary = len(self._spans)  # Track where this attempt's tool spans start

        for attempt in range(max_retries + 1):
            if attempt > 0:
                retry_span = self._start_step_span(f"retry_attempt_{attempt}")
                span_boundary = len(self._spans)  # Reset boundary for this attempt
                print(f"  [retry] Attempt {attempt + 1}/{max_retries + 1}")

            # Gather market context (recorded as span inside)
            market = await self._gather_market_context(symbol)

            # Gather chart analysis and news concurrently
            chart_task = self._analyse_chart(symbol)
            news_task = self._gather_news_and_sentiment(symbol)

            (chart, screenshot_path), (_, sentiment) = await asyncio.gather(
                chart_task, news_task
            )

            # Perform Stock vs Bank Nifty comparison
            comparison_span = self._start_step_span("compare_charts")
            try:
                print("    [compare_charts] Comparing stock chart against BANKNIFTY chart...")
                comparison = await self._compare_charts(symbol, chart, market)
                market.comparison = comparison
                print(f"    [compare_charts] Comparison: {comparison}")
                self._end_step_span(comparison_span, output={"comparison": comparison})
            except Exception as exc:
                self._end_step_span(comparison_span, status="failed", error=str(exc))
                market.comparison = f"Comparison error: {exc}"

            # Verify (FR6) — only pass spans from the current attempt
            current_spans = self._spans[span_boundary:]
            span_summary = [s.to_dict() for s in current_spans]
            verification = await self._verifier.run(
                symbol=symbol,
                market=market,
                chart=chart,
                sentiment=sentiment,
                retry_feedback=missing_evidence_feedback,
                step_records=span_summary,
            )

            if attempt > 0:
                self._end_step_span(retry_span,
                                  status="success" if verification.passed else "failed",
                                  output={"passed": verification.passed, "confidence": verification.confidence_score})

            if verification.passed or attempt >= max_retries:
                break

            for m in (verification.missing_evidence or []):
                msg = f"{m.aspect}: {m.detail}"
                if msg not in missing_evidence_feedback:
                    missing_evidence_feedback.append(msg)

        return {
            "market": market,
            "chart": chart,
            "sentiment": sentiment,
            "verification": verification,
            "screenshot_path": screenshot_path,
        }

    # ── Main run method ──────────────────────────────────────────────────

    async def run(  # type: ignore[override]
        self,
        query: str,
        market_context_data: dict[str, Any] | None = None,
        chart_analysis_data: dict[str, Any] | None = None,
        sentiment_data: dict[str, Any] | None = None,
    ) -> FinalReport:
        """Run the full research pipeline.

        Every step is recorded as an observability span (FR8).
        After execution the FinalReport is validated deterministically
        and the results are passed to the verifier.
        """
        await self._ensure_tools()
        assert self._observability is not None
        assert self._context_mgr is not None
        assert self._store is not None

        self._spans = []
        trace = await self._observability.trace(
            name="trademind_research",
            metadata={"query": query},
        )

        start = time.monotonic()
        steps: list[ExecutionStep] = []

        def _add_step(name: str, agent: str) -> ExecutionStep:
            step = ExecutionStep(step=name, agent=agent, status="running")
            steps.append(step)
            return step

        def _complete_step(
            step: ExecutionStep, status: str = "success", output: Any = None
        ) -> None:
            step.status = status
            step.output = output
            step.completed_at = datetime.now(timezone.utc)

        def _fail_step(step: ExecutionStep, error: str) -> None:
            step.status = "failed"
            step.error = error
            step.completed_at = datetime.now(timezone.utc)

        # ── 1. Classify intent ──────────────────────────────────────────
        intent_span = self._start_step_span("classify_intent")
        intent_step = _add_step("classify_intent", "coordinator")
        try:
            intent = await self.classify_intent(query)
            _complete_step(intent_step, output=intent.model_dump())
            self._end_step_span(intent_span, output=intent.model_dump())
        except Exception as exc:
            _fail_step(intent_step, str(exc))
            self._end_step_span(intent_span, status="failed", error=str(exc))
            raise

        # ── 2. Gather context ──────────────────────────────────────────
        context_span = self._start_step_span("gather_context")
        context_step = _add_step("gather_context", "context_manager")
        try:
            context_data = await self._context_mgr.enrich(query, intent.symbol)
            context_prompt = self._context_mgr.format_context_prompt(context_data)
            _complete_step(context_step, output=context_data)
            self._end_step_span(context_span, output=context_data)
        except Exception as exc:
            context_data = {}
            context_prompt = ""
            _fail_step(context_step, str(exc))
            self._end_step_span(context_span, status="failed", error=str(exc))

        # ── 3. Create the plan ──────────────────────────────────────────
        plan_span = self._start_step_span("create_plan")
        plan_step = _add_step("create_plan", "planner")
        try:
            plan: Plan = await self._planner.run(intent, context=context_prompt)
            _complete_step(plan_step, output=plan.model_dump())
            self._end_step_span(plan_span, output=plan.model_dump())
        except Exception as exc:
            plan = Plan(intent="", steps=[])
            _fail_step(plan_step, str(exc))
            self._end_step_span(plan_span, status="failed", error=str(exc))

        # ── 4. Execute plan steps (with retry) ──────────────────────────
        execute_span = self._start_step_span("execute_plan")
        execute_step = _add_step("execute_plan", "coordinator")

        try:
            if market_context_data or chart_analysis_data or sentiment_data:
                market = MarketContext(**market_context_data) if market_context_data else None
                chart = ChartAnalysis(**chart_analysis_data) if chart_analysis_data else None
                sentiment = SentimentAnalysis(**sentiment_data) if sentiment_data else None
                span_summary = self._observability.get_span_summary() if self._observability else []
                verification = await self._verifier.run(
                    symbol=intent.symbol,
                    market=market,
                    chart=chart,
                    sentiment=sentiment,
                    step_records=span_summary,
                )
                collected = {
                    "market": market,
                    "chart": chart,
                    "sentiment": sentiment,
                    "verification": verification,
                    "screenshot_path": None,
                }
            else:
                collected = await self._run_with_retry(intent, plan)

            _complete_step(execute_step, output={k: str(type(v)) for k, v in collected.items()})
            self._end_step_span(execute_span, output={"steps_completed": len(self._spans)})
        except Exception as exc:
            _fail_step(execute_step, str(exc))
            self._end_step_span(execute_span, status="failed", error=str(exc))
            collected = {"market": None, "chart": None, "sentiment": None, "verification": None, "screenshot_path": None}

        market = collected.get("market")
        chart = collected.get("chart")
        sentiment = collected.get("sentiment")
        verification = collected.get("verification")
        screenshot_path = collected.get("screenshot_path")



        # ── 5. Build final report ────────────────────────────────────────
        build_span = self._start_step_span("build_report")
        report_step = _add_step("build_report", "coordinator")

        evidence: list[str] = []
        risks: list[str] = []

        if isinstance(market, MarketContext) and market.summary:
            evidence.append(f"Market context: {market.summary}")
            if market.comparison:
                evidence.append(f"Index comparison: {market.comparison}")
        if isinstance(chart, ChartAnalysis):
            if chart.trend:
                evidence.append(f"Chart trend: {chart.trend}")
            if chart.pattern:
                evidence.append(f"Pattern detected: {chart.pattern}")
        if isinstance(sentiment, SentimentAnalysis):
            evidence.append(f"Sentiment: {sentiment.overall.value} ({sentiment.score:+.2f})")

        if hasattr(verification, 'contradictions') and verification.contradictions:
            for c in verification.contradictions:
                risks.append(f"Contradiction — {c.aspect}: {c.detail}")
        if hasattr(verification, 'missing_evidence') and verification.missing_evidence:
            for m in verification.missing_evidence:
                risks.append(f"Missing — {m.aspect}: {m.detail}")

        bias = self._determine_bias(
            verification.confidence_score if hasattr(verification, "confidence_score") else 0.0,
            chart if isinstance(chart, ChartAnalysis) else None,
            sentiment if isinstance(sentiment, SentimentAnalysis) else None,
        )

        # Include observability spans in detailed analysis (filter for current run)
        span_summary = self._observability.get_span_summary() if self._observability else []

        report = FinalReport(
            symbol=intent.symbol,
            bias=bias,
            confidence=round(verification.confidence_score, 2) if hasattr(verification, "confidence_score") else 0.0,
            evidence=evidence,
            risks=risks,
            suggested_trade=TradeSuggestion(
                rationale="Generated by verifying confluence of technical, market, and sentiment signals.",
            ),
            detailed_analysis={
                "intent": intent.model_dump(),
                "plan": plan.model_dump() if plan else {},
                "context": context_data,
                "market_context": market.model_dump() if isinstance(market, MarketContext) else market,
                "chart_analysis": chart.model_dump() if isinstance(chart, ChartAnalysis) else chart,
                "sentiment": sentiment.model_dump() if isinstance(sentiment, SentimentAnalysis) else sentiment,
                "screenshot_path": screenshot_path,
                "observability_spans": span_summary,
            },
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # ── 6. Deterministic output validation ──────────────────────────
        # Validate the final report structure (pure deterministic checks)
        validate_span = self._start_step_span("output_validation")
        report_issues: list[str] = []
        step_checks: list[Any] = []
        validation_text = ""

        try:
            report_issues = self._validator.validate_report(report)
            step_checks = self._validator.validate_steps(steps)
            validation_text = self._validator.format_validation_report(
                report_issues, step_checks
            )
            self._end_step_span(validate_span, output={
                "report_issues": len(report_issues),
                "steps_total": len(steps),
                "steps_failed": sum(1 for s in step_checks if s.status == "failed"),
            })

            # Add validation issues to risks
            for issue in report_issues:
                risks.append(f"Validation — {issue}")
            for check in step_checks:
                if check.status == "failed":
                    risks.append(f"Step failed — {check.step}: {check.issue}")
        except Exception as exc:
            validation_text = f"Output validation error: {exc}"
            self._end_step_span(validate_span, status="failed", error=str(exc))

        # Update report with validation details
        verification_dict = verification.model_dump() if hasattr(verification, "model_dump") else {}
        verification_dict["step_checks"] = [s.model_dump() for s in step_checks]
        verification_dict["output_validation"] = validation_text
        report.detailed_analysis["verification"] = verification_dict
        report.detailed_analysis["output_validation"] = validation_text

        # ── 7. Run LLM Judge ───────────────────────────────────────────
        judge_span = self._start_step_span("llm_judge")
        judge_step = _add_step("llm_judge", "judge")
        
        try:
            current_spans_summary = [s.to_dict() for s in self._spans if s.name != "llm_judge"]
            judge_result = await self._judge.run(
                report=report,
                step_records=current_spans_summary,
            )
            
            report.detailed_analysis["llm_judge"] = judge_result.model_dump()
            
            print("\n================== LLM JUDGE VERDICT ==================")
            print(f"Workflow Verified: {judge_result.workflow_verified}")
            print(f"Evaluation Notes: {judge_result.evaluation_notes}")
            if judge_result.mismatches_found:
                print(f"Mismatches Found: {judge_result.mismatches_found}")
            print("=======================================================")
            
            _complete_step(judge_step, output=judge_result.model_dump())
            self._end_step_span(judge_span, output=judge_result.model_dump())
        except Exception as exc:
            _fail_step(judge_step, str(exc))
            self._end_step_span(judge_span, status="failed", error=str(exc))

        _complete_step(report_step, output=report.model_dump())
        self._end_step_span(build_span, output={"symbol": report.symbol, "confidence": report.confidence})

        # ── Save to memory ──────────────────────────────────────────────
        duration_ms = (time.monotonic() - start) * 1000
        self._store.save_execution(
            query=query,
            symbol=intent.symbol,
            intent=intent.model_dump(),
            report=report.model_dump(),
            confidence=report.confidence,
            bias=report.bias.value if hasattr(report.bias, "value") else str(report.bias),
            duration_ms=duration_ms,
        )

        return report

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _determine_bias(
        confidence: float,
        chart: ChartAnalysis | None,
        sentiment: SentimentAnalysis | None,
    ) -> Bias:
        """Simple heuristic bias determination."""
        from models import Bias

        if confidence < 0.4:
            return Bias.neutral

        bullish_signals = 0
        bearish_signals = 0

        if chart:
            trend_lower = chart.trend.lower() if chart.trend else ""
            if "bull" in trend_lower or "up" in trend_lower:
                bullish_signals += 1
            elif "bear" in trend_lower or "down" in trend_lower:
                bearish_signals += 1
            if chart.breakout_probability > 0.6:
                bullish_signals += 1

        if sentiment:
            if sentiment.overall.value == "positive":
                bullish_signals += 1
            elif sentiment.overall.value == "negative":
                bearish_signals += 1

        if bullish_signals > bearish_signals:
            return Bias.bullish
        elif bearish_signals > bullish_signals:
            return Bias.bearish
        return Bias.neutral

    async def close(self) -> None:
        """Clean up all resources."""
        await self._planner.close()
        await self._verifier.close()

        if self._market_tool:
            await self._market_tool.close()
        if self._vision_analyzer:
            await self._vision_analyzer.close()
        if self._news_searcher:
            await self._news_searcher.close()
        if self._sentiment_analyzer:
            await self._sentiment_analyzer.close()
        if self._observability:
            await self._observability.close()
        if self._store:
            self._store.close()

        await super().close()
