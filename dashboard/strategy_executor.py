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
    from supabase import create_client, Client
except ImportError:
    print("Installing required packages...")
    os.system("pip3 install requests pandas numpy supabase")
    import requests
    import hmac
    import hashlib
    from urllib.parse import urlencode
    from supabase import create_client, Client

import pandas as pd
import numpy as np

class DatabaseService:
    """Supabase database service for logging strategy data"""

    def __init__(self):
        # Get environment variables or use defaults
        self.supabase_url = os.getenv('NEXT_PUBLIC_SUPABASE_URL', 'https://hfmcbyqdibxdbimwkcwi.supabase.co')
        self.supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY',
                                      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhmbWNieXFkaWJ4ZGJpbXdrY3dpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTgzMDU3MCwiZXhwIjoyMDg3NDA2NTcwfQ.lAAU3d_wcZVOPMhFVZ80RizUJturvnKtXj2hX5nX8o0')

        try:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Connected to Supabase database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self.client = None

    def get_deployment_by_process_id(self, process_id: str):
        """Get deployment record by process ID"""
        if not self.client:
            return None
        try:
            result = self.client.table('strategy_deployments').select('*').eq('process_id', process_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Database error getting deployment: {e}")
            return None

    def create_position(self, deployment_id: str, position_data: dict):
        """Create a new position record"""
        if not self.client:
            return None
        try:
            result = self.client.table('positions').insert([{
                'deployment_id': deployment_id,
                'position_id': position_data['id'],
                'symbol_1': position_data['symbol1'],
                'symbol_2': position_data['symbol2'],
                'direction': position_data['direction'],
                'status': 'open',
                'entry_price_1': position_data['entry_price1'],
                'entry_price_2': position_data['entry_price2'],
                'entry_z_score': position_data['entry_z_score'],
                'position_size': position_data['size'],
                'entry_time': position_data['entry_time'].isoformat(),
                'realized_pnl': 0.0,
                'net_pnl': 0.0
            }]).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Database error creating position: {e}")
            return None

    def close_position(self, position_id: str, exit_data: dict):
        """Close a position record"""
        if not self.client:
            return None
        try:
            result = self.client.table('positions').update({
                'status': 'closed',
                'exit_price_1': exit_data['exit_price1'],
                'exit_price_2': exit_data['exit_price2'],
                'exit_z_score': exit_data.get('exit_z_score', 0),
                'exit_time': exit_data['exit_time'].isoformat(),
                'exit_reason': exit_data['reason'],
                'realized_pnl': exit_data['pnl'],
                'net_pnl': exit_data['pnl']
            }).eq('position_id', position_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Database error closing position: {e}")
            return None

    def create_trade(self, deployment_id: str, position_id: str, trade_data: dict):
        """Create a trade record"""
        if not self.client:
            return None
        try:
            result = self.client.table('trades').insert([{
                'deployment_id': deployment_id,
                'position_id': position_id,
                'symbol': trade_data['symbol'],
                'side': trade_data['side'],
                'quantity': trade_data['quantity'],
                'price': trade_data['price'],
                'commission': trade_data.get('commission', 0.0),
                'execution_time': trade_data['execution_time'].isoformat(),
                'realized_pnl': trade_data.get('pnl', 0.0)
            }]).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Database error creating trade: {e}")
            return None

    def log_system_event(self, deployment_id: str, log_level: str, log_type: str, message: str):
        """Log a system event"""
        if not self.client:
            return None
        try:
            result = self.client.table('system_logs').insert([{
                'deployment_id': deployment_id,
                'log_level': log_level,
                'log_type': log_type,
                'message': message
            }]).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Database error logging event: {e}")
            return None

    def update_deployment_metrics(self, deployment_id: str, total_trades: int, total_pnl: float):
        """Update deployment performance metrics"""
        if not self.client:
            return None
        try:
            result = self.client.table('strategy_deployments').update({
                'total_trades': total_trades,
                'total_pnl': total_pnl
            }).eq('id', deployment_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Database error updating metrics: {e}")
            return None

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

    def __init__(self, config: StrategyConfig, process_id: str = None):
        self.config = config
        self.process_id = process_id
        self.status = StrategyStatus.STOPPED
        self.client = None
        self.positions = {}
        self.pnl = 0.0
        self.trades_today = 0
        self.last_rebalance = None
        self.running = False

        # Initialize database service
        self.db = DatabaseService()
        self.deployment_id = None

        # Initialize Binance client
        self._init_client()

        # Get deployment info from database if process_id provided
        if self.process_id and self.db.client:
            deployment = self.db.get_deployment_by_process_id(self.process_id)
            if deployment:
                self.deployment_id = deployment['id']
                logger.info(f"Found deployment in database: {self.deployment_id}")
            else:
                logger.warning(f"No deployment found for process_id: {self.process_id}")

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

            logger.info(f"SIGNAL CHECK - Current z-score: {z_score:.2f} | Prices: {self.config.symbol_1}={price1:.2f}, {self.config.symbol_2}={price2:.2f}")
            logger.info(f"ENTRY CRITERIA - Z-score threshold: {self.config.entry_z_score}, Current positions: {len(self.positions)}/{self.config.max_positions}")

            # Check entry conditions
            if abs(z_score) > self.config.entry_z_score and len(self.positions) < self.config.max_positions:
                if z_score > self.config.entry_z_score:
                    # Spread is too high - short symbol1, long symbol2
                    logger.info(f"✅ ENTRY SIGNAL TRIGGERED - Z-score {z_score:.2f} > {self.config.entry_z_score} - Going SHORT")
                    self._enter_position('SHORT', price1, price2, z_score)
                elif z_score < -self.config.entry_z_score:
                    # Spread is too low - long symbol1, short symbol2
                    logger.info(f"✅ ENTRY SIGNAL TRIGGERED - Z-score {z_score:.2f} < -{self.config.entry_z_score} - Going LONG")
                    self._enter_position('LONG', price1, price2, z_score)
            else:
                # Log why entry conditions weren't met
                if abs(z_score) <= self.config.entry_z_score:
                    logger.info(f"❌ NO ENTRY - Z-score {z_score:.2f} below threshold {self.config.entry_z_score}")
                if len(self.positions) >= self.config.max_positions:
                    logger.info(f"❌ NO ENTRY - Max positions reached {len(self.positions)}/{self.config.max_positions}")

        except Exception as e:
            logger.error(f"Error checking entry signals: {e}")

    def check_exit_signals(self):
        """Check for exit signals"""
        try:
            if not self.positions:
                logger.info("EXIT CHECK - No open positions to check")
                return

            logger.info(f"EXIT CHECK - Checking {len(self.positions)} open position(s)")

            # Get current prices
            ticker1 = self.client.get_ticker(symbol=self.config.symbol_1)
            ticker2 = self.client.get_ticker(symbol=self.config.symbol_2)

            price1 = float(ticker1['lastPrice'])
            price2 = float(ticker2['lastPrice'])

            # Calculate current z-score
            z_score = self.calculate_z_score(price1, price2)

            logger.info(f"EXIT CHECK - Current z-score: {z_score:.2f} | Exit threshold: {self.config.exit_z_score} | Stop loss: {self.config.stop_loss_z_score}")

            # Check each position
            for position_id, position in list(self.positions.items()):
                logger.info(f"CHECKING POSITION {position_id} ({position['direction']}) - Entry z-score: {position['entry_z_score']:.2f}")

                # Exit conditions
                exit_condition = False
                exit_reason = ""

                # Mean reversion exit
                if abs(z_score) < self.config.exit_z_score:
                    exit_condition = True
                    exit_reason = "Mean reversion"
                    logger.info(f"✅ EXIT SIGNAL - Mean reversion: |{z_score:.2f}| < {self.config.exit_z_score}")

                # Stop loss
                if position['direction'] == 'LONG' and z_score < -self.config.stop_loss_z_score:
                    exit_condition = True
                    exit_reason = "Stop loss"
                    logger.info(f"🛑 EXIT SIGNAL - LONG stop loss: {z_score:.2f} < -{self.config.stop_loss_z_score}")
                elif position['direction'] == 'SHORT' and z_score > self.config.stop_loss_z_score:
                    exit_condition = True
                    exit_reason = "Stop loss"
                    logger.info(f"🛑 EXIT SIGNAL - SHORT stop loss: {z_score:.2f} > {self.config.stop_loss_z_score}")

                if exit_condition:
                    self._exit_position(position_id, price1, price2, exit_reason)
                else:
                    logger.info(f"➤ POSITION HELD - {position_id} - No exit criteria met")

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
            entry_time = datetime.now()
            self.positions[position_id] = {
                'id': position_id,
                'direction': direction,
                'entry_price1': price1,
                'entry_price2': price2,
                'entry_z_score': z_score,
                'size': self.config.position_size,
                'entry_time': entry_time,
                'symbol1': self.config.symbol_1,
                'symbol2': self.config.symbol_2
            }

            # Log position to database
            if self.deployment_id:
                self.db.create_position(self.deployment_id, self.positions[position_id])
                self.db.log_system_event(
                    self.deployment_id,
                    'info',
                    'position',
                    f"Entered {direction} position {position_id} at z-score {z_score:.2f}"
                )

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

            # Log position closure to database
            if self.deployment_id:
                exit_time = datetime.now()
                # Get current z-score for exit logging
                current_z_score = self.calculate_z_score(price1, price2)

                self.db.close_position(position_id, {
                    'exit_price1': price1,
                    'exit_price2': price2,
                    'exit_z_score': current_z_score,
                    'exit_time': exit_time,
                    'reason': reason,
                    'pnl': pnl
                })

                self.db.log_system_event(
                    self.deployment_id,
                    'info',
                    'position',
                    f"Exited position {position_id} - {reason}, P&L: ${pnl:.2f}"
                )

                # Update deployment metrics
                self.db.update_deployment_metrics(self.deployment_id, self.trades_today, self.pnl)

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

                    # Update metrics in database periodically
                    if self.deployment_id:
                        self.db.update_deployment_metrics(self.deployment_id, self.trades_today, self.pnl)
                        self.db.log_system_event(
                            self.deployment_id,
                            'info',
                            'status',
                            f"Strategy running: {len(self.positions)} positions, P&L: ${self.pnl:.2f}, Trades: {self.trades_today}"
                        )

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
    parser.add_argument('--process-id', type=str, help='Process ID for database tracking')
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    if args.mode:
        config.trading_mode = TradingMode(args.mode)

    # Extract process_id from config file path if not provided
    process_id = args.process_id
    if not process_id and args.config:
        # Extract from config filename (e.g., strategy_123456.json -> strategy_123456)
        import os
        config_name = os.path.basename(args.config)
        if config_name.endswith('.json'):
            process_id = config_name[:-5]  # Remove .json extension

    # Create strategy
    strategy = StatArbStrategy(config, process_id)

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