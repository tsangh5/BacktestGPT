from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.backtest_loop import run_backtest, run_backtest_spec
from backend.llm_decode import decode_natural_language
from backend.schema import StrategySpec

app = FastAPI(
    title="BacktestGPT API",
    description="Conversational AI-powered trading strategy backtesting",
    version="2.0.0",
)
# Wildcard origins require credentials to be disabled per the CORS spec;
# the API is token-free so no credentials are needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "BacktestGPT API is running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


class BacktestRequest(BaseModel):
    """Legacy named-strategy request (SMA crossover or RSI mean-reversion)."""

    ticker: str = "SPY"
    strategy: str = "SMA"
    start_date: Optional[str] = "2015-01-01"
    end_date: Optional[str] = None
    initial_cash: Optional[float] = 100_000
    fees: Optional[float] = 0.001
    sma_fast: Optional[int] = 5
    sma_slow: Optional[int] = 20
    rsi_period: Optional[int] = 14
    rsi_oversold: Optional[int] = 30
    rsi_overbought: Optional[int] = 70


class NaturalBacktestRequest(BaseModel):
    input: str
    conversation_history: Optional[list] = []


@app.post("/backtest")
async def backtest_endpoint(request: BacktestRequest):
    """Run a named preset strategy (SMA crossover or RSI)."""
    try:
        result = run_backtest(
            ticker=request.ticker,
            strategy=request.strategy,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_cash=request.initial_cash,
            fees=request.fees,
            sma_fast=request.sma_fast,
            sma_slow=request.sma_slow,
            rsi_period=request.rsi_period,
            rsi_oversold=request.rsi_oversold,
            rsi_overbought=request.rsi_overbought,
        )
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@app.post("/backtest_spec")
async def backtest_spec_endpoint(spec: StrategySpec):
    """Run a fully-specified strategy AST directly (no LLM involved)."""
    result = run_backtest_spec(spec)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/natural_backtest")
async def natural_backtest_endpoint(request: NaturalBacktestRequest):
    """Conversational natural-language backtesting."""
    try:
        result = decode_natural_language(request.input, request.conversation_history)
        if result is None:
            raise HTTPException(status_code=500, detail="Internal error: no result returned.")
        return result
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
