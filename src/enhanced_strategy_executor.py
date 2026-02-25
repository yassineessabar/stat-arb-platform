#!/usr/bin/env python3
"""
Enhanced Strategy Executor for EC2 Deployment
With REAL trade execution on Binance Testnet
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

        # Initialize Binance Testnet with proper configuration
        self.exchange = ccxt.binance({
            'apiKey': self.config['api_key'],
            'secret': self.config['api_secret'],
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
                'recvWindow': 60000,
                'test': True,  # Enable test mode
            }
        })

        # Manually set testnet URLs - DO NOT use set_sandbox_mode as it causes issues
        self.exchange.urls['api'] = {
            'public': 'https://testnet.binance.vision/api/v3',
            'private': 'https://testnet.binance.vision/api/v3',
            'web': 'https://testnet.binance.vision',
        }

        # Set base URL
        self.exchange.urls['base'] = 'https://testnet.binance.vision'

        # Important: Set hostname for signature generation
        self.exchange.hostname = 'testnet.binance.vision'

        # Load markets
        logger.info("Loading market data...")
        try:
            self.exchange.load_markets()
            logger.info(f"✅ Connected to Binance Testnet")
        except Exception as e:
            logger.error(f"Failed to load markets: {e}")

        self.positions = {}
        self.price_history = {}
        self.trades_executed = []
        self.total_pnl = 0
        self.order_ids = []

        # Get account balance
        self.check_balance()

    def check_balance(self):
        """Check and display account balance"""
        try:
            balance = self.exchange.fetch_balance()

            # Check USDT balance
            usdt_balance = balance['USDT']['free'] if 'USDT' in balance else 0
            btc_balance = balance['BTC']['free'] if 'BTC' in balance else 0
            eth_balance = balance['ETH']['free'] if 'ETH' in balance else 0

            logger.info(f"💰 Account Balances:")
            logger.info(f"   USDT: {usdt_balance:.2f}")
            logger.info(f"   BTC: {btc_balance:.8f}")
            logger.info(f"   ETH: {eth_balance:.8f}")

            return usdt_balance
        except Exception as e:
            logger.warning(f"Could not fetch balance: {e}")
            # Return default balance for testnet
            return 10000  # Assume 10000 USDT for testnet

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
                'spread': ask - bid if ask and bid else 0,
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
            spread_pct = (price_data['spread'] / price * 100) if price > 0 else 0

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
            volatility = np.std(prices_array) / np.mean(prices_array) * 100 if np.mean(prices_array) > 0 else 0

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

            # Use a small portion of balance for testing
            max_position_value = min(self.config['position_size'], balance * 0.1)

            # Get market info for minimum order size
            market = self.exchange.market(symbol)
            min_amount = market['limits']['amount']['min']
            min_cost = market['limits']['cost']['min'] if 'cost' in market['limits'] else 10

            # Calculate amount
            amount = max_position_value / price

            # Round to proper precision
            amount_precision = market['precision']['amount']
            amount = self.exchange.amount_to_precision(symbol, amount)

            # Ensure we meet minimum requirements
            if float(amount) < float(min_amount) if min_amount else False:
                amount = min_amount

            min_cost_value = float(min_cost) if min_cost else 10.0
            if float(amount) * price < min_cost_value:
                amount = min_cost_value / price
                amount = self.exchange.amount_to_precision(symbol, amount)

            return float(amount)

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            # Return a small default amount for testing
            return 0.001  # Small amount for testing

    def execute_trade(self, symbol, signal):
        """Execute REAL trades on Binance Testnet"""
        try:
            price_data = self.fetch_prices(symbol)
            if not price_data:
                return

            current_price = price_data['price']

            if signal == 'BUY':
                if len(self.positions) < self.config['max_positions']:
                    # Calculate order size
                    amount = self.calculate_position_size(symbol, current_price)

                    logger.info(f"🔵 PLACING BUY ORDER: {symbol}")
                    logger.info(f"   Amount: {amount:.8f} | Price: ${current_price:.2f}")

                    try:
                        # Place REAL market buy order on testnet
                        order = self.exchange.create_market_buy_order(
                            symbol=symbol,
                            amount=amount
                        )

                        logger.info(f"✅ BUY ORDER EXECUTED: {symbol}")
                        logger.info(f"   Order ID: {order['id']}")
                        logger.info(f"   Status: {order['status']}")
                        logger.info(f"   Filled: {order.get('filled', amount)}")

                        self.positions[symbol] = {
                            'side': 'long',
                            'entry_price': current_price,
                            'amount': amount,
                            'entry_time': datetime.now(),
                            'order_id': order['id']
                        }

                        self.order_ids.append(order['id'])

                    except Exception as e:
                        logger.error(f"❌ Order failed: {e}")
                        logger.info(f"Creating limit buy order instead...")

                        try:
                            # Try limit order at market price
                            order = self.exchange.create_limit_buy_order(
                                symbol=symbol,
                                amount=amount,
                                price=current_price * 1.001  # Slightly above market for quick fill
                            )

                            logger.info(f"✅ LIMIT BUY ORDER PLACED: {symbol}")
                            logger.info(f"   Order ID: {order['id']}")

                            self.positions[symbol] = {
                                'side': 'long',
                                'entry_price': current_price,
                                'amount': amount,
                                'entry_time': datetime.now(),
                                'order_id': order['id']
                            }

                        except Exception as e2:
                            logger.error(f"Limit order also failed: {e2}")

            elif signal == 'SELL':
                if len(self.positions) < self.config['max_positions']:
                    amount = self.calculate_position_size(symbol, current_price)

                    logger.info(f"🔴 PLACING SELL ORDER: {symbol}")
                    logger.info(f"   Amount: {amount:.8f} | Price: ${current_price:.2f}")

                    try:
                        # For spot trading, we need to have the asset first
                        # So we'll simulate a short by selling what we don't have
                        # In real trading, this would require margin trading

                        # First, try to sell if we have the base currency
                        base_currency = symbol.split('/')[0]
                        balance = self.exchange.fetch_balance()

                        if base_currency in balance and balance[base_currency]['free'] >= amount:
                            order = self.exchange.create_market_sell_order(
                                symbol=symbol,
                                amount=amount
                            )

                            logger.info(f"✅ SELL ORDER EXECUTED: {symbol}")
                            logger.info(f"   Order ID: {order['id']}")

                        else:
                            # Place limit sell order for testing
                            order = self.exchange.create_limit_sell_order(
                                symbol=symbol,
                                amount=amount,
                                price=current_price * 0.999  # Slightly below market
                            )

                            logger.info(f"✅ LIMIT SELL ORDER PLACED: {symbol}")
                            logger.info(f"   Order ID: {order['id']}")

                        self.positions[symbol] = {
                            'side': 'short',
                            'entry_price': current_price,
                            'amount': amount,
                            'entry_time': datetime.now(),
                            'order_id': order.get('id', 'simulated')
                        }

                    except Exception as e:
                        logger.error(f"❌ Sell order failed: {e}")
                        # Track as simulated short
                        self.positions[symbol] = {
                            'side': 'short',
                            'entry_price': current_price,
                            'amount': amount,
                            'entry_time': datetime.now(),
                            'order_id': 'simulated_short'
                        }

            elif signal in ['EXIT_LONG', 'EXIT_SHORT'] and symbol in self.positions:
                position = self.positions[symbol]
                amount = position['amount']
                entry_price = position['entry_price']

                logger.info(f"🏁 CLOSING POSITION: {symbol}")

                try:
                    if position['side'] == 'long':
                        # Sell to close long position
                        order = self.exchange.create_market_sell_order(
                            symbol=symbol,
                            amount=amount
                        )
                        logger.info(f"✅ SELL ORDER EXECUTED (closing long): {symbol}")

                    else:  # short
                        # Buy to close short position
                        order = self.exchange.create_market_buy_order(
                            symbol=symbol,
                            amount=amount
                        )
                        logger.info(f"✅ BUY ORDER EXECUTED (closing short): {symbol}")

                    logger.info(f"   Order ID: {order['id']}")

                except Exception as e:
                    logger.error(f"Failed to close position: {e}")
                    order = {'id': 'close_failed'}

                # Calculate PnL
                if position['side'] == 'long':
                    pnl = (current_price - entry_price) * amount
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:
                    pnl = (entry_price - current_price) * amount
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100

                self.total_pnl += pnl

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
                    f"Amount: {pos['amount']:.8f} | "
                    f"{pnl_color}PnL: ${pnl:.2f} ({pnl_pct:+.2f}%){Style.RESET_ALL}"
                )

                if pos.get('order_id') and pos['order_id'] not in ['simulated', 'simulated_short']:
                    logger.info(f"   Order ID: {pos['order_id']}")

    def check_open_orders(self):
        """Check status of open orders on testnet"""
        try:
            open_orders = self.exchange.fetch_open_orders()
            if open_orders:
                logger.info(f"📋 Open Orders: {len(open_orders)}")
                for order in open_orders:
                    logger.info(f"   {order['symbol']}: {order['side']} {order['amount']} @ {order['price']}")
        except Exception as e:
            logger.debug(f"Could not fetch open orders: {e}")

    def run(self):
        """Main bot loop"""
        logger.info("=" * 60)
        logger.info("🤖 STATISTICAL ARBITRAGE BOT - TESTNET TRADING")
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
        logger.info("📌 Check your orders at: https://testnet.binance.vision/")
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

                # Check open orders
                self.check_open_orders()

                # Show total PnL
                if self.total_pnl != 0:
                    pnl_color = Fore.GREEN if self.total_pnl > 0 else Fore.RED
                    logger.info(f"\n{pnl_color}💼 TOTAL P&L: ${self.total_pnl:.2f}{Style.RESET_ALL}")

                # Show next update timer
                logger.info(f"\n⏳ Next update in {self.config['update_interval']} seconds...")
                logger.info(f"📌 Check orders at: https://testnet.binance.vision/")

                # Wait for next update
                time.sleep(self.config['update_interval'])

            except KeyboardInterrupt:
                logger.info("\n" + "=" * 60)
                logger.info("🛑 BOT STOPPED BY USER")
                logger.info("=" * 60)
                logger.info(f"Total trades executed: {len(self.trades_executed)}")
                logger.info(f"Final P&L: ${self.total_pnl:.2f}")

                # Cancel any open orders
                try:
                    self.exchange.cancel_all_orders()
                    logger.info("Cancelled all open orders")
                except:
                    pass

                break

            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                logger.info("Retrying in 10 seconds...")
                time.sleep(10)

if __name__ == "__main__":
    bot = StatArbBot()
    bot.run()