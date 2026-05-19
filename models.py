"""Shared Pydantic models used across agents, tools, and the API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ───────────────────────────────────────────────────────────────


class Timeframe(str, Enum):
    intraday = "intraday"
    short_term = "short_term"
    swing = "swing"


class AnalysisType(str, Enum):
    technical = "technical"
    fundamental = "fundamental"
    sentiment = "sentiment"
    full = "full"


class Bias(str, Enum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class SentimentLabel(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


# ── Intent ──────────────────────────────────────────────────────────────


class Intent(BaseModel):
    """Parsed intent from a user query."""

    symbol: str
    timeframe: Timeframe = Timeframe.intraday
    analysis_type: AnalysisType = AnalysisType.full
    raw_query: str = ""


# ── Market Context ──────────────────────────────────────────────────────


class IndexData(BaseModel):
    name: str
    change_pct: float = 0.0
    trend: str = ""


class SectorData(BaseModel):
    name: str
    change_pct: float = 0.0
    strength: str = ""


class MarketContext(BaseModel):
    banknifty_trend: str = ""
    banknifty_pattern: str = ""
    banknifty_rsi: float | None = None
    comparison: str = ""
    sectors: list[SectorData] = []
    market_breadth: str = ""
    volatility_index: float = 0.0
    summary: str = ""


# ── Chart Analysis ──────────────────────────────────────────────────────


class SupportResistance(BaseModel):
    support: list[float] = []
    resistance: list[float] = []


class ChartAnalysis(BaseModel):
    trend: str = ""
    support_resistance: SupportResistance = SupportResistance()
    rsi: float | None = None
    breakout_probability: float = 0.0
    volume_confidence: float = 0.0
    pattern: str = ""
    notes: str = ""


# ── News / Sentiment ────────────────────────────────────────────────────


class NewsArticle(BaseModel):
    title: str
    source: str = ""
    url: str = ""
    summary: str = ""
    sentiment: SentimentLabel = SentimentLabel.neutral
    relevance: float = 0.5


class SentimentAnalysis(BaseModel):
    overall: SentimentLabel = SentimentLabel.neutral
    score: float = 0.0  # -1 to +1
    articles: list[NewsArticle] = []
    summary: str = ""


# ── Verification ────────────────────────────────────────────────────────


class Contradiction(BaseModel):
    aspect: str
    detail: str


class MissingEvidence(BaseModel):
    aspect: str
    detail: str


class StepCheck(BaseModel):
    step: str
    agent: str
    status: str  # success | failed | skipped
    issue: str = ""

    @field_validator("step", mode="before")
    @classmethod
    def coerce_step(cls, v: Any) -> str:
        return str(v)

    @field_validator("issue", mode="before")
    @classmethod
    def coerce_issue(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class VerificationResult(BaseModel):
    confidence_score: float = 0.0
    contradictions: list[Contradiction] = []
    missing_evidence: list[MissingEvidence] = []
    signal_agreement: str = ""
    risk_reward_ratio: float | None = None
    passed: bool = False
    step_checks: list[StepCheck] = []  # FR8: per-step observability checks
    output_validation: str = ""  # deterministic structural check result


# ── Trade Suggestion ────────────────────────────────────────────────────


class TradeSuggestion(BaseModel):
    entry: str = ""
    stop_loss: str = ""
    target: str = ""
    rationale: str = ""


class FinalReport(BaseModel):
    symbol: str = ""
    bias: Bias = Bias.neutral
    confidence: float = 0.0
    evidence: list[str] = []
    risks: list[str] = []
    suggested_trade: TradeSuggestion = TradeSuggestion()
    detailed_analysis: dict[str, Any] = {}
    generated_at: str = ""


# ── Execution Log ───────────────────────────────────────────────────────


class ExecutionStep(BaseModel):
    step: str
    agent: str
    status: str = "pending"  # pending | running | success | failed | retry
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: Any = None
    error: str | None = None
    retry_count: int = 0


class ExecutionTrace(BaseModel):
    query: str
    intent: Intent | None = None
    steps: list[ExecutionStep] = []
    final_report: FinalReport | None = None
    total_duration_ms: float = 0.0
    token_usage: dict[str, int] = {}


class JudgeResult(BaseModel):
    workflow_verified: bool = False
    evaluation_notes: str = ""
    mismatches_found: list[str] = []
    steps_verified_count: int = 0

