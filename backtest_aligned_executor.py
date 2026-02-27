#!/usr/bin/env python3
"""
Backtest-Aligned Strategy Executor
==================================

This executor uses the EXACT SAME strategy engine as the backtest to ensure
identical behavior between backtesting and live trading.

Key features:
- Uses core.strategy_engine.StatArbStrategyEngine (same as backtest)
- Pair trading with Kalman filters (not individual asset mean reversion)
- Regime detection and filtering
- Multi-tier pair selection
- Exact same z-score calculations on spreads

This should produce identical signals to the backtest.
"""

import os
import sys
import json
import time
import logging
import numpy as np
import pandas as pd
import requests
import hmac
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the EXACT strategy engine used in backtesting
from core.strategy_engine import StatArbStrategyEngine

# Setup logging to match the original executor format
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class SimpleBinanceClient:
    """Simplified Binance client for futures trading"""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret

        if testnet:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"

        self.session = requests.Session()
        self.session.headers.update({'X-MBX-APIKEY': self.api_key})

    def _sign_request(self, params: dict) -> dict:
        """Sign request with HMAC SHA256"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        return params

    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            response = self.session.get(f"{self.base_url}/fapi/v1/ticker/price", params={'symbol': symbol})
            if response.status_code == 200:
                return float(response.json()['price'])
            else:
                logger.error(f"Failed to get price for {symbol}: {response.text}")
                return 0.0
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return 0.0

    def get_prices_batch(self, symbols: list) -> dict:
        """Get prices for multiple symbols"""
        prices = {}
        for symbol in symbols:
            price = self.get_price(symbol)
            if price > 0:
                prices[symbol] = price
        return prices

    def get_account_balance(self):
        """Get account balance"""
        try:
            params = {'timestamp': int(time.time() * 1000)}
            params = self._sign_request(params)

            response = self.session.get(f"{self.base_url}/fapi/v2/account", params=params)
            if response.status_code == 200:
                account = response.json()
                balance = account.get('totalWalletBalance', '0')
                logger.info(f"💰 USDT Balance: {balance} USDT")
                return account
            else:
                logger.error(f"Failed to get account: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return None

    def place_order(self, symbol: str, side: str, quantity: float) -> dict:
        """Place a REAL futures market order"""
        try:
            # Get correct precision for each symbol
            precision = self.get_symbol_precision(symbol)

            params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': f"{quantity:.{precision}f}",
                'timestamp': int(time.time() * 1000)
            }

            # Sign request
            params = self._sign_request(params)

            # Place REAL futures order
            response = self.session.post(f"{self.base_url}/fapi/v1/order", data=params)

            if response.status_code == 200:
                order = response.json()
                logger.info(f"✅ ORDER EXECUTED: {side} {quantity} {symbol}")
                logger.info(f"   Order ID: {order['orderId']}")
                logger.info(f"   Status: {order['status']}")
                return order
            else:
                logger.error(f"❌ Order failed: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def get_symbol_precision(self, symbol: str) -> int:
        """Get the correct quantity precision for each symbol"""
        symbol_precisions = {
            'BTCUSDT': 3,   # BTC futures use 3 decimal places
            'ETHUSDT': 3,   # ETH futures use 3 decimal places
            'BNBUSDT': 2,   # BNB futures use 2 decimal places
            'SOLUSDT': 0,   # SOL futures use 0 decimal places
            'XRPUSDT': 1,   # XRP futures use 1 decimal place
            'ADAUSDT': 0,   # ADA futures use 0 decimal places
            'AVAXUSDT': 1,  # AVAX futures use 1 decimal place
            'DOGEUSDT': 0,  # DOGE futures use 0 decimal places
            'DOTUSDT': 1,   # DOT futures use 1 decimal place
            'MATICUSDT': 0, # MATIC futures use 0 decimal places
        }
        return symbol_precisions.get(symbol, 3)  # Default to 3 if unknown


class BacktestAlignedBot:
    """Statistical Arbitrage Bot using exact backtest strategy engine"""

    def __init__(self, config_file='strategy_config.json'):
        """Initialize bot with backtest-aligned strategy engine"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        logger.info("=" * 60)
        logger.info("📈 BACKTEST-ALIGNED STATISTICAL ARBITRAGE BOT")
        logger.info("=" * 60)

        # Initialize the EXACT strategy engine from backtest
        config_dir = Path(__file__).parent / "config"
        self.engine = StatArbStrategyEngine(config_dir)

        logger.info(f"✅ Using exact backtest strategy engine")
        logger.info(f"📊 Parameters: z_entry={self.engine.params['signals']['z_entry']}")
        logger.info(f"📊 Parameters: z_exit_long={self.engine.params['signals']['z_exit_long']}")

        # Initialize Binance client
        self.client = SimpleBinanceClient(
            api_key=self.config['api_key'],
            api_secret=self.config['api_secret'],
            testnet=self.config.get('use_testnet', True)
        )

        # Trading state
        self.price_history = pd.DataFrame()
        self.positions = {}
        self.active_pairs = []
        self.universe = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
            'ADAUSDT', 'AVAXUSDT', 'DOGEUSDT', 'DOTUSDT', 'MATICUSDT'
        ]

        # Check balance
        self.client.get_account_balance()

    def fetch_price_data(self):
        """Fetch current prices and update history (same as backtest)"""
        # Get current prices for all universe assets
        prices = self.client.get_prices_batch(self.universe)

        if not prices:
            logger.warning("No price data received")
            return

        # Add to history as DataFrame (same format as backtest)
        new_row = pd.DataFrame([prices], index=[pd.Timestamp.now()])

        if self.price_history.empty:
            self.price_history = new_row
        else:
            self.price_history = pd.concat([self.price_history, new_row])

        # Keep only required lookback periods (same as backtest)
        max_lookback = 250  # Conservative lookback for all components
        if len(self.price_history) > max_lookback:
            self.price_history = self.price_history.tail(max_lookback)

    def initialize_pairs(self):
        """Initialize pairs using strategy engine (same as backtest)"""
        min_periods = self.engine.params['cointegration']['rolling_window']

        if len(self.price_history) < min_periods:
            logger.info(f"📊 Need {min_periods} periods, have {len(self.price_history)}")
            return False

        logger.info("🔍 Analyzing universe for trading pairs...")

        # Use EXACT same universe analysis as backtest
        universe_analysis = self.engine.analyze_universe(self.price_history)

        # Initialize pairs (same as backtest)
        self.active_pairs = universe_analysis['selected_pairs']
        self.engine.initialize_pairs(self.active_pairs, self.price_history)

        logger.info(f"✅ Initialized {len(self.active_pairs)} pairs:")
        for i, pair in enumerate(self.active_pairs[:5]):
            logger.info(f"   {i+1}. {pair['pair']} (Tier {pair['tier']}) - Score: {pair['score']:.1f}")

        return True

    def generate_signals(self):
        """Generate signals using exact backtest logic"""
        if len(self.active_pairs) == 0:
            return {}

        if len(self.price_history) < 2:
            return {}

        # Use EXACT same signal generation as backtest
        signals_result = self.engine.generate_signals(self.price_history)

        return signals_result.get('pair_signals', {})

    def execute_trades(self, signals):
        """Execute trades based on signals (converted to individual asset orders)"""
        if not signals:
            return

        # Process each pair signal
        for pair_name, signal_series in signals.items():
            if not isinstance(signal_series, pd.Series) or signal_series.empty:
                continue

            # Get the latest signal
            latest_signal = signal_series.iloc[-1] if len(signal_series) > 0 else 0.0

            # Skip if signal is too small
            if abs(latest_signal) < 0.1:
                continue

            # Extract pair assets
            if '-' not in pair_name:
                continue

            asset_a, asset_b = pair_name.split('-')

            # Convert pair signal to individual asset trades
            # In pair trading: long the pair = long asset_a, short asset_b
            if latest_signal > 0.5:  # Strong long signal
                logger.info(f"🟢 LONG SIGNAL: {pair_name} (signal: {latest_signal:.2f})")
                self.execute_pair_trade(asset_a, asset_b, 'LONG')

            elif latest_signal < -0.5:  # Strong short signal
                logger.info(f"🔴 SHORT SIGNAL: {pair_name} (signal: {latest_signal:.2f})")
                self.execute_pair_trade(asset_a, asset_b, 'SHORT')

    def execute_pair_trade(self, asset_a: str, asset_b: str, direction: str):
        """Execute a pair trade (long A/short B or vice versa)"""
        try:
            pair_key = f"{asset_a}-{asset_b}"

            # Check if we already have this position
            if pair_key in self.positions:
                logger.info(f"⏸️  Position already exists for {pair_key}")
                return

            # Calculate position sizes (simple $100 each leg)
            price_a = self.client.get_price(asset_a)
            price_b = self.client.get_price(asset_b)

            if price_a <= 0 or price_b <= 0:
                logger.error(f"Invalid prices: {asset_a}=${price_a}, {asset_b}=${price_b}")
                return

            # Calculate quantities for $100 notional each
            min_notional = 100.0
            qty_a = min_notional / price_a
            qty_b = min_notional / price_b

            # Apply precision rounding
            precision_a = self.client.get_symbol_precision(asset_a)
            precision_b = self.client.get_symbol_precision(asset_b)
            qty_a = round(qty_a, precision_a)
            qty_b = round(qty_b, precision_b)

            if direction == 'LONG':
                # Long the pair = Long A, Short B
                logger.info(f"🔵 EXECUTING LONG PAIR: {pair_key}")
                order_a = self.client.place_order(asset_a, 'BUY', qty_a)
                order_b = self.client.place_order(asset_b, 'SELL', qty_b)

            else:  # SHORT
                # Short the pair = Short A, Long B
                logger.info(f"🔴 EXECUTING SHORT PAIR: {pair_key}")
                order_a = self.client.place_order(asset_a, 'SELL', qty_a)
                order_b = self.client.place_order(asset_b, 'BUY', qty_b)

            # Track position if orders succeeded
            if order_a and order_b:
                self.positions[pair_key] = {
                    'direction': direction,
                    'asset_a': asset_a,
                    'asset_b': asset_b,
                    'qty_a': qty_a,
                    'qty_b': qty_b,
                    'entry_time': datetime.now(),
                    'order_a': order_a['orderId'],
                    'order_b': order_b['orderId']
                }
                logger.info(f"✅ PAIR POSITION CREATED: {pair_key}")

        except Exception as e:
            logger.error(f"❌ Error executing pair trade {asset_a}-{asset_b}: {e}")

    def check_exit_signals(self):
        """Check for exit signals on existing positions"""
        if not self.positions:
            return

        # Get current signals
        signals = self.generate_signals()

        positions_to_close = []

        for pair_key, position in self.positions.items():
            if pair_key in signals:
                signal_series = signals[pair_key]
                if isinstance(signal_series, pd.Series) and not signal_series.empty:
                    latest_signal = signal_series.iloc[-1]

                    # Close position if signal flipped or became neutral
                    position_direction = position['direction']

                    if position_direction == 'LONG' and latest_signal < 0.1:
                        logger.info(f"🔄 EXIT LONG: {pair_key} (signal: {latest_signal:.2f})")
                        positions_to_close.append(pair_key)

                    elif position_direction == 'SHORT' and latest_signal > -0.1:
                        logger.info(f"🔄 EXIT SHORT: {pair_key} (signal: {latest_signal:.2f})")
                        positions_to_close.append(pair_key)

        # Close positions
        for pair_key in positions_to_close:
            self.close_pair_position(pair_key)

    def close_pair_position(self, pair_key: str):
        """Close a pair position"""
        if pair_key not in self.positions:
            return

        position = self.positions[pair_key]

        try:
            # Close both legs (reverse the original trades)
            asset_a = position['asset_a']
            asset_b = position['asset_b']
            qty_a = position['qty_a']
            qty_b = position['qty_b']

            if position['direction'] == 'LONG':
                # Close long pair = Sell A, Buy B
                self.client.place_order(asset_a, 'SELL', qty_a)
                self.client.place_order(asset_b, 'BUY', qty_b)
            else:
                # Close short pair = Buy A, Sell B
                self.client.place_order(asset_a, 'BUY', qty_a)
                self.client.place_order(asset_b, 'SELL', qty_b)

            # Remove from positions
            del self.positions[pair_key]
            logger.info(f"✅ POSITION CLOSED: {pair_key}")

        except Exception as e:
            logger.error(f"❌ Error closing position {pair_key}: {e}")

    def run(self):
        """Main trading loop using exact backtest logic"""
        logger.info("=" * 60)
        logger.info("📌 Check orders at: https://testnet.binancefuture.com/")
        logger.info("=" * 60)

        iteration = 0

        while True:
            try:
                iteration += 1
                logger.info(f"\n🔄 ITERATION #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
                logger.info("-" * 50)

                # 1. Fetch current price data (same as backtest)
                self.fetch_price_data()

                # 2. Initialize pairs if not done yet (same as backtest)
                if not self.active_pairs:
                    if not self.initialize_pairs():
                        logger.info("⏳ Collecting more data for pair initialization...")
                        time.sleep(60)
                        continue

                # 3. Generate signals using exact backtest logic
                logger.info("📊 Generating signals using backtest engine...")
                signals = self.generate_signals()

                # 4. Check exit conditions for existing positions
                self.check_exit_signals()

                # 5. Execute new trades based on signals
                self.execute_trades(signals)

                # 6. Status report
                logger.info("-" * 50)
                logger.info("📈 PORTFOLIO STATUS")
                logger.info("-" * 50)
                logger.info(f"   Active Pairs: {len(self.active_pairs)}")
                logger.info(f"   Open Positions: {len(self.positions)}")
                logger.info(f"   Data Points: {len(self.price_history)}")

                if self.positions:
                    logger.info("   Current Positions:")
                    for pair, pos in self.positions.items():
                        logger.info(f"     {pair}: {pos['direction']}")

                logger.info(f"⏰ Next check in 60 seconds...")
                time.sleep(60)

            except KeyboardInterrupt:
                logger.info("\n🛑 Shutting down...")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                time.sleep(30)


def main():
    """Main execution function"""
    try:
        bot = BacktestAlignedBot()
        bot.run()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())