#!/usr/bin/env python3
"""
Dashboard Runner
================

Simple script to run the trading dashboard with sample data or live data.
"""

import asyncio
import logging
import time
import random
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from monitoring.web_dashboard import WebDashboard


class DashboardDemo:
    """Demo class to populate dashboard with sample data."""

    def __init__(self, dashboard: WebDashboard):
        self.dashboard = dashboard
        self.running = False

    async def start_demo(self):
        """Start demo data generation."""
        self.running = True

        # Initialize with some starting values
        portfolio_value = 100000
        total_pnl = 0
        daily_pnl = 0
        positions = {}

        while self.running:
            try:
                # Generate sample performance metrics
                daily_return = random.normalvariate(0.001, 0.02)  # ~20% annual vol
                daily_pnl = portfolio_value * daily_return
                total_pnl += daily_pnl
                portfolio_value += daily_pnl

                performance_metrics = {
                    'total_pnl': total_pnl,
                    'daily_pnl': daily_pnl,
                    'portfolio_value': portfolio_value,
                    'total_return': total_pnl / 100000,
                    'current_drawdown': max(0, random.uniform(0, 0.05)),
                    'max_drawdown': random.uniform(0.02, 0.08),
                    'daily_return': daily_return
                }

                self.dashboard.update_performance(performance_metrics)

                # Generate sample positions
                symbols = ['BTC-USDT', 'ETH-USDT', 'BNB-USDT', 'ADA-USDT', 'SOL-USDT']
                positions = {}
                total_exposure = 0

                for symbol in symbols[:random.randint(2, 5)]:
                    value = random.uniform(1000, 15000)
                    positions[symbol] = {'usd_value': value}
                    total_exposure += value

                leverage = total_exposure / portfolio_value if portfolio_value > 0 else 0
                self.dashboard.update_positions(positions, total_exposure, leverage)

                # Generate sample execution
                if random.random() < 0.3:  # 30% chance of execution
                    symbol = random.choice(symbols)
                    side = random.choice(['BUY', 'SELL'])
                    quantity = random.uniform(0.1, 5.0)
                    market_price = random.uniform(20000, 50000)
                    execution_price = market_price * (1 + random.normalvariate(0, 0.0001))

                    self.dashboard.update_execution(symbol, side, quantity, market_price, execution_price)

                # Generate sample risk metrics
                risk_data = {
                    'risk_level': random.choice(['LOW', 'MEDIUM', 'HIGH']),
                    'var_95_1d': random.uniform(0.01, 0.05),
                    'expected_shortfall': random.uniform(0.015, 0.08),
                    'correlation_status': random.choice(['NORMAL', 'ELEVATED', 'HIGH']),
                    'risk_violations': [],
                    'leverage': leverage,
                    'current_drawdown': performance_metrics['current_drawdown']
                }

                if random.random() < 0.1:  # 10% chance of risk violation
                    risk_data['risk_violations'] = ['Position size limit exceeded']

                self.dashboard.update_risk(risk_data)

                # Generate sample alerts
                if random.random() < 0.05:  # 5% chance of alert
                    alert_types = [
                        ('performance_divergence', 'warning', 'Performance deviating from target'),
                        ('correlation_spike', 'warning', 'High correlation detected'),
                        ('drawdown_warning', 'critical', 'Drawdown threshold exceeded'),
                        ('execution_failure', 'warning', 'Order execution failed')
                    ]

                    alert_type, severity, message = random.choice(alert_types)
                    alert_data = {
                        'type': alert_type,
                        'severity': severity,
                        'message': message,
                        'timestamp': time.time()
                    }

                    self.dashboard.add_alert(alert_data)

                # Wait before next update
                await asyncio.sleep(2)  # Update every 2 seconds for demo

            except Exception as e:
                logging.error(f"Error in demo data generation: {e}")
                await asyncio.sleep(5)

    def stop_demo(self):
        """Stop demo data generation."""
        self.running = False


async def main():
    """Main function to run the dashboard."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

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
        'update_interval': 3  # WebSocket update interval in seconds
    }

    # Choose port
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}, using default 8080")

    print(f"Starting Statistical Arbitrage Dashboard on port {port}")
    print(f"Open your browser to: http://localhost:{port}")
    print("Press Ctrl+C to stop")

    # Create and start dashboard
    dashboard = WebDashboard(config, port)
    demo = DashboardDemo(dashboard)
    runner = None

    try:
        # Start web server
        runner = await dashboard.start_server()

        # Start demo data generation
        demo_task = asyncio.create_task(demo.start_demo())

        print("\nDashboard is running with live demo data!")
        print("Features:")
        print("- Real-time performance charts")
        print("- Live position monitoring")
        print("- Execution quality metrics")
        print("- Risk monitoring")
        print("- Alert system")
        print("- WebSocket real-time updates")

        # Keep running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        demo.stop_demo()
        if 'demo_task' in locals():
            demo_task.cancel()
            try:
                await demo_task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logging.error(f"Dashboard error: {e}")

    finally:
        if runner:
            await dashboard.stop_server(runner)

if __name__ == "__main__":
    asyncio.run(main())