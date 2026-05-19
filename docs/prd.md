# Product Requirements Document (PRD)

# Product Name
**Agentic Harness Demo**  
**Subtitle:** AI-powered Intraday Trading Research Harness

---

## 1. Problem Statement

Retail traders struggle to combine:
- technical analysis
- market context
- sentiment
- news
- structured decision making

Most tools are fragmented and require manual interpretation.

Existing AI tools:
- hallucinate
- provide generic buy/sell suggestions
- lack observability
- do not verify evidence
- fail to explain reasoning

We need a system that:
> Researches an intraday opportunity like an analyst.

Instead of blindly predicting, the system should:
- gather evidence
- analyze charts
- inspect sentiment
- verify confidence
- explain trade setup

---

## 2. Vision

Build a **local-first agent harness** capable of:

`observe → reason → execute → verify → retry`

to generate **research-backed intraday trade opportunities**.

The product should teach:
- agent harness design
- observability
- browser automation
- model orchestration
- guardrails
- verification loops

while remaining practical and extensible.

---

## 3. Goals

### Primary Goals
Learn:
- agent harness architecture
- multi-agent orchestration
- verification loops
- observability
- local AI systems

Deliver:
- reusable framework
- Medium blog content
- foundation for a trading dashboard

### Business Goal
Create an extensible AI research engine that later evolves into:
- quant trading assistant
- swing research system
- portfolio analyzer

---

## 4. Non-Goals (V1)

V1 will NOT include:
- autonomous trading
- brokerage integration
- placing real orders
- financial guarantees
- stock prediction claims

Focus:
> Decision support system

---

## 5. User Persona

### Primary User
Independent trader / developer.

Pain points:
- Too much information
- No structured analysis
- Hard to combine signals
- Emotional decisions

---

## 6. Recommended Model Strategy

### Primary Reasoning Model
**Qwen3 14B**

Purpose:
- coordinator agent
- planner
- verifier
- reflection agent
- trade reasoning

Why:
- strong reasoning
- structured JSON output
- fast enough for Mac Mini 24GB
- good local inference performance

---

### Vision Model
**Qwen2.5-VL 7B**

Purpose:
- TradingView screenshot understanding
- chart interpretation
- support/resistance
- trend analysis

Pipeline:
`Playwright → Screenshot → Vision Model → Structured Signals`

---

### Fast Utility Model (Optional)
**Qwen3 4B**

Purpose:
- classification
- guardrails
- summarization
- quick routing

---

## 7. System Architecture

```text
User Query
      ↓
Coordinator Agent
      ↓
Planner Agent
      ↓
Tool Router
      ↓
Specialized Agents
      ↓
Verification Layer
      ↓
Retry Engine
      ↓
Final Report
```

### Specialized Agents
- Market Context Agent
- Chart Analysis Agent
- News Agent
- Sentiment Agent
- Verification Agent

---

## 8. Core User Flow

Example Input:

> Analyze Reliance for intraday

Execution Flow:

```text
Intent Detection
      ↓
Market Context
      ↓
TradingView Browser Agent
      ↓
Chart Screenshot
      ↓
Vision Analysis
      ↓
News Analysis
      ↓
Sentiment Analysis
      ↓
Verification Layer
      ↓
Confidence Score
      ↓
Final Trade Research
```

---

## 9. Functional Requirements

### FR1 — Intent Classifier
Determine:
- stock symbol
- timeframe
- analysis type

Output:

```json
{
  "symbol": "RELIANCE",
  "timeframe": "intraday"
}
```

### FR2 — Browser Automation
Open TradingView and:
- search stock
- switch timeframe
- capture screenshot

Technology:
- Playwright

### FR3 — Chart Vision Analysis
Analyze:
- trend
- support
- resistance
- RSI
- breakout probability
- volume confidence

Return JSON schema.

### FR4 — Market Context
Analyze:
- NIFTY trend
- sector movement
- market breadth
- volatility

### FR5 — News Agent
Retrieve:
- company news
- macro news
- sector developments

Classify:
- positive
- neutral
- negative

### FR6 — Verification Layer
Validate:
- signal agreement
- news consistency
- trend alignment
- risk reward

Return:
- confidence score
- contradictions
- missing evidence

### FR7 — Retry Engine
If confidence < threshold:
- retry retrieval
- improve prompt
- gather missing evidence

### FR8 — Observability
Track execution in Langfuse:
- prompts
- traces
- retries
- latency
- token usage
- failure reasons

---

## 10. Tech Stack

### Backend
- FastAPI
- PydanticAI
- Ollama
- SQLite

### Models
- Qwen3 14B
- Qwen2.5-VL 7B
- Qwen3 4B (optional)

### Browser
- Playwright

### Observability
- Langfuse

### Storage
- SQLite
- Local JSON cache

---

## 11. Folder Structure

```text
agentic-harness-demo/

├── agents/
│   ├── coordinator.py
│   ├── planner.py
│   ├── verifier.py
│   ├── reflector.py
│
├── browser/
│   └── tradingview.py
│
├── tools/
│   ├── search.py
│   ├── sentiment.py
│   ├── screenshot.py
│
├── context/
│   ├── memory.py
│   └── context_manager.py
│
├── observability/
│   └── langfuse.py
│
├── prompts/
│   ├── planner.md
│   ├── verifier.md
│   └── chart_analysis.md
│
├── api/
│   └── fastapi.py
│
└── docs/
    └── prd.md
```

---

## 12. Success Metrics

### Technical
- Langfuse traces visible
- Browser automation stable
- JSON outputs structured
- Verification loop working

### Product
Output should feel:
> Useful for a trader, not generic AI advice.

---

## 13. MVP Milestones

### Phase 1
Core harness:
- coordinator
- planner
- tools

### Phase 2
Playwright integration.

### Phase 3
TradingView screenshots + vision model.

### Phase 4
Verification loop.

### Phase 5
Langfuse observability.

### Phase 6
Blog + documentation.

---

## 14. Example Output

```text
Symbol: RELIANCE

Bias:
Bullish (Moderate Confidence)

Evidence:
✔ Opening strength above VWAP
✔ Positive sentiment
✔ Sector momentum

Risks:
✖ Resistance nearby

Suggested Trade:
Entry: 1448 breakout
SL: 1441
Target: 1460

Confidence:
73%
```

---

## 15. Blog Positioning

Recommended title:

**Building a Production-Style Trading Research Agent with PydanticAI, Playwright, Ollama & Langfuse**
