"""
Real-Time Web Dashboard for Statistical Arbitrage Platform
=========================================================

Web-based dashboard providing real-time monitoring and visualization
of trading operations, performance metrics, and system health.

Features:
- Real-time performance metrics and charts
- Live position and risk monitoring
- Execution quality tracking
- Interactive data visualization
- Mobile-responsive interface
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

import aiohttp
from aiohttp import web, WSMsgType
import aiohttp_cors
import numpy as np

from .dashboard import TradingDashboard
from .metrics import LiveMonitor

logger = logging.getLogger(__name__)


class WebDashboard:
    """Web-based trading dashboard server."""

    def __init__(self, config: Dict, port: int = 8080):
        """
        Initialize web dashboard.

        Args:
            config: Dashboard configuration
            port: Server port
        """
        self.config = config
        self.port = port

        # Core components
        self.dashboard = TradingDashboard(config.get('dashboard', {}))
        self.monitor = LiveMonitor(config.get('monitoring', {}))

        # Web components
        self.app = web.Application()
        self.websocket_connections = set()

        # Update interval
        self.update_interval = config.get('update_interval', 5)  # 5 seconds
        self.update_task = None

        # Setup routes
        self._setup_routes()
        self._setup_cors()

        logger.info(f"Web dashboard initialized on port {port}")

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_get('/', self._serve_dashboard)
        self.app.router.add_get('/api/status', self._api_status)
        self.app.router.add_get('/api/dashboard', self._api_dashboard)
        self.app.router.add_get('/api/performance', self._api_performance)
        self.app.router.add_get('/api/positions', self._api_positions)
        self.app.router.add_get('/api/execution', self._api_execution)
        self.app.router.add_get('/api/alerts', self._api_alerts)
        self.app.router.add_get('/ws', self._websocket_handler)

    def _setup_cors(self):
        """Setup CORS for API access."""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        # Add CORS to all routes
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def _serve_dashboard(self, request):
        """Serve main dashboard HTML."""
        html_content = self._generate_dashboard_html()
        return web.Response(text=html_content, content_type='text/html')

    async def _api_status(self, request):
        """API endpoint for system status."""
        health_check = self.monitor.get_health_check()
        return web.json_response(health_check)

    async def _api_dashboard(self, request):
        """API endpoint for complete dashboard data."""
        dashboard_data = self.dashboard.get_dashboard_data()
        monitor_data = self.monitor.get_dashboard_data()

        combined_data = {
            **dashboard_data,
            'monitoring': monitor_data,
            'timestamp': datetime.now().isoformat()
        }

        return web.json_response(json.loads(json.dumps(combined_data, default=self._json_serializer)))

    async def _api_performance(self, request):
        """API endpoint for performance charts."""
        hours = int(request.query.get('hours', 24))
        chart_data = self.dashboard.get_performance_chart_data(hours)
        return web.json_response(json.loads(json.dumps(chart_data, default=self._json_serializer)))

    async def _api_positions(self, request):
        """API endpoint for position data."""
        position_data = self.dashboard.get_position_chart_data()
        return web.json_response(position_data)

    async def _api_execution(self, request):
        """API endpoint for execution analytics."""
        execution_data = self.dashboard.get_execution_analytics()
        return web.json_response(json.loads(json.dumps(execution_data, default=self._json_serializer)))

    async def _api_alerts(self, request):
        """API endpoint for alerts."""
        alerts = self.monitor.check_alerts()
        return web.json_response({'alerts': alerts})

    async def _websocket_handler(self, request):
        """WebSocket handler for real-time updates."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websocket_connections.add(ws)
        logger.debug("WebSocket connection established")

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    # Handle incoming WebSocket messages if needed
                    pass
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            self.websocket_connections.discard(ws)
            logger.debug("WebSocket connection closed")

        return ws

    async def _broadcast_update(self):
        """Broadcast updates to all WebSocket connections."""
        if not self.websocket_connections:
            return

        try:
            # Get latest data
            dashboard_data = self.dashboard.get_dashboard_data()
            monitor_data = self.monitor.get_dashboard_data()

            update_data = {
                'type': 'dashboard_update',
                'data': {
                    **dashboard_data,
                    'monitoring': monitor_data
                },
                'timestamp': datetime.now().isoformat()
            }

            # Send to all connected clients
            message = json.dumps(update_data, default=self._json_serializer)
            disconnected = set()

            for ws in self.websocket_connections:
                try:
                    await ws.send_str(message)
                except ConnectionResetError:
                    disconnected.add(ws)

            # Remove disconnected clients
            self.websocket_connections -= disconnected

        except Exception as e:
            logger.error(f"Error broadcasting update: {e}")

    async def _update_loop(self):
        """Main update loop for real-time data."""
        while True:
            try:
                await self._broadcast_update()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(self.update_interval)

    def _json_serializer(self, obj):
        """JSON serializer for numpy and datetime objects."""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object {obj} of type {type(obj)} is not JSON serializable")

    def _generate_dashboard_html(self) -> str:
        """Generate complete dashboard HTML."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Statistical Arbitrage Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            color: #e0e0e0;
        }

        .dashboard {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding: 20px 0;
            border-bottom: 1px solid #333;
        }

        .title {
            color: #fff;
            font-size: 28px;
            font-weight: 600;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #4CAF50;
        }

        .status-dot.warning { background: #FF9800; }
        .status-dot.critical { background: #f44336; }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .grid-3 {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: #2a2a2a;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #3a3a3a;
        }

        .card h3 {
            margin: 0 0 15px 0;
            color: #fff;
            font-size: 18px;
        }

        .metric {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #333;
        }

        .metric:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }

        .metric-label {
            color: #b0b0b0;
        }

        .metric-value {
            color: #fff;
            font-weight: 600;
        }

        .metric-value.positive { color: #4CAF50; }
        .metric-value.negative { color: #f44336; }

        .chart-container {
            position: relative;
            height: 300px;
            margin-top: 15px;
        }

        .alerts {
            background: #2a2a2a;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #3a3a3a;
            margin-bottom: 20px;
        }

        .alert {
            padding: 10px 15px;
            border-radius: 6px;
            margin-bottom: 10px;
            border-left: 4px solid #4CAF50;
        }

        .alert.warning {
            background: rgba(255, 152, 0, 0.1);
            border-left-color: #FF9800;
        }

        .alert.critical {
            background: rgba(244, 67, 54, 0.1);
            border-left-color: #f44336;
        }

        .loading {
            text-align: center;
            color: #b0b0b0;
            font-style: italic;
        }

        @media (max-width: 768px) {
            .grid, .grid-3 {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="dashboard">
        <div class="header">
            <h1 class="title">Statistical Arbitrage Dashboard</h1>
            <div class="status-indicator">
                <div class="status-dot" id="statusDot"></div>
                <span id="systemStatus">Connecting...</span>
            </div>
        </div>

        <div id="alertsContainer" class="alerts" style="display: none;">
            <h3>Active Alerts</h3>
            <div id="alertsList"></div>
        </div>

        <div class="grid-3">
            <div class="card">
                <h3>Performance</h3>
                <div id="performanceMetrics" class="loading">Loading...</div>
            </div>

            <div class="card">
                <h3>Risk Metrics</h3>
                <div id="riskMetrics" class="loading">Loading...</div>
            </div>

            <div class="card">
                <h3>Execution Quality</h3>
                <div id="executionMetrics" class="loading">Loading...</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Portfolio Performance</h3>
                <div class="chart-container">
                    <canvas id="performanceChart"></canvas>
                </div>
            </div>

            <div class="card">
                <h3>Position Distribution</h3>
                <div class="chart-container">
                    <canvas id="positionsChart"></canvas>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>System Health</h3>
                <div id="systemHealth" class="loading">Loading...</div>
            </div>

            <div class="card">
                <h3>Recent Activity</h3>
                <div id="recentActivity" class="loading">Loading...</div>
            </div>
        </div>
    </div>

    <script>
        class TradingDashboard {
            constructor() {
                this.ws = null;
                this.charts = {};
                this.reconnectAttempts = 0;
                this.maxReconnectAttempts = 5;

                this.init();
            }

            async init() {
                await this.loadInitialData();
                this.initCharts();
                this.connectWebSocket();

                // Refresh data every 10 seconds as fallback
                setInterval(() => this.loadInitialData(), 10000);
            }

            async loadInitialData() {
                try {
                    const response = await fetch('/api/dashboard');
                    const data = await response.json();
                    this.updateDashboard(data);
                } catch (error) {
                    console.error('Error loading initial data:', error);
                }
            }

            connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;

                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                    this.updateStatus('connected', 'CONNECTED');
                };

                this.ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        if (message.type === 'dashboard_update') {
                            this.updateDashboard(message.data);
                        }
                    } catch (error) {
                        console.error('Error parsing WebSocket message:', error);
                    }
                };

                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.updateStatus('warning', 'DISCONNECTED');
                    this.scheduleReconnect();
                };

                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.updateStatus('critical', 'ERROR');
                };
            }

            scheduleReconnect() {
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    setTimeout(() => this.connectWebSocket(), 5000);
                }
            }

            initCharts() {
                // Performance chart
                const performanceCtx = document.getElementById('performanceChart').getContext('2d');
                this.charts.performance = new Chart(performanceCtx, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: 'Portfolio Value',
                            data: [],
                            borderColor: '#4CAF50',
                            backgroundColor: 'rgba(76, 175, 80, 0.1)',
                            tension: 0.3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: {
                                type: 'time',
                                time: { unit: 'hour' }
                            },
                            y: {
                                beginAtZero: false
                            }
                        }
                    }
                });

                // Positions chart
                const positionsCtx = document.getElementById('positionsChart').getContext('2d');
                this.charts.positions = new Chart(positionsCtx, {
                    type: 'doughnut',
                    data: {
                        labels: [],
                        datasets: [{
                            data: [],
                            backgroundColor: [
                                '#4CAF50', '#2196F3', '#FF9800', '#E91E63',
                                '#9C27B0', '#00BCD4', '#8BC34A', '#FF5722'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right'
                            }
                        }
                    }
                });
            }

            updateDashboard(data) {
                this.updatePerformanceMetrics(data.performance_summary || {});
                this.updateRiskMetrics(data.risk_summary || {});
                this.updateExecutionMetrics(data.execution_quality || {});
                this.updateSystemHealth(data.system_health || {});
                this.updateRecentActivity(data.recent_activity || []);
                this.updateAlerts(data.alerts || []);
                this.updateCharts(data);

                // Update system status
                const health = data.system_health || {};
                const status = health.status || 'UNKNOWN';
                this.updateStatus(status.toLowerCase(), status);
            }

            updatePerformanceMetrics(performance) {
                const container = document.getElementById('performanceMetrics');
                container.innerHTML = `
                    <div class="metric">
                        <span class="metric-label">Total PnL</span>
                        <span class="metric-value ${performance.total_pnl >= 0 ? 'positive' : 'negative'}">
                            $${this.formatNumber(performance.total_pnl)}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Daily PnL</span>
                        <span class="metric-value ${performance.daily_pnl >= 0 ? 'positive' : 'negative'}">
                            $${this.formatNumber(performance.daily_pnl)}
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Sharpe Ratio</span>
                        <span class="metric-value">${(performance.sharpe_ratio || 0).toFixed(2)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Current DD</span>
                        <span class="metric-value negative">${(performance.current_drawdown * 100 || 0).toFixed(1)}%</span>
                    </div>
                `;
            }

            updateRiskMetrics(risk) {
                const container = document.getElementById('riskMetrics');
                container.innerHTML = `
                    <div class="metric">
                        <span class="metric-label">Risk Level</span>
                        <span class="metric-value">${risk.risk_level || 'UNKNOWN'}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">VaR (95%)</span>
                        <span class="metric-value">${(risk.var_95 * 100 || 0).toFixed(2)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Leverage</span>
                        <span class="metric-value">${(risk.leverage_utilization * 100 || 0).toFixed(1)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Violations</span>
                        <span class="metric-value">${risk.violations ? risk.violations.length : 0}</span>
                    </div>
                `;
            }

            updateExecutionMetrics(execution) {
                const container = document.getElementById('executionMetrics');
                container.innerHTML = `
                    <div class="metric">
                        <span class="metric-label">Avg Slippage</span>
                        <span class="metric-value">${(execution.avg_slippage_bps || 0).toFixed(1)} bps</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Fill Rate</span>
                        <span class="metric-value">${(execution.fill_rate * 100 || 0).toFixed(1)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Executions (1h)</span>
                        <span class="metric-value">${execution.last_hour_executions || 0}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Total Executions</span>
                        <span class="metric-value">${execution.total_executions || 0}</span>
                    </div>
                `;
            }

            updateSystemHealth(health) {
                const container = document.getElementById('systemHealth');
                container.innerHTML = `
                    <div class="metric">
                        <span class="metric-label">Health Score</span>
                        <span class="metric-value">${health.health_score || 0}/100</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Uptime</span>
                        <span class="metric-value">${this.formatDuration(health.uptime || 0)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Data Points</span>
                        <span class="metric-value">${Object.values(health.data_points || {}).reduce((a, b) => a + b, 0)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Issues</span>
                        <span class="metric-value">${health.issues ? health.issues.length : 0}</span>
                    </div>
                `;
            }

            updateRecentActivity(activities) {
                const container = document.getElementById('recentActivity');
                if (!activities || activities.length === 0) {
                    container.innerHTML = '<div class="loading">No recent activity</div>';
                    return;
                }

                const activityHtml = activities.slice(0, 5).map(activity => `
                    <div class="metric">
                        <span class="metric-label">${activity.type}</span>
                        <span class="metric-value">${new Date(activity.timestamp * 1000).toLocaleTimeString()}</span>
                    </div>
                    <div style="font-size: 12px; color: #b0b0b0; margin-bottom: 10px;">
                        ${activity.description}
                    </div>
                `).join('');

                container.innerHTML = activityHtml;
            }

            updateAlerts(alerts) {
                const container = document.getElementById('alertsContainer');
                const alertsList = document.getElementById('alertsList');

                if (!alerts || alerts.length === 0) {
                    container.style.display = 'none';
                    return;
                }

                container.style.display = 'block';
                const alertsHtml = alerts.map(alert => `
                    <div class="alert ${alert.severity}">
                        <strong>${alert.type.toUpperCase()}:</strong> ${alert.message}
                    </div>
                `).join('');

                alertsList.innerHTML = alertsHtml;
            }

            async updateCharts(data) {
                // Update performance chart
                try {
                    const response = await fetch('/api/performance?hours=24');
                    const perfData = await response.json();

                    if (perfData.timestamps && perfData.values) {
                        const chartData = perfData.timestamps.map((timestamp, i) => ({
                            x: new Date(timestamp * 1000),
                            y: perfData.values[i]
                        }));

                        this.charts.performance.data.datasets[0].data = chartData;
                        this.charts.performance.update('none');
                    }
                } catch (error) {
                    console.error('Error updating performance chart:', error);
                }

                // Update positions chart
                try {
                    const response = await fetch('/api/positions');
                    const posData = await response.json();

                    if (posData.labels && posData.values) {
                        this.charts.positions.data.labels = posData.labels;
                        this.charts.positions.data.datasets[0].data = posData.values;
                        this.charts.positions.update('none');
                    }
                } catch (error) {
                    console.error('Error updating positions chart:', error);
                }
            }

            updateStatus(level, text) {
                const dot = document.getElementById('statusDot');
                const status = document.getElementById('systemStatus');

                dot.className = `status-dot ${level}`;
                status.textContent = text;
            }

            formatNumber(value) {
                if (value === undefined || value === null) return '0.00';
                return Math.abs(value) > 1000 ?
                    (value / 1000).toFixed(1) + 'K' :
                    value.toFixed(2);
            }

            formatDuration(seconds) {
                const hours = Math.floor(seconds / 3600);
                const minutes = Math.floor((seconds % 3600) / 60);
                return `${hours}h ${minutes}m`;
            }
        }

        // Initialize dashboard when page loads
        document.addEventListener('DOMContentLoaded', () => {
            new TradingDashboard();
        });
    </script>
</body>
</html>'''

    async def start_server(self):
        """Start the web dashboard server."""
        try:
            # Start update task
            self.update_task = asyncio.create_task(self._update_loop())

            # Start web server
            runner = web.AppRunner(self.app)
            await runner.setup()

            site = web.TCPSite(runner, '0.0.0.0', self.port)
            await site.start()

            logger.info(f"Dashboard server started on http://localhost:{self.port}")

            return runner

        except Exception as e:
            logger.error(f"Failed to start dashboard server: {e}")
            raise

    async def stop_server(self, runner):
        """Stop the web dashboard server."""
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        await runner.cleanup()
        logger.info("Dashboard server stopped")

    # Data update methods for live trading integration
    def update_performance(self, metrics: Dict):
        """Update performance metrics."""
        self.dashboard.update_performance_metrics(metrics)

    def update_positions(self, positions: Dict, total_exposure: float, leverage: float):
        """Update position data."""
        self.dashboard.update_position_data(positions, total_exposure, leverage)

    def update_execution(self, symbol: str, side: str, quantity: float,
                        market_price: float, execution_price: float):
        """Update execution metrics."""
        execution_data = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'market_price': market_price,
            'execution_price': execution_price,
            'slippage_bps': abs((execution_price - market_price) / market_price) * 10000,
            'notional_usd': quantity * execution_price,
            'execution_time': 0.1,  # Placeholder
            'filled': True
        }
        self.dashboard.update_execution_metrics(execution_data)
        self.monitor.update_execution(symbol, side, quantity, market_price, execution_price)

    def update_risk(self, risk_data: Dict):
        """Update risk metrics."""
        self.dashboard.update_risk_metrics(risk_data)

    def add_alert(self, alert_data: Dict):
        """Add alert to dashboard."""
        self.dashboard.add_alert(alert_data)


async def run_dashboard(config: Dict, port: int = 8080):
    """
    Run the web dashboard server.

    Args:
        config: Configuration dictionary
        port: Server port
    """
    dashboard = WebDashboard(config, port)
    runner = None

    try:
        runner = await dashboard.start_server()

        # Keep server running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down dashboard...")
    finally:
        if runner:
            await dashboard.stop_server(runner)


if __name__ == "__main__":
    # Sample configuration
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
        'update_interval': 5  # WebSocket update interval
    }

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_dashboard(config))