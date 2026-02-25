#!/usr/bin/env python3
"""
Enhanced Strategy Executor for EC2 Deployment
With improved logging and actual trade execution on Binance Testnet
"""

import json
import time
import logging
from datetime import datetime
import ccxt
import pandas as pd
import numpy as np
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

# Setup enhanced logging
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""

    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.MAGENTA,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class StatArbBot:
    def __init__(self, config_file='strategy_config.json'):
        """Initialize the bot with config"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        logger.info("=" * 60)
        logger.info("🚀 INITIALIZING STATISTICAL ARBITRAGE BOT")
        logger.info("=" * 60)

        # Initialize exchange (Testnet)
        self.exchange = ccxt.binance({
            'apiKey': self.config['api_key'],
            'secret': self.config['api_secret'],
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'sandboxMode': True
            },
            'hostname': 'testnet.binance.vision',
            'urls': {
                'logo': 'https://user-images.githubusercontent.com/1294454/29604020-d5483cdc-87ee-11e7-94c7-d1a8d9169293.jpg',
                'api': {
                    'public': 'https://testnet.binance.vision/api',
                    'private': 'https://testnet.binance.vision/api',
                    'v3': 'https://testnet.binance.vision/api/v3',
                    'v1': 'https://testnet.binance.vision/api/v1',
                },
                'www': 'https://testnet.binance.vision',
                'doc': 'https://binance-docs.github.io/apidocs/spot/en',
                'fees': 'https://www.binance.com/en/fee/schedule',
            }
        })
        self.exchange.set_sandbox_mode(True)

        # Load markets
        logger.info("Loading market data...")
        self.exchange.load_markets()

        self.positions = {}
        self.price_history = {}
        self.trades_executed = []
        self.total_pnl = 0

        # Get account balance
        self.check_balance()

    def check_balance(self):
        """Check and display account balance"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['USDT']['free'] if 'USDT' in balance else 0
            logger.info(f"💰 Account Balance: {usdt_balance:.2f} USDT")
            return usdt_balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0

    def fetch_prices(self, symbol):
        """Fetch current price for a symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            bid = ticker['bid']
            ask = ticker['ask']
            volume = ticker['quoteVolume']
            return {
                'price': price,
                'bid': bid,
                'ask': ask,
                'spread': ask - bid,
                'volume': volume
            }
        except Exception as e:
            logger.error(f"❌ Error fetching price for {symbol}: {e}")
            return None

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
        logger.info("📊 MARKET ANALYSIS")
        logger.info("-" * 60)

        for symbol in self.config['trading_pairs']:
            # Fetch comprehensive price data
            price_data = self.fetch_prices(symbol)
            if price_data is None:
                continue

            price = price_data['price']
            spread_pct = (price_data['spread'] / price) * 100

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

            # Calculate z-score and other metrics
            zscore = self.calculate_zscore(self.price_history[symbol])
            prices_array = np.array(self.price_history[symbol])
            volatility = np.std(prices_array) / np.mean(prices_array) * 100

            # Determine signal
            signal = 'HOLD'
            signal_emoji = '⏸️'

            if symbol not in self.positions:
                if zscore < -self.config['entry_threshold']:
                    signal = 'BUY'
                    signal_emoji = '🟢'
                    signals[symbol] = signal
                elif zscore > self.config['entry_threshold']:
                    signal = 'SELL'
                    signal_emoji = '🔴'
                    signals[symbol] = signal
            else:
                # Check exit conditions
                position = self.positions[symbol]
                if position['side'] == 'long' and zscore > -self.config['exit_threshold']:
                    signal = 'EXIT_LONG'
                    signal_emoji = '🏁'
                    signals[symbol] = signal
                elif position['side'] == 'short' and zscore < self.config['exit_threshold']:
                    signal = 'EXIT_SHORT'
                    signal_emoji = '🏁'
                    signals[symbol] = signal

            # Enhanced logging
            logger.info(
                f"{signal_emoji} {symbol}: ${price:.2f} | "
                f"Z-Score: {zscore:+.2f} | "
                f"Vol: {volatility:.1f}% | "
                f"Spread: {spread_pct:.3f}% | "
                f"Signal: {signal}"
            )

        return signals

    def calculate_position_size(self, symbol, price):
        """Calculate position size based on available balance"""
        try:
            balance = self.check_balance()
            max_position = min(self.config['position_size'], balance * 0.9)  # Use max 90% of balance

            # Get minimum order size for the symbol
            market = self.exchange.market(symbol)
            min_cost = market['limits']['cost']['min'] if market['limits']['cost']['min'] else 10

            position_size = max(max_position, min_cost * 1.1)  # At least 10% above minimum

            return position_size
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return self.config['position_size']

    def execute_trade(self, symbol, signal):
        """Execute actual trades on Binance Testnet"""
        try:
            price_data = self.fetch_prices(symbol)
            if not price_data:
                return

            current_price = price_data['price']

            if signal == 'BUY':
                if len(self.positions) < self.config['max_positions']:
                    # Calculate order size
                    position_size = self.calculate_position_size(symbol, current_price)
                    amount = position_size / current_price

                    logger.info(f"🔵 EXECUTING BUY ORDER: {symbol}")
                    logger.info(f"   Amount: {amount:.6f} | Value: ${position_size:.2f}")

                    # Place market buy order
                    try:
                        order = self.exchange.create_market_buy_order(symbol, amount)

                        self.positions[symbol] = {
                            'side': 'long',
                            'entry_price': current_price,
                            'amount': amount,
                            'size': position_size,
                            'entry_time': datetime.now(),
                            'order_id': order['id']
                        }

                        logger.info(f"✅ BUY ORDER FILLED: {symbol} @ ${current_price:.2f}")
                        logger.info(f"   Order ID: {order['id']}")

                        self.trades_executed.append({
                            'time': datetime.now(),
                            'symbol': symbol,
                            'side': 'BUY',
                            'price': current_price,
                            'amount': amount
                        })

                    except Exception as e:
                        logger.error(f"❌ Order failed: {e}")
                        # For testnet, simulate the position
                        self.positions[symbol] = {
                            'side': 'long',
                            'entry_price': current_price,
                            'amount': position_size / current_price,
                            'size': position_size,
                            'entry_time': datetime.now(),
                            'order_id': 'simulated'
                        }
                        logger.info(f"📝 Position simulated (testnet): LONG {symbol}")

            elif signal == 'SELL':
                if len(self.positions) < self.config['max_positions']:
                    position_size = self.calculate_position_size(symbol, current_price)
                    amount = position_size / current_price

                    logger.info(f"🔴 EXECUTING SELL ORDER: {symbol}")
                    logger.info(f"   Amount: {amount:.6f} | Value: ${position_size:.2f}")

                    try:
                        # For short selling (not available on spot, simulate it)
                        self.positions[symbol] = {
                            'side': 'short',
                            'entry_price': current_price,
                            'amount': amount,
                            'size': position_size,
                            'entry_time': datetime.now(),
                            'order_id': 'short_simulated'
                        }

                        logger.info(f"📝 SHORT position simulated: {symbol} @ ${current_price:.2f}")

                    except Exception as e:
                        logger.error(f"❌ Order failed: {e}")

            elif signal in ['EXIT_LONG', 'EXIT_SHORT'] and symbol in self.positions:
                position = self.positions[symbol]
                entry_price = position['entry_price']
                amount = position['amount']

                # Calculate PnL
                if position['side'] == 'long':
                    pnl = (current_price - entry_price) * amount
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100

                    logger.info(f"🏁 CLOSING LONG POSITION: {symbol}")

                    try:
                        # Sell to close long position
                        order = self.exchange.create_market_sell_order(symbol, amount)
                        logger.info(f"✅ SELL ORDER FILLED: {symbol} @ ${current_price:.2f}")
                    except:
                        logger.info(f"📝 Position close simulated (testnet)")

                else:  # short
                    pnl = (entry_price - current_price) * amount
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                    logger.info(f"🏁 CLOSING SHORT POSITION: {symbol}")
                    logger.info(f"📝 Position close simulated (testnet)")

                # Update total PnL
                self.total_pnl += pnl

                # Log PnL with color
                pnl_color = Fore.GREEN if pnl > 0 else Fore.RED
                logger.info(f"{pnl_color}   PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")
                logger.info(f"   Total PnL: ${self.total_pnl:.2f}")

                del self.positions[symbol]

        except Exception as e:
            logger.error(f"❌ Error executing trade for {symbol}: {e}")

    def check_stop_loss_take_profit(self):
        """Check stop loss and take profit for open positions"""
        for symbol, position in list(self.positions.items()):
            if symbol not in self.price_history or not self.price_history[symbol]:
                continue

            current_price = self.price_history[symbol][-1]
            entry_price = position['entry_price']

            if position['side'] == 'long':
                pnl = (current_price - entry_price) / entry_price
            else:
                pnl = (entry_price - current_price) / entry_price

            # Check stop loss
            if pnl <= -self.config['stop_loss']:
                logger.warning(f"⛔ STOP LOSS TRIGGERED: {symbol} @ {pnl*100:.2f}%")
                self.execute_trade(symbol, 'EXIT_LONG' if position['side'] == 'long' else 'EXIT_SHORT')

            # Check take profit
            elif pnl >= self.config['take_profit']:
                logger.info(f"💰 TAKE PROFIT TRIGGERED: {symbol} @ {pnl*100:.2f}%")
                self.execute_trade(symbol, 'EXIT_LONG' if position['side'] == 'long' else 'EXIT_SHORT')

    def display_positions(self):
        """Display current positions with details"""
        if self.positions:
            logger.info("=" * 60)
            logger.info("📊 OPEN POSITIONS")
            logger.info("=" * 60)

            for symbol, pos in self.positions.items():
                current_price = self.price_history[symbol][-1] if symbol in self.price_history else pos['entry_price']

                if pos['side'] == 'long':
                    pnl = (current_price - pos['entry_price']) * pos['amount']
                    pnl_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                else:
                    pnl = (pos['entry_price'] - current_price) * pos['amount']
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
        """Main bot loop"""
        logger.info("=" * 60)
        logger.info("🤖 STATISTICAL ARBITRAGE BOT - LIVE TRADING")
        logger.info("=" * 60)
        logger.info(f"📍 Exchange: Binance Testnet")
        logger.info(f"📈 Trading Pairs: {', '.join(self.config['trading_pairs'])}")
        logger.info(f"⏱️  Update Interval: {self.config['update_interval']}s")
        logger.info(f"📊 Lookback Period: {self.config['lookback_period']}")
        logger.info(f"🎯 Entry Z-Score: ±{self.config['entry_threshold']}")
        logger.info(f"🏁 Exit Z-Score: ±{self.config['exit_threshold']}")
        logger.info(f"🛑 Stop Loss: {self.config['stop_loss']*100:.1f}%")
        logger.info(f"💰 Take Profit: {self.config['take_profit']*100:.1f}%")
        logger.info("=" * 60)

        iteration = 0
        while True:
            try:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 ITERATION #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")

                # Check for trading signals
                signals = self.check_signals()

                # Execute trades based on signals
                for symbol, signal in signals.items():
                    self.execute_trade(symbol, signal)

                # Check stop loss and take profit
                self.check_stop_loss_take_profit()

                # Display current positions
                self.display_positions()

                # Show total PnL
                if self.total_pnl != 0:
                    pnl_color = Fore.GREEN if self.total_pnl > 0 else Fore.RED
                    logger.info(f"\n{pnl_color}💼 TOTAL P&L: ${self.total_pnl:.2f}{Style.RESET_ALL}")

                # Show next update timer
                logger.info(f"\n⏳ Next update in {self.config['update_interval']} seconds...")

                # Wait for next update
                time.sleep(self.config['update_interval'])

            except KeyboardInterrupt:
                logger.info("\n" + "=" * 60)
                logger.info("🛑 BOT STOPPED BY USER")
                logger.info("=" * 60)
                logger.info(f"Total trades executed: {len(self.trades_executed)}")
                logger.info(f"Final P&L: ${self.total_pnl:.2f}")
                break

            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                logger.info("Retrying in 10 seconds...")
                time.sleep(10)

if __name__ == "__main__":
    bot = StatArbBot()
    bot.run()