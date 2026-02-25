#!/usr/bin/env python3
"""
Enhanced Strategy Executor for EC2 Deployment
Simple version that reads from strategy_config.json
"""

import json
import time
import logging
from datetime import datetime
import ccxt
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StatArbBot:
    def __init__(self, config_file='strategy_config.json'):
        """Initialize the bot with config"""
        with open(config_file, 'r') as f:
            self.config = json.load(f)

        # Initialize exchange
        self.exchange = ccxt.binance({
            'apiKey': self.config['api_key'],
            'secret': self.config['api_secret'],
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })

        self.positions = {}
        self.price_history = {}

    def fetch_prices(self, symbol):
        """Fetch current price for a symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
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

        for symbol in self.config['trading_pairs']:
            # Update price history
            price = self.fetch_prices(symbol)
            if price is None:
                continue

            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(price)

            # Keep only lookback period
            if len(self.price_history[symbol]) > self.config['lookback_period']:
                self.price_history[symbol] = self.price_history[symbol][-self.config['lookback_period']:]

            # Calculate z-score
            if len(self.price_history[symbol]) >= self.config['lookback_period']:
                zscore = self.calculate_zscore(self.price_history[symbol])

                # Generate signals
                if abs(zscore) > self.config['entry_threshold']:
                    if zscore > 0:
                        signals[symbol] = 'SELL'
                    else:
                        signals[symbol] = 'BUY'
                elif abs(zscore) < self.config['exit_threshold'] and symbol in self.positions:
                    signals[symbol] = 'EXIT'

                logger.info(f"{symbol}: Price={price:.4f}, Z-Score={zscore:.2f}, Signal={signals.get(symbol, 'HOLD')}")

        return signals

    def execute_trade(self, symbol, signal):
        """Execute a trade based on signal"""
        try:
            if signal == 'BUY':
                if len(self.positions) < self.config['max_positions']:
                    # Place buy order
                    logger.info(f"BUYING {symbol} - Position Size: {self.config['position_size']} USDT")
                    self.positions[symbol] = {
                        'side': 'long',
                        'entry_price': self.price_history[symbol][-1],
                        'size': self.config['position_size'],
                        'entry_time': datetime.now()
                    }

            elif signal == 'SELL':
                if len(self.positions) < self.config['max_positions']:
                    # Place sell order
                    logger.info(f"SELLING {symbol} - Position Size: {self.config['position_size']} USDT")
                    self.positions[symbol] = {
                        'side': 'short',
                        'entry_price': self.price_history[symbol][-1],
                        'size': self.config['position_size'],
                        'entry_time': datetime.now()
                    }

            elif signal == 'EXIT' and symbol in self.positions:
                # Exit position
                position = self.positions[symbol]
                current_price = self.price_history[symbol][-1]

                if position['side'] == 'long':
                    pnl = (current_price - position['entry_price']) / position['entry_price'] * 100
                else:
                    pnl = (position['entry_price'] - current_price) / position['entry_price'] * 100

                logger.info(f"EXITING {symbol} - PnL: {pnl:.2f}%")
                del self.positions[symbol]

        except Exception as e:
            logger.error(f"Error executing trade for {symbol}: {e}")

    def check_stop_loss_take_profit(self):
        """Check stop loss and take profit for open positions"""
        for symbol, position in list(self.positions.items()):
            current_price = self.price_history[symbol][-1] if symbol in self.price_history else None

            if current_price is None:
                continue

            entry_price = position['entry_price']

            if position['side'] == 'long':
                pnl = (current_price - entry_price) / entry_price
            else:
                pnl = (entry_price - current_price) / entry_price

            # Check stop loss
            if pnl <= -self.config['stop_loss']:
                logger.warning(f"STOP LOSS hit for {symbol} - PnL: {pnl*100:.2f}%")
                del self.positions[symbol]

            # Check take profit
            elif pnl >= self.config['take_profit']:
                logger.info(f"TAKE PROFIT hit for {symbol} - PnL: {pnl*100:.2f}%")
                del self.positions[symbol]

    def run(self):
        """Main bot loop"""
        logger.info("Starting Statistical Arbitrage Bot...")
        logger.info(f"Trading pairs: {self.config['trading_pairs']}")
        logger.info(f"Update interval: {self.config['update_interval']} seconds")

        while True:
            try:
                # Check for trading signals
                signals = self.check_signals()

                # Execute trades based on signals
                for symbol, signal in signals.items():
                    self.execute_trade(symbol, signal)

                # Check stop loss and take profit
                self.check_stop_loss_take_profit()

                # Display current positions
                if self.positions:
                    logger.info(f"Open positions: {len(self.positions)}")
                    for symbol, pos in self.positions.items():
                        logger.info(f"  {symbol}: {pos['side']} @ {pos['entry_price']:.4f}")

                # Wait for next update
                time.sleep(self.config['update_interval'])

            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)

if __name__ == "__main__":
    bot = StatArbBot()
    bot.run()