"""
Position Manager
===============

Centralized position management for the trading platform:
- Real-time position tracking and reconciliation
- Position lifecycle management (open, modify, close)
- Position analytics and reporting
- Integration with risk management
- Position hedging and rebalancing

Maintains accurate position state across all trading pairs.
"""

import time
import asyncio
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging
import pandas as pd
import numpy as np

from live.binance_client import BinanceClient
from risk.position_risk import PositionRiskManager

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Comprehensive position management system.
    """

    def __init__(self, client: BinanceClient, risk_manager: PositionRiskManager,
                 config: Dict):
        """
        Initialize position manager.

        Args:
            client: Binance client for position updates
            risk_manager: Risk manager for validation
            config: Position management configuration
        """
        self.client = client
        self.risk_manager = risk_manager
        self.config = config

        # Position tracking
        self.current_positions = {}
        self.target_positions = {}
        self.position_history = []

        # Position analytics
        self.pnl_tracking = {}
        self.position_analytics = {}

        # Reconciliation settings
        self.reconciliation_interval = config.get('reconciliation_interval', 300)  # 5 minutes
        self.position_tolerance = config.get('position_tolerance', 0.01)  # 1% tolerance

        # Position limits
        self.max_position_age = config.get('max_position_age_hours', 72)  # 72 hours
        self.rebalance_threshold = config.get('rebalance_threshold', 0.05)  # 5%

        # State tracking
        self.last_reconciliation = 0
        self.position_lock = asyncio.Lock()

        logger.info("Position manager initialized")

    async def update_positions_from_exchange(self) -> Dict:
        """
        Fetch current positions from exchange.

        Returns:
            Dictionary of current positions
        """
        try:
            async with self.client:
                position_data = await self.client.get_position_risk()

            updated_positions = {}

            for pos_info in position_data:
                symbol = pos_info['symbol']
                position_amt = float(pos_info['positionAmt'])
                mark_price = float(pos_info['markPrice'])
                entry_price = float(pos_info['entryPrice'])
                unrealized_pnl = float(pos_info['unRealizedPnL'])

                # Only track non-zero positions
                if abs(position_amt) > 1e-8:
                    updated_positions[symbol] = {
                        'symbol': symbol,
                        'quantity': position_amt,
                        'entry_price': entry_price,
                        'mark_price': mark_price,
                        'unrealized_pnl': unrealized_pnl,
                        'notional_value': position_amt * mark_price,
                        'side': 'LONG' if position_amt > 0 else 'SHORT',
                        'last_update': time.time()
                    }

            # Update internal tracking
            async with self.position_lock:
                self.current_positions = updated_positions
                self._update_position_analytics()

            logger.debug(f"Updated {len(updated_positions)} positions from exchange")

            return updated_positions

        except Exception as e:
            logger.error(f"Failed to update positions from exchange: {e}")
            return self.current_positions

    def set_target_positions(self, targets: Dict[str, float]) -> None:
        """
        Set target positions.

        Args:
            targets: Target positions {symbol: target_notional_value}
        """
        self.target_positions = targets.copy()
        logger.info(f"Target positions updated: {len(targets)} symbols")

    def calculate_position_differences(self) -> Dict[str, Dict]:
        """
        Calculate differences between current and target positions.

        Returns:
            Dictionary of position differences
        """
        differences = {}

        # Check all target positions
        for symbol, target_value in self.target_positions.items():
            current_value = self.current_positions.get(symbol, {}).get('notional_value', 0)
            difference = target_value - current_value

            if abs(difference) > 100:  # Minimum $100 difference
                differences[symbol] = {
                    'symbol': symbol,
                    'current_value': current_value,
                    'target_value': target_value,
                    'difference': difference,
                    'percentage_diff': abs(difference) / max(abs(target_value), 100),
                    'action_needed': 'BUY' if difference > 0 else 'SELL'
                }

        # Check for positions to close (not in targets)
        for symbol, position in self.current_positions.items():
            if symbol not in self.target_positions:
                if abs(position['notional_value']) > 100:
                    differences[symbol] = {
                        'symbol': symbol,
                        'current_value': position['notional_value'],
                        'target_value': 0,
                        'difference': -position['notional_value'],
                        'percentage_diff': 1.0,  # 100% difference
                        'action_needed': 'CLOSE',
                        'close_position': True
                    }

        return differences

    async def reconcile_positions(self) -> Dict:
        """
        Reconcile positions and identify discrepancies.

        Returns:
            Reconciliation report
        """
        current_time = time.time()

        # Check if reconciliation is needed
        if current_time - self.last_reconciliation < self.reconciliation_interval:
            return {'status': 'skipped', 'reason': 'too_soon'}

        logger.info("Starting position reconciliation")

        # Update positions from exchange
        await self.update_positions_from_exchange()

        # Calculate differences
        differences = self.calculate_position_differences()

        # Identify large discrepancies
        large_discrepancies = {
            symbol: diff for symbol, diff in differences.items()
            if diff['percentage_diff'] > self.rebalance_threshold
        }

        # Check for stale positions
        stale_positions = self._check_stale_positions()

        reconciliation_report = {
            'timestamp': current_time,
            'total_positions': len(self.current_positions),
            'target_positions': len(self.target_positions),
            'differences_found': len(differences),
            'large_discrepancies': len(large_discrepancies),
            'stale_positions': len(stale_positions),
            'differences_detail': differences,
            'stale_positions_detail': stale_positions,
            'requires_action': len(large_discrepancies) > 0 or len(stale_positions) > 0
        }

        self.last_reconciliation = current_time

        if reconciliation_report['requires_action']:
            logger.warning(f"Position reconciliation found issues: "
                          f"{len(large_discrepancies)} discrepancies, "
                          f"{len(stale_positions)} stale positions")

        return reconciliation_report

    def _check_stale_positions(self) -> List[Dict]:
        """Check for stale positions that haven't been updated."""
        current_time = time.time()
        max_age = self.max_position_age * 3600  # Convert hours to seconds

        stale_positions = []

        for symbol, position in self.current_positions.items():
            last_update = position.get('last_update', 0)
            age = current_time - last_update

            if age > max_age:
                stale_positions.append({
                    'symbol': symbol,
                    'age_hours': age / 3600,
                    'last_update': last_update,
                    'position_value': position.get('notional_value', 0)
                })

        return stale_positions

    def _update_position_analytics(self) -> None:
        """Update position analytics and metrics."""
        current_time = time.time()

        # Calculate portfolio metrics
        total_long_value = sum(pos['notional_value'] for pos in self.current_positions.values()
                              if pos['notional_value'] > 0)
        total_short_value = sum(abs(pos['notional_value']) for pos in self.current_positions.values()
                               if pos['notional_value'] < 0)
        total_exposure = total_long_value + total_short_value

        # Calculate PnL metrics
        total_unrealized_pnl = sum(pos['unrealized_pnl'] for pos in self.current_positions.values())

        # Position distribution
        position_sizes = [abs(pos['notional_value']) for pos in self.current_positions.values()]
        avg_position_size = np.mean(position_sizes) if position_sizes else 0
        max_position_size = np.max(position_sizes) if position_sizes else 0

        # Update analytics
        self.position_analytics = {
            'timestamp': current_time,
            'total_positions': len(self.current_positions),
            'total_long_value': total_long_value,
            'total_short_value': total_short_value,
            'total_exposure': total_exposure,
            'net_exposure': total_long_value - total_short_value,
            'total_unrealized_pnl': total_unrealized_pnl,
            'avg_position_size': avg_position_size,
            'max_position_size': max_position_size,
            'position_count_by_side': {
                'long': sum(1 for pos in self.current_positions.values() if pos['notional_value'] > 0),
                'short': sum(1 for pos in self.current_positions.values() if pos['notional_value'] < 0)
            }
        }

        # Store historical snapshot
        self.position_history.append(self.position_analytics.copy())

        # Keep only recent history (last 1000 snapshots)
        if len(self.position_history) > 1000:
            self.position_history = self.position_history[-1000:]

    def get_position_summary(self) -> Dict:
        """Get position summary for monitoring."""
        return {
            'current_positions': self.current_positions,
            'target_positions': self.target_positions,
            'analytics': self.position_analytics,
            'last_reconciliation': self.last_reconciliation,
            'reconciliation_due': time.time() - self.last_reconciliation > self.reconciliation_interval
        }

    def get_position_performance(self, symbol: str = None) -> Dict:
        """
        Get position performance metrics.

        Args:
            symbol: Specific symbol (None for all positions)

        Returns:
            Performance metrics
        """
        if symbol:
            # Single position performance
            position = self.current_positions.get(symbol)
            if not position:
                return {'error': f'Position {symbol} not found'}

            return {
                'symbol': symbol,
                'unrealized_pnl': position['unrealized_pnl'],
                'unrealized_pnl_percent': position['unrealized_pnl'] / abs(position['notional_value']) if position['notional_value'] != 0 else 0,
                'position_value': position['notional_value'],
                'entry_price': position['entry_price'],
                'current_price': position['mark_price'],
                'price_change_percent': (position['mark_price'] - position['entry_price']) / position['entry_price'] if position['entry_price'] != 0 else 0
            }
        else:
            # Portfolio performance
            total_unrealized_pnl = sum(pos['unrealized_pnl'] for pos in self.current_positions.values())
            total_notional = sum(abs(pos['notional_value']) for pos in self.current_positions.values())

            winning_positions = [pos for pos in self.current_positions.values() if pos['unrealized_pnl'] > 0]
            losing_positions = [pos for pos in self.current_positions.values() if pos['unrealized_pnl'] < 0]

            return {
                'total_unrealized_pnl': total_unrealized_pnl,
                'total_unrealized_pnl_percent': total_unrealized_pnl / total_notional if total_notional > 0 else 0,
                'winning_positions': len(winning_positions),
                'losing_positions': len(losing_positions),
                'win_rate': len(winning_positions) / len(self.current_positions) if self.current_positions else 0,
                'avg_winner': np.mean([pos['unrealized_pnl'] for pos in winning_positions]) if winning_positions else 0,
                'avg_loser': np.mean([pos['unrealized_pnl'] for pos in losing_positions]) if losing_positions else 0,
                'largest_winner': max([pos['unrealized_pnl'] for pos in self.current_positions.values()]) if self.current_positions else 0,
                'largest_loser': min([pos['unrealized_pnl'] for pos in self.current_positions.values()]) if self.current_positions else 0
            }

    def get_position_risk_metrics(self) -> Dict:
        """Get position-level risk metrics."""
        if not self.current_positions:
            return {}

        # Calculate risk metrics per position
        position_risks = {}

        for symbol, position in self.current_positions.items():
            notional = abs(position['notional_value'])
            unrealized_pnl_pct = position['unrealized_pnl'] / notional if notional > 0 else 0

            # Simple risk metrics
            position_risks[symbol] = {
                'notional_value': notional,
                'unrealized_pnl_percent': unrealized_pnl_pct,
                'risk_score': self._calculate_position_risk_score(position),
                'days_held': (time.time() - position.get('last_update', time.time())) / 86400,
                'concentration_risk': notional / self.position_analytics.get('total_exposure', 1)
            }

        # Portfolio-level risk
        total_exposure = sum(abs(pos['notional_value']) for pos in self.current_positions.values())
        max_single_exposure = max([abs(pos['notional_value']) for pos in self.current_positions.values()]) if self.current_positions else 0

        portfolio_risk = {
            'total_exposure': total_exposure,
            'max_single_exposure': max_single_exposure,
            'concentration_ratio': max_single_exposure / total_exposure if total_exposure > 0 else 0,
            'position_count': len(self.current_positions),
            'long_short_imbalance': abs(self.position_analytics.get('net_exposure', 0)) / total_exposure if total_exposure > 0 else 0
        }

        return {
            'position_risks': position_risks,
            'portfolio_risk': portfolio_risk
        }

    def _calculate_position_risk_score(self, position: Dict) -> float:
        """
        Calculate risk score for a position (0-100).

        Args:
            position: Position dictionary

        Returns:
            Risk score (higher = riskier)
        """
        score = 0

        # Size risk (0-30 points)
        notional = abs(position['notional_value'])
        if notional > 50000:
            score += 30
        elif notional > 25000:
            score += 20
        elif notional > 10000:
            score += 10

        # PnL risk (0-30 points)
        unrealized_pnl_pct = position['unrealized_pnl'] / notional if notional > 0 else 0
        if unrealized_pnl_pct < -0.10:  # Losing more than 10%
            score += 30
        elif unrealized_pnl_pct < -0.05:  # Losing more than 5%
            score += 20
        elif unrealized_pnl_pct < -0.02:  # Losing more than 2%
            score += 10

        # Time risk (0-20 points)
        age_hours = (time.time() - position.get('last_update', time.time())) / 3600
        if age_hours > 48:
            score += 20
        elif age_hours > 24:
            score += 10
        elif age_hours > 12:
            score += 5

        # Concentration risk (0-20 points)
        total_exposure = self.position_analytics.get('total_exposure', 1)
        concentration = notional / total_exposure
        if concentration > 0.30:
            score += 20
        elif concentration > 0.20:
            score += 15
        elif concentration > 0.10:
            score += 10

        return min(score, 100)

    def get_rebalancing_recommendations(self) -> List[Dict]:
        """Get position rebalancing recommendations."""
        recommendations = []

        differences = self.calculate_position_differences()

        for symbol, diff in differences.items():
            if diff['percentage_diff'] > self.rebalance_threshold:
                recommendation = {
                    'symbol': symbol,
                    'action': diff['action_needed'],
                    'current_value': diff['current_value'],
                    'target_value': diff['target_value'],
                    'recommended_trade_size': abs(diff['difference']),
                    'priority': 'HIGH' if diff['percentage_diff'] > 0.15 else 'MEDIUM',
                    'reason': f"{diff['percentage_diff']:.1%} deviation from target"
                }
                recommendations.append(recommendation)

        # Sort by priority and size
        recommendations.sort(key=lambda x: (
            0 if x['priority'] == 'HIGH' else 1,
            -x['recommended_trade_size']
        ))

        return recommendations

    async def emergency_close_all(self) -> Dict:
        """
        Emergency close all positions.

        Returns:
            Closure results
        """
        logger.critical("Emergency position closure initiated")

        closure_results = {
            'initiated_at': time.time(),
            'positions_to_close': len(self.current_positions),
            'closures_attempted': 0,
            'closures_successful': 0,
            'closures_failed': 0,
            'errors': []
        }

        for symbol, position in self.current_positions.items():
            try:
                # Calculate close order parameters
                quantity = abs(position['quantity'])
                side = 'SELL' if position['quantity'] > 0 else 'BUY'

                # Place market order to close
                async with self.client:
                    close_order = await self.client.place_order(
                        symbol=symbol,
                        side=side,
                        order_type="MARKET",
                        quantity=quantity,
                        reduce_only=True
                    )

                closure_results['closures_attempted'] += 1
                closure_results['closures_successful'] += 1

                logger.warning(f"Emergency close: {symbol} {side} {quantity}")

            except Exception as e:
                closure_results['closures_failed'] += 1
                closure_results['errors'].append(f"{symbol}: {str(e)}")
                logger.error(f"Failed to close {symbol}: {e}")

        # Clear target positions
        self.target_positions.clear()

        logger.critical(f"Emergency closure complete: {closure_results['closures_successful']}/{closure_results['closures_attempted']} successful")

        return closure_results

    def export_position_report(self) -> Dict:
        """Export comprehensive position report."""
        return {
            'timestamp': time.time(),
            'position_summary': self.get_position_summary(),
            'position_performance': self.get_position_performance(),
            'risk_metrics': self.get_position_risk_metrics(),
            'rebalancing_recommendations': self.get_rebalancing_recommendations(),
            'recent_analytics': self.position_history[-10:] if len(self.position_history) >= 10 else self.position_history
        }