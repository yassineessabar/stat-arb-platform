#!/usr/bin/env python3
"""
Live Trading Dashboard Runner
============================

Runs the dashboard with REAL trading data from:
- Live Binance market data
- Actual trading bot positions and P&L
- Real execution metrics
- Live risk calculations

This replaces simulated data with actual trading feeds.
"""

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from monitoring.live_data_connector import run_dashboard_with_live_data
from live.trading_bot import StatArbTradingBot


class LiveDashboardRunner:
    """Runner for live trading dashboard with real data feeds."""

    def __init__(self, port: int = 8080, connect_to_trading_bot: bool = False):
        """
        Initialize live dashboard runner.

        Args:
            port: Dashboard server port
            connect_to_trading_bot: Whether to connect to live trading bot
        """
        self.port = port
        self.connect_to_trading_bot = connect_to_trading_bot
        self.trading_bot = None
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """Start the live dashboard with real trading data."""
        logger = logging.getLogger(__name__)

        # Configuration for live dashboard
        config = {
            'dashboard': {
                'enabled': True,
                'update_interval': 60
            },
            'monitoring': {
                'targets': {
                    'sharpe': 1.0,
                    'annual_vol': 0.20,
                    'max_drawdown': 0.15
                }
            },
            'update_interval': 30  # Live data update every 30 seconds
        }

        print(f"🚀 Starting LIVE Trading Dashboard on port {self.port}")
        print(f"📊 Dashboard URL: http://localhost:{self.port}")
        print("=" * 60)
        print("LIVE DATA SOURCES:")
        print("✅ Real Binance market data")
        print("✅ Live price feeds and volatility")
        print("✅ Actual market correlations")

        if self.connect_to_trading_bot:
            try:
                print("✅ Live trading bot integration")
                print("✅ Real position data")
                print("✅ Actual P&L tracking")
                print("✅ Live execution metrics")

                # Initialize trading bot
                logger.info("Initializing trading bot for live data...")
                self.trading_bot = StatArbTradingBot()

                # Start trading bot in background
                bot_task = asyncio.create_task(self.trading_bot.start())

                # Give bot time to initialize
                await asyncio.sleep(5)

            except Exception as e:
                logger.warning(f"Could not connect to trading bot: {e}")
                print("⚠️  Trading bot connection failed - using market data only")
                self.trading_bot = None
        else:
            print("📈 Market data simulation (no trading bot)")
            print("📊 Real market-based P&L estimation")
            print("🔍 Market volatility-based risk metrics")

        print("=" * 60)
        print("🔴 IMPORTANT: This uses REAL market data and APIs")
        print("💰 If connected to trading bot, shows ACTUAL positions")
        print("⚡ Updates every 30 seconds with live data")
        print("=" * 60)
        print("Press Ctrl+C to stop")

        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Start live dashboard
            dashboard_task = asyncio.create_task(
                run_dashboard_with_live_data(config, self.trading_bot, self.port)
            )

            # Wait for shutdown signal
            await self.shutdown_event.wait()

            # Cancel tasks
            dashboard_task.cancel()
            if 'bot_task' in locals():
                bot_task.cancel()

            # Wait for cleanup
            await asyncio.gather(dashboard_task, return_exceptions=True)
            if 'bot_task' in locals():
                await asyncio.gather(bot_task, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error running live dashboard: {e}")
            raise

        finally:
            if self.trading_bot:
                try:
                    await self.trading_bot.shutdown()
                except:
                    pass

            print("\n🛑 Live dashboard stopped")


async def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('live_dashboard.log')
        ]
    )

    # Parse command line arguments
    port = 8080
    connect_trading_bot = False

    if len(sys.argv) > 1:
        if sys.argv[1] == '--with-bot':
            connect_trading_bot = True
            print("🤖 Trading bot integration enabled")
        elif sys.argv[1] == '--help':
            print("Live Trading Dashboard Runner")
            print("Usage:")
            print("  python run_live_dashboard.py [--with-bot] [port]")
            print("")
            print("Options:")
            print("  --with-bot    Connect to live trading bot (requires bot setup)")
            print("  port         Dashboard port (default: 8080)")
            print("")
            print("Examples:")
            print("  python run_live_dashboard.py                # Market data only")
            print("  python run_live_dashboard.py --with-bot     # Full live integration")
            print("  python run_live_dashboard.py 8081          # Custom port")
            return
        else:
            try:
                port = int(sys.argv[1])
            except ValueError:
                print(f"Invalid port: {sys.argv[1]}")
                return

    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Invalid port: {sys.argv[2]}")
            return

    # Create and start runner
    runner = LiveDashboardRunner(port, connect_trading_bot)

    try:
        await runner.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
    except Exception as e:
        logging.error(f"Live dashboard crashed: {e}")
        print(f"\n❌ Dashboard error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)