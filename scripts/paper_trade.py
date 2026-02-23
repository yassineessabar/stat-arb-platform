#!/usr/bin/env python3
"""
Paper Trading Runner
===================

Start paper trading with the v6 strategy.
Runs the full trading bot in simulation mode.

Usage:
    python scripts/paper_trade.py
    python scripts/paper_trade.py --balance 50000
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from live.trading_bot import StatArbTradingBot


def setup_logging(verbose: bool = False):
    """Setup logging for paper trading."""
    level = logging.DEBUG if verbose else logging.INFO

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler('paper_trading.log')
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(level)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def create_paper_config(balance: float = 100000) -> dict:
    """Create paper trading configuration."""
    config_updates = {
        'exchange': {
            'environment': 'paper',
            'paper_trading': {
                'initial_balance_usdt': balance,
                'simulate_latency_ms': 50,
                'simulate_slippage': True,
                'simulate_funding': True
            }
        }
    }
    return config_updates


async def run_paper_trading(balance: float = 100000, verbose: bool = False):
    """
    Run paper trading session.

    Args:
        balance: Starting balance in USDT
        verbose: Enable verbose logging
    """
    print("="*70)
    print("  STATISTICAL ARBITRAGE v6 — PAPER TRADING")
    print("="*70)
    print(f"  Starting balance: ${balance:,.0f} USDT")
    print(f"  Strategy: Multi-pair stat-arb with 20% vol targeting")
    print(f"  Environment: Paper trading simulation")
    print("="*70)

    # Setup logging
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    try:
        # Initialize trading bot
        logger.info("Initializing trading bot...")
        bot = StatArbTradingBot()

        # Update config for paper trading
        config_updates = create_paper_config(balance)

        # Set paper trading mode directly
        bot.is_paper_trading = True

        # Override exchange config
        if 'exchange' not in bot.config:
            bot.config['exchange'] = {}

        bot.config['exchange']['environment'] = 'paper'
        bot.config['exchange']['paper_trading'] = config_updates['exchange']['paper_trading']

        logger.info("Configuration updated for paper trading")

        # Start trading
        logger.info("Starting paper trading session...")
        print("\n🚀 Paper trading started!")
        print("   Press Ctrl+C to stop gracefully")
        print("   Monitor logs: tail -f paper_trading.log")

        await bot.start()

    except KeyboardInterrupt:
        logger.info("Paper trading stopped by user")
        print("\n⚠️ Paper trading stopped by user")

    except Exception as e:
        logger.error(f"Paper trading failed: {e}")
        print(f"\n❌ Paper trading failed: {e}")
        raise


def print_startup_info():
    """Print startup information."""
    print("\n📋 PAPER TRADING INFO:")
    print("  • Simulates real trading with virtual money")
    print("  • Uses live market data and real-time signals")
    print("  • Includes realistic slippage and latency")
    print("  • No real money at risk")
    print("\n🎯 STRATEGY FEATURES:")
    print("  • 20% volatility targeting")
    print("  • Dynamic hedge ratios via Kalman filter")
    print("  • Regime-aware signal generation")
    print("  • Multi-layer risk controls")
    print("\n📊 MONITORING:")
    print("  • Real-time performance tracking")
    print("  • Position and risk monitoring")
    print("  • Execution quality metrics")
    print("  • Automated alerts")


async def status_monitor(bot: StatArbTradingBot):
    """Monitor and display trading status."""
    while True:
        try:
            await asyncio.sleep(300)  # Update every 5 minutes

            if bot.is_running:
                status = await bot.get_status()
                print(f"\n📊 Status Update: {pd.Timestamp.now().strftime('%H:%M:%S')}")

                if 'execution' in status:
                    exec_stats = status['execution']
                    print(f"   Executions: {exec_stats.get('recent_executions', 0)}")
                    print(f"   Queue size: {exec_stats.get('queue_size', 0)}")

                if 'risk' in status:
                    risk_stats = status['risk']
                    print(f"   Portfolio equity: ${risk_stats.get('portfolio_equity', 0):,.0f}")
                    print(f"   Leverage: {risk_stats.get('leverage', 0):.2f}x")
                    print(f"   Drawdown: {risk_stats.get('drawdown', 0):.1%}")

        except Exception as e:
            logging.getLogger(__name__).warning(f"Status monitor error: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run Statistical Arbitrage v6 Paper Trading')

    parser.add_argument('--balance', type=float, default=100000,
                       help='Starting balance in USDT (default: 100000)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--no-monitor', action='store_true',
                       help='Disable status monitoring')

    args = parser.parse_args()

    # Validate arguments
    if args.balance <= 0:
        print("❌ Error: Balance must be positive")
        sys.exit(1)

    if args.balance < 1000:
        print("⚠️ Warning: Balance is very low, some pairs may not be tradeable")

    # Print startup info
    print_startup_info()

    try:
        # Run paper trading
        asyncio.run(run_paper_trading(args.balance, args.verbose))

    except KeyboardInterrupt:
        print("\n👋 Paper trading session ended")
    except Exception as e:
        print(f"\n❌ Paper trading crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Import here to avoid circular imports
    import pandas as pd

    main()