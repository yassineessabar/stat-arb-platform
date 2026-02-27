#!/usr/bin/env python3
"""
Simple Working Strategy Executor
Based on the version that successfully placed orders 3 days ago
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
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleBinanceClient:
    """Simple Binance client that actually places spot orders like the working version"""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret

        # Use FUTURES testnet URL to match your working API keys
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
            'XRPUSDT': 0,   # XRP futures use 0 decimal places (corrected)
            'ADAUSDT': 0,   # ADA futures use 0 decimal places
            'AVAXUSDT': 2,  # AVAX futures use 2 decimal places (corrected)
            'DOGEUSDT': 0,  # DOGE futures use 0 decimal places
            'DOTUSDT': 2,   # DOT futures use 2 decimal places (corrected)
            'MATICUSDT': 0, # MATIC futures use 0 decimal places
        }
        return symbol_precisions.get(symbol, 3)  # Default to 3 if unknown

class SimpleStatArbBot:
    def __init__(self, config_file='strategy_config.json'):
        """Initialize the simple bot using working patterns"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        logger.info("=" * 60)
        logger.info("🚀 SIMPLE STATISTICAL ARBITRAGE BOT")
        logger.info("=" * 60)

        # Initialize client using working pattern
        self.client = SimpleBinanceClient(
            api_key=self.config['api_key'],
            api_secret=self.config['api_secret'],
            testnet=True
        )

        self.price_history = {}
        self.positions = {}

        # Check balance
        self.client.get_account_balance()

    def fetch_prices(self, symbol):
        """Fetch current price for a symbol"""
        price = self.client.get_price(symbol.replace('/', ''))
        return {'price': price} if price > 0 else None

    def calculate_zscore(self, prices):
        """Calculate z-score for price series"""
        if len(prices) < self.config['lookback_period']:
            return 0

        mean = np.mean(prices)
        std = np.std(prices)

        if std == 0:
            return 0

        return (prices[-1] - mean) / std

    def check_signals(self):
        """Check trading signals using pair spread analysis (aligned with backtest)"""
        signals = {}

        logger.info("-" * 60)
        logger.info("📊 MARKET ANALYSIS (PAIR-BASED)")
        logger.info("-" * 60)

        # Fetch all prices first
        all_prices = {}
        for symbol in self.config['trading_pairs']:
            price_data = self.fetch_prices(symbol)
            if price_data is not None:
                all_prices[symbol] = price_data['price']

        # Update price history for all symbols
        for symbol, price in all_prices.items():
            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(price)

            # Keep only lookback period
            if len(self.price_history[symbol]) > self.config['lookback_period']:
                self.price_history[symbol] = self.price_history[symbol][-self.config['lookback_period']:]

        # Check if we have enough data for all symbols
        min_data_points = min([len(self.price_history.get(s, [])) for s in self.config['trading_pairs']] + [0])

        if min_data_points < self.config['lookback_period']:
            logger.info(f"📈 Collecting data... [{min_data_points}/{self.config['lookback_period']}]")
            return signals

        # Generate pair-based signals (simplified pair trading approach)
        pairs = self.config['trading_pairs']

        # Create simple pairs from the trading pairs list
        for i in range(len(pairs)):
            for j in range(i + 1, len(pairs)):
                asset_a = pairs[i].replace('/', '')
                asset_b = pairs[j].replace('/', '')

                if asset_a in self.price_history and asset_b in self.price_history:
                    # Calculate spread using price ratio (simplified vs hedge ratio)
                    prices_a = np.array(self.price_history[asset_a])
                    prices_b = np.array(self.price_history[asset_b])

                    # Use price ratio as a simple spread proxy
                    spreads = prices_a / prices_b

                    # Calculate z-score on the spread (not individual prices)
                    spread_zscore = self.calculate_zscore(spreads.tolist())

                    pair_name = f"{asset_a}-{asset_b}"

                    # Pair trading signals (more sophisticated than individual asset signals)
                    signal = 'HOLD'
                    signal_emoji = '⏸️'

                    # Check if we already have a position for this pair
                    if pair_name not in self.positions:
                        if spread_zscore > self.config['entry_threshold']:
                            # Spread is high: short the pair (short A, long B)
                            signal = 'SHORT_PAIR'
                            signal_emoji = '🔴'
                            signals[asset_a] = 'SELL'
                            signals[asset_b] = 'BUY'
                            logger.info(f"{signal_emoji} PAIR {pair_name}: Spread Z-Score: {spread_zscore:+.2f} | SHORT PAIR")
                        elif spread_zscore < -self.config['entry_threshold']:
                            # Spread is low: long the pair (long A, short B)
                            signal = 'LONG_PAIR'
                            signal_emoji = '🟢'
                            signals[asset_a] = 'BUY'
                            signals[asset_b] = 'SELL'
                            logger.info(f"{signal_emoji} PAIR {pair_name}: Spread Z-Score: {spread_zscore:+.2f} | LONG PAIR")
                        else:
                            logger.info(f"⏸️ PAIR {pair_name}: Spread Z-Score: {spread_zscore:+.2f} | HOLD")
                    else:
                        logger.info(f"📍 PAIR {pair_name}: Spread Z-Score: {spread_zscore:+.2f} | POSITION OPEN")

        # Also show individual asset analysis for reference
        logger.info("📊 Individual Asset Analysis (Reference):")
        for symbol in self.config['trading_pairs']:
            symbol_clean = symbol.replace('/', '')
            if symbol_clean in all_prices and symbol_clean in self.price_history:
                price = all_prices[symbol_clean]
                zscore = self.calculate_zscore(self.price_history[symbol_clean])
                logger.info(f"   {symbol}: ${price:.2f} | Individual Z-Score: {zscore:+.2f}")

        return signals

    def execute_trade(self, symbol, signal):
        """Execute REAL trades using working patterns (now pair-aware)"""
        try:
            if signal == 'BUY':
                logger.info(f"🔵 EXECUTING BUY: {symbol}")

                # Calculate minimum quantity for futures ($100 minimum)
                price = self.client.get_price(symbol.replace('/', ''))
                symbol_name = symbol.replace('/', '')

                # Ensure minimum $100 notional value
                min_notional = 100.0
                min_quantity = min_notional / price if price > 0 else 0.001

                # Get symbol-specific precision and apply it
                precision = self.client.get_symbol_precision(symbol_name)
                quantity = round(min_quantity, precision)

                # Double check that notional meets minimum after rounding
                notional_value = quantity * price
                if notional_value < min_notional and price > 0:
                    # Add one unit in the smallest precision to ensure we meet minimum
                    quantity += 10 ** (-precision)
                    quantity = round(quantity, precision)

                # Place REAL order
                order = self.client.place_order(symbol.replace('/', ''), 'BUY', quantity)

                if order:
                    # Store position with pair awareness
                    self.positions[symbol] = {
                        'side': 'long',
                        'quantity': quantity,
                        'order_id': order['orderId'],
                        'entry_time': datetime.now(),
                        'type': 'pair_leg'  # Mark as part of pair trade
                    }
                    logger.info(f"✅ LONG POSITION CREATED: {symbol}")

            elif signal == 'SELL':
                logger.info(f"🔴 EXECUTING SELL: {symbol}")

                # Calculate minimum quantity for futures ($100 minimum)
                price = self.client.get_price(symbol.replace('/', ''))
                symbol_name = symbol.replace('/', '')

                # Ensure minimum $100 notional value
                min_notional = 100.0
                min_quantity = min_notional / price if price > 0 else 0.001

                # Get symbol-specific precision and apply it
                precision = self.client.get_symbol_precision(symbol_name)
                quantity = round(min_quantity, precision)

                # Double check that notional meets minimum after rounding
                notional_value = quantity * price
                if notional_value < min_notional and price > 0:
                    # Add one unit in the smallest precision to ensure we meet minimum
                    quantity += 10 ** (-precision)
                    quantity = round(quantity, precision)

                # Place REAL order
                order = self.client.place_order(symbol.replace('/', ''), 'SELL', quantity)

                if order:
                    # Store position with pair awareness
                    self.positions[symbol] = {
                        'side': 'short',
                        'quantity': quantity,
                        'order_id': order['orderId'],
                        'entry_time': datetime.now(),
                        'type': 'pair_leg'  # Mark as part of pair trade
                    }
                    logger.info(f"✅ SHORT POSITION CREATED: {symbol}")

        except Exception as e:
            logger.error(f"❌ Error executing trade for {symbol}: {e}")

    def run(self):
        """Main bot loop using working patterns (now backtest-aligned)"""
        logger.info("=" * 60)
        logger.info("📈 BACKTEST-ALIGNED STATISTICAL ARBITRAGE BOT")
        logger.info("📌 Check orders at: https://testnet.binancefuture.com/")
        logger.info("📊 Using pair-based spread analysis (like backtest)")
        logger.info("=" * 60)

        iteration = 0
        while True:
            try:
                iteration += 1
                logger.info(f"\n🔄 ITERATION #{iteration} - {datetime.now().strftime('%H:%M:%S')}")

                # Check for trading signals (now pair-based)
                signals = self.check_signals()

                # Execute trades based on signals
                for symbol, signal in signals.items():
                    self.execute_trade(symbol, signal)

                # Status summary
                logger.info("-" * 60)
                logger.info("📈 PORTFOLIO STATUS")
                logger.info("-" * 60)
                open_positions = sum(1 for p in self.positions.values() if p.get('type') == 'pair_leg')
                logger.info(f"   Open Positions: {open_positions}")
                logger.info(f"   Signals Generated: {len(signals)}")

                if self.positions:
                    logger.info("   Current Positions:")
                    for symbol, pos in self.positions.items():
                        side = pos['side'].upper()
                        qty = pos['quantity']
                        logger.info(f"     {symbol}: {side} {qty}")

                logger.info(f"⏰ Next check in {self.config['update_interval']} seconds...")

                # Wait for next update
                time.sleep(self.config['update_interval'])

            except KeyboardInterrupt:
                logger.info("\n🛑 BOT STOPPED BY USER")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                time.sleep(10)

if __name__ == "__main__":
    bot = SimpleStatArbBot()
    bot.run()