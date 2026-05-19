# Agentic Harness Demo

**AI-powered Intraday Trading Research Harness**

A local-first agent system that researches intraday trading opportunities like an analyst — gathering evidence, analyzing charts, inspecting sentiment, verifying confidence, and explaining trade setups.

## Quick Start

```bash
# 1. Clone and enter the project
cd agentic-harness-demo

# 2. Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Install Playwright browser
playwright install chromium

# 4. Make sure your local model server (Ollama or oMLX) is running
# If using Ollama:
#   ollama serve
#   ollama pull qwen3:14b
#   ollama pull qwen2.5-vl:7b
#   ollama pull qwen3:4b
# If using oMLX:
#   Make sure your oMLX server is running on the configured port (default 8000)
#   and configure OMLX_ENABLED=True, OMLX_API_KEY, and OMLX_BASE_URL in your .env file.

# 6. Run a setup check
python main.py setup

# 7. Analyse a stock
python main.py analyse "Analyze AAPL for intraday"
```

## CLI Usage

```bash
# Analyse a stock
python main.py analyse "Analyze RELIANCE for intraday"
python main.py analyse -s AAPL "What's the outlook today?"

# Show past analyses
python main.py history
python main.py history --symbol RELIANCE

# Run setup checks
python main.py setup

# View configuration
python main.py show-config
```

## API

Start the FastAPI server:

```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn api.fastapi:app --reload --port 8000
```

```bash
curl -X POST http://localhost:8000/analyse \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze RELIANCE for intraday"}'

curl http://localhost:8000/history?symbol=RELIANCE
```

## Architecture

```
User Query
     ↓
Coordinator Agent  ── Intent classifier → Market context → Chart vision → News → Sentiment
     ↓
Planner Agent  ── Decomposes intent into an execution plan
     ↓
Verification Layer  ── Cross-checks signals, confidence score, retry if needed
     ↓
Retry Engine  ── Improve prompts with missing evidence, re-run (FR7)
     ↓
Final Report  ── Structured output with bias, confidence, evidence, risks
```

### Agents

| Agent | Responsibility |
|---|---|
| **Coordinator** | Orchestrates the full pipeline, retry engine |
| **Planner** | Decomposes intent into ordered execution steps |
| **Verifier** | Cross-checks all signals, computes confidence score |
| **Reflector** | Reviews execution quality and suggests improvements |

### Tools

| Tool | Responsibility |
|---|---|
| **Market Context** | NIFTY/BankNifty trend, sector movement, volatility |
| **Chart Vision** | TradingView screenshot → Qwen2.5-VL → trend, S/R, RSI |
| **News Search** | Retrieves company & macro news via LLM |
| **Sentiment** | Scores news articles positive/neutral/negative |
| **Screenshot** | Saves chart screenshots to disk |

## Tech Stack

- **Backend:** FastAPI + Pydantic + httpx
- **Models:** Qwen3 14B (reasoning), Qwen2.5-VL 7B (vision), Qwen3 4B (utility) via Ollama or oMLX (OpenAI-compatible inference server)
- **Browser:** Playwright + Chromium for TradingView automation
- **Storage:** SQLite for execution history
- **Observability:** Langfuse (optional, with no-op stub)

## Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `REASONING_MODEL` | `qwen3:14b` | Main reasoning model |
| `VISION_MODEL` | `qwen2.5-vl:7b` | Chart vision model |
| `MIN_CONFIDENCE_THRESHOLD` | `0.6` | Minimum confidence to pass verification |
| `MAX_RETRIES` | `2` | Max retry attempts for low confidence |

## Project Structure

```
agentic-harness-demo/
├── agents/
│   ├── coordinator.py     # Main orchestrator + retry engine
│   ├── planner.py         # Intent → execution plan
│   ├── verifier.py        # Signal cross-check + confidence
│   └── reflector.py       # Post-execution quality review
├── browser/
│   └── tradingview.py     # Playwright TradingView automation
├── tools/
│   ├── search.py          # News retrieval
│   ├── sentiment.py       # Sentiment scoring
│   ├── vision.py          # Chart vision analysis (Qwen2.5-VL)
│   ├── market.py          # Market context generation
│   └── screenshot.py      # Screenshot file management
├── context/
│   ├── memory.py          # SQLite execution history
│   └── context_manager.py # Context enrichment for prompts
├── observability/
│   └── langfuse.py        # Langfuse integration (optional)
├── prompts/
│   ├── planner.md
│   ├── verifier.md
│   └── chart_analysis.md
├── api/
│   └── fastapi.py         # REST API
├── docs/
│   └── prd.md             # Product Requirements Document
├── main.py                # CLI entry point
├── config.py              # Settings management
├── models.py              # Shared Pydantic models
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

## License

MIT
