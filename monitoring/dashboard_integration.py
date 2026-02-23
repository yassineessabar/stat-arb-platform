"""
Dashboard Integration Module
===========================

Integrates the dashboard with the live trading system:
- Connects trading bot to dashboard updates
- Real-time data pipeline from trading to dashboard
- Event-driven updates for trades, positions, and alerts
"""

import asyncio
import logging
from typing import Dict, Optional
import time

from monitoring.web_dashboard import WebDashboard
from monitoring.live_data_connector import LiveDataConnector
from live.trading_bot import StatArbTradingBot

logger = logging.getLogger(__name__)


class DashboardIntegration:
    """Integrates trading bot with dashboard for real-time updates."""

    def __init__(self, dashboard: WebDashboard, trading_bot: StatArbTradingBot):
        """
        Initialize dashboard integration.

        Args:
            dashboard: WebDashboard instance
            trading_bot: StatArbTradingBot instance
        """
        self.dashboard = dashboard
        self.trading_bot = trading_bot
        self.live_connector = LiveDataConnector(dashboard, trading_bot)

        # Integration state
        self.is_running = False
        self.update_task = None

        # Performance tracking
        self.last_position_update = 0
        self.last_execution_update = 0

        logger.info("Dashboard integration initialized")

    async def start(self) -> None:
        """Start the integration between trading bot and dashboard."""
        if self.is_running:
            logger.warning("Integration already running")
            return

        logger.info("Starting dashboard integration...")

        try:
            # Initialize live data connector
            await self.live_connector.initialize()

            # Hook into trading bot events
            self._setup_trading_bot_hooks()

            # Start update loop
            self.update_task = asyncio.create_task(self._integration_loop())
            self.is_running = True

            logger.info("Dashboard integration started successfully")

        except Exception as e:
            logger.error(f"Failed to start dashboard integration: {e}")
            raise

    async def stop(self) -> None:
        """Stop the dashboard integration."""
        if not self.is_running:
            return

        logger.info("Stopping dashboard integration...")

        self.is_running = False

        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        logger.info("Dashboard integration stopped")

    def _setup_trading_bot_hooks(self) -> None:
        """Setup hooks into trading bot for real-time updates."""
        # Note: In a production system, these would be event-driven callbacks
        # For now, we'll use the polling approach in the integration loop

        logger.info("Trading bot hooks configured")

    async def _integration_loop(self) -> None:
        """Main integration loop for real-time updates."""
        logger.info("Integration loop started")

        while self.is_running:
            try:
                # Update dashboard with latest trading data
                await self._update_from_trading_bot()

                # Check for new trading events
                await self._check_trading_events()

                # Update at 30-second intervals
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in integration loop: {e}")
                await asyncio.sleep(10)  # Retry in 10 seconds

    async def _update_from_trading_bot(self) -> None:
        """Update dashboard with latest data from trading bot."""
        if not self.trading_bot.is_running:
            return

        try:
            # Get bot status
            bot_status = await self.trading_bot.get_status()

            # Update dashboard with real trading data
            await self._update_performance_from_bot(bot_status)
            await self._update_positions_from_bot(bot_status)
            await self._update_execution_from_bot(bot_status)
            await self._update_risk_from_bot(bot_status)

        except Exception as e:
            logger.error(f"Failed to update from trading bot: {e}")

    async def _update_performance_from_bot(self, bot_status: Dict) -> None:
        """Update performance metrics from trading bot."""
        try:
            if 'risk' not in bot_status:
                return

            risk_metrics = bot_status['risk']

            # Calculate performance metrics
            total_pnl = risk_metrics.get('total_pnl', 0.0)
            portfolio_value = risk_metrics.get('portfolio_value', 100000.0)
            current_drawdown = risk_metrics.get('current_drawdown', 0.0)

            performance_metrics = {
                'total_pnl': total_pnl,
                'daily_pnl': total_pnl * 0.1,  # Approximate daily component
                'portfolio_value': portfolio_value,
                'total_return': total_pnl / 100000.0,  # Assuming 100k initial
                'current_drawdown': current_drawdown,
                'max_drawdown': risk_metrics.get('max_drawdown', current_drawdown),
                'daily_return': (total_pnl * 0.1) / 100000.0,
                'sharpe_ratio': risk_metrics.get('sharpe_ratio', 1.0),
                'realized_vol': risk_metrics.get('volatility', 0.18)
            }

            self.dashboard.update_performance(performance_metrics)

        except Exception as e:
            logger.error(f"Failed to update performance from bot: {e}")

    async def _update_positions_from_bot(self, bot_status: Dict) -> None:
        """Update position data from trading bot."""
        try:
            # Get current positions from bot
            if self.trading_bot.binance_client:
                position_risk = await self.trading_bot.binance_client.get_position_risk()

                positions = {}
                total_exposure = 0.0

                for pos in position_risk:
                    position_amt = float(pos['positionAmt'])
                    if position_amt != 0:  # Only active positions
                        symbol = pos['symbol']
                        mark_price = float(pos['markPrice'])
                        usd_value = abs(position_amt * mark_price)

                        positions[symbol] = {'usd_value': usd_value}
                        total_exposure += usd_value

                # Calculate leverage
                portfolio_value = bot_status.get('risk', {}).get('portfolio_value', 100000.0)
                leverage = total_exposure / portfolio_value if portfolio_value > 0 else 0

                self.dashboard.update_positions(positions, total_exposure, leverage)
                self.last_position_update = time.time()

        except Exception as e:
            logger.error(f"Failed to update positions from bot: {e}")

    async def _update_execution_from_bot(self, bot_status: Dict) -> None:
        """Update execution metrics from trading bot."""
        try:
            if 'execution' not in bot_status:
                return

            execution_status = bot_status['execution']

            # Get recent execution data
            recent_orders = execution_status.get('recent_orders', [])

            for order in recent_orders[-5:]:  # Last 5 orders
                if 'symbol' in order and 'status' in order:
                    if order['status'] == 'FILLED':
                        symbol = order['symbol']
                        side = order['side']
                        quantity = float(order.get('executedQty', 0))

                        # Estimate prices (would be in real order data)
                        avg_price = float(order.get('avgPrice', order.get('price', 0)))
                        market_price = avg_price * 0.999  # Assume slight slippage

                        if quantity > 0 and avg_price > 0:
                            self.dashboard.update_execution(
                                symbol, side, quantity, market_price, avg_price
                            )

            self.last_execution_update = time.time()

        except Exception as e:
            logger.error(f"Failed to update execution from bot: {e}")

    async def _update_risk_from_bot(self, bot_status: Dict) -> None:
        """Update risk metrics from trading bot."""
        try:
            if 'risk' not in bot_status:
                return

            risk_metrics = bot_status['risk']

            risk_data = {
                'risk_level': risk_metrics.get('risk_level', 'MEDIUM'),
                'var_95_1d': risk_metrics.get('var_95', 0.025),
                'expected_shortfall': risk_metrics.get('expected_shortfall', 0.035),
                'correlation_status': 'NORMAL',  # Would calculate from market data
                'risk_violations': risk_metrics.get('violations', []),
                'leverage': risk_metrics.get('leverage', 0.0),
                'current_drawdown': risk_metrics.get('current_drawdown', 0.0)
            }

            self.dashboard.update_risk(risk_data)

        except Exception as e:
            logger.error(f"Failed to update risk from bot: {e}")

    async def _check_trading_events(self) -> None:
        """Check for new trading events and alerts."""
        try:
            if not self.trading_bot.monitor:
                return

            # Check for new alerts from trading bot
            alerts = self.trading_bot.monitor.check_alerts()

            for alert in alerts:
                # Add alert to dashboard
                alert_data = {
                    'type': alert.get('type', 'unknown'),
                    'severity': alert.get('severity', 'info'),
                    'message': alert.get('message', 'Trading alert'),
                    'timestamp': time.time(),
                    'source': 'trading_bot'
                }

                self.dashboard.add_alert(alert_data)

        except Exception as e:
            logger.error(f"Failed to check trading events: {e}")

    def get_integration_status(self) -> Dict:
        """Get current integration status."""
        return {
            'is_running': self.is_running,
            'trading_bot_connected': self.trading_bot.is_running,
            'last_position_update': self.last_position_update,
            'last_execution_update': self.last_execution_update,
            'update_count': getattr(self, 'update_count', 0)
        }


async def run_integrated_dashboard(port: int = 8080) -> None:
    """
    Run dashboard with full trading bot integration.

    Args:
        port: Dashboard server port
    """
    # Configuration
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
        'update_interval': 30
    }

    # Initialize components
    dashboard = WebDashboard(config, port)
    trading_bot = StatArbTradingBot()
    integration = DashboardIntegration(dashboard, trading_bot)

    runner = None

    try:
        logger.info("Starting integrated trading dashboard...")

        # Start dashboard server
        runner = await dashboard.start_server()

        # Start trading bot
        bot_task = asyncio.create_task(trading_bot.start())

        # Give bot time to initialize
        await asyncio.sleep(5)

        # Start integration
        await integration.start()

        logger.info(f"Integrated dashboard running on http://localhost:{port}")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down integrated dashboard...")
    finally:
        # Cleanup
        await integration.stop()

        if 'bot_task' in locals():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass

        await trading_bot.shutdown()

        if runner:
            await dashboard.stop_server(runner)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_integrated_dashboard())