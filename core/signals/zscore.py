"""
Z-Score Signal Generation
========================

Implements the exact z-score signal logic from the v6 notebook.
Converts spread mean reversion signals into position sizing signals.

Key Features:
- Adaptive lookback based on OU half-life
- Graduated position sizing based on z-score magnitude
- Tiered entry/exit thresholds for asymmetric mean reversion
- Funding momentum and weekend boost overlays

WARNING: Production code. Parameters are frozen from 3.98 Sharpe validation.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class ZScoreSignalGenerator:
    """
    Generate trading signals based on spread z-scores.

    Implements the exact v6 signal logic that achieved 63.7% annual return.
    """

    def __init__(self, params: Dict):
        """
        Initialize signal generator with v6 parameters.

        Args:
            params: Parameter dictionary from config/params_v6.yaml
        """
        self.params = params

        # Core signal parameters (frozen from v6)
        self.z_entry = params['signals']['z_entry']              # 1.0
        self.z_exit_long = params['signals']['z_exit_long']      # 0.20
        self.z_exit_short = params['signals']['z_exit_short']    # 0.10
        self.z_stop = params['signals']['z_stop']                # 3.5
        self.min_holding = params['signals']['min_holding']      # 2

        # Lookback calculation
        self.lookback_mult = params['signals']['lookback_multiplier']  # 2.0
        self.min_lookback = params['signals']['min_lookback']          # 12
        self.max_lookback = params['signals']['max_lookback']          # 80

        # Position sizing
        self.z_size_min = params['sizing']['z_size_min']         # 0.8
        self.z_size_max = params['sizing']['z_size_max']         # 2.5
        self.z_size_cap_z = params['sizing']['z_size_cap_z']     # 3.0

        # Funding and weekend boosts
        self.funding_window = params['funding']['momentum_window']      # 5
        self.funding_quantile = params['funding']['extreme_quantile']   # 0.82
        self.funding_boost = params['funding']['boost']                 # 1.5
        self.weekend_boost = params['weekend']['boost']                 # 1.25

        logger.info("Z-score signal generator initialized with v6 parameters")

    def calculate_lookback(self, half_life: float) -> int:
        """
        Calculate adaptive lookback period based on OU half-life.

        Args:
            half_life: Ornstein-Uhlenbeck half-life in days

        Returns:
            Lookback period in days
        """
        lookback = int(np.clip(
            self.lookback_mult * half_life,
            self.min_lookback,
            self.max_lookback
        ))
        return lookback

    def calculate_zscore(self, spread: pd.Series, lookback: int) -> pd.Series:
        """
        Calculate rolling z-score of spread.

        Args:
            spread: Spread time series
            lookback: Lookback period for rolling statistics

        Returns:
            Z-score time series
        """
        rolling_mean = spread.rolling(lookback).mean()
        rolling_std = spread.rolling(lookback).std()

        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)

        z_score = (spread - rolling_mean) / rolling_std
        return z_score.dropna()

    def generate_raw_signals(self, z_score: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        Generate raw directional signals based on z-score thresholds.

        Args:
            z_score: Z-score time series

        Returns:
            Tuple of (raw_signal, signal_direction) series
        """
        signal = pd.Series(0.0, index=z_score.index)
        direction = pd.Series(0.0, index=z_score.index)

        position = 0.0
        holding_periods = 0

        for i in range(1, len(z_score)):
            z_current = z_score.iloc[i]

            if np.isnan(z_current):
                signal.iloc[i] = 0.0
                direction.iloc[i] = 0.0
                continue

            # Entry logic
            if position == 0:
                if z_current < -self.z_entry:  # Enter long spread
                    position = 1.0
                    holding_periods = 0
                elif z_current > self.z_entry:  # Enter short spread
                    position = -1.0
                    holding_periods = 0

            # Exit logic
            else:
                holding_periods += 1

                # Stop loss
                if abs(z_current) > self.z_stop:
                    position = 0.0
                    holding_periods = 0

                # Regular exits (after min holding period)
                elif holding_periods >= self.min_holding:
                    if position > 0 and z_current > -self.z_exit_long:
                        position = 0.0
                        holding_periods = 0
                    elif position < 0 and z_current < self.z_exit_short:
                        position = 0.0
                        holding_periods = 0

            direction.iloc[i] = position

            # Position sizing based on z-score magnitude
            if position != 0:
                z_abs = abs(z_current)
                z_scale = np.clip(
                    z_abs / self.z_entry,
                    self.z_size_min,
                    self.z_size_max
                )

                # Cap sizing at extreme z-scores
                if z_abs > self.z_size_cap_z:
                    z_scale = self.z_size_max

                signal.iloc[i] = position * z_scale
            else:
                signal.iloc[i] = 0.0

        return signal, direction

    def apply_funding_boost(self, signal: pd.Series, z_score: pd.Series,
                          returns_a: pd.Series, returns_b: pd.Series,
                          beta: pd.Series) -> pd.Series:
        """
        Apply funding momentum boost overlay.

        Args:
            signal: Base signal
            z_score: Z-score series
            returns_a: Returns of asset A
            returns_b: Returns of asset B
            beta: Dynamic hedge ratio

        Returns:
            Signal with funding boost applied
        """
        # Calculate spread momentum
        momentum_a = returns_a.rolling(self.funding_window).sum()
        momentum_b = returns_b.rolling(self.funding_window).sum()
        spread_momentum = (momentum_a - beta.shift(1) * momentum_b).reindex(z_score.index)

        # Calculate extreme quantiles
        momentum_high = spread_momentum.expanding().quantile(self.funding_quantile)
        momentum_low = spread_momentum.expanding().quantile(1 - self.funding_quantile)

        # Apply boost when momentum aligns with position
        funding_multiplier = pd.Series(1.0, index=signal.index)

        # Boost long spread positions when momentum is extremely positive
        long_boost = ((spread_momentum > momentum_high) & (z_score > 0))
        funding_multiplier[long_boost] = self.funding_boost

        # Boost short spread positions when momentum is extremely negative
        short_boost = ((spread_momentum < momentum_low) & (z_score < 0))
        funding_multiplier[short_boost] = self.funding_boost

        boosted_signal = signal * funding_multiplier

        logger.debug(f"Funding boost applied: {(funding_multiplier > 1).mean():.1%} of periods")

        return boosted_signal

    def apply_weekend_boost(self, signal: pd.Series) -> pd.Series:
        """
        Apply weekend boost (Friday-Sunday).

        Args:
            signal: Base signal

        Returns:
            Signal with weekend boost applied
        """
        # Get day of week (0=Monday, 6=Sunday)
        day_of_week = pd.Series([d.dayofweek for d in signal.index], index=signal.index)

        # Apply boost for Friday (4) and weekend days (5, 6)
        weekend_multiplier = 1.0 + (day_of_week >= 4).astype(float) * (self.weekend_boost - 1.0)
        weekend_signal = signal * weekend_multiplier

        logger.debug(f"Weekend boost applied: {(weekend_multiplier > 1).mean():.1%} of periods")

        return weekend_signal

    def generate_full_signals(self, spread: pd.Series, half_life: float,
                            returns_a: pd.Series, returns_b: pd.Series,
                            beta: pd.Series, regime_filter: pd.Series,
                            tier_weight: float = 1.0) -> Dict[str, pd.Series]:
        """
        Generate complete trading signals with all overlays.

        Args:
            spread: Spread time series
            half_life: OU half-life for lookback calculation
            returns_a: Returns of asset A
            returns_b: Returns of asset B
            beta: Dynamic hedge ratio series
            regime_filter: Boolean series indicating favorable regime
            tier_weight: Tier-based weight multiplier (0.5 for tier 2, 1.0 for tier 1)

        Returns:
            Dictionary with signal components
        """
        # Calculate adaptive lookback and z-score
        lookback = self.calculate_lookback(half_life)
        z_score = self.calculate_zscore(spread, lookback)

        # Apply regime filter to z-score
        z_score_filtered = z_score.copy()
        z_score_filtered[~regime_filter.reindex(z_score.index, fill_value=False)] = np.nan

        # Generate raw signals
        raw_signal, direction = self.generate_raw_signals(z_score_filtered)

        # Apply funding boost
        funded_signal = self.apply_funding_boost(
            raw_signal, z_score, returns_a, returns_b, beta
        )

        # Apply weekend boost
        boosted_signal = self.apply_weekend_boost(funded_signal)

        # Apply tier weight (v6 feature for marginal pairs)
        final_signal = boosted_signal * tier_weight

        return {
            'signal': final_signal,
            'raw_signal': raw_signal,
            'direction': direction,
            'z_score': z_score,
            'lookback': lookback,
            'funding_boost_pct': ((funded_signal / raw_signal.replace(0, 1)) > 1).mean(),
            'weekend_boost_pct': ((boosted_signal / funded_signal.replace(0, 1)) > 1).mean()
        }

    def get_signal_diagnostics(self, signal_output: Dict) -> Dict:
        """
        Calculate signal diagnostics for monitoring.

        Args:
            signal_output: Output from generate_full_signals

        Returns:
            Dictionary of diagnostic metrics
        """
        signal = signal_output['signal']
        direction = signal_output['direction']

        # Count trades (direction changes)
        trades = (direction.diff().abs() > 0).sum() // 2

        # Time in market
        time_active = (direction != 0).mean()

        # Average signal magnitude
        avg_signal = signal[signal != 0].abs().mean() if (signal != 0).any() else 0

        # Z-score statistics
        z_score = signal_output['z_score'].dropna()
        z_stats = {
            'z_mean': z_score.mean(),
            'z_std': z_score.std(),
            'z_min': z_score.min(),
            'z_max': z_score.max()
        }

        return {
            'lookback': signal_output['lookback'],
            'n_trades': trades,
            'time_in_market': time_active,
            'avg_signal_magnitude': avg_signal,
            'funding_boost_frequency': signal_output['funding_boost_pct'],
            'weekend_boost_frequency': signal_output['weekend_boost_pct'],
            **z_stats
        }