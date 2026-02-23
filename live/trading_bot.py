"""
Main Trading Bot
===============

Orchestrates the complete live trading system:
- Data feeds and signal generation
- Position management and execution
- Risk monitoring and controls
- Performance tracking and alerts

This is the main entry point for live trading operations.
"""

import asyncio
import logging
import os
import time
import yaml
from pathlib import Path
from typing import Dict, Optional
import signal
import pandas as pd

from live.binance_client import BinanceClient
from live.execution_engine import ExecutionEngine
from core.strategy_engine import StatArbStrategyEngine
from risk.position_risk import PositionRiskManager
from monitoring.metrics import LiveMonitor

logger = logging.getLogger(__name__)


class StatArbTradingBot:
    """
    Main trading bot orchestrating the complete stat-arb system.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize trading bot.

        Args:
            config_path: Path to configuration directory
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config"

        self.config_path = Path(config_path)

        # Load environment variables from .env file
        self._load_env_vars()

        self.config = self._load_config()

        # Initialize components
        self.binance_client = None
        self.execution_engine = None
        self.strategy_engine = None
        self.risk_manager = None
        self.monitor = None

        # Bot state
        self.is_running = False
        # Default to paper trading for safety
        self.is_paper_trading = True
        self.shutdown_event = asyncio.Event()

        # Signal generation frequency
        self.signal_interval = 3600  # 1 hour
        self.position_check_interval = 300  # 5 minutes

        environment = self.config.get('exchange', {}).get('environment', 'paper')
        logger.info(f"Trading bot initialized: {environment} mode")

    def _load_env_vars(self) -> None:
        """Load environment variables from .env file."""
        env_file = Path(__file__).parent.parent / ".env"

        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            logger.debug("Loaded environment variables from .env file")
        else:
            logger.debug("No .env file found")

    def _load_config(self) -> Dict:
        """Load all configuration files."""
        configs = {}

        # Load all YAML files in config directory
        for config_file in self.config_path.glob("*.yaml"):
            with open(config_file, 'r') as f:
                config_name = config_file.stem
                configs[config_name] = yaml.safe_load(f)

        # Merge relevant configs
        merged_config = {
            **configs.get('params_v6', {}),
            'exchange': configs.get('exchange', {}),
            'risk_limits': configs.get('risk_limits', {}),
            'universe': configs.get('universe', {})
        }

        # Debug config loading
        logger.debug(f"Loaded configs: {list(configs.keys())}")
        logger.debug(f"Universe symbols count: {len(merged_config.get('universe', {}).get('symbols', []))}")


        logger.info("Configuration loaded from YAML files")
        return merged_config

    async def initialize(self) -> None:
        """Initialize all bot components."""
        logger.info("Initializing trading bot components...")

        # Initialize Binance client
        exchange_config = self.config.get('exchange', {})

        # Handle nested exchange config safely
        if isinstance(exchange_config, dict) and 'exchange' in exchange_config:
            inner_config = exchange_config['exchange']
        elif isinstance(exchange_config, dict):
            inner_config = exchange_config
        else:
            inner_config = {}

        environment = inner_config.get('environment', 'paper')
        testnet = environment != 'live'

        # Load API credentials from environment variables
        if environment == 'paper' or testnet:
            api_key = os.getenv('BINANCE_TESTNET_API_KEY', '')
            api_secret = os.getenv('BINANCE_TESTNET_API_SECRET', '')
        else:
            api_key = os.getenv('BINANCE_LIVE_API_KEY', '')
            api_secret = os.getenv('BINANCE_LIVE_API_SECRET', '')

        # Fallback to config file if env vars not set
        if not api_key:
            api_key = inner_config.get('api_key', '')
        if not api_secret:
            api_secret = inner_config.get('api_secret', '')

        self.binance_client = BinanceClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            paper_trading=self.is_paper_trading
        )

        # Initialize strategy engine
        self.strategy_engine = StatArbStrategyEngine(self.config_path)

        # Initialize risk manager
        account_balance = await self._get_account_balance()
        risk_limits_config = self.config.get('risk_limits', {})

        self.risk_manager = PositionRiskManager(
            risk_limits_config,
            account_balance
        )

        # Initialize monitor
        self.monitor = LiveMonitor(self.config)

        # Initialize execution engine
        self.execution_engine = ExecutionEngine(
            self.binance_client,
            self.risk_manager,
            exchange_config
        )

        logger.info("All components initialized successfully")

    async def _get_account_balance(self) -> float:
        """Get current account balance."""
        try:
            account_info = await self.binance_client.get_account_info()

            for asset in account_info.get('assets', []):
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])

        except Exception as e:
            logger.warning(f"Failed to get account balance: {e}")

        # Default balance for paper trading
        return 100000.0

    async def start(self) -> None:
        """Start the trading bot."""
        if self.is_running:
            logger.warning("Bot is already running")
            return

        logger.info("Starting stat-arb trading bot...")

        try:
            # Initialize components first
            await self.initialize()

            # Use single context manager for entire bot lifecycle
            async with self.binance_client:
                self.is_running = True

                # Set up signal handlers for graceful shutdown
                self._setup_signal_handlers()

                # Start main trading loops
                tasks = [
                    asyncio.create_task(self._strategy_loop()),
                    asyncio.create_task(self._execution_loop()),
                    asyncio.create_task(self._monitoring_loop()),
                    asyncio.create_task(self._risk_monitoring_loop())
                ]

                logger.info("Trading bot started successfully")

                # Wait for shutdown signal
                await self.shutdown_event.wait()

                # Cancel all tasks
                for task in tasks:
                    task.cancel()

                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.critical(f"Critical error in trading bot: {e}")
            raise

        finally:
            if hasattr(self, 'shutdown'):
                await self.shutdown()

    async def _strategy_loop(self) -> None:
        """Main strategy loop - generates signals periodically."""
        logger.info("Strategy loop started")

        while not self.shutdown_event.is_set():
            try:
                await self._run_strategy_cycle()

                # Wait for next cycle
                await asyncio.sleep(self.signal_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in strategy loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _run_strategy_cycle(self) -> None:
        """Run one complete strategy cycle."""
        logger.debug("Running strategy cycle...")

        try:
            # Fetch market data
            market_data = await self._fetch_market_data()

            if market_data.empty:
                logger.warning("No market data received, skipping cycle")
                return

            # Generate signals
            # Initialize strategy if needed
            if not self.strategy_engine.active_pairs:
                universe_analysis = self.strategy_engine.analyze_universe(market_data)
                self.strategy_engine.initialize_pairs(
                    universe_analysis['selected_pairs'],
                    market_data
                )

            # Generate current signals
            signal_results = self.strategy_engine.generate_signals(market_data)

            # Convert to target positions
            pair_signals = signal_results['pair_signals']

            # Get latest signals (most recent row)
            latest_signals = {}
            for pair, signal_series in pair_signals.items():
                if not signal_series.empty:
                    latest_signals[pair] = signal_series.iloc[-1]

            # Set target positions
            if latest_signals:
                await self.execution_engine.set_target_positions(latest_signals)

            logger.info(f"Strategy cycle complete: {len(latest_signals)} signals generated")

        except Exception as e:
            logger.error(f"Strategy cycle failed: {e}")

    async def _fetch_market_data(self) -> pd.DataFrame:
        """Fetch current market data for strategy."""
        universe_config = self.config.get('universe', {})

        # Handle nested universe structure
        if 'universe' in universe_config:
            symbols = universe_config['universe'].get('symbols', [])
        else:
            symbols = universe_config.get('symbols', [])

        # Fallback to core pairs if no symbols configured
        if not symbols:
            symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
            logger.warning(f"No symbols in universe config, using fallback: {symbols}")
        else:
            logger.info(f"Using {len(symbols)} symbols from universe config")

        market_data = {}

        for symbol in symbols:
            try:
                # Get recent price data
                klines = await self.binance_client.get_klines(
                    symbol,
                    interval='1d',
                    limit=1000
                )

                # Convert to DataFrame
                df = self.binance_client.klines_to_dataframe(klines, symbol)
                market_data[symbol.replace('USDT', '')] = df['close']

            except Exception as e:
                logger.warning(f"Failed to fetch data for {symbol}: {e}")

        if market_data:
            price_df = pd.DataFrame(market_data)
            return price_df.dropna()
        else:
            return pd.DataFrame()

    async def _execution_loop(self) -> None:
        """Execution engine loop."""
        logger.info("Execution loop started")

        # Start order processing
        await self.execution_engine.process_orders()

    async def _monitoring_loop(self) -> None:
        """Monitoring loop - tracks performance and alerts."""
        logger.info("Monitoring loop started")

        while not self.shutdown_event.is_set():
            try:
                # Update monitoring metrics
                await self._update_monitoring()

                # Check alerts
                alerts = self.monitor.check_alerts()
                for alert in alerts:
                    await self._handle_alert(alert)

                await asyncio.sleep(60)  # Update every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)

    async def _risk_monitoring_loop(self) -> None:
        """Risk monitoring loop."""
        logger.info("Risk monitoring loop started")

        while not self.shutdown_event.is_set():
            try:
                # Update positions and risk metrics
                await self._update_risk_monitoring()

                # Reconcile positions
                await self.execution_engine.reconcile_positions()

                await asyncio.sleep(self.position_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in risk monitoring: {e}")
                await asyncio.sleep(60)

    async def _update_monitoring(self) -> None:
        """Update monitoring metrics."""
        try:
            # Get current positions
            positions = await self.binance_client.get_position_risk()

            # Calculate current PnL (simplified)
            total_pnl = sum(float(pos['unRealizedPnL']) for pos in positions)

            # Update strategy metrics
            position_values = {
                pos['symbol']: float(pos['positionAmt']) * float(pos['markPrice'])
                for pos in positions
            }

            self.monitor.update_strategy_performance(total_pnl, position_values)

        except Exception as e:
            logger.error(f"Failed to update monitoring: {e}")

    async def _update_risk_monitoring(self) -> None:
        """Update risk monitoring."""
        try:
            # Get current positions
            positions = await self.binance_client.get_position_risk()

            # Update risk manager
            position_values = {
                pos['symbol']: float(pos['positionAmt']) * float(pos['markPrice'])
                for pos in positions
            }

            self.risk_manager.update_positions(position_values)

            # Check for emergency conditions
            risk_metrics = self.risk_manager.get_risk_metrics()

            if risk_metrics['emergency_mode']:
                logger.critical("Emergency mode detected - initiating liquidation")
                await self.execution_engine.emergency_liquidate()

        except Exception as e:
            logger.error(f"Failed to update risk monitoring: {e}")

    async def _handle_alert(self, alert: Dict) -> None:
        """Handle monitoring alerts."""
        logger.warning(f"ALERT [{alert['severity']}]: {alert['message']}")

        # In production, would send to Slack, email, etc.
        # For now, just log the alert

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self._initiate_shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _initiate_shutdown(self) -> None:
        """Initiate graceful shutdown."""
        if not self.shutdown_event.is_set():
            logger.info("Initiating graceful shutdown...")
            self.shutdown_event.set()

    async def shutdown(self) -> None:
        """Gracefully shutdown the trading bot."""
        logger.info("Shutting down trading bot...")

        try:
            if self.execution_engine:
                await self.execution_engine.shutdown()

            if self.binance_client:
                await self.binance_client.__aexit__(None, None, None)

            self.is_running = False
            logger.info("Trading bot shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def get_status(self) -> Dict:
        """Get current bot status."""
        status = {
            'is_running': self.is_running,
            'mode': 'paper' if self.is_paper_trading else 'live',
            'uptime': time.time(),  # Would track actual uptime
        }

        if self.execution_engine:
            status['execution'] = self.execution_engine.get_execution_status()

        if self.risk_manager:
            status['risk'] = self.risk_manager.get_risk_metrics()

        if self.monitor:
            status['health'] = self.monitor.get_health_check()

        return status


async def main():
    """Main entry point for the trading bot."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create and start bot
    bot = StatArbTradingBot()

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())