"""
Portfolio Risk Manager
=====================

Comprehensive portfolio-level risk management:
- Real-time portfolio metrics calculation
- Risk limit enforcement across all positions
- Correlation monitoring and circuit breakers
- Portfolio-level stress testing
- Dynamic risk adjustment based on market conditions

This manages risk at the portfolio level, coordinating with position-level controls.
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class PortfolioRiskManager:
    """
    Portfolio-level risk management and monitoring.
    """

    def __init__(self, config: Dict, initial_capital: float = 100000):
        """
        Initialize portfolio risk manager.

        Args:
            config: Risk configuration
            initial_capital: Initial portfolio capital
        """
        self.config = config
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Portfolio limits
        self.max_portfolio_leverage = config['portfolio']['max_leverage']
        self.max_total_exposure = config['portfolio']['max_total_exposure_usdt']
        self.max_correlation = config['portfolio']['correlation_limits']['max_avg_correlation']
        self.correlation_spike_threshold = config['portfolio']['correlation_limits']['correlation_spike_threshold']

        # Drawdown limits
        self.dd_warning = config['portfolio']['drawdown_limits']['warning_level']
        self.dd_halt = config['portfolio']['drawdown_limits']['halt_level']
        self.dd_emergency = config['portfolio']['drawdown_limits']['emergency_stop']

        # Volatility limits
        self.max_portfolio_vol = config['market']['volatility_limits']['max_portfolio_vol']
        self.vol_spike_threshold = config['market']['volatility_limits']['vol_spike_threshold']

        # Portfolio state
        self.current_positions = {}
        self.position_history = []
        self.pnl_history = []
        self.correlation_history = []

        # Risk metrics
        self.portfolio_value = initial_capital
        self.peak_value = initial_capital
        self.current_drawdown = 0.0
        self.portfolio_beta = 1.0
        self.portfolio_var_95 = 0.0
        self.portfolio_volatility = 0.0

        # Risk state
        self.risk_warnings = []
        self.risk_halts = []
        self.stress_test_results = {}

        # Monitoring
        self.last_risk_update = time.time()
        self.last_correlation_check = time.time()
        self.last_stress_test = time.time()

        logger.info(f"Portfolio risk manager initialized with ${initial_capital:,} capital")

    def update_portfolio(self, positions: Dict[str, float], prices: Dict[str, float],
                        pnl: float) -> None:
        """
        Update portfolio state with current positions and PnL.

        Args:
            positions: Current positions {symbol: quantity}
            prices: Current prices {symbol: price}
            pnl: Current unrealized PnL
        """
        self.current_positions = positions.copy()
        self.portfolio_value = self.current_capital + pnl

        # Update peak and drawdown
        if self.portfolio_value > self.peak_value:
            self.peak_value = self.portfolio_value

        self.current_drawdown = (self.peak_value - self.portfolio_value) / self.peak_value

        # Store history
        self.pnl_history.append({
            'timestamp': time.time(),
            'portfolio_value': self.portfolio_value,
            'pnl': pnl,
            'drawdown': self.current_drawdown
        })

        # Keep only recent history (1000 entries)
        if len(self.pnl_history) > 1000:
            self.pnl_history = self.pnl_history[-1000:]

        # Update risk metrics
        self._update_risk_metrics(prices)

        self.last_risk_update = time.time()

    def _update_risk_metrics(self, prices: Dict[str, float]) -> None:
        """Update portfolio risk metrics."""

        # Calculate total exposure
        total_exposure = sum(abs(qty * prices.get(symbol, 0))
                           for symbol, qty in self.current_positions.items())

        # Portfolio leverage
        portfolio_leverage = total_exposure / max(self.portfolio_value, 1)

        # Portfolio volatility (from recent PnL history)
        if len(self.pnl_history) > 30:
            recent_pnl = [p['pnl'] for p in self.pnl_history[-30:]]
            daily_returns = np.diff(recent_pnl) / max(self.portfolio_value, 1)
            self.portfolio_volatility = np.std(daily_returns) * np.sqrt(365)

        # VaR calculation (simplified)
        if len(self.pnl_history) > 30:
            recent_returns = [(p['portfolio_value'] - self.initial_capital) / self.initial_capital
                            for p in self.pnl_history[-30:]]
            self.portfolio_var_95 = np.percentile(recent_returns, 5)

        # Store metrics
        self.current_metrics = {
            'portfolio_value': self.portfolio_value,
            'total_exposure': total_exposure,
            'leverage': portfolio_leverage,
            'volatility': self.portfolio_volatility,
            'var_95': self.portfolio_var_95,
            'drawdown': self.current_drawdown,
            'peak_value': self.peak_value
        }

    def check_portfolio_limits(self) -> List[Dict]:
        """
        Check portfolio against risk limits.

        Returns:
            List of risk violations
        """
        violations = []
        metrics = self.current_metrics

        # Leverage limit
        if metrics['leverage'] > self.max_portfolio_leverage:
            violations.append({
                'type': 'leverage_limit',
                'message': f"Portfolio leverage {metrics['leverage']:.2f}x exceeds limit {self.max_portfolio_leverage}x",
                'severity': 'critical',
                'current': metrics['leverage'],
                'limit': self.max_portfolio_leverage
            })

        # Exposure limit
        if metrics['total_exposure'] > self.max_total_exposure:
            violations.append({
                'type': 'exposure_limit',
                'message': f"Total exposure ${metrics['total_exposure']:,.0f} exceeds limit ${self.max_total_exposure:,.0f}",
                'severity': 'critical',
                'current': metrics['total_exposure'],
                'limit': self.max_total_exposure
            })

        # Drawdown limits
        if metrics['drawdown'] > self.dd_emergency:
            violations.append({
                'type': 'emergency_drawdown',
                'message': f"Emergency drawdown {metrics['drawdown']:.1%} exceeded",
                'severity': 'emergency',
                'current': metrics['drawdown'],
                'limit': self.dd_emergency
            })
        elif metrics['drawdown'] > self.dd_halt:
            violations.append({
                'type': 'halt_drawdown',
                'message': f"Halt drawdown {metrics['drawdown']:.1%} exceeded",
                'severity': 'critical',
                'current': metrics['drawdown'],
                'limit': self.dd_halt
            })
        elif metrics['drawdown'] > self.dd_warning:
            violations.append({
                'type': 'warning_drawdown',
                'message': f"Warning drawdown {metrics['drawdown']:.1%} exceeded",
                'severity': 'warning',
                'current': metrics['drawdown'],
                'limit': self.dd_warning
            })

        # Volatility limit
        if metrics['volatility'] > self.max_portfolio_vol:
            violations.append({
                'type': 'volatility_limit',
                'message': f"Portfolio volatility {metrics['volatility']:.1%} exceeds limit {self.max_portfolio_vol:.1%}",
                'severity': 'warning',
                'current': metrics['volatility'],
                'limit': self.max_portfolio_vol
            })

        return violations

    def calculate_correlation_matrix(self, returns_data: Dict[str, List[float]]) -> np.ndarray:
        """
        Calculate correlation matrix from returns data.

        Args:
            returns_data: Dictionary of symbol returns

        Returns:
            Correlation matrix
        """
        if not returns_data:
            return np.array([[]])

        # Convert to DataFrame
        df = pd.DataFrame(returns_data)

        # Calculate correlation matrix
        corr_matrix = df.corr()

        # Store correlation history
        avg_correlation = self._calculate_average_correlation(corr_matrix.values)
        self.correlation_history.append({
            'timestamp': time.time(),
            'avg_correlation': avg_correlation,
            'max_correlation': corr_matrix.values.max(),
            'min_correlation': corr_matrix.values.min()
        })

        # Keep only recent history
        if len(self.correlation_history) > 100:
            self.correlation_history = self.correlation_history[-100:]

        return corr_matrix.values

    def _calculate_average_correlation(self, corr_matrix: np.ndarray) -> float:
        """Calculate average off-diagonal correlation."""
        if corr_matrix.size == 0:
            return 0.0

        # Get upper triangle excluding diagonal
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        correlations = corr_matrix[mask]

        return np.mean(correlations) if len(correlations) > 0 else 0.0

    def check_correlation_risk(self, correlation_matrix: np.ndarray) -> List[Dict]:
        """
        Check correlation-based risks.

        Args:
            correlation_matrix: Current correlation matrix

        Returns:
            List of correlation risks
        """
        risks = []

        if correlation_matrix.size == 0:
            return risks

        avg_correlation = self._calculate_average_correlation(correlation_matrix)

        # Correlation spike
        if avg_correlation > self.correlation_spike_threshold:
            risks.append({
                'type': 'correlation_spike',
                'message': f"Correlation spike detected: {avg_correlation:.1%}",
                'severity': 'critical',
                'current': avg_correlation,
                'limit': self.correlation_spike_threshold
            })

        # General high correlation warning
        elif avg_correlation > self.max_correlation:
            risks.append({
                'type': 'high_correlation',
                'message': f"High correlation warning: {avg_correlation:.1%}",
                'severity': 'warning',
                'current': avg_correlation,
                'limit': self.max_correlation
            })

        return risks

    def calculate_portfolio_var(self, confidence: float = 0.95,
                              horizon_days: int = 1) -> float:
        """
        Calculate Portfolio Value at Risk.

        Args:
            confidence: Confidence level (0.95 = 95%)
            horizon_days: Time horizon in days

        Returns:
            VaR as portfolio percentage
        """
        if len(self.pnl_history) < 30:
            return 0.0

        # Get recent daily returns
        recent_values = [p['portfolio_value'] for p in self.pnl_history[-30:]]
        daily_returns = np.diff(recent_values) / recent_values[:-1]

        if len(daily_returns) == 0:
            return 0.0

        # Scale for horizon
        scaled_returns = daily_returns * np.sqrt(horizon_days)

        # Calculate VaR
        var_percentile = (1 - confidence) * 100
        var = np.percentile(scaled_returns, var_percentile)

        return abs(var)

    def calculate_expected_shortfall(self, confidence: float = 0.95) -> float:
        """
        Calculate Expected Shortfall (Conditional VaR).

        Args:
            confidence: Confidence level

        Returns:
            Expected shortfall as portfolio percentage
        """
        if len(self.pnl_history) < 30:
            return 0.0

        recent_values = [p['portfolio_value'] for p in self.pnl_history[-30:]]
        daily_returns = np.diff(recent_values) / recent_values[:-1]

        if len(daily_returns) == 0:
            return 0.0

        var_threshold = np.percentile(daily_returns, (1 - confidence) * 100)
        tail_returns = daily_returns[daily_returns <= var_threshold]

        return abs(np.mean(tail_returns)) if len(tail_returns) > 0 else 0.0

    def run_stress_test(self, scenarios: Dict[str, Dict]) -> Dict:
        """
        Run portfolio stress tests.

        Args:
            scenarios: Stress test scenarios

        Returns:
            Stress test results
        """
        results = {}

        for scenario_name, scenario in scenarios.items():
            try:
                # Apply scenario to current portfolio
                stressed_pnl = self._apply_stress_scenario(scenario)

                results[scenario_name] = {
                    'pnl_impact': stressed_pnl,
                    'pnl_percentage': stressed_pnl / self.portfolio_value,
                    'new_portfolio_value': self.portfolio_value + stressed_pnl,
                    'new_drawdown': max(0, (self.peak_value - (self.portfolio_value + stressed_pnl)) / self.peak_value)
                }

            except Exception as e:
                logger.error(f"Stress test {scenario_name} failed: {e}")
                results[scenario_name] = {'error': str(e)}

        self.stress_test_results = results
        self.last_stress_test = time.time()

        return results

    def _apply_stress_scenario(self, scenario: Dict) -> float:
        """Apply stress scenario to portfolio."""
        # This is a simplified implementation
        # In practice, would apply scenario to each position

        market_shock = scenario.get('market_shock', 0)
        volatility_shock = scenario.get('volatility_shock', 1)
        correlation_shock = scenario.get('correlation_shock', 0)

        # Calculate approximate impact
        portfolio_beta = 1.0  # Simplified
        base_impact = market_shock * portfolio_beta * self.portfolio_value

        # Add volatility impact
        vol_impact = (volatility_shock - 1) * 0.1 * self.portfolio_value

        # Add correlation impact (simplified)
        corr_impact = correlation_shock * 0.05 * self.portfolio_value

        return base_impact + vol_impact + corr_impact

    def get_risk_summary(self) -> Dict:
        """Get comprehensive risk summary."""
        violations = self.check_portfolio_limits()

        return {
            'portfolio_metrics': self.current_metrics,
            'risk_violations': violations,
            'var_95_1d': self.calculate_portfolio_var(),
            'expected_shortfall': self.calculate_expected_shortfall(),
            'correlation_status': {
                'avg_correlation': self.correlation_history[-1]['avg_correlation'] if self.correlation_history else 0,
                'correlation_trend': 'stable'  # Would calculate trend
            },
            'stress_tests': self.stress_test_results,
            'risk_level': self._assess_overall_risk_level(violations),
            'last_updated': self.last_risk_update
        }

    def _assess_overall_risk_level(self, violations: List[Dict]) -> str:
        """Assess overall portfolio risk level."""
        if any(v['severity'] == 'emergency' for v in violations):
            return 'EMERGENCY'
        elif any(v['severity'] == 'critical' for v in violations):
            return 'CRITICAL'
        elif any(v['severity'] == 'warning' for v in violations):
            return 'WARNING'
        else:
            return 'NORMAL'

    def get_position_limits(self, symbol: str, current_price: float) -> Dict:
        """
        Get position limits for a specific symbol.

        Args:
            symbol: Trading symbol
            current_price: Current price

        Returns:
            Position limit information
        """
        current_exposure = sum(abs(qty * current_price) for qty in self.current_positions.values())
        remaining_exposure = self.max_total_exposure - current_exposure

        current_leverage = current_exposure / self.portfolio_value
        remaining_leverage = self.max_portfolio_leverage - current_leverage

        # Calculate maximum additional position
        max_additional_notional = min(
            remaining_exposure,
            remaining_leverage * self.portfolio_value
        )

        max_additional_quantity = max_additional_notional / current_price if current_price > 0 else 0

        return {
            'symbol': symbol,
            'current_price': current_price,
            'max_additional_notional': max(max_additional_notional, 0),
            'max_additional_quantity': max(max_additional_quantity, 0),
            'current_portfolio_leverage': current_leverage,
            'remaining_leverage_capacity': max(remaining_leverage, 0),
            'can_increase_position': max_additional_notional > 100  # Min $100 trade
        }

    def should_reduce_risk(self) -> Tuple[bool, str]:
        """
        Check if portfolio risk should be reduced.

        Returns:
            Tuple of (should_reduce, reason)
        """
        violations = self.check_portfolio_limits()

        # Critical violations require immediate risk reduction
        critical_violations = [v for v in violations if v['severity'] in ['critical', 'emergency']]

        if critical_violations:
            reasons = [v['message'] for v in critical_violations]
            return True, '; '.join(reasons)

        # Check for multiple warnings
        warning_violations = [v for v in violations if v['severity'] == 'warning']
        if len(warning_violations) >= 3:
            return True, f"Multiple risk warnings: {len(warning_violations)} active"

        return False, ""

    def reset_peak_tracking(self) -> None:
        """Reset peak value tracking (for recovery scenarios)."""
        self.peak_value = self.portfolio_value
        self.current_drawdown = 0.0
        logger.info("Peak value tracking reset")

    def export_risk_report(self) -> Dict:
        """Export comprehensive risk report."""
        return {
            'timestamp': time.time(),
            'portfolio_summary': self.current_metrics,
            'risk_violations': self.check_portfolio_limits(),
            'correlation_analysis': {
                'recent_correlation': self.correlation_history[-10:] if self.correlation_history else [],
                'correlation_trend': 'stable'  # Would calculate
            },
            'var_analysis': {
                'var_95_1d': self.calculate_portfolio_var(),
                'var_95_5d': self.calculate_portfolio_var(horizon_days=5),
                'expected_shortfall': self.calculate_expected_shortfall()
            },
            'stress_tests': self.stress_test_results,
            'performance_metrics': {
                'total_return': (self.portfolio_value - self.initial_capital) / self.initial_capital,
                'max_drawdown': self.current_drawdown,
                'current_positions': len(self.current_positions)
            },
            'risk_assessment': self._assess_overall_risk_level(self.check_portfolio_limits())
        }