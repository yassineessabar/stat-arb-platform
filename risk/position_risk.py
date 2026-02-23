"""
Position Risk Manager
====================

Real-time risk monitoring and position validation:
- Pre-trade risk checks
- Real-time portfolio risk monitoring
- Circuit breakers and emergency stops
- Position limit enforcement

Implements the exact risk controls from the v6 notebook.
"""

import time
from typing import Dict, List, Optional, Tuple
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class PositionRiskManager:
    """
    Real-time risk management for position validation and monitoring.
    """

    def __init__(self, config: Dict, account_balance: float = 100000):
        """
        Initialize position risk manager.

        Args:
            config: Risk configuration from risk_limits.yaml
            account_balance: Current account balance in USD
        """
        self.config = config
        self.account_balance = account_balance

        # Risk limits from config
        self.max_total_exposure = config['portfolio']['max_total_exposure_usdt']
        self.max_leverage = config['portfolio']['max_leverage']
        self.max_pair_weight = config['pair']['max_pair_weight']
        self.max_position_value = config['pair']['max_position_value_usdt']

        # Drawdown limits
        self.dd_warning = config['portfolio']['drawdown_limits']['warning_level']
        self.dd_halt = config['portfolio']['drawdown_limits']['halt_level']
        self.dd_emergency = config['portfolio']['drawdown_limits']['emergency_stop']

        # Position tracking
        self.current_positions = {}
        self.portfolio_equity = account_balance
        self.peak_equity = account_balance
        self.current_drawdown = 0.0

        # Risk state
        self.risk_halted = False
        self.emergency_mode = False
        self.halt_start_time = None

        # Monitoring
        self.last_risk_check = time.time()
        self.risk_violations = []

        logger.info(f"Risk manager initialized: ${account_balance:,} balance, "
                   f"{self.max_leverage}x max leverage")

    async def validate_trade(self, trade: Dict) -> bool:
        """
        Validate trade against risk limits before execution.

        Args:
            trade: Trade dictionary with symbol, side, quantity, etc.

        Returns:
            True if trade is allowed, False if blocked
        """
        if self.emergency_mode:
            logger.warning("Trade blocked: Emergency mode active")
            return False

        if self.risk_halted:
            logger.warning("Trade blocked: Risk halt active")
            return False

        symbol = trade['symbol']
        difference_usd = trade['difference_usd']

        # Check individual position limits
        if not self._validate_position_limits(symbol, difference_usd):
            return False

        # Check portfolio limits
        if not self._validate_portfolio_limits(difference_usd):
            return False

        # Check leverage limits
        if not self._validate_leverage_limits():
            return False

        # All checks passed
        return True

    def _validate_position_limits(self, symbol: str, position_change_usd: float) -> bool:
        """Validate individual position limits."""
        current_position = self.current_positions.get(symbol, 0.0)
        new_position = current_position + position_change_usd

        # Check maximum position value
        if abs(new_position) > self.max_position_value:
            self._log_violation(f"Position limit exceeded for {symbol}: "
                              f"${abs(new_position):,.0f} > ${self.max_position_value:,.0f}")
            return False

        # Check pair weight limit
        pair_weight = abs(new_position) / max(self.account_balance, 1)
        if pair_weight > self.max_pair_weight:
            self._log_violation(f"Pair weight exceeded for {symbol}: "
                              f"{pair_weight:.1%} > {self.max_pair_weight:.1%}")
            return False

        return True

    def _validate_portfolio_limits(self, position_change_usd: float) -> bool:
        """Validate portfolio-level limits."""
        # Calculate total exposure after trade
        total_exposure = sum(abs(pos) for pos in self.current_positions.values())
        new_total_exposure = total_exposure + abs(position_change_usd)

        if new_total_exposure > self.max_total_exposure:
            self._log_violation(f"Total exposure limit exceeded: "
                              f"${new_total_exposure:,.0f} > ${self.max_total_exposure:,.0f}")
            return False

        return True

    def _validate_leverage_limits(self) -> bool:
        """Validate leverage limits."""
        total_exposure = sum(abs(pos) for pos in self.current_positions.values())
        current_leverage = total_exposure / max(self.account_balance, 1)

        if current_leverage > self.max_leverage:
            self._log_violation(f"Leverage limit exceeded: "
                              f"{current_leverage:.2f}x > {self.max_leverage:.2f}x")
            return False

        return True

    def update_positions(self, positions: Dict[str, float]) -> None:
        """
        Update current position tracking.

        Args:
            positions: Dictionary mapping symbols to USD position values
        """
        self.current_positions = positions.copy()
        self._update_portfolio_metrics()

    def _update_portfolio_metrics(self) -> None:
        """Update portfolio-level risk metrics."""
        # Calculate current portfolio value
        total_position_value = sum(self.current_positions.values())
        self.portfolio_equity = self.account_balance + total_position_value

        # Update peak equity and drawdown
        if self.portfolio_equity > self.peak_equity:
            self.peak_equity = self.portfolio_equity

        self.current_drawdown = (self.peak_equity - self.portfolio_equity) / self.peak_equity

        # Check drawdown triggers
        self._check_drawdown_triggers()

    def _check_drawdown_triggers(self) -> None:
        """Check if drawdown triggers should be activated."""
        if self.current_drawdown > self.dd_emergency and not self.emergency_mode:
            self._activate_emergency_mode()

        elif self.current_drawdown > self.dd_halt and not self.risk_halted:
            self._activate_risk_halt()

        elif self.current_drawdown > self.dd_warning:
            logger.warning(f"Drawdown warning: {self.current_drawdown:.1%}")

        # Check for halt recovery
        if self.risk_halted and self.current_drawdown < self.dd_halt * 0.8:
            cooldown_hours = self.config['temporal']['cool_down_periods']['after_halt_minutes'] / 60
            if self.halt_start_time and time.time() - self.halt_start_time > cooldown_hours * 3600:
                self._deactivate_risk_halt()

    def _activate_risk_halt(self) -> None:
        """Activate risk halt."""
        self.risk_halted = True
        self.halt_start_time = time.time()

        logger.critical(f"RISK HALT ACTIVATED: Drawdown {self.current_drawdown:.1%}")

        self._log_violation(f"Risk halt triggered at {self.current_drawdown:.1%} drawdown")

    def _deactivate_risk_halt(self) -> None:
        """Deactivate risk halt after cooldown."""
        self.risk_halted = False
        self.halt_start_time = None

        logger.warning("Risk halt deactivated after cooldown")

    def _activate_emergency_mode(self) -> None:
        """Activate emergency mode."""
        self.emergency_mode = True

        logger.critical(f"EMERGENCY MODE ACTIVATED: Drawdown {self.current_drawdown:.1%}")

        self._log_violation(f"Emergency stop triggered at {self.current_drawdown:.1%} drawdown")

        # Emergency mode requires manual intervention to deactivate

    def check_correlation_spike(self, correlation_matrix: pd.DataFrame) -> bool:
        """
        Check for dangerous correlation spikes.

        Args:
            correlation_matrix: Current pair correlation matrix

        Returns:
            True if correlation spike detected
        """
        if correlation_matrix.empty:
            return False

        # Calculate average off-diagonal correlation
        mask = ~np.eye(correlation_matrix.shape[0], dtype=bool)
        avg_correlation = correlation_matrix.values[mask].mean()

        threshold = self.config['portfolio']['correlation_limits']['correlation_spike_threshold']

        if avg_correlation > threshold:
            logger.critical(f"Correlation spike detected: {avg_correlation:.3f} > {threshold:.3f}")
            self._log_violation(f"Correlation spike: {avg_correlation:.3f}")
            return True

        return False

    def check_volatility_spike(self, current_vol: float, historical_vol: float) -> bool:
        """
        Check for volatility spikes.

        Args:
            current_vol: Current portfolio volatility
            historical_vol: Historical average volatility

        Returns:
            True if vol spike detected
        """
        vol_ratio = current_vol / max(historical_vol, 0.01)
        threshold = self.config['market']['volatility_limits']['vol_spike_threshold']

        if vol_ratio > threshold:
            logger.warning(f"Volatility spike detected: {vol_ratio:.2f}x normal")
            self._log_violation(f"Vol spike: {vol_ratio:.2f}x")
            return True

        return False

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics for monitoring."""
        total_exposure = sum(abs(pos) for pos in self.current_positions.values())
        leverage = total_exposure / max(self.account_balance, 1)

        largest_position = max(abs(pos) for pos in self.current_positions.values()) if self.current_positions else 0
        largest_weight = largest_position / max(self.account_balance, 1)

        return {
            'portfolio_equity': self.portfolio_equity,
            'total_exposure_usd': total_exposure,
            'leverage': leverage,
            'drawdown': self.current_drawdown,
            'largest_position_usd': largest_position,
            'largest_position_weight': largest_weight,
            'num_positions': len(self.current_positions),
            'risk_halted': self.risk_halted,
            'emergency_mode': self.emergency_mode,
            'recent_violations': len([v for v in self.risk_violations if time.time() - v['timestamp'] < 3600])
        }

    def get_position_limits(self, symbol: str) -> Dict:
        """
        Get position limits for a specific symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with position limits
        """
        current_position = self.current_positions.get(symbol, 0.0)
        current_weight = abs(current_position) / max(self.account_balance, 1)

        max_additional_usd = min(
            self.max_position_value - abs(current_position),
            self.account_balance * self.max_pair_weight - abs(current_position),
            self.max_total_exposure - sum(abs(pos) for pos in self.current_positions.values())
        )

        return {
            'symbol': symbol,
            'current_position_usd': current_position,
            'current_weight': current_weight,
            'max_position_usd': self.max_position_value,
            'max_weight': self.max_pair_weight,
            'max_additional_usd': max(max_additional_usd, 0),
            'can_increase': max_additional_usd > 100,  # Minimum $100 trade
        }

    def _log_violation(self, message: str) -> None:
        """Log risk violation."""
        violation = {
            'timestamp': time.time(),
            'message': message
        }
        self.risk_violations.append(violation)

        # Keep only recent violations
        cutoff_time = time.time() - 86400  # 24 hours
        self.risk_violations = [v for v in self.risk_violations if v['timestamp'] > cutoff_time]

        logger.warning(f"Risk violation: {message}")

    def reset_emergency_mode(self, manual_override: bool = False) -> bool:
        """
        Reset emergency mode (requires manual confirmation).

        Args:
            manual_override: Manual confirmation required

        Returns:
            True if reset successful
        """
        if not manual_override:
            logger.error("Emergency mode reset requires manual override")
            return False

        self.emergency_mode = False
        logger.warning("Emergency mode manually reset")
        return True

    def get_risk_summary(self) -> str:
        """Get human-readable risk summary."""
        metrics = self.get_risk_metrics()

        status = "EMERGENCY" if self.emergency_mode else "HALTED" if self.risk_halted else "NORMAL"

        summary = f"""
Risk Status: {status}
Portfolio Equity: ${metrics['portfolio_equity']:,.0f}
Total Exposure: ${metrics['total_exposure_usd']:,.0f}
Leverage: {metrics['leverage']:.2f}x
Drawdown: {metrics['drawdown']:.1%}
Positions: {metrics['num_positions']}
Recent Violations: {metrics['recent_violations']}
"""
        return summary.strip()