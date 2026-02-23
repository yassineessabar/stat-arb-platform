"""
Strategy Engine - Main Trading Logic
====================================

Orchestrates the complete v6 statistical arbitrage strategy:
1. Kalman filter hedge ratio estimation
2. Regime detection and filtering
3. Z-score signal generation
4. Portfolio construction and position sizing

This is the main engine that coordinates all strategy components
and produces target positions for execution.

WARNING: Production code implementing exact notebook logic.
"""

import numpy as np
import pandas as pd
import yaml
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path

from .pairs.kalman import KalmanPairFilter, PairCointegration
from .signals.zscore import ZScoreSignalGenerator
from .signals.regime import RegimeDetector
from .portfolio.position_sizer import PortfolioPositionSizer

logger = logging.getLogger(__name__)


class StatArbStrategyEngine:
    """
    Complete statistical arbitrage strategy implementation.

    Coordinates all strategy components to generate target positions
    from market data input.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize strategy engine.

        Args:
            config_path: Path to configuration directory
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config"

        self.config_path = Path(config_path)
        self.params = self._load_config()

        # Initialize strategy components
        self.pair_analyzer = PairCointegration(
            min_adf_pvalue=self.params['pair_selection']['min_adf_pvalue'],
            min_correlation=self.params['pair_selection']['min_correlation'],
            min_half_life=self.params['pair_selection']['min_half_life'],
            max_half_life=self.params['pair_selection']['max_half_life']
        )

        self.signal_generator = ZScoreSignalGenerator(self.params)
        self.regime_detector = RegimeDetector(self.params)
        self.position_sizer = PortfolioPositionSizer(self.params)

        # Strategy state
        self.active_pairs = {}
        self.kalman_filters = {}
        self.pair_diagnostics = {}

        logger.info(f"Strategy engine initialized with v6 parameters")

    def _load_config(self) -> Dict:
        """Load configuration from YAML files."""
        params_file = self.config_path / "params_v6.yaml"

        with open(params_file, 'r') as f:
            config = yaml.safe_load(f)

        logger.info(f"Configuration loaded from {params_file}")
        return config

    def analyze_universe(self, price_data: pd.DataFrame) -> Dict:
        """
        Analyze universe of assets for viable trading pairs.

        Args:
            price_data: DataFrame with asset prices (columns = assets, index = dates)

        Returns:
            Dictionary with pair analysis results
        """
        logger.info(f"Analyzing universe of {len(price_data.columns)} assets")

        # Convert to log prices
        log_prices = np.log(price_data)
        assets = list(price_data.columns)

        pair_results = []

        # Analyze all possible pairs
        from itertools import combinations
        for asset_a, asset_b in combinations(assets, 2):
            try:
                y = log_prices[asset_a]
                x = log_prices[asset_b]

                analysis = self.pair_analyzer.analyze_pair(y, x)
                analysis['pair'] = f"{asset_a}-{asset_b}"
                analysis['asset_a'] = asset_a
                analysis['asset_b'] = asset_b

                pair_results.append(analysis)

            except Exception as e:
                logger.warning(f"Failed to analyze pair {asset_a}-{asset_b}: {e}")

        # Sort by quality score and select top pairs
        viable_pairs = [p for p in pair_results if p['viable']]
        viable_pairs.sort(key=lambda x: x['score'], reverse=True)

        max_pairs = self.params['pair_selection']['max_pairs']
        selected_pairs = viable_pairs[:max_pairs]

        logger.info(f"Selected {len(selected_pairs)} pairs from {len(pair_results)} analyzed")

        return {
            'all_pairs': pair_results,
            'selected_pairs': selected_pairs,
            'n_tier1': sum(1 for p in selected_pairs if p['tier'] == 1),
            'n_tier2': sum(1 for p in selected_pairs if p['tier'] == 2)
        }

    def initialize_pairs(self, pair_list: List[Dict], price_data: pd.DataFrame) -> None:
        """
        Initialize Kalman filters and state for selected pairs.

        Args:
            pair_list: List of pair dictionaries from analyze_universe
            price_data: Price data for initialization
        """
        logger.info(f"Initializing {len(pair_list)} pairs")

        log_prices = np.log(price_data)

        for pair_info in pair_list:
            pair_name = pair_info['pair']
            asset_a = pair_info['asset_a']
            asset_b = pair_info['asset_b']

            try:
                # Initialize Kalman filter
                kalman_filter = KalmanPairFilter(
                    delta=self.params['kalman']['delta'],
                    ve=self.params['kalman']['ve']
                )

                # Store pair information
                self.active_pairs[pair_name] = {
                    'asset_a': asset_a,
                    'asset_b': asset_b,
                    'tier': pair_info['tier'],
                    'half_life': pair_info['half_life'],
                    'static_beta': pair_info['beta_static']
                }

                self.kalman_filters[pair_name] = kalman_filter

                logger.debug(f"Initialized pair {pair_name} (tier {pair_info['tier']})")

            except Exception as e:
                logger.error(f"Failed to initialize pair {pair_name}: {e}")

    def generate_signals(self, price_data: pd.DataFrame,
                        returns_data: Optional[pd.DataFrame] = None) -> Dict:
        """
        Generate trading signals for all active pairs.

        Args:
            price_data: Current price data
            returns_data: Return data (computed if not provided)

        Returns:
            Dictionary with signals and diagnostics for all pairs
        """
        if returns_data is None:
            returns_data = price_data.pct_change().fillna(0)

        log_prices = np.log(price_data)

        pair_signals = {}
        pair_diagnostics = {}

        logger.info(f"Generating signals for {len(self.active_pairs)} pairs")

        for pair_name, pair_info in self.active_pairs.items():
            try:
                asset_a = pair_info['asset_a']
                asset_b = pair_info['asset_b']
                tier = pair_info['tier']
                half_life = pair_info['half_life']

                # Get price and return series
                y = log_prices[asset_a]
                x = log_prices[asset_b]
                ret_a = returns_data[asset_a]
                ret_b = returns_data[asset_b]

                # Update Kalman filter
                kalman_result = self.kalman_filters[pair_name].fit_series(y, x)
                beta = kalman_result['beta']
                spread = kalman_result['spread']

                # Generate regime filter
                regime_output = self.regime_detector.generate_regime_filter(
                    price_data[asset_a], price_data[asset_b],
                    ret_a, ret_b, beta, spread
                )

                # Calculate tier weight
                tier_weight = 1.0 if tier == 1 else self.params['tier_thresholds']['tier2_weight_discount']

                # Generate signals
                signal_output = self.signal_generator.generate_full_signals(
                    spread, half_life, ret_a, ret_b, beta,
                    regime_output['combined_filter'], tier_weight
                )

                pair_signals[pair_name] = signal_output['signal']

                # Collect diagnostics
                signal_diag = self.signal_generator.get_signal_diagnostics(signal_output)
                regime_diag = self.regime_detector.get_regime_diagnostics(regime_output)
                kalman_diag = self.kalman_filters[pair_name].get_diagnostics()

                pair_diagnostics[pair_name] = {
                    'tier': tier,
                    'half_life': half_life,
                    **signal_diag,
                    **regime_diag,
                    **kalman_diag
                }

            except Exception as e:
                logger.error(f"Failed to generate signals for {pair_name}: {e}")
                pair_signals[pair_name] = pd.Series(0.0, index=price_data.index)

        self.pair_diagnostics = pair_diagnostics

        return {
            'pair_signals': pair_signals,
            'pair_diagnostics': pair_diagnostics
        }

    def construct_portfolio(self, pair_signals: Dict[str, pd.Series]) -> Dict:
        """
        Construct portfolio from pair signals.

        Args:
            pair_signals: Dictionary of pair signals

        Returns:
            Portfolio construction results
        """
        logger.info("Constructing portfolio from pair signals")

        # Convert signals to PnL (for backtesting) or pass through for live trading
        # In live trading, this would be the actual PnL from executed trades
        # For now, we'll use the signals directly

        portfolio_result = self.position_sizer.construct_portfolio(pair_signals)

        return portfolio_result

    def run_backtest(self, price_data: pd.DataFrame,
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> Dict:
        """
        Run complete backtest on historical data.

        Args:
            price_data: Historical price data
            start_date: Start date for backtest
            end_date: End date for backtest

        Returns:
            Complete backtest results
        """
        logger.info("Running complete backtest")

        # Filter date range
        if start_date:
            price_data = price_data[price_data.index >= start_date]
        if end_date:
            price_data = price_data[price_data.index <= end_date]

        # Analyze universe and select pairs
        universe_analysis = self.analyze_universe(price_data)

        # Initialize selected pairs
        self.initialize_pairs(universe_analysis['selected_pairs'], price_data)

        # Generate signals
        signal_results = self.generate_signals(price_data)

        # Construct portfolio
        portfolio_results = self.construct_portfolio(signal_results['pair_signals'])

        # Calculate performance metrics
        portfolio_pnl = portfolio_results['portfolio_pnl']
        performance_metrics = self._calculate_performance_metrics(portfolio_pnl)

        return {
            'universe_analysis': universe_analysis,
            'signal_results': signal_results,
            'portfolio_results': portfolio_results,
            'performance_metrics': performance_metrics,
            'portfolio_pnl': portfolio_pnl
        }

    def _calculate_performance_metrics(self, pnl_series: pd.Series) -> Dict:
        """Calculate comprehensive performance metrics."""

        if len(pnl_series) < 30:
            return {'error': 'Insufficient data for metrics'}

        returns = pnl_series.dropna()
        equity = (1 + returns).cumprod()

        # Basic metrics
        total_return = equity.iloc[-1] - 1
        annual_return = returns.mean() * self.params['data']['trading_days_year']
        annual_vol = returns.std() * np.sqrt(self.params['data']['trading_days_year'])

        # Risk metrics
        sharpe_ratio = annual_return / annual_vol if annual_vol > 0 else 0

        drawdown = (equity - equity.cummax()) / equity.cummax()
        max_drawdown = drawdown.min()

        # Additional metrics
        positive_days = (returns > 0).mean()
        profit_factor = returns[returns > 0].sum() / abs(returns[returns < 0].sum()) if (returns < 0).any() else np.inf

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'hit_rate': positive_days,
            'profit_factor': profit_factor,
            'n_observations': len(returns)
        }

    def get_current_positions(self, current_prices: pd.Series, account_value: float) -> Dict:
        """
        Get current target positions for live trading.

        Args:
            current_prices: Current asset prices
            account_value: Current account value

        Returns:
            Dictionary of target positions by asset
        """
        # This would be implemented for live trading
        # Generate signals for current data point and convert to positions

        # For now, return empty positions
        return {}

    def get_strategy_diagnostics(self) -> Dict:
        """Get comprehensive strategy diagnostics for monitoring."""

        return {
            'active_pairs': len(self.active_pairs),
            'pair_diagnostics': self.pair_diagnostics,
            'strategy_version': self.params['strategy']['version'],
            'config_path': str(self.config_path)
        }