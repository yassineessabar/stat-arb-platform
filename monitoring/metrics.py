"""
Trading Metrics and Monitoring
==============================

Real-time metrics collection and monitoring for the stat-arb strategy:
- Execution metrics (fills, slippage, latency)
- Strategy performance tracking
- Risk monitoring
- Live vs backtest divergence analysis

Key metrics to track from the v6 notebook validation:
- Realized vs target volatility
- Correlation spikes
- Turnover decay
- PnL factor stability
- Drawdown speed
"""

import time
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ExecutionMetrics:
    """Track execution-related metrics."""

    def __init__(self, lookback_window: int = 1000):
        """
        Initialize execution metrics tracker.

        Args:
            lookback_window: Number of recent executions to track
        """
        self.lookback_window = lookback_window

        # Execution tracking
        self.executions = deque(maxlen=lookback_window)
        self.failures = deque(maxlen=lookback_window)

        # Real-time counters
        self.total_executions = 0
        self.total_failures = 0
        self.total_volume_usd = 0.0

        logger.debug("Execution metrics initialized")

    def record_execution(self, symbol: str, side: str, quantity: float,
                        market_price: float, execution_price: float) -> None:
        """
        Record successful execution.

        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            quantity: Executed quantity
            market_price: Market price at order time
            execution_price: Actual execution price
        """
        execution = {
            'timestamp': time.time(),
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'market_price': market_price,
            'execution_price': execution_price,
            'slippage_bps': self._calculate_slippage_bps(market_price, execution_price, side),
            'notional_usd': quantity * execution_price
        }

        self.executions.append(execution)
        self.total_executions += 1
        self.total_volume_usd += execution['notional_usd']

        logger.debug(f"Execution recorded: {symbol} {side} {quantity:.6f} @ ${execution_price}")

    def record_execution_failure(self, symbol: str, error_message: str) -> None:
        """
        Record execution failure.

        Args:
            symbol: Trading symbol
            error_message: Error description
        """
        failure = {
            'timestamp': time.time(),
            'symbol': symbol,
            'error': error_message
        }

        self.failures.append(failure)
        self.total_failures += 1

        logger.warning(f"Execution failure recorded: {symbol} - {error_message}")

    def _calculate_slippage_bps(self, market_price: float, execution_price: float, side: str) -> float:
        """Calculate slippage in basis points."""
        if side == 'BUY':
            # Positive slippage = paid more than market
            slippage = (execution_price - market_price) / market_price
        else:
            # Positive slippage = received less than market
            slippage = (market_price - execution_price) / market_price

        return slippage * 10000  # Convert to basis points

    def get_summary(self) -> Dict:
        """Get execution metrics summary."""
        if not self.executions:
            return {
                'total_executions': 0,
                'success_rate': 0.0,
                'avg_slippage_bps': 0.0,
                'total_volume_usd': 0.0
            }

        slippages = [ex['slippage_bps'] for ex in self.executions]
        recent_executions = len(self.executions)
        recent_failures = len(self.failures)

        success_rate = recent_executions / max(recent_executions + recent_failures, 1)

        return {
            'total_executions': self.total_executions,
            'recent_executions': recent_executions,
            'success_rate': success_rate,
            'avg_slippage_bps': np.mean(slippages),
            'max_slippage_bps': np.max(slippages),
            'total_volume_usd': self.total_volume_usd,
            'recent_volume_usd': sum(ex['notional_usd'] for ex in self.executions)
        }


class StrategyMetrics:
    """Track strategy performance metrics."""

    def __init__(self, target_metrics: Dict):
        """
        Initialize strategy metrics tracker.

        Args:
            target_metrics: Target metrics from v6 validation
        """
        self.target_metrics = target_metrics

        # Performance tracking
        self.daily_pnl = []
        self.equity_curve = [100000]  # Start with 100k
        self.drawdown_series = []

        # Real-time metrics
        self.current_positions = {}
        self.daily_turnover = deque(maxlen=30)  # 30-day turnover
        self.correlation_history = deque(maxlen=100)

        # v6 validation targets
        self.target_sharpe = target_metrics.get('sharpe', 1.0)
        self.target_vol = target_metrics.get('annual_vol', 0.20)
        self.max_expected_dd = target_metrics.get('max_drawdown', 0.15)

        logger.info(f"Strategy metrics initialized: target Sharpe={self.target_sharpe:.2f}")

    def record_daily_pnl(self, pnl: float, positions: Dict[str, float]) -> None:
        """
        Record daily PnL and positions.

        Args:
            pnl: Daily PnL in USD
            positions: Current positions by symbol
        """
        self.daily_pnl.append({
            'timestamp': time.time(),
            'pnl': pnl,
            'date': pd.Timestamp.now().date()
        })

        # Update equity curve
        new_equity = self.equity_curve[-1] + pnl
        self.equity_curve.append(new_equity)

        # Calculate drawdown
        peak_equity = max(self.equity_curve)
        current_dd = (peak_equity - new_equity) / peak_equity
        self.drawdown_series.append(current_dd)

        # Update positions
        self.current_positions = positions.copy()

        logger.debug(f"Daily PnL recorded: ${pnl:,.2f}, equity: ${new_equity:,.0f}")

    def record_turnover(self, turnover_usd: float) -> None:
        """Record daily turnover."""
        self.daily_turnover.append({
            'timestamp': time.time(),
            'turnover': turnover_usd
        })

    def record_correlation(self, avg_correlation: float) -> None:
        """Record average pair correlation."""
        self.correlation_history.append({
            'timestamp': time.time(),
            'correlation': avg_correlation
        })

    def get_live_performance(self) -> Dict:
        """Calculate live performance metrics."""
        if len(self.daily_pnl) < 2:
            return {'error': 'Insufficient data'}

        pnl_series = pd.Series([p['pnl'] for p in self.daily_pnl])

        # Annualized metrics
        daily_return = pnl_series.mean()
        daily_vol = pnl_series.std()

        annual_return = daily_return * 365
        annual_vol = daily_vol * np.sqrt(365)

        sharpe_ratio = annual_return / annual_vol if annual_vol > 0 else 0
        current_dd = self.drawdown_series[-1] if self.drawdown_series else 0

        # Calculate divergence from targets
        sharpe_divergence = sharpe_ratio - self.target_sharpe
        vol_divergence = annual_vol - self.target_vol

        return {
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe_ratio,
            'current_drawdown': current_dd,
            'max_drawdown': max(self.drawdown_series) if self.drawdown_series else 0,
            'total_pnl': sum(p['pnl'] for p in self.daily_pnl),
            'n_observations': len(self.daily_pnl),
            'sharpe_divergence': sharpe_divergence,
            'vol_divergence': vol_divergence
        }

    def get_regime_indicators(self) -> Dict:
        """Get regime change indicators."""
        if len(self.correlation_history) < 10:
            return {'correlation_spike': False, 'correlation_level': 0}

        recent_corr = [c['correlation'] for c in list(self.correlation_history)[-10:]]
        avg_recent_corr = np.mean(recent_corr)

        # Correlation spike if above 0.8
        correlation_spike = avg_recent_corr > 0.8

        return {
            'correlation_spike': correlation_spike,
            'correlation_level': avg_recent_corr,
            'correlation_trend': recent_corr[-1] - recent_corr[0] if len(recent_corr) >= 2 else 0
        }


class LiveMonitor:
    """Comprehensive live trading monitor."""

    def __init__(self, config: Dict):
        """
        Initialize live monitor.

        Args:
            config: Configuration dictionary
        """
        self.config = config

        # Component metrics
        self.execution_metrics = ExecutionMetrics()
        self.strategy_metrics = StrategyMetrics(config.get('targets', {}))

        # Alert thresholds
        self.performance_alert_threshold = 0.10  # 10% performance divergence
        self.risk_alert_threshold = 0.08         # 8% drawdown
        self.correlation_alert_threshold = 0.85   # 85% correlation

        # Monitoring state
        self.alerts_sent = defaultdict(int)
        self.last_alert_time = defaultdict(float)
        self.alert_cooldown = 3600  # 1 hour between same alerts

        logger.info("Live monitor initialized")

    def update_execution(self, symbol: str, side: str, quantity: float,
                        market_price: float, execution_price: float) -> None:
        """Update execution metrics."""
        self.execution_metrics.record_execution(symbol, side, quantity, market_price, execution_price)

    def update_strategy_performance(self, pnl: float, positions: Dict[str, float]) -> None:
        """Update strategy performance."""
        self.strategy_metrics.record_daily_pnl(pnl, positions)

    def update_market_regime(self, correlation: float, volatility: float) -> None:
        """Update market regime indicators."""
        self.strategy_metrics.record_correlation(correlation)

    def check_alerts(self) -> List[Dict]:
        """Check for alert conditions."""
        alerts = []

        # Performance alerts
        perf_metrics = self.strategy_metrics.get_live_performance()
        if 'sharpe_divergence' in perf_metrics:
            if abs(perf_metrics['sharpe_divergence']) > self.performance_alert_threshold:
                if self._should_send_alert('performance_divergence'):
                    alerts.append({
                        'type': 'performance_divergence',
                        'severity': 'warning',
                        'message': f"Sharpe divergence: {perf_metrics['sharpe_divergence']:+.2f}",
                        'data': perf_metrics
                    })

        # Drawdown alerts
        if 'current_drawdown' in perf_metrics:
            if perf_metrics['current_drawdown'] > self.risk_alert_threshold:
                if self._should_send_alert('drawdown_warning'):
                    alerts.append({
                        'type': 'drawdown_warning',
                        'severity': 'critical',
                        'message': f"Drawdown alert: {perf_metrics['current_drawdown']:.1%}",
                        'data': perf_metrics
                    })

        # Regime alerts
        regime = self.strategy_metrics.get_regime_indicators()
        if regime['correlation_spike']:
            if self._should_send_alert('correlation_spike'):
                alerts.append({
                    'type': 'correlation_spike',
                    'severity': 'warning',
                    'message': f"Correlation spike: {regime['correlation_level']:.1%}",
                    'data': regime
                })

        return alerts

    def _should_send_alert(self, alert_type: str) -> bool:
        """Check if alert should be sent based on cooldown."""
        last_time = self.last_alert_time.get(alert_type, 0)
        current_time = time.time()

        if current_time - last_time > self.alert_cooldown:
            self.last_alert_time[alert_type] = current_time
            self.alerts_sent[alert_type] += 1
            return True

        return False

    def get_dashboard_data(self) -> Dict:
        """Get comprehensive data for monitoring dashboard."""
        return {
            'execution': self.execution_metrics.get_summary(),
            'strategy': self.strategy_metrics.get_live_performance(),
            'regime': self.strategy_metrics.get_regime_indicators(),
            'alerts': self.check_alerts(),
            'timestamp': time.time()
        }

    def get_health_check(self) -> Dict:
        """Get system health check."""
        exec_summary = self.execution_metrics.get_summary()
        strategy_summary = self.strategy_metrics.get_live_performance()

        health_score = 100
        issues = []

        # Check execution health
        if exec_summary['success_rate'] < 0.95:
            health_score -= 20
            issues.append(f"Low success rate: {exec_summary['success_rate']:.1%}")

        if exec_summary.get('avg_slippage_bps', 0) > 10:
            health_score -= 15
            issues.append(f"High slippage: {exec_summary['avg_slippage_bps']:.1f} bps")

        # Check strategy health
        if 'current_drawdown' in strategy_summary:
            if strategy_summary['current_drawdown'] > 0.05:
                health_score -= 25
                issues.append(f"Drawdown: {strategy_summary['current_drawdown']:.1%}")

        # Check divergence
        if 'sharpe_divergence' in strategy_summary:
            if abs(strategy_summary['sharpe_divergence']) > 0.5:
                health_score -= 20
                issues.append("Significant performance divergence")

        health_status = 'healthy' if health_score >= 80 else 'warning' if health_score >= 60 else 'critical'

        return {
            'health_score': max(health_score, 0),
            'status': health_status,
            'issues': issues,
            'timestamp': time.time()
        }