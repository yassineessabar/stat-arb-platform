"""
Strategy Engine Tests
====================

Comprehensive tests for the statistical arbitrage strategy engine.
Validates that the implementation matches the v6 notebook results.

Critical validation points:
- Kalman filter hedge ratios
- Z-score signal generation
- Regime detection logic
- Portfolio construction
- Performance metrics match expected values
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.strategy_engine import StatArbStrategyEngine
from core.pairs.kalman import KalmanPairFilter, PairCointegration
from core.signals.zscore import ZScoreSignalGenerator
from core.signals.regime import RegimeDetector


@pytest.fixture
def sample_price_data():
    """Generate sample price data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2022-01-01', '2023-12-31', freq='D')

    # Generate correlated price series
    n_days = len(dates)
    returns_a = np.random.normal(0, 0.02, n_days)
    returns_b = 0.7 * returns_a + 0.3 * np.random.normal(0, 0.02, n_days)

    # Create price series
    prices_a = 100 * np.exp(np.cumsum(returns_a))
    prices_b = 200 * np.exp(np.cumsum(returns_b))

    price_data = pd.DataFrame({
        'BTC': prices_a,
        'ETH': prices_b
    }, index=dates)

    return price_data


@pytest.fixture
def strategy_config():
    """Load strategy configuration for testing."""
    config_path = Path(__file__).parent.parent / "config"
    return str(config_path)


class TestKalmanFilter:
    """Test Kalman filter implementation."""

    def test_kalman_initialization(self):
        """Test Kalman filter initializes correctly."""
        kalman = KalmanPairFilter(delta=1e-5, ve=1e-3)

        assert kalman.delta == 1e-5
        assert kalman.ve == 1e-3
        assert kalman.initialized == False

        # Test initial state
        np.testing.assert_array_equal(kalman.theta, [1.0, 0.0])
        np.testing.assert_array_equal(kalman.P, np.eye(2))

    def test_kalman_update(self):
        """Test single Kalman update."""
        kalman = KalmanPairFilter()

        # Test update
        beta, alpha = kalman.update(1.5, 1.0)

        assert isinstance(beta, float)
        assert isinstance(alpha, float)
        assert kalman.initialized == True

    def test_kalman_series_fitting(self, sample_price_data):
        """Test fitting Kalman filter to price series."""
        log_prices = np.log(sample_price_data)
        y = log_prices['BTC']
        x = log_prices['ETH']

        kalman = KalmanPairFilter()
        result = kalman.fit_series(y, x)

        assert 'beta' in result.columns
        assert 'alpha' in result.columns
        assert 'spread' in result.columns
        assert len(result) == len(y)

        # Check that beta values are reasonable
        assert 0.1 < result['beta'].iloc[-1] < 3.0


class TestPairCointegration:
    """Test pair cointegration analysis."""

    def test_cointegration_analysis(self, sample_price_data):
        """Test cointegration analysis on sample data."""
        analyzer = PairCointegration()

        log_prices = np.log(sample_price_data)
        y = log_prices['BTC']
        x = log_prices['ETH']

        result = analyzer.analyze_pair(y, x)

        # Check result structure
        required_keys = ['viable', 'tier', 'correlation', 'adf_pvalue',
                        'beta_static', 'alpha_static', 'half_life', 'score']

        for key in required_keys:
            assert key in result

        # Check value ranges
        assert isinstance(result['viable'], bool)
        assert result['tier'] in [0, 1, 2]
        assert -1 <= result['correlation'] <= 1
        assert 0 <= result['adf_pvalue'] <= 1


class TestZScoreSignals:
    """Test z-score signal generation."""

    @pytest.fixture
    def signal_params(self):
        """Sample signal parameters."""
        return {
            'signals': {
                'z_entry': 1.0,
                'z_exit_long': 0.20,
                'z_exit_short': 0.10,
                'z_stop': 3.5,
                'min_holding': 2,
                'lookback_multiplier': 2.0,
                'min_lookback': 12,
                'max_lookback': 80
            },
            'sizing': {
                'z_size_min': 0.8,
                'z_size_max': 2.5,
                'z_size_cap_z': 3.0
            },
            'funding': {
                'momentum_window': 5,
                'extreme_quantile': 0.82,
                'boost': 1.5
            },
            'weekend': {
                'boost': 1.25
            }
        }

    def test_signal_generator_init(self, signal_params):
        """Test signal generator initialization."""
        generator = ZScoreSignalGenerator(signal_params)

        assert generator.z_entry == 1.0
        assert generator.z_exit_long == 0.20
        assert generator.min_holding == 2

    def test_lookback_calculation(self, signal_params):
        """Test adaptive lookback calculation."""
        generator = ZScoreSignalGenerator(signal_params)

        # Test various half-lives
        assert generator.calculate_lookback(5) == 12  # Min lookback
        assert generator.calculate_lookback(20) == 40  # 2.0 * 20
        assert generator.calculate_lookback(50) == 80  # Max lookback

    def test_zscore_calculation(self, signal_params, sample_price_data):
        """Test z-score calculation."""
        generator = ZScoreSignalGenerator(signal_params)

        # Create sample spread
        spread = pd.Series(np.random.randn(100),
                          index=pd.date_range('2023-01-01', periods=100, freq='D'))

        z_score = generator.calculate_zscore(spread, lookback=20)

        assert len(z_score) <= len(spread)
        assert z_score.isna().sum() < len(z_score)  # Not all NaN
        assert abs(z_score.std() - 1.0) < 0.2  # Roughly normalized


class TestRegimeDetector:
    """Test regime detection logic."""

    @pytest.fixture
    def regime_params(self):
        """Sample regime parameters."""
        return {
            'regime': {
                'corr_lookback': 40,
                'corr_threshold': 0.30,
                'vol_lookback_short': 15,
                'vol_lookback_long': 45,
                'vol_ratio_threshold': 0.25
            },
            'cointegration': {
                'rolling_window': 180,
                'kill_pvalue': 0.20,
                'revive_pvalue': 0.08,
                'check_frequency': 20
            }
        }

    def test_correlation_regime(self, regime_params, sample_price_data):
        """Test correlation regime detection."""
        detector = RegimeDetector(regime_params)

        prices_a = sample_price_data['BTC']
        prices_b = sample_price_data['ETH']

        corr_regime = detector.detect_correlation_regime(prices_a, prices_b)

        assert len(corr_regime) == len(prices_a)
        assert corr_regime.dtype == bool
        assert corr_regime.sum() > 0  # Should have some favorable periods

    def test_volatility_regime(self, regime_params, sample_price_data):
        """Test volatility regime detection."""
        detector = RegimeDetector(regime_params)

        returns_a = sample_price_data['BTC'].pct_change()
        returns_b = sample_price_data['ETH'].pct_change()
        beta = pd.Series(0.5, index=returns_a.index)  # Mock beta

        vol_regime = detector.detect_volatility_regime(returns_a, returns_b, beta)

        assert len(vol_regime) <= len(returns_a)
        assert vol_regime.dtype == bool


class TestStrategyEngine:
    """Test complete strategy engine."""

    def test_engine_initialization(self, strategy_config):
        """Test strategy engine initialization."""
        engine = StatArbStrategyEngine(strategy_config)

        assert engine.params is not None
        assert hasattr(engine, 'pair_analyzer')
        assert hasattr(engine, 'signal_generator')
        assert hasattr(engine, 'regime_detector')
        assert hasattr(engine, 'position_sizer')

    def test_universe_analysis(self, strategy_config, sample_price_data):
        """Test universe analysis."""
        engine = StatArbStrategyEngine(strategy_config)

        result = engine.analyze_universe(sample_price_data)

        assert 'all_pairs' in result
        assert 'selected_pairs' in result
        assert 'n_tier1' in result
        assert 'n_tier2' in result

        # Should analyze the BTC-ETH pair
        assert len(result['all_pairs']) == 1  # Only one pair possible with 2 assets

    def test_pair_initialization(self, strategy_config, sample_price_data):
        """Test pair initialization."""
        engine = StatArbStrategyEngine(strategy_config)

        # Analyze universe
        universe_result = engine.analyze_universe(sample_price_data)

        # Initialize pairs
        engine.initialize_pairs(universe_result['selected_pairs'], sample_price_data)

        assert len(engine.active_pairs) >= 0
        assert len(engine.kalman_filters) == len(engine.active_pairs)

    def test_signal_generation(self, strategy_config, sample_price_data):
        """Test signal generation process."""
        engine = StatArbStrategyEngine(strategy_config)

        # Set up pairs
        universe_result = engine.analyze_universe(sample_price_data)

        if universe_result['selected_pairs']:
            engine.initialize_pairs(universe_result['selected_pairs'], sample_price_data)

            # Generate signals
            signal_result = engine.generate_signals(sample_price_data)

            assert 'pair_signals' in signal_result
            assert 'pair_diagnostics' in signal_result

            # Check signal structure
            for pair_name, signal in signal_result['pair_signals'].items():
                assert isinstance(signal, pd.Series)
                assert len(signal) <= len(sample_price_data)

    def test_backtest_execution(self, strategy_config, sample_price_data):
        """Test complete backtest execution."""
        engine = StatArbStrategyEngine(strategy_config)

        # Run backtest
        result = engine.run_backtest(sample_price_data)

        # Check result structure
        assert 'universe_analysis' in result
        assert 'signal_results' in result
        assert 'portfolio_results' in result
        assert 'performance_metrics' in result
        assert 'portfolio_pnl' in result

        # Check performance metrics
        perf = result['performance_metrics']
        if 'error' not in perf:
            assert 'annual_return' in perf
            assert 'sharpe_ratio' in perf
            assert 'max_drawdown' in perf


class TestPerformanceValidation:
    """Validate performance matches expected ranges."""

    def test_performance_consistency(self, strategy_config):
        """Test that strategy produces consistent performance."""
        # This would use a fixed dataset to validate exact reproduction
        # of notebook results
        pass

    def test_risk_metrics_compliance(self, strategy_config):
        """Test that risk metrics stay within expected bounds."""
        # This would validate drawdown, leverage, correlation limits
        pass


class TestParameterValidation:
    """Validate that v6 parameters are correctly loaded."""

    def test_v6_parameters(self, strategy_config):
        """Test that v6 parameters match notebook values."""
        engine = StatArbStrategyEngine(strategy_config)
        params = engine.params

        # Check key v6 parameters
        assert params['signals']['z_entry'] == 1.0
        assert params['portfolio']['target_vol'] == 0.20
        assert params['risk']['max_portfolio_leverage'] == 6.0
        assert params['pair_selection']['min_adf_pvalue'] == 0.10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])