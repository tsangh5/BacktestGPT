from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, HTTPException
from typing import Union, Optional
from pydantic import BaseModel
from backend.backtest_loop import run_backtest
from backend.llm_decode import decode_natural_language

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BacktestRequest(BaseModel):
    ticker: str = "SPY"
    strategy: str = "SMA"
    start_date: Optional[str] = "2010-01-01"
    end_date: Optional[str] = "2025-01-01"
    initial_cash: Optional[float] = 100000
    fees: Optional[float] = 0.001
    # Strategy-specific parameters
    sma_fast: Optional[int] = 5
    sma_slow: Optional[int] = 20
    rsi_period: Optional[int] = 14
    rsi_oversold: Optional[int] = 30
    rsi_overbought: Optional[int] = 70
    momentum_threshold: Optional[float] = 0.02
    stop_loss: Optional[float] = -0.01

# New model for natural language input
class NaturalBacktestRequest(BaseModel):
    input: str
    conversation_history: Optional[list] = []

@app.post("/backtest")
async def backtest_endpoint(request: BacktestRequest):
    """Main backtest endpoint"""
    try:
        # Extract strategy parameters
        strategy_params = {}
        
        if request.strategy == "SMA":
            strategy_params = {
                'sma_fast': request.sma_fast,
                'sma_slow': request.sma_slow
            }
        elif request.strategy == "RSI":
            strategy_params = {
                'rsi_period': request.rsi_period,
                'rsi_oversold': request.rsi_oversold,
                'rsi_overbought': request.rsi_overbought
            }
        elif request.strategy == "MOMENTUM":
            strategy_params = {
                'momentum_threshold': request.momentum_threshold,
                'stop_loss': request.stop_loss
            }
        
        # Run backtest
        result = run_backtest(
            ticker=request.ticker,
            strategy=request.strategy,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_cash=request.initial_cash,
            fees=request.fees,
            **strategy_params
        )
        
        # Handle errors
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# New endpoint for natural language backtest
@app.post("/natural_backtest")
async def natural_backtest_endpoint(request: NaturalBacktestRequest):
    """Backtest endpoint for natural language input"""
    import traceback
    print(f"[natural_backtest] Received text input: {request.input}")
    try:
        result = decode_natural_language(request.input, request.conversation_history)
        if result is None:
            print("[natural_backtest] Error: decode_natural_language returned None")
            raise HTTPException(status_code=500, detail="Internal error: No result returned.")
        
        # If there's an error in the result, return it as part of the response (not as HTTP error)
        # This allows the frontend to display the helpful error message
        if result.get("error"):
            print(f"[natural_backtest] Parsing error: {result['error']}")
            return result  # Return the error as part of the JSON response
        
        print(f"[natural_backtest] Success. Returning result.")
        return result
    except Exception as e:
        print(f"[natural_backtest] Unexpected error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")