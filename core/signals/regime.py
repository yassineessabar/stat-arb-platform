"""
Regime Detection and Filtering
==============================

Implements regime detection logic from the v6 notebook to filter trading signals.
Only trade when market conditions are favorable for mean reversion.

Key Features:
- Correlation-based regime detection
- Volatility regime analysis
- Rolling cointegration monitoring
- Circuit breakers for adverse conditions

WARNING: Production code. Logic is frozen from 3.98 Sharpe validation.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Detect favorable market regimes for statistical arbitrage trading.

    Implements the exact v6 regime logic that achieved high Sharpe ratios.
    """

    def __init__(self, params: Dict):
        """
        Initialize regime detector with v6 parameters.

        Args:
            params: Parameter dictionary from config/params_v6.yaml
        """
        self.params = params

        # Correlation regime parameters
        self.corr_lookback = params['regime']['corr_lookback']           # 40
        self.corr_threshold = params['regime']['corr_threshold']         # 0.30

        # Volatility regime parameters
        self.vol_lookback_short = params['regime']['vol_lookback_short'] # 15
        self.vol_lookback_long = params['regime']['vol_lookback_long']   # 45
        self.vol_ratio_threshold = params['regime']['vol_ratio_threshold'] # 0.25

        # Cointegration monitoring
        self.coint_window = params['cointegration']['rolling_window']    # 180
        self.coint_kill_pvalue = params['cointegration']['kill_pvalue']  # 0.20
        self.coint_revive_pvalue = params['cointegration']['revive_pvalue'] # 0.08
        self.coint_check_freq = params['cointegration']['check_frequency'] # 20

        logger.info("Regime detector initialized with v6 parameters")

    def detect_correlation_regime(self, prices_a: pd.Series, prices_b: pd.Series) -> pd.Series:
        """
        Detect correlation regime between two assets.

        Args:
            prices_a: Price series for asset A
            prices_b: Price series for asset B

        Returns:
            Boolean series indicating favorable correlation regime
        """
        # Rolling correlation with adaptive lookback
        rolling_corr = prices_a.rolling(self.corr_lookback).corr(prices_b)

        # Favorable regime: correlation above threshold
        corr_regime = rolling_corr > self.corr_threshold

        logger.debug(f"Correlation regime: {corr_regime.mean():.1%} favorable periods")

        return corr_regime.fillna(False)

    def detect_volatility_regime(self, returns_a: pd.Series, returns_b: pd.Series,
                               beta: pd.Series) -> pd.Series:
        """
        Detect volatility regime for spread mean reversion.

        Args:
            returns_a: Returns of asset A
            returns_b: Returns of asset B
            beta: Dynamic hedge ratio series

        Returns:
            Boolean series indicating favorable volatility regime
        """
        # Calculate spread returns (portfolio return of the pair)
        spread_returns = returns_a - beta.shift(1) * returns_b
        spread_returns = spread_returns.dropna()

        # Short-term vs long-term volatility
        vol_short = spread_returns.rolling(self.vol_lookback_short).std()
        vol_long = spread_returns.rolling(self.vol_lookback_long).std()

        # Favorable regime: short-term vol > threshold * long-term vol
        # This indicates sufficient volatility for mean reversion opportunities
        vol_ratio = vol_short / vol_long.replace(0, np.nan)
        vol_regime = vol_ratio > self.vol_ratio_threshold

        logger.debug(f"Volatility regime: {vol_regime.mean():.1%} favorable periods")

        return vol_regime.fillna(False)

    def monitor_cointegration(self, spread: pd.Series) -> pd.Series:
        """
        Monitor rolling cointegration relationship.

        Args:
            spread: Spread time series

        Returns:
            Boolean series indicating cointegration is alive
        """
        from statsmodels.tsa.stattools import adfuller

        coint_alive = pd.Series(True, index=spread.index)

        # Check cointegration at regular intervals
        window = self.coint_window
        frequency = self.coint_check_freq

        for i in range(window, len(spread), frequency):
            # Extract rolling window
            window_spread = spread.iloc[max(0, i - window):i]

            if len(window_spread) < 60:
                continue

            try:
                # ADF test on rolling window
                adf_result = adfuller(window_spread.dropna(), autolag='AIC')
                pvalue = adf_result[1]
            except Exception as e:
                logger.warning(f"ADF test failed at index {i}: {e}")
                pvalue = 1.0

            # Determine cointegration status
            if pvalue > self.coint_kill_pvalue:
                alive = False  # Kill cointegration
            elif pvalue < self.coint_revive_pvalue:
                alive = True   # Revive cointegration
            else:
                # Keep previous status
                alive = coint_alive.iloc[min(i-1, len(coint_alive)-1)]

            # Apply status to next period
            end_idx = min(i + frequency, len(coint_alive))
            for j in range(i, end_idx):
                if j < len(coint_alive):
                    coint_alive.iloc[j] = alive

        dead_periods = (~coint_alive).mean()
        logger.debug(f"Cointegration monitoring: {dead_periods:.1%} periods marked as dead")

        return coint_alive

    def generate_regime_filter(self, prices_a: pd.Series, prices_b: pd.Series,
                             returns_a: pd.Series, returns_b: pd.Series,
                             beta: pd.Series, spread: pd.Series) -> Dict[str, pd.Series]:
        """
        Generate comprehensive regime filter combining all components.

        Args:
            prices_a: Price series for asset A
            prices_b: Price series for asset B
            returns_a: Returns of asset A
            returns_b: Returns of asset B
            beta: Dynamic hedge ratio series
            spread: Spread time series

        Returns:
            Dictionary with regime components and combined filter
        """
        logger.info("Generating comprehensive regime filter")

        # Individual regime components
        corr_regime = self.detect_correlation_regime(prices_a, prices_b)
        vol_regime = self.detect_volatility_regime(returns_a, returns_b, beta)
        coint_regime = self.monitor_cointegration(spread)

        # Align all series to common index
        common_index = spread.index
        corr_aligned = corr_regime.reindex(common_index, fill_value=False)
        vol_aligned = vol_regime.reindex(common_index, fill_value=False)
        coint_aligned = coint_regime.reindex(common_index, fill_value=True)

        # Combined regime filter (all conditions must be true)
        combined_filter = corr_aligned & vol_aligned & coint_aligned

        # Calculate regime statistics
        regime_stats = {
            'correlation_favorable': corr_aligned.mean(),
            'volatility_favorable': vol_aligned.mean(),
            'cointegration_alive': coint_aligned.mean(),
            'combined_favorable': combined_filter.mean()
        }

        logger.info(f"Regime statistics: {regime_stats}")

        return {
            'correlation_regime': corr_aligned,
            'volatility_regime': vol_aligned,
            'cointegration_regime': coint_aligned,
            'combined_filter': combined_filter,
            'stats': regime_stats
        }

    def get_regime_diagnostics(self, regime_output: Dict) -> Dict:
        """
        Calculate regime diagnostics for monitoring.

        Args:
            regime_output: Output from generate_regime_filter

        Returns:
            Dictionary of diagnostic metrics
        """
        stats = regime_output['stats']
        combined = regime_output['combined_filter']

        # Regime transition analysis
        regime_changes = combined.diff().abs().sum()
        avg_regime_duration = len(combined) / max(regime_changes, 1)

        # Regime breakdown
        regime_breakdown = {
            'favorable_time': stats['combined_favorable'],
            'correlation_time': stats['correlation_favorable'],
            'volatility_time': stats['volatility_favorable'],
            'cointegration_time': stats['cointegration_alive'],
            'avg_favorable_duration': avg_regime_duration,
            'regime_transitions': regime_changes
        }

        return regime_breakdown


class MarketStressDetector:
    """
    Detect market stress conditions that require additional risk controls.
    """

    def __init__(self, params: Dict):
        """
        Initialize stress detector.

        Args:
            params: Parameter dictionary
        """
        self.params = params
        self.vol_spike_threshold = 2.0  # 2x normal volatility
        self.corr_spike_threshold = 0.95  # 95% correlation spike

    def detect_volatility_spike(self, returns: pd.Series, window: int = 20) -> pd.Series:
        """
        Detect volatility spikes.

        Args:
            returns: Return series
            window: Rolling window for volatility calculation

        Returns:
            Boolean series indicating vol spikes
        """
        vol = returns.rolling(window).std()
        vol_ma = vol.rolling(window * 2).mean()

        vol_ratio = vol / vol_ma.replace(0, np.nan)
        vol_spike = vol_ratio > self.vol_spike_threshold

        return vol_spike.fillna(False)

    def detect_correlation_spike(self, corr_matrix: pd.DataFrame) -> pd.Series:
        """
        Detect correlation spikes across pairs.

        Args:
            corr_matrix: Rolling correlation matrix

        Returns:
            Boolean series indicating correlation spikes
        """
        # Average off-diagonal correlation
        mask = ~np.eye(corr_matrix.shape[1], dtype=bool)
        avg_corr = corr_matrix.where(mask).mean(axis=1)

        corr_spike = avg_corr > self.corr_spike_threshold

        return corr_spike.fillna(False)

    def get_stress_level(self, **kwargs) -> float:
        """
        Calculate overall market stress level (0-1 scale).

        Returns:
            Stress level between 0 (calm) and 1 (extreme stress)
        """
        # This would be implemented with actual market data
        # For now, return baseline stress
        return 0.2