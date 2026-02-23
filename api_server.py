#!/usr/bin/env python3
"""
API Server for Stat Arb Platform
=================================

FastAPI server to provide REST endpoints for the dashboard.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import pickle
import pandas as pd
import asyncio
from pathlib import Path

# Import strategy engine
from core.strategy_engine import StatArbStrategyEngine

app = FastAPI(title="Stat Arb Platform API")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global strategy instance
strategy_engine = None

class BacktestRequest(BaseModel):
    start_date: str
    end_date: Optional[str] = None

class BacktestResult(BaseModel):
    id: str
    date: datetime
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    viable_pairs: int
    validation: str

class TradingAction(BaseModel):
    action: str  # start, stop, pause

@app.on_event("startup")
async def startup_event():
    """Initialize strategy engine on startup."""
    global strategy_engine
    strategy_engine = StatArbStrategyEngine()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/api/backtest/results")
async def list_backtest_results() -> List[BacktestResult]:
    """List all available backtest results."""
    results = []

    # Find all pickle files
    for pkl_file in Path(".").glob("backtest_results_*.pkl"):
        try:
            with open(pkl_file, 'rb') as f:
                data = pickle.load(f)

            # Extract metadata
            pm = data.get('performance_metrics', {})
            ua = data.get('universe_analysis', {})

            # Check validation
            checks_passed = 0
            if pm.get('annual_return', 0) > 0.25: checks_passed += 1
            if pm.get('sharpe_ratio', 0) > 1.0: checks_passed += 1
            if abs(pm.get('max_drawdown', 0)) < 0.15: checks_passed += 1
            if pm.get('profit_factor', 0) > 1.0: checks_passed += 1
            if pm.get('sharpe_ratio', 0) < 3.5: checks_passed += 1

            result = BacktestResult(
                id=pkl_file.name,
                date=datetime.fromtimestamp(pkl_file.stat().st_mtime),
                annual_return=pm.get('annual_return', 0) * 100,
                sharpe_ratio=pm.get('sharpe_ratio', 0),
                max_drawdown=pm.get('max_drawdown', 0) * 100,
                total_return=pm.get('total_return', 0) * 100,
                viable_pairs=len(ua.get('selected_pairs', [])),
                validation="passed" if checks_passed == 5 else "failed"
            )
            results.append(result)
        except Exception as e:
            print(f"Error loading {pkl_file}: {e}")

    return sorted(results, key=lambda x: x.date, reverse=True)

@app.post("/api/backtest/run")
async def run_backtest(request: BacktestRequest):
    """Run a new backtest."""
    try:
        # Import here to avoid circular dependencies
        from scripts.run_backtest import fetch_crypto_data, run_backtest, save_results

        # Fetch data
        price_data = fetch_crypto_data(request.start_date, request.end_date)

        # Run backtest
        results = run_backtest(price_data)

        # Save results
        save_results(results)

        return {
            "success": True,
            "annual_return": results['performance_metrics']['annual_return'],
            "sharpe_ratio": results['performance_metrics']['sharpe_ratio'],
            "max_drawdown": results['performance_metrics']['max_drawdown']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/strategy/status")
async def get_strategy_status():
    """Get current strategy status."""
    if strategy_engine is None:
        return {"status": "not_initialized"}

    return {
        "status": "initialized",
        "config": strategy_engine.config,
        "timestamp": datetime.now()
    }

@app.post("/api/trading/{action}")
async def control_trading(action: str):
    """Control live trading (start/stop/pause)."""
    valid_actions = ["start", "stop", "pause"]

    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    # In production, this would control actual trading
    return {
        "success": True,
        "action": action,
        "message": f"Trading {action} successful",
        "timestamp": datetime.now()
    }

@app.get("/api/positions")
async def get_positions():
    """Get current trading positions."""
    # Mock data for demonstration
    positions = [
        {
            "pair": "XLM-XRP",
            "side": "LONG",
            "entry_price": 2.145,
            "current_price": 2.178,
            "pnl": 1.54,
            "size": 10000,
            "status": "active"
        }
    ]
    return positions

@app.get("/api/notebook/execute")
async def execute_notebook_cell(code: str):
    """Execute Python code from notebook."""
    # This would need proper sandboxing in production
    try:
        # Create isolated namespace
        namespace = {}
        exec(code, namespace)

        # Capture output (simplified)
        return {
            "success": True,
            "output": str(namespace.get('result', ''))
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)