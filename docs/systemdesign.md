# System Design Document — Agentic Harness Demo

> **AI-powered Intraday Trading Research Harness**
> Version 0.1.0 | Local-first | Multi-agent architecture

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [System Context & Scope](#2-system-context--scope)
3. [Component Architecture](#3-component-architecture)
4. [Data Models](#4-data-models)
5. [Agent Design](#5-agent-design)
6. [Tool Design](#6-tool-design)
7. [Execution Flow](#7-execution-flow)
8. [Retry Engine (FR7)](#8-retry-engine-fr7)
9. [Browser Automation](#9-browser-automation)
10. [API Layer](#10-api-layer)
11. [Observability](#11-observability)
12. [Configuration & Environment](#12-configuration--environment)
13. [Storage Schema](#13-storage-schema)
14. [Error Handling Strategy](#14-error-handling-strategy)
15. [Extensibility Points](#15-extensibility-points)

---

## 1. Architecture Overview

### High-Level Philosophy

Agentic Harness Demo follows the **`observe → reason → execute → verify → retry`** loop:

```
                    ┌─────────────────────────────────────┐
                    │          User Query                  │
                    └────────────┬────────────────────────┘
                                 │
                    ┌────────────▼────────────────────────┐
                    │      1. Intent Classification        │  ◄── FR1
                    │     (symbol, timeframe, type)        │
                    └────────────┬────────────────────────┘
                                 │
                    ┌────────────▼────────────────────────┐
                    │      2. Context Enrichment           │
                    │  (past analyses, system state)       │
                    └────────────┬────────────────────────┘
                                 │
                    ┌────────────▼────────────────────────┐
                    │      3. Plan Generation              │
                    │  (ordered steps with dependencies)   │
                    └────────────┬────────────────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Market Context  │ │  Chart Vision   │ │  News + Sentiment│
    │     (FR4)        │ │     (FR3)       │ │     (FR5)        │
    └────────┬─────────┘ └────────┬────────┘ └────────┬────────┘
              │                   │                    │
              └───────────────────┼────────────────────┘
                                  │
                    ┌─────────────▼─────────────────────┐
                    │      4. Verification Layer (FR6)   │
                    │  cross-check → contradictions →    │
                    │  confidence score                  │
                    └─────────────┬─────────────────────┘
                                  │
                    ┌─────────────▼─────────────────────┐
                    │  Confidence ≥ Threshold?           │
                    └─────────────┬─────────────────────┘
                        YES │              │ NO
                            ▼              ▼
                    ┌──────────────┐  ┌────────────────┐
                    │  5. Retry    │  │  Improve Prompt │
                    │   Complete   │  │  Re-run Tools   │──◄── FR7
                    └──────┬───────┘  └────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Final Report│
                    │  (structured │
                    │   JSON)      │
                    └──────────────┘
```

### Architectural Style

- **Multi-Agent Orchestration**: Central coordinator delegates to specialized agents
- **Pipeline Architecture**: Deterministic step ordering with parallel branches
- **Observer Pattern**: Verifier observes outputs, closes the feedback loop
- **Strategy Pattern**: Tools are interchangeable implementations behind interfaces

---

## 2. System Context & Scope

### In Scope (V1)

| Area | Coverage |
|---|---|
| **Intent parsing** | Extract symbol, timeframe, analysis type from natural language |
| **Market context** | NIFTY/BankNifty trends, sector movement, volatility (LLM-generated) |
| **Chart analysis** | TradingView → Playwright screenshot → Qwen2.5-VL vision analysis |
| **News retrieval** | LLM-generated plausible news headlines (replaceable with real API) |
| **Sentiment scoring** | Aggregate article-level sentiment into composite score |
| **Signal verification** | Cross-check all signals, identify contradictions, compute confidence |
| **Retry engine** | If confidence < threshold, collect missing evidence and re-verify |
| **Observability** | Langfuse stub (no-op until credentials configured) |
| **Persistence** | SQLite for execution history |
| **CLI** | Click-based command-line interface |
| **REST API** | FastAPI with `/analyse`, `/history`, `/health` endpoints |

### Out of Scope (V1)

- Autonomous trading or order placement
- Brokerage API integration
- Real-time data streaming
- Financial guarantees or predictions
- Multi-user authentication
- WebSocket feeds

---

## 3. Component Architecture

### Package Structure

```
agentic-harness-demo/
│
├── agents/                    # Orchestration layer
│   ├── base.py                # Abstract base with Ollama HTTP client
│   ├── coordinator.py         # Pipeline orchestrator + retry engine
│   ├── planner.py             # Intent → execution plan
│   ├── verifier.py            # Signal cross-check + confidence scoring
│   └── reflector.py           # Post-execution quality review
│
├── browser/                   # Browser automation
│   └── tradingview.py         # Playwright TradingView controller
│
├── tools/                     # Specialized research tools
│   ├── market.py              # Market context generation
│   ├── vision.py              # Chart vision analysis (Qwen2.5-VL)
│   ├── search.py              # News retrieval
│   ├── sentiment.py           # Sentiment scoring
│   └── screenshot.py          # Screenshot file management
│
├── context/                   # Memory & context
│   ├── memory.py              # SQLite-backed execution store
│   └── context_manager.py     # Prompt enrichment from history
│
├── observability/             # Telemetry
│   └── langfuse.py            # Langfuse integration (optional)
│
├── api/                       # REST interface
│   └── fastapi.py             # FastAPI application
│
├── prompts/                   # Prompt documentation (informational)
│   ├── planner.md             #   Note: Runtime prompts are hardcoded in
│   ├── verifier.md            #   planner.py (PLANNER_PROMPT) and
│   └── chart_analysis.md      #   verifier.py (VERIFIER_PROMPT). The .md
│                               #   files serve as reference documentation.
│
├── docs/                      # Documentation
│   ├── prd.md                 # Product Requirements Document
│   └── systemdesign.md        # This file
│
├── main.py                    # CLI entry point (Click)
├── config.py                  # Pydantic Settings
├── models.py                  # Shared Pydantic models
├── pyproject.toml             # Project metadata
├── requirements.txt           # Dependencies
├── .env.example               # Environment template
└── README.md                  # Quick start guide
```

### Dependency Graph

```
main.py (CLI)
   │
   ├── config.py ─────────────► models.py
   │
   ├── agents/coordinator.py
   │     │
   │     ├── agents/base.py ──► config.py (Ollama URL)
   │     ├── agents/planner.py
   │     ├── agents/verifier.py
   │     ├── tools/market.py
   │     ├── tools/vision.py
   │     ├── tools/search.py
   │     ├── tools/sentiment.py
   │     ├── tools/screenshot.py
   │     ├── browser/tradingview.py
   │     ├── context/context_manager.py
   │     ├── context/memory.py
   │     └── observability/langfuse.py
   │
   ├── api/fastapi.py
   │     ├── agents/coordinator.py
   │     └── context/memory.py
   │
   └── context/memory.py ───► config.py (DB path)
```

---

## 4. Data Models

### Core Entity Relationship

```
Intent
  │
  ├── symbol: str
  ├── timeframe: enum (intraday | short_term | swing)
  ├── analysis_type: enum (technical | fundamental | sentiment | full)
  └── raw_query: str
       │
       ▼
MarketContext                   ChartAnalysis                  SentimentAnalysis
  ├── nifty_trend: str            ├── trend: str                  ├── overall: enum
  ├── banknifty_trend: str        ├── support_resistance          ├── score: float (-1..1)
  ├── sectors: list<SectorData>   │   ├── support: list[float]    ├── articles: list<NewsArticle>
  ├── market_breadth: str         │   └── resistance: list[float] └── summary: str
  ├── volatility_index: float     ├── rsi: float?
  └── summary: str                ├── breakout_probability: float
                                   ├── volume_confidence: float
                                   ├── pattern: str
                                   └── notes: str
                                        │
                                        ▼
                              VerificationResult
                                ├── confidence_score: float
                                ├── contradictions: list<Contradiction>
                                ├── missing_evidence: list<MissingEvidence>
                                ├── signal_agreement: str
                                ├── risk_reward_ratio: float?
                                └── passed: bool
                                        │
                                        ▼
                              FinalReport
                                ├── symbol: str
                                ├── bias: enum (bullish | bearish | neutral)
                                ├── confidence: float
                                ├── evidence: list[str]
                                ├── risks: list[str]
                                ├── suggested_trade: TradeSuggestion
                                │   ├── entry: str
                                │   ├── stop_loss: str
                                │   ├── target: str
                                │   └── rationale: str
                                ├── detailed_analysis: dict
                                └── generated_at: str
```

### Key Type Definitions

| Model | Purpose | Key Fields |
|---|---|---|
| `Intent` | Parsed user intent | symbol, timeframe, analysis_type |
| `MarketContext` | Macro backdrop | nifty_trend, sectors, volatility_index |
| `ChartAnalysis` | Technical analysis | trend, S/R levels, RSI, breakout_prob |
| `SupportResistance` | Price levels | support[], resistance[] |
| `NewsArticle` | Individual article | title, source, sentiment, relevance |
| `SentimentAnalysis` | Aggregate sentiment | overall (enum), score (-1..+1) |
| `Contradiction` | Signal conflict | aspect, detail |
| `MissingEvidence` | Data gap | aspect, detail |
| `VerificationResult` | Cross-check output | confidence_score, passed, contradictions |
| `TradeSuggestion` | Trade parameters | entry, stop_loss, target, rationale |
| `FinalReport` | Complete output | all the above in a single envelope |
| `ExecutionStep` | Trace step | step, agent, status, timestamps |
| `ExecutionTrace` | Full trace | query, steps[], final_report, duration |

---

## 5. Agent Design

### 5.1 BaseAgent (`agents/base.py`)

**Responsibility**: Abstract base class providing Ollama HTTP client infrastructure.

**Key Design Decisions**:
- Uses **lazy initialization** for `httpx.AsyncClient` (created on first use)
- Supports both `chat()` and `generate()` methods
- `chat()` accepts an optional `response_format` Pydantic model:
  - Enables `"format": "json"` in the Ollama payload
  - Auto-parses the response JSON into the specified model
- **API-level retry**: Up to `max_retries` (default 2) with exponential backoff
- All agents inherit connection management via `close()`

```
BaseAgent
  ├── model: str
  ├── temperature: float
  ├── max_retries: int
  ├── client: httpx.AsyncClient (lazy)
  │
  ├── chat(messages, response_format?) → dict
  ├── generate(prompt, response_format?) → dict
  └── close()
```

### 5.2 CoordinatorAgent (`agents/coordinator.py`)

**Responsibility**: Central orchestrator. Runs the full research pipeline.

**State**:
- References to all sub-agents and tools (lazy-initialized)
- `MemoryStore`, `ContextManager`, `LangfuseTracker`, `OutputValidator`

**Flow**:
```
run(query)
  ├── _ensure_tools() — lazy init all components
  │     (also initializes LangfuseTracker trace)
  ├── classify_intent(query) → Intent (FR1)                     ◄── span
  ├── _context_mgr.enrich(query, symbol) → context             ◄── span
  ├── _planner.run(intent, context) → Plan                      ◄── span
  ├── _run_with_retry(intent, plan) → collected evidence        ◄── span
  │     ├── _gather_market_context(symbol) (FR4)                ◄── span
  │     ├── _analyse_chart(symbol) (FR3)                        ◄── span
  │     ├── _gather_news_and_sentiment(symbol) (FR5)            ◄── 2 spans
  │     ├── _verifier.run(symbol, market, chart, sentiment,
  │     │                step_records, output_validation) (FR6)
  │     └── if not passed → collect feedback → retry (FR7)     ◄── retry spans
  ├── Build FinalReport                                          ◄── span
  ├── OutputValidator.validate_report(report)                    ◄── span (deterministic)
  ├── OutputValidator.validate_steps(steps)
  ├── Save to MemoryStore
  └── Return FinalReport (with step_checks + validation in risks)
```

**Key Interfaces**:
- `run(query)` — Main entry point, returns `FinalReport`
- `run(query, market_context_data, chart_analysis_data, sentiment_data)` — Overloaded for API/testing with pre-collected data
- `classify_intent(query)` — FR1, returns structured `Intent`
- Per-step observability: Every pipeline step is recorded as a `Span` (start/end) via `_start_step_span()` / `_end_step_span()`
- `OutputValidator` — Called after report generation for deterministic structural checks. Results are injected into the verifier's context for the verification layer and added to the `risks` list.

### 5.3 PlannerAgent (`agents/planner.py`)

**Responsibility**: Decomposes intent into an ordered execution plan.

**Models**:
- `PlanStep`: step_id, agent, description, depends_on[]
- `Plan`: intent string, steps[]

**Design**:
- Uses the reasoning model (`qwen3:14b`) to generate a plan
- Accepts optional `context` parameter with past analyses data
- Produces steps with explicit `depends_on` for parallel execution
- The plan is stored in the final report for observability

### 5.4 VerifierAgent (`agents/verifier.py`)

**Responsibility**: Cross-checks all evidence and produces a confidence score (FR6).

**Design**:
- Accepts `MarketContext`, `ChartAnalysis`, `SentimentAnalysis` as evidence
- Accepts `step_records` (observability span summary — FR8) injected into the prompt
- Accepts `output_validation_result` (OutputValidator results — deterministic step check) injected into the prompt
- Optional `retry_feedback` parameter for the retry engine (FR7)
- Returns `VerificationResult` with:
  - `confidence_score` (0.0–1.0)
  - `contradictions[]` (aspect, detail)
  - `missing_evidence[]` (aspect, detail)
  - `signal_agreement` (natural language description)
  - `risk_reward_ratio` (optional)
  - `passed` (boolean, confidence >= 0.6)
  - `step_checks[]` — step execution records (FR8)
  - `output_validation` — deterministic validation result string

**Prompt Philosophy**: "Be critical. It's better to flag uncertainty than to be overconfident."

### 5.5 ReflectorAgent (`agents/reflector.py`)

**Responsibility**: Post-execution quality review (extensibility point).

**Design**:
- Accepts the full execution trace
- Returns `Reflection` with weaknesses, improvements, missing data
- Currently defined but not wired into the coordinator pipeline
- Intended for Phase 5+ where post-execution refinement is needed

**Note on `ExecutionTrace` model**: The `ExecutionTrace` model (defined in `models.py`) and `ReflectorAgent` both exist for future use but are **not yet constructed or called** in the current pipeline. The coordinator tracks individual `ExecutionStep` objects internally. Full trace assembly and reflection will be wired in a future phase.

---

## 6. Tool Design

### 6.1 MarketContextTool (`tools/market.py`)

**Purpose**: Generate macro market context (FR4).

**Implementation**:
- Prompts the **fast model** (`qwen3:4b`) for structured market data
- Returns `MarketContext` with NIFTY/BankNifty trends, sector data, volatility
- **V1 uses LLM simulation** (no real market data API)
- Extensibility: Replace with Alpha Vantage, Yahoo Finance, or Twelve Data

**API**:
```python
async def get_context(symbol: str) -> MarketContext
```

### 6.2 ChartVisionAnalyzer (`tools/vision.py`)

**Purpose**: Analyze chart screenshots using vision model (FR3).

**Pipeline**: `TradingView Screenshot (bytes)` → `Base64 encode` → `Ollama vision API` → `Parsed ChartAnalysis`

**Implementation**:
- Base64-encodes the captured PNG screenshot
- Sends to `qwen2.5-vl:7b` via Ollama's chat API with `images` field
- Requests structured JSON: trend, S/R levels, RSI, breakout probability, volume confidence, pattern
- Uses temperature 0.1 for deterministic output
- Falls back gracefully on error

**API**:
```python
async def analyze(image_bytes: bytes, symbol: str) -> ChartAnalysis
```

### 6.3 NewsSearcher (`tools/search.py`)

**Purpose**: Retrieve company/macro news (FR5).

**Implementation**:
- Prompts the **fast model** (`qwen3:4b`) to generate plausible recent news
- Returns `list[NewsArticle]` with title, source, sentiment, relevance
- **V1 uses LLM simulation** — replace with NewsAPI, Google News, or RSS feeds
- Falls back to a single neutral article on error

**API**:
```python
async def search(symbol: str, max_articles: int = 5) -> list[NewsArticle]
```

### 6.4 SentimentAnalyzer (`tools/sentiment.py`)

**Purpose**: Aggregate article-level sentiment into a composite score.

**Implementation**:
- Maps sentiment labels to numeric values: positive=+1, neutral=0, negative=-1
- Computes arithmetic mean across all articles
- Classifies: >0.2 positive, <-0.2 negative, else neutral
- Generates a human-readable summary string

**API**:
```python
async def analyze(articles: list[NewsArticle]) -> SentimentAnalysis
```

### 6.6 OutputValidator (`tools/validator.py`)

**Purpose**: Perform **deterministic** structural validation of the `FinalReport` and execution steps.

**Design**:
- **Zero LLM calls** — pure logic checks only
- `validate_report(report)` — checks field presence, confidence range [0,1], bias validity, evidence presence, `detailed_analysis` key completeness
- `validate_steps(steps)` — checks `ExecutionStep` statuses, returns `list[StepCheck]`
- `format_validation_report()` — human-readable summary of all checks
- Results are injected into the verifier's context (so the LLM can factor structural issues into its confidence assessment)
- Results are appended to `FinalReport.risks` (e.g., "Step failed — chart_analysis: browser timeout")

**API**:
```python
@staticmethod
def validate_report(report: FinalReport) -> list[str]
@staticmethod
def validate_steps(steps: list[ExecutionStep]) -> list[StepCheck]
@staticmethod
def all_steps_passed(steps: list[ExecutionStep]) -> bool
@staticmethod
def format_validation_report(report_issues, step_checks) -> str
```

### 6.5 ScreenshotCapture (`tools/screenshot.py`)

**Purpose**: Persist chart screenshots to disk.

**Implementation**:
- Saves PNG bytes to `~/.trademind/screenshots/` (configurable)
- Filename format: `{SYMBOL}_{label}_{YYYYMMDD_HHMMSS}.png`
- Provides `get_latest()` for retrieving most recent screenshot

**API**:
```python
async def save(image_data: bytes, symbol: str, label: str = "") -> Path
def get_latest(symbol: str) -> Path | None
```

---

## 7. Execution Flow

### Detailed Sequence

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  User    │    │Coordinator│    │ Context  │    │ Planner  │    │  Tools   │    │ Verifier │
│  / CLI   │    │  Agent   │    │ Manager  │    │  Agent   │    │          │    │  Agent   │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │               │               │               │
     │  analyse()    │               │               │               │               │
     │──────────────►│               │               │               │               │
     │               │               │               │               │               │
     │               │classifyIntent │               │               │               │
     │               │────(self)────►│               │               │               │
     │               │◄────Intent────│               │               │               │
     │               │               │               │               │               │
     │               │ enrich()      │               │               │               │
     │               │──────────────►│               │               │               │
     │               │◄───context────│               │               │               │
     │               │               │               │               │               │
     │               │ run(intent,   │               │               │               │
     │               │     context)  │               │               │               │
     │               │──────────────────────────────►│               │               │
     │               │◄────────────Plan──────────────│               │               │
     │               │               │               │               │               │
     │               │──────────────────────────┬─────────────────────────────────────│
     │               │           ┌───────────────┼───────────────┐                    │
     │               │           ▼               ▼               ▼                    │
     │               │    get_context()   analyze_chart()   search + sentiment        │
     │               │    (Market-Tool)   (Browser+Vision)  (News+Sentiment Tools)    │
     │               │           │               │               │                    │
     │               │           └───────────────┼───────────────┘                    │
     │               │                           │                                    │
     │               │        verify(symbol,     │                                    │
     │               │           market, chart,  │                                    │
     │               │           sentiment)      │                                    │
     │               │───────────────────────────────────────────────────────────────►│
     │               │◄──────────────────────VerificationResult───────────────────────│
     │               │                           │                                    │
     │               │  if not passed: collect   │                                    │
     │               │  missing_evidence, retry  │                                    │
     │               │                           │                                    │
     │               │  build FinalReport         │                                    │
     │               │  save to MemoryStore       │                                    │
     │               │                           │                                    │
     │◄───Report─────│                           │                                    │
```

### Concurrency Model

```
Timeline:           T0          T1          T2          T3          T4
                    │           │           │           │           │
Intent Classify     ████████░░░│           │           │           │
                    │           │           │           │           │
Context Enrich      ░░░░░░░░░░░████████░░░│           │           │
                    │           │           │           │           │
Plan Generation     ░░░░░░░░░░░░░░░░███████│           │           │
                    │           │           │           │           │
Market Context      ░░░░░░░░░░░░░░░░░░░░░░░████████░░░│           │
Chart Vision       ░░░░░░░░░░░░░░░░░░░░░░░│████████░░░│           │ (parallel)
News + Sentiment   ░░░░░░░░░░░░░░░░░░░░░░░│████████░░░│           │ (parallel)
                    │           │           │           │           │
Verification        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░████████░░░│
                    │           │           │           │           │
Report Build        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██████
```

**Key**: `█` = active, `░` = idle/waiting

---

## 8. Retry Engine (FR7)

### Design

The retry engine implements the **`verify → detect gaps → improve → re-verify`** loop:

```
_run_with_retry(intent, plan)
    │
    ├── missing_evidence_feedback = []
    │
    ├── for attempt in range(max_retries + 1):
    │     │
    │     ├── gather_market_context(symbol)
    │     ├── analyse_chart(symbol)          ── parallel ──┐
    │     ├── gather_news_and_sentiment(symbol)           ──┘
    │     │
    │     ├── verifier.run(
    │     │     symbol,
    │     │     market, chart, sentiment,
    │     │     retry_feedback=missing_evidence_feedback  ← injected
    │     │   )
    │     │
    │     ├── if verification.passed → break (success)
    │     │
    │     └── collect missing_evidence:
    │           for m in verification.missing_evidence:
    │             msg = f"{m.aspect}: {m.detail}"
    │             if msg not in missing_evidence_feedback:
    │                 missing_evidence_feedback.append(msg)
    │
    └── return collected evidence
```

### Retry Parameters (configurable)

| Parameter | Default | Description |
|---|---|---|
| `min_confidence_threshold` | 0.6 | Minimum confidence to pass verification |
| `max_retries` | 2 | Maximum retry attempts |

### Feedback Mechanism

On each retry, the `VerifierAgent` receives a `retry_feedback` list containing descriptions of previously missing evidence. This is injected into the verifier's prompt:

```
[Retry Feedback — Previous attempt flagged missing evidence:
  - Volume divergence: No trend confirmation
  - News recency: No data from last 24 hours
Please check if these gaps have been addressed.]
```

This causes the verifier to re-evaluate with awareness of what was previously missing, enabling a more nuanced confidence assessment on subsequent attempts.

---

## 9. Browser Automation

### TradingViewBrowser (`browser/tradingview.py`)

**Technology**: Playwright (Chromium)

**Lifecycle**:
```python
async with TradingViewBrowser() as tv:
    await tv.search_symbol("AAPL")
    await tv.set_timeframe("1D")
    screenshot = await tv.capture_screenshot()
```

**Methods**:

| Method | Description | Key Selectors |
|---|---|---|
| `start()` | Launch Chromium with anti-detection args | `--disable-blink-features=AutomationControlled` |
| `search_symbol(symbol)` | Navigate to TradingView, search symbol | `[data-name=symbol-search]` |
| `set_timeframe(timeframe)` | Switch chart timeframe | `[data-name=timeframe-toolbar] button` |
| `capture_screenshot(path?)` | Capture chart container screenshot | `[class*=chart-container]` canvas |
| `stop()` | Close browser and Playwright | — |

**Anti-Detection**:
- Custom user-agent (Chrome 120 on macOS)
- 1920x1080 viewport
- `--disable-blink-features=AutomationControlled` flag
- Realistic typing delays (50ms per character)

**Graceful Degradation**:
- Timeframe switching is best-effort (silent failure)
- Screenshot falls back to full-page if chart container not found
- Browser failures are caught and return fallback analysis

---

## 10. API Layer

### FastAPI Application (`api/fastapi.py`)

**Endpoints**:

| Method | Path | Description | Request | Response |
|---|---|---|---|---|
| `GET` | `/health` | Health check | — | `{"status": "ok"}` |
| `POST` | `/analyse` | Run research pipeline | `AnalyseRequest` | `AnalyseResponse` |
| `GET` | `/history` | Past executions | `symbol?`, `limit?` | `list[dict]` |

**AnalyseRequest Schema**:
```json
{
  "query": "Analyze RELIANCE for intraday",
  "symbol": null,
  "timeframe": null
}
```

**AnalyseResponse Schema**:
```json
{
  "query": "Analyze RELIANCE for intraday",
  "report": { ... FinalReport ... },
  "execution_id": 42,
  "error": null
}
```

**Server**:
```bash
PYTHONPATH=. uvicorn api.fastapi:app --reload --port 8000
```

### CLI (`main.py`)

**Commands**:

| Command | Description |
|---|---|
| `analyse <query>` | Run research pipeline |
| `history [--symbol] [--limit]` | View past analyses |
| `setup` | Verify environment readiness |
| `show-config [--output]` | Display/save configuration |

**CLI Output (Rich formatting)**:
```
┌─────────────────────────────────────┐
│         TradeMind Analysis          │
│                                     │
│                AAPL                 │
│                                     │
│     Bias: Bullish (73% confidence)  │
│                                     │
│             Evidence:               │
└─────────────────────────────────────┘
  ✔ Market context: NIFTY trending up
  ✔ Chart trend: Bullish with resistance
  ✔ Sentiment: positive (+0.45)

Risks:
  ✖ Contradiction — Volume vs Price

Suggested Trade
  Field      Value
  Entry      185 breakout
  Stop Loss  182
  Target     192
  Rationale  confluence of signals
```

---

## 11. Observability

### LangfuseTracker (`observability/langfuse.py`)

**Design**: Strategy pattern with no-op fallback

**States**:
1. **Disabled** (default): All trace calls `print()` to console
2. **Enabled + No SDK**: Prints warning, falls back to no-op
3. **Enabled + SDK installed**: Sends real traces to Langfuse

**Configuration**:
```env
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

**Span Lifecycle**:

```python
span = self._observability.start_span("classify_intent")
# ... step runs ...
self._observability.end_span(span, status="success", output=result)
```

Each span captures:
- `name` — step identifier
- `status` — `"running"` | `"success"` | `"failed"`
- `started_at` / `completed_at` — monotonic timers
- `duration_ms` — computed from start/end
- `error` — exception string if failed
- `output` — structured result data

**Actual Trace Structure** (live):

```
trademind_research [trace]
  ├── classify_intent [span]
  ├── gather_context [span]
  ├── create_plan [span]
  ├── execute_plan [span]
  │   ├── market_context [span]
  │   ├── chart_analysis [span]
  │   ├── news_search [span]
  │   ├── sentiment_analysis [span]
  │   └── retry_attempt_N [span]  (only if FR7 triggers)
  ├── build_report [span]
  └── output_validation [span]   ← deterministic checks
```

**Span → Verification pipeline (FR8)**:

After execution, `get_span_summary()` returns all completed spans as a `list[dict]`. This is passed to the `VerifierAgent` as `step_records`:

```python
span_summary = self._observability.get_span_summary()
verification = await self._verifier.run(
    ...,
    step_records=span_summary,     # ← FR8: spans feed verification
    output_validation=validation_text,  # ← deterministic checks
)
```

The verifier evaluates:
- Did all expected steps complete?
- Did any step fail, take too long, or produce errors?
- Does output validation reveal structural issues?

**Retry boundary isolation**:

On retry, spans are scoped to the current attempt via a `span_boundary` index. The verifier only sees spans from the *current* attempt, not stale data from previous failed runs.

---

## 12. Configuration & Environment

### Settings Hierarchy

```
1. Default values (in config.py)
       │
       ▼
2. .env file (in project root)
       │
       ▼
3. Environment variables (no prefix)
```

### Config Schema (`config.py`)

| Category | Key | Type | Default |
|---|---|---|---|
| **Ollama** | `ollama_base_url` | str | `http://localhost:11434` |
| | `reasoning_model` | str | `qwen3:14b` |
| | `vision_model` | str | `qwen2.5-vl:7b` |
| | `fast_model` | str | `qwen3:4b` |
| **Storage** | `data_dir` | Path | `~/.trademind` |
| | `db_path` | Path | `{data_dir}/trademind.db` |
| **Browser** | `tradingview_url` | str | `https://www.tradingview.com` |
| | `browser_headless` | bool | `true` |
| | `browser_screenshot_dir` | Path | `{data_dir}/screenshots` |
| **Langfuse** | `langfuse_enabled` | bool | `false` |
| | `langfuse_public_key` | str | `""` |
| | `langfuse_secret_key` | str | `""` |
| | `langfuse_host` | str | `https://cloud.langfuse.com` |
| **Retry** | `min_confidence_threshold` | float | `0.6` |
| | `max_retries` | int | `2` |
| **API** | `api_host` | str | `0.0.0.0` |
| | `api_port` | int | `8000` |

### Computed Properties

```python
@property
def ollama_chat_url(self) -> str:
    return f"{self.ollama_base_url}/api/chat"

@property
def ollama_generate_url(self) -> str:
    return f"{self.ollama_base_url}/api/generate"
```

---

## 13. Storage Schema

### SQLite Schema (`context/memory.py`)

**Table: `executions`**

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment ID |
| `query` | TEXT NOT NULL | Raw user query |
| `symbol` | TEXT | Extracted stock symbol |
| `intent` | TEXT | JSON: Intent model |
| `report` | TEXT | JSON: FinalReport model |
| `confidence` | REAL | Confidence score (0–1) |
| `bias` | TEXT | bullish/bearish/neutral |
| `duration_ms` | REAL | Execution duration |
| `created_at` | TEXT | ISO 8601 timestamp |

**Table: `screenshots`**

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment ID |
| `execution_id` | INTEGER FK | References executions(id) |
| `symbol` | TEXT NOT NULL | Stock symbol |
| `file_path` | TEXT NOT NULL | Path to PNG file |
| `created_at` | TEXT | ISO 8601 timestamp |

**Indices**:
- `idx_exec_symbol` on `executions(symbol)` for symbol lookups
- `idx_exec_created` on `executions(created_at DESC)` for recent-first queries

### Data Directory Layout

```
~/.trademind/
├── trademind.db           # SQLite database
└── screenshots/
    ├── AAPL_chart_20250101_120000.png
    ├── RELIANCE_chart_20250101_120500.png
    └── ...
```

---

## 14. Error Handling Strategy

### Layer 1: Tool-Level Resilience

Each tool wraps its operations in try/except and returns **fallback defaults** rather than raising:

| Tool | Fallback on Error |
|---|---|
| `MarketContextTool` | `MarketContext(summary="unavailable")` |
| `ChartVisionAnalyzer` | `ChartAnalysis(trend="Unknown")` with error in notes |
| `NewsSearcher` | Single neutral `NewsArticle` |
| `SentimentAnalyzer` | Neutral with 0.0 score |
| `TradingViewBrowser` | Returns fallback analysis, pipeline continues |

### Layer 2: Agent-Level Retry

`BaseAgent.chat()` has API-level retry:
- Up to `max_retries` attempts (default 2)
- Exponential backoff: `1.0s`, `2.0s`
- Raises `RuntimeError` only after all attempts fail

### Layer 3: Pipeline-Level Retry (FR7)

`CoordinatorAgent._run_with_retry()` has business-level retry:
- Triggers when `verification.passed == False`
- Collects missing evidence and feeds it back
- Only re-runs verification (not full tool execution in V1)

### Layer 4: CLI/API Entry Points

- CLI: Prints error message to console, exits with code 1
- API: Returns HTTP 500 with error detail

### Error Propagation Decision Tree

```
Error occurs
    │
    ├── Is it a tool error? → Return fallback, log, continue
    │
    ├── Is it an LLM API error? → Retry (up to 2x), then raise
    │
    ├── Is it low confidence? → Retry with feedback (up to 2x), then continue
    │
    └── Is it a framework error? → Propagate to caller (CLI/API)
```

---

## 15. Extensibility Points

### 1. Real Market Data API

Replace `MarketContextTool` → Use Alpha Vantage / Yahoo Finance / Twelve Data:
```python
class RealMarketDataTool(MarketContextTool):
    async def get_context(self, symbol: str) -> MarketContext:
        # Implementation with REST API calls
```

### 2. Real News API

Replace `NewsSearcher` → Use NewsAPI / Google News RSS:
```python
class RealNewsSearcher(NewsSearcher):
    async def search(self, symbol: str, max_articles: int = 5) -> list[NewsArticle]:
        # Implementation with NewsAPI
```

### 3. Trading Strategy Engine

Add a strategy module in `agents/strategy.py`:
- Entry/exit rule generation
- Position sizing
- Risk management rules

### 4. Multi-Timeframe Analysis

Extend `ChartVisionAnalyzer` to capture multiple timeframes:
```python
async def analyse_multi_timeframe(self, symbol: str, timeframes: list[str]) -> dict[str, ChartAnalysis]:
    async with TradingViewBrowser() as tv:
        await tv.search_symbol(symbol)
        results = {}
        for tf in timeframes:
            await tv.set_timeframe(tf)
            image = await tv.capture_screenshot()
            results[tf] = await self.analyze(image, symbol)
        return results
```

### 5. Langfuse Full Integration

Uncomment Langfuse configuration and implement spans:
```python
trace = await self._observability.trace("agentic_harness_research")
with trace.span("classify_intent") as span:
    intent = await self.classify_intent(query)
    span.set_output(intent)
```

### 6. WebSocket / Real-Time

Add WebSocket endpoint to `api/fastapi.py`:
```python
@app.websocket("/ws/analyse")
async def websocket_analyse(websocket: WebSocket):
    query = await websocket.receive_text()
    async for partial in coordinator.run_streaming(query):
        await websocket.send_json(partial)
```

### 7. Additional Models

Replace the LLM providers by changing `config.py`:
```python
# Example: Switch to GPT-4
REASONING_MODEL=gpt-4
OLLAMA_BASE_URL=https://api.openai.com/v1
```

---

## Appendix A: Functional Requirements Mapping

| FR# | Description | Implementation | Status |
|---|---|---|---|
| FR1 | Intent Classifier | `CoordinatorAgent.classify_intent()` | ✅ |
| FR2 | Browser Automation | `TradingViewBrowser` | ✅ |
| FR3 | Chart Vision Analysis | `ChartVisionAnalyzer` + `tradingview.py` | ✅ |
| FR4 | Market Context | `MarketContextTool` | ✅ |
| FR5 | News Agent | `NewsSearcher` + `SentimentAnalyzer` | ✅ |
| FR6 | Verification Layer | `VerifierAgent` | ✅ |
| FR7 | Retry Engine | `CoordinatorAgent._run_with_retry()` | ✅ |
| FR8 | Observability | `LangfuseTracker` (`start_span`/`end_span` per step, spans → verifier) | ✅ |
| — | Deterministic validation | `OutputValidator` (structural checks, no LLM) | ✅ |
| — | Step checks | `VerificationResult.step_checks` (observability + validation combined) | ✅ |

## Appendix B: Technology Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent framework | Plain Python classes | No framework lock-in, easy to test |
| LLM protocol | Ollama REST API | Local-first, no API keys needed |
| Data models | Pydantic v2 | Type safety + JSON Schema generation |
| Browser automation | Playwright | Industry standard, Python-native async |
| CLI framework | Click + Rich | Simple, beautiful terminal output |
| API framework | FastAPI | Async-native, auto-docs |
| Storage | SQLite | Zero-config, sufficient for single-user |
| Configuration | pydantic-settings | Type-safe env vars + .env support |
