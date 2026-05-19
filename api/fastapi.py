"""FastAPI application exposing the research pipeline via REST."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agents.coordinator import CoordinatorAgent
from context.memory import MemoryStore
from models import FinalReport

app = FastAPI(
    title="TradeMind Harness",
    description="AI-powered Intraday Trading Research API",
    version="0.1.0",
)

store = MemoryStore()


class AnalyseRequest(BaseModel):
    query: str = Field(description="Natural language query, e.g. 'Analyze RELIANCE for intraday'")
    symbol: str | None = Field(None, description="Optional override for stock symbol")
    timeframe: str | None = Field(None, description="Optional override: intraday, short_term, swing")


class AnalyseResponse(BaseModel):
    query: str
    report: FinalReport
    execution_id: int | None = None
    error: str | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.post("/analyse", response_model=AnalyseResponse)
async def analyse(req: AnalyseRequest) -> dict[str, Any]:
    """Run the full research pipeline for a given query."""
    coordinator = CoordinatorAgent()
    try:
        report = await coordinator.run(query=req.query)
        execution_id = store.save_execution(
            query=req.query,
            symbol=report.symbol,
            intent=report.detailed_analysis.get("intent"),
            report=report.model_dump(),
            confidence=report.confidence,
            bias=report.bias.value if hasattr(report.bias, "value") else str(report.bias),
        )
        return {"query": req.query, "report": report, "execution_id": execution_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await coordinator.close()


@app.get("/history")
async def history(symbol: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Retrieve past execution records."""
    if symbol:
        return store.get_by_symbol(symbol.upper(), limit=limit)
    return store.get_recent(limit=limit)
