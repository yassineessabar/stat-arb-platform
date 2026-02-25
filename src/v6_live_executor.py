#!/usr/bin/env python3
"""
V6 Strategy Live Executor - Aligned with Backtest
Uses proven order placement logic from simple_working_executor.py
Implements v6 pair trading strategy from backtest
"""

import json
import time
import logging
from datetime import datetime
import requests
import hmac
import hashlib
from urllib.parse import urlencode
import numpy as np
import pandas as pd
from colorama import init, Fore, Style
from typing import Dict, List, Optional, Tuple
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Initialize colorama for colored output
init(autoreset=True)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleBinanceClient:
    """Binance client with proven order placement logic from simple_working_executor"""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret

        # Use FUTURES testnet URL (proven to work)
        if testnet:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"

        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key
        })

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

    def get_account_balance(self):
        """Get account balance"""
        try:
            params = {
                'timestamp': int(time.time() * 1000)
            }
            params = self._sign_request(params)

            response = self.session.get(f"{self.base_url}/fapi/v2/account", params=params)
            if response.status_code == 200:
                account = response.json()
                logger.info(f"💰 USDT Balance: {account.get('totalWalletBalance', '0')} USDT")
                return account
            else:
                logger.error(f"Failed to get account: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return None

    def place_order(self, symbol: str, side: str, quantity: float) -> dict:
        """Place a REAL futures market order with proven logic"""
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
            'ADAUSDT': 0,   # ADA futures use 0 decimal places
        }
        return symbol_precisions.get(symbol, 3)  # Default to 3 if unknown


class V6StatArbBot:
    """V6 Statistical Arbitrage Bot - Pair Trading Implementation"""

    def __init__(self, config_file='strategy_config.json'):
        """Initialize the v6 bot with config"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        logger.info("=" * 60)
        logger.info("🚀 V6 STATISTICAL ARBITRAGE BOT (PAIR TRADING)")
        logger.info("=" * 60)

        # Initialize client using proven pattern
        self.client = SimpleBinanceClient(
            api_key=self.config['api_key'],
            api_secret=self.config['api_secret'],
            testnet=True
        )

        # V6 Strategy Parameters (from backtest)
        self.v6_params = {
            'z_entry': 1.0,          # Lower entry threshold from v6
            'z_exit_long': 0.20,     # Exit closer to mean
            'z_exit_short': 0.10,
            'z_stop': 3.5,           # Tighter stop
            'lookback_period': 20,   # For spread calculation
            'min_correlation': 0.40, # Minimum correlation for pairs
        }

        # Trading pairs for pair trading (not individual assets)
        self.trading_pairs = self._generate_pairs()
        self.spread_history = {}
        self.positions = {}
        self.pair_hedge_ratios = {}

        # Check balance
        self.client.get_account_balance()

    def _generate_pairs(self) -> List[Tuple[str, str]]:
        """Generate trading pairs from configured assets"""
        assets = [symbol.replace('/USDT', '') for symbol in self.config['trading_pairs']]
        pairs = []

        # Create pairs from assets
        for i in range(len(assets)):
            for j in range(i + 1, len(assets)):
                pairs.append((f"{assets[i]}/USDT", f"{assets[j]}/USDT"))

        logger.info(f"📊 Generated {len(pairs)} trading pairs for analysis")
        return pairs

    def fetch_prices(self, symbol: str) -> float:
        """Fetch current price for a symbol"""
        price = self.client.get_price(symbol.replace('/', ''))
        return price if price > 0 else None

    def calculate_spread(self, price1: float, price2: float, hedge_ratio: float) -> float:
        """Calculate spread between two assets with hedge ratio"""
        return np.log(price1) - hedge_ratio * np.log(price2)

    def calculate_hedge_ratio(self, prices1: List[float], prices2: List[float]) -> float:
        """Calculate optimal hedge ratio using OLS regression"""
        if len(prices1) < 2 or len(prices2) < 2:
            return 1.0

        # Convert to log prices
        log_p1 = np.log(prices1)
        log_p2 = np.log(prices2)

        # Simple OLS: hedge_ratio = cov(p1, p2) / var(p2)
        covariance = np.cov(log_p1, log_p2)[0, 1]
        variance = np.var(log_p2)

        if variance > 0:
            return covariance / variance
        return 1.0

    def calculate_zscore(self, spreads: List[float]) -> float:
        """Calculate z-score for spread series"""
        if len(spreads) < self.v6_params['lookback_period']:
            return 0

        mean = np.mean(spreads)
        std = np.std(spreads)

        if std == 0:
            return 0

        return (spreads[-1] - mean) / std

    def check_pair_signals(self):
        """Check trading signals for all pairs"""
        signals = {}

        logger.info("-" * 60)
        logger.info("📊 PAIR ANALYSIS (V6 Strategy)")
        logger.info("-" * 60)

        for pair in self.trading_pairs:
            asset1, asset2 = pair

            # Fetch prices
            price1 = self.fetch_prices(asset1)
            price2 = self.fetch_prices(asset2)

            if price1 is None or price2 is None:
                continue

            # Initialize history if needed
            pair_key = f"{asset1}_{asset2}"
            if pair_key not in self.spread_history:
                self.spread_history[pair_key] = {
                    'prices1': [],
                    'prices2': [],
                    'spreads': []
                }

            # Update price history
            self.spread_history[pair_key]['prices1'].append(price1)
            self.spread_history[pair_key]['prices2'].append(price2)

            # Keep only lookback period
            max_history = self.v6_params['lookback_period'] * 2
            if len(self.spread_history[pair_key]['prices1']) > max_history:
                self.spread_history[pair_key]['prices1'] = self.spread_history[pair_key]['prices1'][-max_history:]
                self.spread_history[pair_key]['prices2'] = self.spread_history[pair_key]['prices2'][-max_history:]
                self.spread_history[pair_key]['spreads'] = self.spread_history[pair_key]['spreads'][-max_history:]

            # Need minimum data
            if len(self.spread_history[pair_key]['prices1']) < self.v6_params['lookback_period']:
                progress = len(self.spread_history[pair_key]['prices1'])
                logger.info(f"📈 {asset1}-{asset2}: Collecting data... [{progress}/{self.v6_params['lookback_period']}]")
                continue

            # Calculate hedge ratio
            hedge_ratio = self.calculate_hedge_ratio(
                self.spread_history[pair_key]['prices1'][-self.v6_params['lookback_period']:],
                self.spread_history[pair_key]['prices2'][-self.v6_params['lookback_period']:]
            )
            self.pair_hedge_ratios[pair_key] = hedge_ratio

            # Calculate spread
            spread = self.calculate_spread(price1, price2, hedge_ratio)
            self.spread_history[pair_key]['spreads'].append(spread)

            # Calculate z-score
            zscore = self.calculate_zscore(self.spread_history[pair_key]['spreads'])

            # Check correlation
            correlation = np.corrcoef(
                self.spread_history[pair_key]['prices1'][-self.v6_params['lookback_period']:],
                self.spread_history[pair_key]['prices2'][-self.v6_params['lookback_period']:]
            )[0, 1]

            # Determine signal
            signal = 'HOLD'
            signal_emoji = '⏸️'

            # Only trade if correlation is strong enough
            if abs(correlation) >= self.v6_params['min_correlation']:
                if pair_key not in self.positions:
                    if zscore < -self.v6_params['z_entry']:
                        signal = 'BUY_SPREAD'  # Buy asset1, sell asset2
                        signal_emoji = '🟢'
                        signals[pair_key] = (signal, asset1, asset2, hedge_ratio)
                    elif zscore > self.v6_params['z_entry']:
                        signal = 'SELL_SPREAD'  # Sell asset1, buy asset2
                        signal_emoji = '🔴'
                        signals[pair_key] = (signal, asset1, asset2, hedge_ratio)
                else:
                    # Check exit conditions
                    position = self.positions[pair_key]
                    if position['type'] == 'long_spread' and zscore > -self.v6_params['z_exit_long']:
                        signal = 'EXIT_LONG_SPREAD'
                        signal_emoji = '🏁'
                        signals[pair_key] = (signal, asset1, asset2, hedge_ratio)
                    elif position['type'] == 'short_spread' and zscore < self.v6_params['z_exit_short']:
                        signal = 'EXIT_SHORT_SPREAD'
                        signal_emoji = '🏁'
                        signals[pair_key] = (signal, asset1, asset2, hedge_ratio)

            logger.info(
                f"{signal_emoji} {asset1}-{asset2}: "
                f"Spread Z-Score: {zscore:+.2f} | "
                f"Corr: {correlation:.2f} | "
                f"Hedge: {hedge_ratio:.3f} | "
                f"Signal: {signal}"
            )

        return signals

    def execute_pair_trade(self, pair_key: str, signal: Tuple):
        """Execute pair trades using proven order placement"""
        try:
            signal_type, asset1, asset2, hedge_ratio = signal

            # Calculate position sizes
            price1 = self.client.get_price(asset1.replace('/', ''))
            price2 = self.client.get_price(asset2.replace('/', ''))

            if price1 <= 0 or price2 <= 0:
                return

            # Ensure minimum $100 notional per leg
            min_notional = 100.0

            # Asset 1 quantity
            symbol1 = asset1.replace('/', '')
            precision1 = self.client.get_symbol_precision(symbol1)
            quantity1 = min_notional / price1
            quantity1 = round(quantity1, precision1)

            # Check and adjust if needed
            if quantity1 * price1 < min_notional:
                quantity1 += 10 ** (-precision1)
                quantity1 = round(quantity1, precision1)

            # Asset 2 quantity (scaled by hedge ratio)
            symbol2 = asset2.replace('/', '')
            precision2 = self.client.get_symbol_precision(symbol2)
            quantity2 = (min_notional * hedge_ratio) / price2
            quantity2 = round(quantity2, precision2)

            # Check and adjust if needed
            if quantity2 * price2 < min_notional:
                quantity2 += 10 ** (-precision2)
                quantity2 = round(quantity2, precision2)

            if signal_type == 'BUY_SPREAD':
                logger.info(f"🔵 EXECUTING BUY SPREAD: {asset1} (BUY) - {asset2} (SELL)")

                # Buy asset1
                order1 = self.client.place_order(symbol1, 'BUY', quantity1)

                # Sell asset2
                order2 = self.client.place_order(symbol2, 'SELL', quantity2)

                if order1 and order2:
                    self.positions[pair_key] = {
                        'type': 'long_spread',
                        'asset1': asset1,
                        'asset2': asset2,
                        'quantity1': quantity1,
                        'quantity2': quantity2,
                        'hedge_ratio': hedge_ratio,
                        'entry_time': datetime.now()
                    }
                    logger.info(f"✅ LONG SPREAD POSITION CREATED: {pair_key}")

            elif signal_type == 'SELL_SPREAD':
                logger.info(f"🔴 EXECUTING SELL SPREAD: {asset1} (SELL) - {asset2} (BUY)")

                # Sell asset1
                order1 = self.client.place_order(symbol1, 'SELL', quantity1)

                # Buy asset2
                order2 = self.client.place_order(symbol2, 'BUY', quantity2)

                if order1 and order2:
                    self.positions[pair_key] = {
                        'type': 'short_spread',
                        'asset1': asset1,
                        'asset2': asset2,
                        'quantity1': quantity1,
                        'quantity2': quantity2,
                        'hedge_ratio': hedge_ratio,
                        'entry_time': datetime.now()
                    }
                    logger.info(f"✅ SHORT SPREAD POSITION CREATED: {pair_key}")

            elif signal_type in ['EXIT_LONG_SPREAD', 'EXIT_SHORT_SPREAD']:
                if pair_key in self.positions:
                    pos = self.positions[pair_key]
                    logger.info(f"🏁 CLOSING SPREAD POSITION: {pair_key}")

                    if pos['type'] == 'long_spread':
                        # Close long spread: sell asset1, buy asset2
                        order1 = self.client.place_order(symbol1, 'SELL', pos['quantity1'])
                        order2 = self.client.place_order(symbol2, 'BUY', pos['quantity2'])
                    else:
                        # Close short spread: buy asset1, sell asset2
                        order1 = self.client.place_order(symbol1, 'BUY', pos['quantity1'])
                        order2 = self.client.place_order(symbol2, 'SELL', pos['quantity2'])

                    if order1 and order2:
                        del self.positions[pair_key]
                        logger.info(f"✅ SPREAD POSITION CLOSED: {pair_key}")

        except Exception as e:
            logger.error(f"❌ Error executing pair trade for {pair_key}: {e}")

    def run(self):
        """Main bot loop using v6 strategy"""
        logger.info("=" * 60)
        logger.info("📌 V6 Strategy Parameters:")
        logger.info(f"   Entry Z-Score: ±{self.v6_params['z_entry']}")
        logger.info(f"   Exit Z-Score: {self.v6_params['z_exit_long']}/{self.v6_params['z_exit_short']}")
        logger.info(f"   Stop Z-Score: ±{self.v6_params['z_stop']}")
        logger.info(f"   Min Correlation: {self.v6_params['min_correlation']}")
        logger.info("=" * 60)
        logger.info("📌 Check your orders at: https://testnet.binance.vision/")
        logger.info("=" * 60)

        iteration = 0
        while True:
            try:
                iteration += 1
                logger.info(f"\n🔄 ITERATION #{iteration} - {datetime.now().strftime('%H:%M:%S')}")

                # Check for pair trading signals
                signals = self.check_pair_signals()

                # Execute trades based on signals
                for pair_key, signal in signals.items():
                    self.execute_pair_trade(pair_key, signal)

                # Display positions
                if self.positions:
                    logger.info("-" * 60)
                    logger.info("📊 OPEN POSITIONS")
                    for pair_key, pos in self.positions.items():
                        logger.info(f"  {pair_key}: {pos['type']} | Hedge: {pos['hedge_ratio']:.3f}")

                # Wait for next update
                time.sleep(self.config['update_interval'])

            except KeyboardInterrupt:
                logger.info("\n🛑 BOT STOPPED BY USER")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                time.sleep(10)


if __name__ == "__main__":
    bot = V6StatArbBot()
    bot.run()