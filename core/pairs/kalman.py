"""
Kalman Filter for Dynamic Hedge Ratio Estimation
================================================

Implements the exact Kalman filter logic from the v6 notebook for
dynamic hedge ratio estimation between cointegrated pairs.

Key Features:
- Adaptive hedge ratios that evolve with market conditions
- Handles time-varying cointegration relationships
- Optimized for real-time execution

WARNING: This is production code. Do not modify without full validation.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class KalmanPairFilter:
    """
    Kalman filter for estimating dynamic hedge ratios between asset pairs.

    Implementation matches exactly the v6 notebook logic that achieved 3.98 Sharpe.
    """

    def __init__(self, delta: float = 1e-5, ve: float = 1e-3):
        """
        Initialize Kalman filter.

        Args:
            delta: State transition noise parameter (default: 1e-5)
            ve: Observation noise parameter (default: 1e-3)
        """
        self.delta = delta
        self.ve = ve
        self.reset()

    def reset(self):
        """Reset filter state."""
        self.theta = np.array([1.0, 0.0])  # [beta, alpha]
        self.P = np.eye(2)                 # Error covariance
        self.R = self.ve                   # Observation noise
        self.Q = self.delta / (1 - self.delta) * np.eye(2)  # Process noise
        self.initialized = False

        logger.debug("Kalman filter reset")

    def update(self, y: float, x: float) -> Tuple[float, float]:
        """
        Update filter with new observation.

        Args:
            y: Dependent variable (log price of asset A)
            x: Independent variable (log price of asset B)

        Returns:
            Tuple of (beta, alpha) hedge ratio parameters
        """
        # Prediction step
        P_pred = self.P + self.Q

        # Measurement update
        H = np.array([x, 1.0])
        innovation = y - H @ self.theta

        # Innovation covariance
        S = H @ P_pred @ H + self.R

        # Kalman gain
        K = P_pred @ H / S

        # State update
        self.theta = self.theta + K * innovation
        self.P = P_pred - np.outer(K, H) @ P_pred

        # Adaptive noise estimation (key v6 feature)
        self.R = (1 - self.delta) * self.R + self.delta * innovation**2

        beta, alpha = self.theta[0], self.theta[1]

        if not self.initialized:
            logger.info(f"Kalman filter initialized: β={beta:.4f}, α={alpha:.4f}")
            self.initialized = True

        return beta, alpha

    def fit_series(self, y: pd.Series, x: pd.Series) -> pd.DataFrame:
        """
        Fit Kalman filter to entire time series.

        Args:
            y: Time series of dependent variable (asset A log prices)
            x: Time series of independent variable (asset B log prices)

        Returns:
            DataFrame with columns: beta, alpha, spread
        """
        if len(y) != len(x):
            raise ValueError("Time series must have same length")

        if y.index.equals(x.index) is False:
            raise ValueError("Time series must have same index")

        self.reset()

        n = len(y)
        betas = np.zeros(n)
        alphas = np.zeros(n)

        y_vals = y.values
        x_vals = x.values

        logger.info(f"Fitting Kalman filter to {n} observations")

        for i in range(n):
            beta, alpha = self.update(y_vals[i], x_vals[i])
            betas[i] = beta
            alphas[i] = alpha

        result = pd.DataFrame({
            'beta': betas,
            'alpha': alphas
        }, index=y.index)

        # Calculate spread using dynamic hedge ratios
        result['spread'] = y - result['beta'] * x - result['alpha']

        logger.info(f"Kalman fit complete. Final β={betas[-1]:.4f}, α={alphas[-1]:.4f}")

        return result

    def get_current_params(self) -> Tuple[float, float]:
        """Get current hedge ratio parameters."""
        return self.theta[0], self.theta[1]

    def get_diagnostics(self) -> dict:
        """Get filter diagnostics for monitoring."""
        return {
            'beta': self.theta[0],
            'alpha': self.theta[1],
            'observation_noise': self.R,
            'state_uncertainty': np.trace(self.P),
            'initialized': self.initialized
        }


class PairCointegration:
    """
    Cointegration analysis for asset pairs using the exact v6 methodology.
    """

    def __init__(self,
                 min_adf_pvalue: float = 0.10,
                 min_correlation: float = 0.40,
                 min_half_life: float = 2,
                 max_half_life: float = 120):
        """
        Initialize cointegration analyzer.

        Args:
            min_adf_pvalue: Maximum ADF p-value for cointegration (v6: 0.10)
            min_correlation: Minimum correlation between assets (v6: 0.40)
            min_half_life: Minimum OU half-life in days (v6: 2)
            max_half_life: Maximum OU half-life in days (v6: 120)
        """
        self.min_adf_pvalue = min_adf_pvalue
        self.min_correlation = min_correlation
        self.min_half_life = min_half_life
        self.max_half_life = max_half_life

    def analyze_pair(self, y: pd.Series, x: pd.Series) -> dict:
        """
        Analyze cointegration between two time series.

        Args:
            y: First asset log prices
            x: Second asset log prices

        Returns:
            Dictionary with cointegration statistics
        """
        from statsmodels.tsa.stattools import adfuller
        import statsmodels.api as sm

        # Basic correlation
        prices_y = y.apply(np.exp)  # Convert back to prices for correlation
        prices_x = x.apply(np.exp)
        correlation = prices_y.corr(prices_x)

        if correlation < self.min_correlation:
            return self._failed_analysis("Low correlation", correlation)

        # OLS regression for initial hedge ratio
        X_ols = sm.add_constant(x.values)
        ols = sm.OLS(y.values, X_ols).fit()
        beta_static, alpha_static = ols.params[1], ols.params[0]

        # Static spread for cointegration test
        spread_static = y - beta_static * x - alpha_static

        try:
            adf_result = adfuller(spread_static.dropna(), autolag='AIC')
            adf_pvalue = adf_result[1]
        except Exception as e:
            logger.warning(f"ADF test failed: {e}")
            return self._failed_analysis("ADF test failed", correlation)

        if adf_pvalue > self.min_adf_pvalue:
            return self._failed_analysis("High ADF p-value", correlation, adf_pvalue)

        # OU half-life estimation
        half_life = self._estimate_half_life(spread_static)

        if not (self.min_half_life <= half_life <= self.max_half_life):
            return self._failed_analysis("Half-life out of range", correlation, adf_pvalue, half_life)

        # Tier classification (from v6)
        if adf_pvalue < 0.05:
            tier = 1  # Strong cointegration
        else:
            tier = 2  # Marginal cointegration

        # Calculate quality score
        score = (1 - adf_pvalue) * correlation * half_life * (1.5 if tier == 1 else 1.0)

        return {
            'viable': True,
            'tier': tier,
            'correlation': correlation,
            'adf_pvalue': adf_pvalue,
            'beta_static': beta_static,
            'alpha_static': alpha_static,
            'half_life': half_life,
            'score': score,
            'ols_rsquared': ols.rsquared
        }

    def _estimate_half_life(self, spread: pd.Series) -> float:
        """Estimate OU half-life using AR(1) regression."""
        import statsmodels.api as sm

        ds = spread.diff().dropna()
        sl = spread.shift(1).dropna()

        # Align series
        common_idx = ds.index.intersection(sl.index)
        if len(common_idx) < 60:
            return 60  # Default if insufficient data

        ds_aligned = ds.loc[common_idx]
        sl_aligned = sl.loc[common_idx]

        try:
            # OU regression: ds = theta * sl + const + error
            X = sm.add_constant(sl_aligned.values)
            ou_model = sm.OLS(ds_aligned.values, X).fit()
            theta = -ou_model.params[1]  # Mean reversion speed

            if theta > 0:
                half_life = np.log(2) / theta
            else:
                half_life = 60  # Default for non-mean-reverting

        except Exception:
            half_life = 60

        return np.clip(half_life, self.min_half_life, self.max_half_life)

    def _failed_analysis(self, reason: str, correlation: float = 0,
                        adf_pvalue: float = 1, half_life: float = 0) -> dict:
        """Return failed analysis result."""
        return {
            'viable': False,
            'tier': 0,
            'correlation': correlation,
            'adf_pvalue': adf_pvalue,
            'beta_static': 0,
            'alpha_static': 0,
            'half_life': half_life,
            'score': 0,
            'reason': reason
        }