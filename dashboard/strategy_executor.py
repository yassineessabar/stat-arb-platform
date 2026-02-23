#!/usr/bin/env python3
"""
Strategy Executor for Statistical Arbitrage Platform
Runs 24/7 on server for live or paper trading
"""

import os
import sys
import json
import time
import signal
import logging
import asyncio
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# Add required packages
try:
    import requests
    import hmac
    import hashlib
    from urllib.parse import urlencode
except ImportError:
    print("Installing required packages...")
    os.system("pip3 install requests pandas numpy")
    import requests
    import hmac
    import hashlib
    from urllib.parse import urlencode

import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('strategy_executor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"

class StrategyStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

@dataclass
class StrategyConfig:
    """Strategy configuration parameters"""
    strategy_name: str
    trading_mode: TradingMode
    symbol_1: str
    symbol_2: str
    lookback_period: int
    entry_z_score: float
    exit_z_score: float
    stop_loss_z_score: float
    position_size: float
    max_positions: int
    rebalance_frequency: int  # in minutes
    api_key: str
    api_secret: str
    testnet: bool = True

class BinanceClient:
    """Simple Binance API client for strategy execution"""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://testnet.binancefuture.com' if testnet else 'https://fapi.binance.com'

    def _sign_request(self, params: dict) -> str:
        """Sign request parameters"""
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, endpoint: str, params: dict = None, signed: bool = False) -> dict:
        """Make API request"""
        if params is None:
            params = {}

        headers = {'X-MBX-APIKEY': self.api_key}

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._sign_request(params)

        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, params=params, headers=headers)

        if response.status_code != 200:
            logger.error(f"API request failed: {response.status_code} - {response.text}")
            raise Exception(f"API request failed: {response.status_code}")

        return response.json()

    def get_account(self) -> dict:
        """Get account information"""
        return self._make_request('/fapi/v2/account', signed=True)

    def get_ticker(self, symbol: str) -> dict:
        """Get 24hr ticker"""
        return self._make_request('/fapi/v1/ticker/24hr', {'symbol': symbol})

    def get_klines(self, symbol: str, interval: str = '1h', limit: int = 100) -> list:
        """Get kline/candlestick data"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        return self._make_request('/fapi/v1/klines', params)

class StatArbStrategy:
    """Statistical Arbitrage Strategy Executor"""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.status = StrategyStatus.STOPPED
        self.client = None
        self.positions = {}
        self.pnl = 0.0
        self.trades_today = 0
        self.last_rebalance = None
        self.running = False

        # Initialize Binance client
        self._init_client()

    def _init_client(self):
        """Initialize Binance client"""
        try:
            self.client = BinanceClient(
                self.config.api_key,
                self.config.api_secret,
                self.config.testnet
            )

            # Test connection
            account = self.client.get_account()
            logger.info(f"Connected to Binance {'Testnet' if self.config.testnet else 'Live'}")
            logger.info(f"Account balance: {account.get('totalWalletBalance', 0)} USDT")

        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise

    def calculate_z_score(self, price1: float, price2: float) -> float:
        """Calculate z-score for the spread"""
        try:
            # Get historical data
            klines1 = self.client.get_klines(
                symbol=self.config.symbol_1,
                interval='1h',
                limit=self.config.lookback_period
            )
            klines2 = self.client.get_klines(
                symbol=self.config.symbol_2,
                interval='1h',
                limit=self.config.lookback_period
            )

            # Convert to pandas
            df1 = pd.DataFrame(klines1, columns=['time', 'open', 'high', 'low', 'close', 'volume',
                                                  'close_time', 'quote_volume', 'trades',
                                                  'taker_buy_base', 'taker_buy_quote', 'ignore'])
            df2 = pd.DataFrame(klines2, columns=['time', 'open', 'high', 'low', 'close', 'volume',
                                                  'close_time', 'quote_volume', 'trades',
                                                  'taker_buy_base', 'taker_buy_quote', 'ignore'])

            df1['close'] = df1['close'].astype(float)
            df2['close'] = df2['close'].astype(float)

            # Calculate spread
            spread = df1['close'] - df2['close']
            mean_spread = spread.mean()
            std_spread = spread.std()

            # Current spread
            current_spread = price1 - price2

            # Z-score
            if std_spread > 0:
                z_score = (current_spread - mean_spread) / std_spread
            else:
                z_score = 0.0

            return z_score

        except Exception as e:
            logger.error(f"Error calculating z-score: {e}")
            return 0.0

    def check_entry_signals(self):
        """Check for entry signals"""
        try:
            # Get current prices
            ticker1 = self.client.get_ticker(symbol=self.config.symbol_1)
            ticker2 = self.client.get_ticker(symbol=self.config.symbol_2)

            price1 = float(ticker1['lastPrice'])
            price2 = float(ticker2['lastPrice'])

            # Calculate z-score
            z_score = self.calculate_z_score(price1, price2)

            logger.info(f"Current z-score: {z_score:.2f} | Prices: {self.config.symbol_1}={price1:.2f}, {self.config.symbol_2}={price2:.2f}")

            # Check entry conditions
            if abs(z_score) > self.config.entry_z_score and len(self.positions) < self.config.max_positions:
                if z_score > self.config.entry_z_score:
                    # Spread is too high - short symbol1, long symbol2
                    self._enter_position('SHORT', price1, price2, z_score)
                elif z_score < -self.config.entry_z_score:
                    # Spread is too low - long symbol1, short symbol2
                    self._enter_position('LONG', price1, price2, z_score)

        except Exception as e:
            logger.error(f"Error checking entry signals: {e}")

    def check_exit_signals(self):
        """Check for exit signals"""
        try:
            if not self.positions:
                return

            # Get current prices
            ticker1 = self.client.get_ticker(symbol=self.config.symbol_1)
            ticker2 = self.client.get_ticker(symbol=self.config.symbol_2)

            price1 = float(ticker1['lastPrice'])
            price2 = float(ticker2['lastPrice'])

            # Calculate current z-score
            z_score = self.calculate_z_score(price1, price2)

            # Check each position
            for position_id, position in list(self.positions.items()):
                # Exit conditions
                exit_condition = False
                exit_reason = ""

                # Mean reversion exit
                if abs(z_score) < self.config.exit_z_score:
                    exit_condition = True
                    exit_reason = "Mean reversion"

                # Stop loss
                if position['direction'] == 'LONG' and z_score < -self.config.stop_loss_z_score:
                    exit_condition = True
                    exit_reason = "Stop loss"
                elif position['direction'] == 'SHORT' and z_score > self.config.stop_loss_z_score:
                    exit_condition = True
                    exit_reason = "Stop loss"

                if exit_condition:
                    self._exit_position(position_id, price1, price2, exit_reason)

        except Exception as e:
            logger.error(f"Error checking exit signals: {e}")

    def _enter_position(self, direction: str, price1: float, price2: float, z_score: float):
        """Enter a new position"""
        try:
            position_id = f"{direction}_{int(time.time())}"

            if self.config.trading_mode == TradingMode.LIVE:
                # Place actual orders
                # This is simplified - in production you'd handle order execution properly
                logger.warning("Live trading execution not fully implemented for safety")

            # Record position (paper trading or after live execution)
            self.positions[position_id] = {
                'direction': direction,
                'entry_price1': price1,
                'entry_price2': price2,
                'entry_z_score': z_score,
                'size': self.config.position_size,
                'entry_time': datetime.now(),
                'symbol1': self.config.symbol_1,
                'symbol2': self.config.symbol_2
            }

            self.trades_today += 1
            logger.info(f"Entered {direction} position: {position_id} at z-score {z_score:.2f}")

        except Exception as e:
            logger.error(f"Error entering position: {e}")

    def _exit_position(self, position_id: str, price1: float, price2: float, reason: str):
        """Exit a position"""
        try:
            position = self.positions[position_id]

            # Calculate P&L
            if position['direction'] == 'LONG':
                pnl = ((price1 - position['entry_price1']) -
                      (price2 - position['entry_price2'])) * position['size']
            else:  # SHORT
                pnl = ((position['entry_price1'] - price1) -
                      (position['entry_price2'] - price2)) * position['size']

            self.pnl += pnl

            if self.config.trading_mode == TradingMode.LIVE:
                # Close actual orders
                logger.warning("Live trading execution not fully implemented for safety")

            # Remove position
            del self.positions[position_id]

            logger.info(f"Exited position {position_id} - Reason: {reason}, P&L: ${pnl:.2f}")

        except Exception as e:
            logger.error(f"Error exiting position: {e}")

    async def run_strategy(self):
        """Main strategy loop"""
        self.running = True
        self.status = StrategyStatus.RUNNING

        logger.info(f"Starting strategy: {self.config.strategy_name} in {self.config.trading_mode.value} mode")

        while self.running:
            try:
                if self.status == StrategyStatus.RUNNING:
                    # Check for new signals
                    self.check_entry_signals()
                    self.check_exit_signals()

                    # Log status
                    logger.info(f"Status: {len(self.positions)} positions | P&L: ${self.pnl:.2f} | Trades today: {self.trades_today}")

                # Wait for next iteration
                await asyncio.sleep(self.config.rebalance_frequency * 60)

            except Exception as e:
                logger.error(f"Strategy error: {e}")
                self.status = StrategyStatus.ERROR
                await asyncio.sleep(60)  # Wait before retry

    def stop(self):
        """Stop the strategy"""
        logger.info("Stopping strategy...")
        self.running = False
        self.status = StrategyStatus.STOPPED

        # Close all positions if in live mode
        if self.config.trading_mode == TradingMode.LIVE and self.positions:
            logger.info(f"Closing {len(self.positions)} open positions...")
            # Implementation would go here

    def pause(self):
        """Pause the strategy"""
        logger.info("Pausing strategy...")
        self.status = StrategyStatus.PAUSED

    def resume(self):
        """Resume the strategy"""
        logger.info("Resuming strategy...")
        self.status = StrategyStatus.RUNNING

def load_config(config_file: str) -> StrategyConfig:
    """Load strategy configuration from file"""
    with open(config_file, 'r') as f:
        config_data = json.load(f)

    return StrategyConfig(
        strategy_name=config_data['strategy_name'],
        trading_mode=TradingMode(config_data['trading_mode']),
        symbol_1=config_data['symbol_1'],
        symbol_2=config_data['symbol_2'],
        lookback_period=config_data['lookback_period'],
        entry_z_score=config_data['entry_z_score'],
        exit_z_score=config_data['exit_z_score'],
        stop_loss_z_score=config_data['stop_loss_z_score'],
        position_size=config_data['position_size'],
        max_positions=config_data['max_positions'],
        rebalance_frequency=config_data['rebalance_frequency'],
        api_key=config_data['api_key'],
        api_secret=config_data['api_secret'],
        testnet=config_data.get('testnet', True)
    )

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Statistical Arbitrage Strategy Executor')
    parser.add_argument('--config', type=str, required=True, help='Path to strategy config file')
    parser.add_argument('--mode', type=str, choices=['paper', 'live'], default='paper', help='Trading mode')
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    if args.mode:
        config.trading_mode = TradingMode(args.mode)

    # Create strategy
    strategy = StatArbStrategy(config)

    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        strategy.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run strategy
    try:
        asyncio.run(strategy.run_strategy())
    except KeyboardInterrupt:
        strategy.stop()
        logger.info("Strategy stopped by user")

if __name__ == "__main__":
    main()