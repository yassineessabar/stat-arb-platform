#!/usr/bin/env python3
"""
Enhanced Strategy Executor for EC2 Deployment
With REAL trade execution on Binance Testnet using working patterns from tests
"""

import asyncio
import json
import time
import logging
from datetime import datetime
import pandas as pd
import numpy as np
from colorama import init, Fore, Style
import sys
import os

# Add the live directory to Python path to import working modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from live.binance_client import BinanceClient
from live.execution_engine import ExecutionEngine

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

# Mock risk manager for this script
class SimpleRiskManager:
    """Simple risk manager that allows all trades for testing"""

    async def validate_trade(self, trade):
        """Always validate trades for testing"""
        return True

class StatArbBot:
    def __init__(self, config_file='strategy_config.json'):
        """Initialize the bot with config using working patterns from tests"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        logger.info("=" * 60)
        logger.info("🚀 INITIALIZING STATISTICAL ARBITRAGE BOT")
        logger.info("=" * 60)

        # Initialize Binance client using working pattern from tests
        self.client = BinanceClient(
            api_key=self.config['api_key'],
            api_secret=self.config['api_secret'],
            testnet=True,
            paper_trading=False  # ENABLE REAL TRADING on testnet
        )

        # Initialize execution engine with working pattern
        self.risk_manager = SimpleRiskManager()

        # Create config structure expected by ExecutionEngine
        execution_config = {
            'trading': {
                'execution': {
                    'max_slippage_bps': 10,
                    'order_timeout_seconds': 30,
                    'retry_attempts': 3,
                    'min_order_value_usdt': 5
                }
            }
        }

        self.execution_engine = ExecutionEngine(self.client, self.risk_manager, execution_config)

        # Initialize tracking variables
        self.positions = {}  # Local position tracking
        self.price_history = {}
        self.trades_executed = []
        self.total_pnl = 0
        self.order_ids = []

        logger.info(f"✅ Connected to Binance Testnet using working client patterns")

    async def check_balance(self):
        """Check and display account balance using working client"""
        try:
            async with self.client:
                account = await self.client.get_account_info()

            usdt_balance = 0
            btc_balance = 0
            eth_balance = 0

            for balance in account.get('assets', []):
                if balance['asset'] == 'USDT':
                    usdt_balance = float(balance['walletBalance'])
                elif balance['asset'] == 'BTC':
                    btc_balance = float(balance.get('walletBalance', 0))
                elif balance['asset'] == 'ETH':
                    eth_balance = float(balance.get('walletBalance', 0))

            logger.info(f"💰 Account Balances:")
            logger.info(f"   USDT: {usdt_balance:.2f}")
            logger.info(f"   BTC: {btc_balance:.8f}")
            logger.info(f"   ETH: {eth_balance:.8f}")

            return usdt_balance
        except Exception as e:
            logger.warning(f"Could not fetch balance: {e}")
            # Return default balance for testnet
            return 10000  # Assume 10000 USDT for testnet

    async def fetch_prices(self, symbol):
        """Fetch current price for a symbol using working client"""
        try:
            # Convert symbol format (BTC/USDT -> BTCUSDT)
            binance_symbol = symbol.replace('/', '')

            async with self.client:
                ticker = await self.client.get_ticker_24hr(binance_symbol)

            # Safely parse ticker data
            price = float(ticker['lastPrice']) if ticker.get('lastPrice') else 0
            if price <= 0:
                logger.error(f"Invalid price for {symbol}: {ticker.get('lastPrice')}")
                return None

            bid = float(ticker['bidPrice']) if ticker.get('bidPrice') and ticker['bidPrice'] not in [None, ''] else price
            ask = float(ticker['askPrice']) if ticker.get('askPrice') and ticker['askPrice'] not in [None, ''] else price
            volume = float(ticker['quoteVolume']) if ticker.get('quoteVolume') and ticker['quoteVolume'] not in [None, ''] else 0

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

    async def check_signals(self):
        """Check trading signals for all pairs"""
        signals = {}

        logger.info("-" * 60)
        logger.info("📊 MARKET ANALYSIS")
        logger.info("-" * 60)

        for symbol in self.config['trading_pairs']:
            # Fetch comprehensive price data
            price_data = await self.fetch_prices(symbol)
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

    async def execute_trade(self, symbol, signal):
        """Execute REAL trades using working ExecutionEngine patterns"""
        try:
            # Convert symbol format for execution engine (BTC/USDT -> BTCUSDT)
            binance_symbol = symbol.replace('/', '')

            # Calculate position size in USD
            price_data = await self.fetch_prices(symbol)
            if not price_data:
                return

            current_price = price_data['price']
            position_size_usd = self.config.get('position_size', 100)  # Default $100

            # Set target positions based on signal using ExecutionEngine
            if signal == 'BUY':
                if len(self.execution_engine.current_positions) < self.config['max_positions']:
                    logger.info(f"🔵 SETTING BUY TARGET: {symbol} = ${position_size_usd}")

                    # Set target position using ExecutionEngine
                    target_positions = {binance_symbol: position_size_usd}
                    await self.execution_engine.set_target_positions(target_positions)

                    # Start order processing (don't await to avoid blocking)
                    await self.process_orders()

                    # Track position
                    self.positions[symbol] = {
                        'side': 'long',
                        'target_usd': position_size_usd,
                        'entry_price': current_price,
                        'amount': position_size_usd / current_price,
                        'entry_time': datetime.now()
                    }

            elif signal == 'SELL':
                if len(self.execution_engine.current_positions) < self.config['max_positions']:
                    logger.info(f"🔴 SETTING SELL TARGET: {symbol} = ${-position_size_usd}")

                    # Set negative target position for short
                    target_positions = {binance_symbol: -position_size_usd}
                    await self.execution_engine.set_target_positions(target_positions)

                    # Start order processing (don't await to avoid blocking)
                    await self.process_orders()

                    # Track position
                    self.positions[symbol] = {
                        'side': 'short',
                        'target_usd': -position_size_usd,
                        'entry_price': current_price,
                        'amount': position_size_usd / current_price,
                        'entry_time': datetime.now()
                    }

            elif signal in ['EXIT_LONG', 'EXIT_SHORT'] and symbol in self.positions:
                logger.info(f"🏁 CLOSING POSITION: {symbol}")

                # Set target to zero to close position
                target_positions = {binance_symbol: 0.0}
                await self.execution_engine.set_target_positions(target_positions)

                # Start order processing
                asyncio.create_task(self.process_orders())

                # Remove from tracked positions
                if symbol in self.positions:
                    del self.positions[symbol]

        except Exception as e:
            logger.error(f"❌ Error executing trade for {symbol}: {e}")

    async def process_orders(self):
        """Process orders using ExecutionEngine"""
        try:
            # Process a few orders from the queue
            for _ in range(3):
                if not self.execution_engine.order_queue.empty():
                    trade = await asyncio.wait_for(
                        self.execution_engine.order_queue.get(),
                        timeout=1.0
                    )

                    # Execute the trade with proper session context
                    async with self.client:
                        result = await self.execution_engine._execute_trade(trade)
                        if result:
                            logger.info(f"✅ ORDER EXECUTED: {result['symbol']} {result['side']}")
                            self.order_ids.append(result.get('orderId', 'unknown'))

                    self.execution_engine.order_queue.task_done()

        except asyncio.TimeoutError:
            # No orders in queue
            pass
        except Exception as e:
            logger.error(f"Error processing orders: {e}")

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

    async def check_open_orders(self):
        """Check status of open orders using working client"""
        try:
            async with self.client:
                open_orders = await self.client.get_open_orders()
            if open_orders:
                logger.info(f"📋 Open Orders: {len(open_orders)}")
                for order in open_orders:
                    logger.info(f"   {order['symbol']}: {order['side']} {order['origQty']} @ {order.get('price', 'MARKET')}")
        except Exception as e:
            logger.debug(f"Could not fetch open orders: {e}")

    async def run_async(self):
        """Async main bot loop using working patterns"""
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

        # Check balance on startup
        await self.check_balance()

        iteration = 0
        while True:
            try:
                iteration += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"🔄 ITERATION #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info(f"{'='*60}")

                # Check for trading signals
                signals = await self.check_signals()

                # Execute trades based on signals
                for symbol, signal in signals.items():
                    await self.execute_trade(symbol, signal)

                # Check stop loss and take profit (keep sync for now)
                # self.check_stop_loss_take_profit()

                # Display current positions (skip if error)
                try:
                    self.display_positions()
                except Exception as e:
                    logger.debug(f"Position display error: {e}")

                # Check open orders
                await self.check_open_orders()

                # Show execution engine status
                status = self.execution_engine.get_execution_status()
                logger.info(f"🔧 Execution Status: {status['current_positions']} positions, {status['queue_size']} queued orders")

                # Show total PnL
                if self.total_pnl != 0:
                    pnl_color = Fore.GREEN if self.total_pnl > 0 else Fore.RED
                    logger.info(f"\n{pnl_color}💼 TOTAL P&L: ${self.total_pnl:.2f}{Style.RESET_ALL}")

                # Show next update timer
                logger.info(f"\n⏳ Next update in {self.config['update_interval']} seconds...")
                logger.info(f"📌 Check orders at: https://testnet.binance.vision/")

                # Wait for next update
                await asyncio.sleep(self.config['update_interval'])

            except KeyboardInterrupt:
                logger.info("\n" + "=" * 60)
                logger.info("🛑 BOT STOPPED BY USER")
                logger.info("=" * 60)
                logger.info(f"Total order IDs tracked: {len(self.order_ids)}")
                logger.info(f"Final P&L: ${self.total_pnl:.2f}")

                # Shutdown execution engine gracefully
                await self.execution_engine.shutdown()

                break

            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                logger.info("Retrying in 10 seconds...")
                await asyncio.sleep(10)

    def run(self):
        """Main entry point - run the async bot"""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")

if __name__ == "__main__":
    bot = StatArbBot()
    bot.run()