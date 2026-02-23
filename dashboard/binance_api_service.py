#!/usr/bin/env python3
"""
Binance API Service using official Python connector
Provides a FastAPI server for the Next.js dashboard to interact with Binance
"""

import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from binance.um_futures import UMFutures
from binance.error import ClientError, ServerError

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Binance API Service")

# Configure CORS for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API credentials from environment
API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
API_SECRET = os.getenv('BINANCE_TESTNET_API_SECRET')

# Initialize Binance futures client for demo API
# Using the futures demo URL
client = UMFutures(
    key=API_KEY,
    secret=API_SECRET,
    base_url='https://demo-fapi.binance.com'
)

# Response models
class ConnectionTestResponse(BaseModel):
    connected: bool
    latency: Optional[int] = None
    error: Optional[str] = None
    account: Optional[Dict[str, Any]] = None
    timestamp: datetime

class AccountBalance(BaseModel):
    asset: str
    free: float
    locked: float
    total: float

class TradeInfo(BaseModel):
    symbol: str
    id: int
    orderId: int
    price: str
    qty: str
    quoteQty: str
    commission: str
    commissionAsset: str
    time: int
    isBuyer: bool
    isMaker: bool
    isBestMatch: bool

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Binance API Service",
        "timestamp": datetime.now()
    }

@app.get("/api/test-connection", response_model=ConnectionTestResponse)
async def test_connection():
    """Test connection to Binance API"""
    start_time = datetime.now()

    try:
        # Test server time endpoint (doesn't require authentication)
        server_time = client.time()

        # Test authenticated endpoint - get account info
        account_info = client.account()

        latency = int((datetime.now() - start_time).total_seconds() * 1000)

        return ConnectionTestResponse(
            connected=True,
            latency=latency,
            account={
                "canTrade": account_info.get("canTrade", False),
                "canWithdraw": account_info.get("canWithdraw", False),
                "canDeposit": account_info.get("canDeposit", False),
                "balanceCount": len(account_info.get("balances", [])),
                "updateTime": account_info.get("updateTime"),
            },
            timestamp=datetime.now()
        )

    except ClientError as e:
        logger.error(f"Client error: {e.error_code} - {e.error_message}")
        return ConnectionTestResponse(
            connected=False,
            error=f"API Error ({e.error_code}): {e.error_message}",
            timestamp=datetime.now()
        )
    except ServerError as e:
        logger.error(f"Server error: {e.status_code} - {e.message}")
        return ConnectionTestResponse(
            connected=False,
            error=f"Server Error ({e.status_code}): {e.message}",
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return ConnectionTestResponse(
            connected=False,
            error=str(e),
            timestamp=datetime.now()
        )

@app.get("/api/account/balances", response_model=List[AccountBalance])
async def get_balances():
    """Get account balances"""
    try:
        account_info = client.account()
        balances = account_info.get("balances", [])

        # Filter out zero balances
        non_zero_balances = []
        for balance in balances:
            free = float(balance.get("free", 0))
            locked = float(balance.get("locked", 0))
            if free > 0 or locked > 0:
                non_zero_balances.append(AccountBalance(
                    asset=balance["asset"],
                    free=free,
                    locked=locked,
                    total=free + locked
                ))

        return non_zero_balances

    except ClientError as e:
        raise HTTPException(
            status_code=401,
            detail=f"API Error ({e.error_code}): {e.error_message}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trades/{symbol}")
async def get_recent_trades(symbol: str, limit: int = 10):
    """Get recent trades for a symbol"""
    try:
        trades = client.my_trades(symbol=symbol, limit=limit)
        return trades

    except ClientError as e:
        raise HTTPException(
            status_code=401,
            detail=f"API Error ({e.error_code}): {e.error_message}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ticker/{symbol}")
async def get_ticker(symbol: str):
    """Get 24hr ticker statistics for a symbol"""
    try:
        ticker = client.ticker_24hr(symbol=symbol)
        return ticker

    except ClientError as e:
        raise HTTPException(
            status_code=401,
            detail=f"API Error ({e.error_code}): {e.error_message}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/open-orders")
async def get_open_orders(symbol: Optional[str] = None):
    """Get open orders"""
    try:
        if symbol:
            orders = client.get_open_orders(symbol=symbol)
        else:
            orders = client.get_open_orders()
        return orders

    except ClientError as e:
        raise HTTPException(
            status_code=401,
            detail=f"API Error ({e.error_code}): {e.error_message}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug-credentials")
async def debug_credentials():
    """Debug endpoint to verify credentials are loaded"""
    return {
        "hasApiKey": bool(API_KEY),
        "hasSecretKey": bool(API_SECRET),
        "apiKeyLength": len(API_KEY) if API_KEY else 0,
        "secretKeyLength": len(API_SECRET) if API_SECRET else 0,
        "apiKeyPreview": f"{API_KEY[:10]}...{API_KEY[-6:]}" if API_KEY else "MISSING",
        "secretKeyPreview": f"{API_SECRET[:10]}...{API_SECRET[-6:]}" if API_SECRET else "MISSING",
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Binance API Service...")
    logger.info(f"API Key loaded: {bool(API_KEY)}")
    logger.info(f"API Secret loaded: {bool(API_SECRET)}")

    uvicorn.run(app, host="0.0.0.0", port=8001)