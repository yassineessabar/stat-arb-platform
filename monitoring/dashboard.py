"""
Real-Time Trading Dashboard
==========================

Live monitoring dashboard for the statistical arbitrage platform:
- Real-time performance metrics and charts
- Position and risk monitoring
- Execution quality tracking
- Alert status and system health
- Strategy diagnostics and analysis

Provides comprehensive real-time visibility into all trading operations.
"""

import time
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from collections import deque, defaultdict

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class TradingDashboard:
    """
    Real-time trading dashboard with comprehensive monitoring.
    """

    def __init__(self, config: Dict):
        """
        Initialize trading dashboard.

        Args:
            config: Dashboard configuration
        """
        self.config = config

        # Data storage
        self.performance_history = deque(maxlen=1440)  # 24 hours at 1-min intervals
        self.execution_history = deque(maxlen=1000)    # Recent executions
        self.position_history = deque(maxlen=1440)     # Position snapshots
        self.risk_history = deque(maxlen=1440)         # Risk metrics
        self.alert_history = deque(maxlen=100)         # Recent alerts

        # Real-time metrics
        self.current_metrics = {}
        self.system_status = {}
        self.strategy_diagnostics = {}

        # Performance tracking
        self.session_start_time = time.time()
        self.last_update_time = 0

        # Dashboard state
        self.dashboard_enabled = config.get('enabled', True)
        self.update_interval = config.get('update_interval', 60)  # 1 minute

        logger.info("Trading dashboard initialized")

    def update_performance_metrics(self, metrics: Dict) -> None:
        """
        Update performance metrics.

        Args:
            metrics: Performance metrics dictionary
        """
        timestamp = time.time()

        # Add timestamp to metrics
        metrics['timestamp'] = timestamp
        metrics['session_duration'] = timestamp - self.session_start_time

        # Store in history
        self.performance_history.append(metrics)

        # Update current metrics
        self.current_metrics['performance'] = metrics

        logger.debug("Performance metrics updated")

    def update_position_data(self, positions: Dict, total_exposure: float,
                           leverage: float) -> None:
        """
        Update position data.

        Args:
            positions: Current positions {symbol: data}
            total_exposure: Total portfolio exposure
            leverage: Current leverage
        """
        position_data = {
            'timestamp': time.time(),
            'positions': positions,
            'total_exposure': total_exposure,
            'leverage': leverage,
            'num_positions': len(positions),
            'largest_position': max([abs(p.get('usd_value', 0)) for p in positions.values()]) if positions else 0
        }

        self.position_history.append(position_data)
        self.current_metrics['positions'] = position_data

    def update_execution_metrics(self, execution_data: Dict) -> None:
        """
        Update execution metrics.

        Args:
            execution_data: Execution data dictionary
        """
        timestamp = time.time()
        execution_data['timestamp'] = timestamp

        self.execution_history.append(execution_data)

        # Calculate execution quality metrics
        self._calculate_execution_quality()

    def _calculate_execution_quality(self) -> None:
        """Calculate execution quality metrics from recent executions."""
        recent_executions = list(self.execution_history)

        if not recent_executions:
            self.current_metrics['execution_quality'] = {
                'avg_slippage_bps': 0,
                'fill_rate': 0,
                'avg_execution_time': 0,
                'total_executions': 0
            }
            return

        # Calculate metrics
        slippages = [ex.get('slippage_bps', 0) for ex in recent_executions]
        execution_times = [ex.get('execution_time', 0) for ex in recent_executions]
        successful_fills = [ex for ex in recent_executions if ex.get('filled', True)]

        self.current_metrics['execution_quality'] = {
            'avg_slippage_bps': np.mean(slippages) if slippages else 0,
            'max_slippage_bps': np.max(slippages) if slippages else 0,
            'fill_rate': len(successful_fills) / len(recent_executions),
            'avg_execution_time': np.mean(execution_times) if execution_times else 0,
            'total_executions': len(recent_executions),
            'last_hour_executions': len([ex for ex in recent_executions
                                       if time.time() - ex['timestamp'] < 3600])
        }

    def update_risk_metrics(self, risk_data: Dict) -> None:
        """
        Update risk metrics.

        Args:
            risk_data: Risk metrics dictionary
        """
        risk_data['timestamp'] = time.time()
        self.risk_history.append(risk_data)
        self.current_metrics['risk'] = risk_data

    def update_system_status(self, status_data: Dict) -> None:
        """
        Update system status.

        Args:
            status_data: System status data
        """
        self.system_status = {
            **status_data,
            'timestamp': time.time(),
            'uptime': time.time() - self.session_start_time
        }

        self.current_metrics['system'] = self.system_status

    def add_alert(self, alert_data: Dict) -> None:
        """
        Add alert to dashboard.

        Args:
            alert_data: Alert information
        """
        alert_data['dashboard_timestamp'] = time.time()
        self.alert_history.append(alert_data)

    def get_dashboard_data(self) -> Dict:
        """
        Get complete dashboard data for display.

        Returns:
            Complete dashboard data dictionary
        """
        current_time = time.time()

        # Performance summary
        performance_summary = self._get_performance_summary()

        # Position summary
        position_summary = self._get_position_summary()

        # Risk summary
        risk_summary = self._get_risk_summary()

        # System health
        system_health = self._get_system_health()

        # Recent activity
        recent_activity = self._get_recent_activity()

        return {
            'timestamp': current_time,
            'session_duration': current_time - self.session_start_time,
            'performance_summary': performance_summary,
            'position_summary': position_summary,
            'risk_summary': risk_summary,
            'execution_quality': self.current_metrics.get('execution_quality', {}),
            'system_health': system_health,
            'recent_activity': recent_activity,
            'alerts': list(self.alert_history)[-10:],  # Last 10 alerts
            'strategy_diagnostics': self.strategy_diagnostics
        }

    def _get_performance_summary(self) -> Dict:
        """Get performance summary."""
        if not self.performance_history:
            return {
                'total_pnl': 0,
                'daily_pnl': 0,
                'realized_vol': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'current_drawdown': 0
            }

        recent_perf = list(self.performance_history)
        latest = recent_perf[-1]

        # Calculate daily performance
        day_ago = time.time() - 86400
        daily_start = next((p for p in reversed(recent_perf)
                          if p['timestamp'] <= day_ago), recent_perf[0])

        daily_pnl = latest.get('total_pnl', 0) - daily_start.get('total_pnl', 0)

        # Calculate volatility (last 30 data points)
        if len(recent_perf) >= 30:
            pnl_series = [p.get('total_pnl', 0) for p in recent_perf[-30:]]
            pnl_changes = np.diff(pnl_series)
            realized_vol = np.std(pnl_changes) * np.sqrt(1440)  # Annualized (1440 min/day)
        else:
            realized_vol = 0

        # Calculate Sharpe (simplified)
        if realized_vol > 0 and len(recent_perf) >= 10:
            avg_daily_return = np.mean([p.get('daily_return', 0) for p in recent_perf[-10:]])
            sharpe_ratio = (avg_daily_return * 365) / realized_vol
        else:
            sharpe_ratio = 0

        return {
            'total_pnl': latest.get('total_pnl', 0),
            'daily_pnl': daily_pnl,
            'realized_vol': realized_vol,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': latest.get('max_drawdown', 0),
            'current_drawdown': latest.get('current_drawdown', 0),
            'portfolio_value': latest.get('portfolio_value', 0),
            'total_return': latest.get('total_return', 0)
        }

    def _get_position_summary(self) -> Dict:
        """Get position summary."""
        if not self.position_history:
            return {
                'num_positions': 0,
                'total_exposure': 0,
                'leverage': 0,
                'largest_position': 0,
                'position_distribution': {}
            }

        latest_positions = self.position_history[-1]

        # Position distribution
        positions = latest_positions.get('positions', {})
        position_sizes = [abs(p.get('usd_value', 0)) for p in positions.values()]

        if position_sizes:
            distribution = {
                'small': len([p for p in position_sizes if p < 1000]),
                'medium': len([p for p in position_sizes if 1000 <= p < 10000]),
                'large': len([p for p in position_sizes if p >= 10000])
            }
        else:
            distribution = {'small': 0, 'medium': 0, 'large': 0}

        return {
            'num_positions': latest_positions.get('num_positions', 0),
            'total_exposure': latest_positions.get('total_exposure', 0),
            'leverage': latest_positions.get('leverage', 0),
            'largest_position': latest_positions.get('largest_position', 0),
            'position_distribution': distribution,
            'active_pairs': len(positions)
        }

    def _get_risk_summary(self) -> Dict:
        """Get risk summary."""
        if not self.risk_history:
            return {
                'risk_level': 'UNKNOWN',
                'var_95': 0,
                'expected_shortfall': 0,
                'correlation_status': 'UNKNOWN',
                'violations': []
            }

        latest_risk = self.risk_history[-1]

        return {
            'risk_level': latest_risk.get('risk_level', 'UNKNOWN'),
            'var_95': latest_risk.get('var_95_1d', 0),
            'expected_shortfall': latest_risk.get('expected_shortfall', 0),
            'correlation_status': latest_risk.get('correlation_status', 'UNKNOWN'),
            'violations': latest_risk.get('risk_violations', []),
            'leverage_utilization': latest_risk.get('leverage', 0) / 6.0,  # Assuming 6x max leverage
            'dd_from_peak': latest_risk.get('current_drawdown', 0)
        }

    def _get_system_health(self) -> Dict:
        """Get system health summary."""
        health_score = 100
        issues = []

        # Check data freshness
        current_time = time.time()
        if self.performance_history and current_time - self.performance_history[-1]['timestamp'] > 300:
            health_score -= 20
            issues.append("Stale performance data")

        # Check execution quality
        exec_quality = self.current_metrics.get('execution_quality', {})
        if exec_quality.get('fill_rate', 1) < 0.95:
            health_score -= 15
            issues.append("Low execution fill rate")

        if exec_quality.get('avg_slippage_bps', 0) > 10:
            health_score -= 10
            issues.append("High execution slippage")

        # Check recent alerts
        recent_alerts = [alert for alert in self.alert_history
                        if current_time - alert.get('timestamp', 0) < 3600]
        critical_alerts = [alert for alert in recent_alerts
                          if alert.get('severity') in ['critical', 'emergency']]

        if critical_alerts:
            health_score -= 25
            issues.append(f"{len(critical_alerts)} critical alerts")

        # Determine status
        if health_score >= 90:
            status = "EXCELLENT"
        elif health_score >= 80:
            status = "GOOD"
        elif health_score >= 70:
            status = "FAIR"
        elif health_score >= 60:
            status = "POOR"
        else:
            status = "CRITICAL"

        return {
            'health_score': max(health_score, 0),
            'status': status,
            'issues': issues,
            'uptime': current_time - self.session_start_time,
            'last_update': self.last_update_time,
            'data_points': {
                'performance': len(self.performance_history),
                'positions': len(self.position_history),
                'executions': len(self.execution_history),
                'risk_checks': len(self.risk_history)
            }
        }

    def _get_recent_activity(self) -> List[Dict]:
        """Get recent trading activity."""
        activities = []

        # Recent executions
        recent_executions = [ex for ex in self.execution_history
                           if time.time() - ex['timestamp'] < 3600]

        for execution in recent_executions[-5:]:  # Last 5 executions
            activities.append({
                'type': 'execution',
                'timestamp': execution['timestamp'],
                'description': f"Executed {execution.get('side', 'UNKNOWN')} {execution.get('symbol', 'UNKNOWN')}",
                'details': execution
            })

        # Recent alerts
        recent_alerts = [alert for alert in self.alert_history
                        if time.time() - alert.get('timestamp', 0) < 3600]

        for alert in recent_alerts[-5:]:  # Last 5 alerts
            activities.append({
                'type': 'alert',
                'timestamp': alert['timestamp'],
                'description': f"{alert.get('severity', '').upper()}: {alert.get('message', '')}",
                'details': alert
            })

        # Sort by timestamp (most recent first)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)

        return activities[:10]  # Return last 10 activities

    def get_performance_chart_data(self, hours: int = 24) -> Dict:
        """
        Get performance chart data.

        Args:
            hours: Number of hours to include

        Returns:
            Chart data dictionary
        """
        cutoff_time = time.time() - (hours * 3600)
        relevant_data = [p for p in self.performance_history
                        if p['timestamp'] > cutoff_time]

        if not relevant_data:
            return {'timestamps': [], 'values': [], 'drawdown': []}

        timestamps = [p['timestamp'] for p in relevant_data]
        portfolio_values = [p.get('portfolio_value', 0) for p in relevant_data]
        drawdowns = [p.get('current_drawdown', 0) for p in relevant_data]

        return {
            'timestamps': timestamps,
            'values': portfolio_values,
            'drawdown': drawdowns,
            'start_time': timestamps[0] if timestamps else time.time(),
            'end_time': timestamps[-1] if timestamps else time.time()
        }

    def get_position_chart_data(self) -> Dict:
        """Get position distribution chart data."""
        if not self.position_history:
            return {'labels': [], 'values': []}

        latest_positions = self.position_history[-1].get('positions', {})

        # Group by asset type or pair
        position_data = {}
        for symbol, data in latest_positions.items():
            usd_value = abs(data.get('usd_value', 0))
            if usd_value > 100:  # Only show significant positions
                position_data[symbol] = usd_value

        # Sort by size
        sorted_positions = sorted(position_data.items(), key=lambda x: x[1], reverse=True)

        return {
            'labels': [item[0] for item in sorted_positions[:10]],  # Top 10
            'values': [item[1] for item in sorted_positions[:10]]
        }

    def get_execution_analytics(self) -> Dict:
        """Get execution analytics."""
        if not self.execution_history:
            return {}

        recent_executions = list(self.execution_history)

        # Time-based analysis
        hourly_counts = defaultdict(int)
        for execution in recent_executions:
            hour = int(execution['timestamp'] // 3600)
            hourly_counts[hour] += 1

        # Symbol analysis
        symbol_counts = defaultdict(int)
        symbol_slippage = defaultdict(list)

        for execution in recent_executions:
            symbol = execution.get('symbol', 'UNKNOWN')
            symbol_counts[symbol] += 1
            symbol_slippage[symbol].append(execution.get('slippage_bps', 0))

        # Calculate averages
        symbol_stats = {}
        for symbol in symbol_counts:
            symbol_stats[symbol] = {
                'count': symbol_counts[symbol],
                'avg_slippage': np.mean(symbol_slippage[symbol])
            }

        return {
            'hourly_distribution': dict(hourly_counts),
            'symbol_stats': symbol_stats,
            'total_executions': len(recent_executions),
            'avg_execution_size': np.mean([ex.get('notional_usd', 0) for ex in recent_executions])
        }

    def export_dashboard_report(self, format: str = 'json') -> str:
        """
        Export dashboard data as a report.

        Args:
            format: Export format ('json', 'csv', 'summary')

        Returns:
            Formatted report string
        """
        dashboard_data = self.get_dashboard_data()

        if format == 'json':
            return json.dumps(dashboard_data, indent=2, default=str)

        elif format == 'summary':
            performance = dashboard_data['performance_summary']
            system = dashboard_data['system_health']

            summary = f"""
TRADING DASHBOARD SUMMARY
========================

Session Duration: {dashboard_data['session_duration'] / 3600:.1f} hours
System Health: {system['status']} ({system['health_score']}/100)

PERFORMANCE:
  Portfolio Value: ${performance['portfolio_value']:,.2f}
  Total PnL: ${performance['total_pnl']:,.2f}
  Daily PnL: ${performance['daily_pnl']:,.2f}
  Current Drawdown: {performance['current_drawdown']:.1%}
  Sharpe Ratio: {performance['sharpe_ratio']:.2f}

POSITIONS:
  Active Positions: {dashboard_data['position_summary']['num_positions']}
  Total Exposure: ${dashboard_data['position_summary']['total_exposure']:,.0f}
  Current Leverage: {dashboard_data['position_summary']['leverage']:.2f}x

RISK:
  Risk Level: {dashboard_data['risk_summary']['risk_level']}
  VaR (95%): {dashboard_data['risk_summary']['var_95']:.2%}
  Active Violations: {len(dashboard_data['risk_summary']['violations'])}

EXECUTION:
  Average Slippage: {dashboard_data['execution_quality'].get('avg_slippage_bps', 0):.1f} bps
  Fill Rate: {dashboard_data['execution_quality'].get('fill_rate', 0):.1%}
  Recent Executions: {dashboard_data['execution_quality'].get('last_hour_executions', 0)}
"""
            return summary.strip()

        else:
            raise ValueError(f"Unsupported format: {format}")

    def reset_session(self) -> None:
        """Reset dashboard session (for new trading session)."""
        self.session_start_time = time.time()
        self.performance_history.clear()
        self.execution_history.clear()
        self.position_history.clear()
        self.risk_history.clear()
        self.alert_history.clear()

        logger.info("Dashboard session reset")

    def update_strategy_diagnostics(self, diagnostics: Dict) -> None:
        """Update strategy diagnostics data."""
        self.strategy_diagnostics = {
            **diagnostics,
            'timestamp': time.time()
        }