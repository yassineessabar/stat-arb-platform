"""
Binance Futures Client
=====================

Production-ready Binance Futures API client with:
- Paper trading simulation
- Live trading execution
- Real-time data feeds
- Comprehensive error handling
- Rate limiting and connection management

Supports both testnet and live trading environments.
"""

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple, Union
import logging

import aiohttp
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class BinanceClient:
    """
    Async Binance Futures client for live and paper trading.
    """

    def __init__(self, api_key: str = "", api_secret: str = "",
                 testnet: bool = True, paper_trading: bool = True):
        """
        Initialize Binance client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet (default: True)
            paper_trading: Enable paper trading simulation (default: True)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.paper_trading = paper_trading

        # Base URLs
        if testnet:
            self.base_url = "https://testnet.binancefuture.com"  # Futures testnet
        else:
            self.base_url = "https://fapi.binance.com"

        # Session management
        self.session = None
        self.rate_limiter = RateLimiter()

        # Paper trading state
        if paper_trading:
            self.paper_state = PaperTradingSimulator()

        logger.info(f"Binance client initialized: testnet={testnet}, paper={paper_trading}")

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _generate_signature(self, params: Dict) -> str:
        """Generate HMAC SHA256 signature for authenticated requests."""
        query_string = urllib.parse.urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _make_request(self, method: str, endpoint: str,
                          params: Dict = None, signed: bool = False) -> Dict:
        """
        Make HTTP request to Binance API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            params: Request parameters
            signed: Whether request requires signature

        Returns:
            JSON response as dictionary
        """
        if params is None:
            params = {}

        url = f"{self.base_url}{endpoint}"
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}

        # Add timestamp and signature for authenticated requests
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)

        # Rate limiting
        await self.rate_limiter.acquire()

        try:
            if method == "GET":
                async with self.session.get(url, params=params, headers=headers) as response:
                    return await self._handle_response(response)
            elif method == "POST":
                async with self.session.post(url, params=params, headers=headers) as response:
                    return await self._handle_response(response)
            elif method == "DELETE":
                async with self.session.delete(url, params=params, headers=headers) as response:
                    return await self._handle_response(response)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {e}")
            raise

    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict:
        """Handle HTTP response and errors."""
        content = await response.text()

        if response.status == 200:
            return json.loads(content)
        else:
            logger.error(f"API error {response.status}: {content}")
            raise Exception(f"API error {response.status}: {content}")

    # ==========================================================================
    # Market Data Methods
    # ==========================================================================

    async def get_klines(self, symbol: str, interval: str = "1d",
                        limit: int = 500, start_time: int = None) -> List[List]:
        """
        Get historical kline/candlestick data.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Time interval (1m, 5m, 1h, 1d, etc.)
            limit: Number of klines to retrieve (max 1000)
            start_time: Start time in milliseconds

        Returns:
            List of kline data
        """
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }

        if start_time:
            params['startTime'] = start_time

        return await self._make_request("GET", "/fapi/v1/klines", params)

    async def get_ticker_24hr(self, symbol: str = None) -> Union[Dict, List[Dict]]:
        """
        Get 24hr ticker price change statistics.

        Args:
            symbol: Trading pair symbol (optional, returns all if None)

        Returns:
            Ticker data for symbol or list of all tickers
        """
        params = {}
        if symbol:
            params['symbol'] = symbol

        return await self._make_request("GET", "/fapi/v1/ticker/24hr", params)

    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        """
        Get order book for a symbol.

        Args:
            symbol: Trading pair symbol
            limit: Number of entries to return (5, 10, 20, 50, 100, 500, 1000)

        Returns:
            Order book data
        """
        params = {'symbol': symbol, 'limit': limit}
        return await self._make_request("GET", "/fapi/v1/depth", params)

    async def get_funding_rate(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """
        Get funding rate history.

        Args:
            symbol: Trading pair symbol (optional)
            limit: Number of records to return

        Returns:
            List of funding rate records
        """
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol

        return await self._make_request("GET", "/fapi/v1/fundingRate", params)

    # ==========================================================================
    # Account and Position Methods
    # ==========================================================================

    async def get_account_info(self) -> Dict:
        """
        Get current account information including balances and positions.

        Returns:
            Account information
        """
        if self.paper_trading:
            return self.paper_state.get_account_info()

        return await self._make_request("GET", "/fapi/v2/account", signed=True)

    async def get_position_risk(self, symbol: str = None) -> List[Dict]:
        """
        Get position information.

        Args:
            symbol: Trading pair symbol (optional)

        Returns:
            List of position information
        """
        if self.paper_trading:
            return self.paper_state.get_position_risk(symbol)

        params = {}
        if symbol:
            params['symbol'] = symbol

        return await self._make_request("GET", "/fapi/v2/positionRisk", params, signed=True)

    async def get_balance(self) -> List[Dict]:
        """
        Get account balance information.

        Returns:
            List of asset balances
        """
        if self.paper_trading:
            return self.paper_state.get_balance()

        account_info = await self.get_account_info()
        return account_info.get('assets', [])

    # ==========================================================================
    # Trading Methods
    # ==========================================================================

    async def place_order(self, symbol: str, side: str, order_type: str,
                         quantity: float, price: float = None,
                         time_in_force: str = "GTC",
                         reduce_only: bool = False) -> Dict:
        """
        Place a new order.

        Args:
            symbol: Trading pair symbol
            side: Order side (BUY or SELL)
            order_type: Order type (LIMIT, MARKET, STOP, etc.)
            quantity: Order quantity
            price: Order price (required for LIMIT orders)
            time_in_force: Time in force (GTC, IOC, FOK)
            reduce_only: Reduce only flag

        Returns:
            Order response
        """
        if self.paper_trading:
            return await self.paper_state.place_order(
                symbol, side, order_type, quantity, price, time_in_force, reduce_only
            )

        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': str(quantity),
            'timeInForce': time_in_force
        }

        if price:
            params['price'] = str(price)

        if reduce_only:
            params['reduceOnly'] = 'true'

        return await self._make_request("POST", "/fapi/v1/order", params, signed=True)

    async def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """
        Cancel an active order.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            Cancel response
        """
        if self.paper_trading:
            return self.paper_state.cancel_order(symbol, order_id)

        params = {
            'symbol': symbol,
            'orderId': order_id
        }

        return await self._make_request("DELETE", "/fapi/v1/order", params, signed=True)

    async def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """
        Get all open orders.

        Args:
            symbol: Trading pair symbol (optional)

        Returns:
            List of open orders
        """
        if self.paper_trading:
            return self.paper_state.get_open_orders(symbol)

        params = {}
        if symbol:
            params['symbol'] = symbol

        return await self._make_request("GET", "/fapi/v1/openOrders", params, signed=True)

    async def get_order_status(self, symbol: str, order_id: int) -> Dict:
        """
        Get order status.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID

        Returns:
            Order status information
        """
        if self.paper_trading:
            return self.paper_state.get_order_status(symbol, order_id)

        params = {
            'symbol': symbol,
            'orderId': order_id
        }

        return await self._make_request("GET", "/fapi/v1/order", params, signed=True)

    # ==========================================================================
    # Data Conversion Methods
    # ==========================================================================

    def klines_to_dataframe(self, klines: List[List], symbol: str) -> pd.DataFrame:
        """
        Convert klines data to pandas DataFrame.

        Args:
            klines: Klines data from get_klines
            symbol: Symbol for reference

        Returns:
            DataFrame with OHLCV data
        """
        columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'count', 'taker_buy_volume',
            'taker_buy_quote_volume', 'ignore'
        ]

        df = pd.DataFrame(klines, columns=columns)

        # Convert to appropriate data types
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df.set_index('open_time', inplace=True)
        df['symbol'] = symbol

        return df[['open', 'high', 'low', 'close', 'volume', 'symbol']]


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 1200):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0

    async def acquire(self):
        """Acquire rate limit token."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()


class PaperTradingSimulator:
    """Paper trading simulator for backtesting and testing."""

    def __init__(self, initial_balance: float = 100000):
        """
        Initialize paper trading simulator.

        Args:
            initial_balance: Starting balance in USDT
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = {}
        self.orders = {}
        self.order_id_counter = 1

        logger.info(f"Paper trading simulator initialized with ${initial_balance:,} USDT")

    def get_account_info(self) -> Dict:
        """Get simulated account information."""
        return {
            'assets': [
                {
                    'asset': 'USDT',
                    'walletBalance': str(self.balance),
                    'unrealizedPnL': '0.00000000',
                    'marginBalance': str(self.balance),
                    'maintMargin': '0.00000000',
                    'initialMargin': '0.00000000',
                    'positionInitialMargin': '0.00000000',
                    'openOrderInitialMargin': '0.00000000'
                }
            ],
            'totalWalletBalance': str(self.balance),
            'totalUnrealizedPnL': '0.00000000',
            'totalMarginBalance': str(self.balance),
            'canTrade': True,
            'canDeposit': True,
            'canWithdraw': True,
            'updateTime': int(time.time() * 1000)
        }

    def get_position_risk(self, symbol: str = None) -> List[Dict]:
        """Get simulated position information."""
        if symbol:
            pos = self.positions.get(symbol, self._empty_position(symbol))
            return [pos]
        else:
            return list(self.positions.values())

    def get_balance(self) -> List[Dict]:
        """Get simulated balance."""
        return [{
            'asset': 'USDT',
            'balance': str(self.balance),
            'withdrawAvailable': str(self.balance),
            'updateTime': int(time.time() * 1000)
        }]

    async def place_order(self, symbol: str, side: str, order_type: str,
                         quantity: float, price: float = None,
                         time_in_force: str = "GTC", reduce_only: bool = False) -> Dict:
        """Simulate order placement."""
        order_id = self.order_id_counter
        self.order_id_counter += 1

        # For simplicity, assume all orders fill immediately at market price
        fill_price = price if price else 50000  # Mock price

        order = {
            'orderId': order_id,
            'symbol': symbol,
            'status': 'FILLED',
            'clientOrderId': f'paper_{order_id}',
            'price': str(fill_price),
            'avgPrice': str(fill_price),
            'origQty': str(quantity),
            'executedQty': str(quantity),
            'cumQuote': str(quantity * fill_price),
            'timeInForce': time_in_force,
            'type': order_type,
            'reduceOnly': reduce_only,
            'side': side,
            'positionSide': 'BOTH',
            'stopPrice': '0',
            'workingType': 'CONTRACT_PRICE',
            'priceProtect': False,
            'origType': order_type,
            'updateTime': int(time.time() * 1000)
        }

        # Update position
        self._update_position(symbol, side, quantity, fill_price)

        logger.info(f"Paper order filled: {side} {quantity} {symbol} @ ${fill_price}")

        return order

    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Simulate order cancellation."""
        return {
            'orderId': order_id,
            'symbol': symbol,
            'status': 'CANCELED',
            'clientOrderId': f'paper_{order_id}'
        }

    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Get simulated open orders (always empty for simplicity)."""
        return []

    def get_order_status(self, symbol: str, order_id: int) -> Dict:
        """Get simulated order status."""
        return {
            'orderId': order_id,
            'symbol': symbol,
            'status': 'FILLED',
            'clientOrderId': f'paper_{order_id}'
        }

    def _update_position(self, symbol: str, side: str, quantity: float, price: float):
        """Update simulated position."""
        if symbol not in self.positions:
            self.positions[symbol] = self._empty_position(symbol)

        pos = self.positions[symbol]
        current_qty = float(pos['positionAmt'])

        if side == 'BUY':
            new_qty = current_qty + quantity
        else:  # SELL
            new_qty = current_qty - quantity

        pos['positionAmt'] = str(new_qty)
        pos['entryPrice'] = str(price)
        pos['updateTime'] = int(time.time() * 1000)

    def _empty_position(self, symbol: str) -> Dict:
        """Create empty position structure."""
        return {
            'symbol': symbol,
            'positionAmt': '0.0',
            'entryPrice': '0.0',
            'markPrice': '0.0',
            'unRealizedPnL': '0.0',
            'liquidationPrice': '0',
            'leverage': '1',
            'maxNotionalValue': '25000',
            'marginType': 'cross',
            'isolatedMargin': '0.0',
            'isAutoAddMargin': 'false',
            'positionSide': 'BOTH',
            'notional': '0',
            'isolatedWallet': '0',
            'updateTime': int(time.time() * 1000)
        }