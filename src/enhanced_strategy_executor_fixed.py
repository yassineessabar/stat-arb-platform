#!/usr/bin/env python3
"""
Enhanced Strategy Executor - FIXED VERSION
Uses proven simple order placement from simple_working_executor.py
Implements v6 parameters from backtest
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
    """Simple Binance client with PROVEN order placement logic"""

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
                usdt_balance = float(account.get('totalWalletBalance', '0'))
                logger.info(f"💰 USDT Balance: {usdt_balance:.2f} USDT")
                return usdt_balance
            else:
                logger.error(f"Failed to get account: {response.text}")
                return 10000  # Default for testnet
        except Exception as e:
            logger.error(f"Error getting account: {e}")
            return 10000  # Default for testnet

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
            'XRPUSDT': 0,   # XRP futures use 0 decimal places (corrected)
            'ADAUSDT': 0,   # ADA futures use 0 decimal places
            'AVAXUSDT': 2,  # AVAX futures use 2 decimal places (corrected)
            'DOGEUSDT': 0,  # DOGE futures use 0 decimal places
            'DOTUSDT': 2,   # DOT futures use 2 decimal places (corrected)
            'MATICUSDT': 0, # MATIC futures use 0 decimal places
        }
        return symbol_precisions.get(symbol, 3)  # Default to 3 if unknown


class EnhancedStatArbBot:
    """Enhanced bot with v6 parameters using simple order placement"""

    def __init__(self, config_file='strategy_config.json'):
        """Initialize the bot with config"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        logger.info("=" * 60)
        logger.info("🚀 ENHANCED STATISTICAL ARBITRAGE BOT (V6 ALIGNED)")
        logger.info("=" * 60)

        # Initialize client using proven pattern
        self.client = SimpleBinanceClient(
            api_key=self.config['api_key'],
            api_secret=self.config['api_secret'],
            testnet=True
        )

        self.price_history = {}
        self.positions = {}

        # Check balance
        self.balance = self.client.get_account_balance()

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
        """Check trading signals for all pairs"""
        signals = {}

        logger.info("-" * 60)
        logger.info("📊 MARKET ANALYSIS (V6 PARAMETERS)")
        logger.info("-" * 60)

        for symbol in self.config['trading_pairs']:
            # Fetch price data
            price_data = self.fetch_prices(symbol)
            if price_data is None:
                continue

            price = price_data['price']

            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(price)

            # Keep only lookback period
            if len(self.price_history[symbol]) > self.config['lookback_period']:
                self.price_history[symbol] = self.price_history[symbol][-self.config['lookback_period']:]

            # Progress indicator
            progress = len(self.price_history[symbol])
            lookback = self.config['lookback_period']

            if progress < lookback:
                logger.info(f"📈 {symbol}: ${price:.2f} | Collecting data... [{progress}/{lookback}]")
                continue

            # Calculate z-score
            zscore = self.calculate_zscore(self.price_history[symbol])

            # Use v6 parameters if available
            v6_params = self.config.get('v6_parameters', {})
            entry_threshold = v6_params.get('z_entry', self.config['entry_threshold'])
            exit_long = v6_params.get('z_exit_long', self.config['exit_threshold'])
            exit_short = v6_params.get('z_exit_short', self.config['exit_threshold'])

            # Determine signal
            signal = 'HOLD'
            signal_emoji = '⏸️'

            if symbol not in self.positions:
                if zscore < -entry_threshold:
                    signal = 'BUY'
                    signal_emoji = '🟢'
                    signals[symbol] = signal
                elif zscore > entry_threshold:
                    signal = 'SELL'
                    signal_emoji = '🔴'
                    signals[symbol] = signal
            else:
                # Check exit conditions with v6 parameters
                position = self.positions[symbol]
                if position['side'] == 'long' and zscore > -exit_long:
                    signal = 'EXIT_LONG'
                    signal_emoji = '🏁'
                    signals[symbol] = signal
                elif position['side'] == 'short' and zscore < exit_short:
                    signal = 'EXIT_SHORT'
                    signal_emoji = '🏁'
                    signals[symbol] = signal

            logger.info(f"{signal_emoji} {symbol}: ${price:.2f} | Z-Score: {zscore:+.2f} | Signal: {signal}")

        return signals

    def execute_trade(self, symbol, signal):
        """Execute trades using proven simple order placement"""
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
                order = self.client.place_order(symbol_name, 'BUY', quantity)

                if order:
                    self.positions[symbol] = {
                        'side': 'long',
                        'quantity': quantity,
                        'entry_price': price,
                        'order_id': order['orderId'],
                        'entry_time': datetime.now()
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
                order = self.client.place_order(symbol_name, 'SELL', quantity)

                if order:
                    self.positions[symbol] = {
                        'side': 'short',
                        'quantity': quantity,
                        'entry_price': price,
                        'order_id': order['orderId'],
                        'entry_time': datetime.now()
                    }
                    logger.info(f"✅ SHORT POSITION CREATED: {symbol}")

            elif signal in ['EXIT_LONG', 'EXIT_SHORT']:
                if symbol in self.positions:
                    position = self.positions[symbol]
                    logger.info(f"🏁 CLOSING POSITION: {symbol}")

                    symbol_name = symbol.replace('/', '')

                    if position['side'] == 'long':
                        # Close long position by selling
                        order = self.client.place_order(symbol_name, 'SELL', position['quantity'])
                    else:
                        # Close short position by buying
                        order = self.client.place_order(symbol_name, 'BUY', position['quantity'])

                    if order:
                        del self.positions[symbol]
                        logger.info(f"✅ POSITION CLOSED: {symbol}")

        except Exception as e:
            logger.error(f"❌ Error executing trade for {symbol}: {e}")

    def display_positions(self):
        """Display current positions"""
        if self.positions:
            logger.info("-" * 60)
            logger.info("📊 OPEN POSITIONS")
            logger.info("-" * 60)

            for symbol, pos in self.positions.items():
                current_price = self.price_history[symbol][-1] if symbol in self.price_history else pos['entry_price']

                if pos['side'] == 'long':
                    pnl = (current_price - pos['entry_price']) * pos['quantity']
                    pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                else:
                    pnl = (pos['entry_price'] - current_price) * pos['quantity']
                    pnl_pct = ((pos['entry_price'] - current_price) / pos['entry_price']) * 100

                pnl_color = Fore.GREEN if pnl > 0 else Fore.RED
                side_emoji = '🟢' if pos['side'] == 'long' else '🔴'

                logger.info(
                    f"{side_emoji} {symbol}: {pos['side'].upper()} | "
                    f"Entry: ${pos['entry_price']:.2f} | "
                    f"Current: ${current_price:.2f} | "
                    f"{pnl_color}PnL: ${pnl:.2f} ({pnl_pct:+.2f}%){Style.RESET_ALL}"
                )

    def run(self):
        """Main bot loop - SIMPLE AND SYNCHRONOUS"""
        logger.info(f"📍 Exchange: Binance Testnet")
        logger.info(f"📈 Trading Pairs: {', '.join(self.config['trading_pairs'])}")
        logger.info(f"⏱️  Update Interval: {self.config['update_interval']}s")
        logger.info(f"📊 Lookback Period: {self.config['lookback_period']}")

        # Display v6 parameters if available
        if 'v6_parameters' in self.config:
            v6 = self.config['v6_parameters']
            logger.info(f"🎯 V6 Entry Z-Score: ±{v6['z_entry']}")
            logger.info(f"🏁 V6 Exit Z-Score: {v6['z_exit_long']}/{v6['z_exit_short']}")
            logger.info(f"⚠️  V6 Stop Z-Score: ±{v6['z_stop']}")
        else:
            logger.info(f"🎯 Entry Z-Score: ±{self.config['entry_threshold']}")
            logger.info(f"🏁 Exit Z-Score: ±{self.config['exit_threshold']}")

        logger.info(f"🛑 Stop Loss: {self.config['stop_loss']*100:.1f}%")
        logger.info(f"💰 Take Profit: {self.config['take_profit']*100:.1f}%")
        logger.info("=" * 60)
        logger.info("📌 Check your orders at: https://testnet.binance.vision/")
        logger.info("=" * 60)

        iteration = 0
        while True:
            try:
                iteration += 1
                logger.info(f"\n🔄 ITERATION #{iteration} - {datetime.now().strftime('%H:%M:%S')}")

                # Check for trading signals
                signals = self.check_signals()

                # Execute trades based on signals
                for symbol, signal in signals.items():
                    self.execute_trade(symbol, signal)

                # Display current positions
                self.display_positions()

                # Wait for next update
                time.sleep(self.config['update_interval'])

            except KeyboardInterrupt:
                logger.info("\n🛑 BOT STOPPED BY USER")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                time.sleep(10)


if __name__ == "__main__":
    bot = EnhancedStatArbBot()
    bot.run()