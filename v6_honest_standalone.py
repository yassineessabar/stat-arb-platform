#!/usr/bin/env python3
"""
HONEST V6 STANDALONE IMPLEMENTATION
====================================

This is an HONEST implementation of the v6 strategy without any artificial calibration.
It implements the actual statistical arbitrage logic:
- Cointegration testing for pair selection
- Kalman filters for dynamic hedge ratios
- Z-score based mean reversion signals
- Proper position sizing and risk management

Requirements:
    pip install pandas numpy yfinance statsmodels scipy

Run with:
    python3 v6_honest_standalone.py

This shows REAL results, not artificially boosted numbers.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
import warnings
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

warnings.filterwarnings('ignore')

# Try importing statsmodels for proper cointegration tests
try:
    from statsmodels.tsa.stattools import adfuller, coint
    import statsmodels.api as sm
    HAS_STATSMODELS = True
    print("✅ Using statsmodels for proper cointegration testing")
except ImportError:
    HAS_STATSMODELS = False
    print("⚠️  statsmodels not found - install it for better results: pip install statsmodels")


# ============================================================================
# CONFIGURATION (Based on actual v6 parameters)
# ============================================================================

CONFIG = {
    'lookback_period': 180,  # Days for cointegration testing
    'z_entry': 2.0,          # Z-score threshold for entry
    'z_exit': 0.5,           # Z-score threshold for exit
    'z_stop': 3.5,           # Stop loss threshold
    'min_correlation': 0.5,  # Minimum correlation for pair selection
    'max_pairs': 20,         # Maximum number of pairs to trade
    'position_size': 0.05,   # 5% per position
    'max_leverage': 2.0,     # Maximum leverage
    'vol_target': 0.15,      # 15% target volatility
}


# ============================================================================
# KALMAN FILTER
# ============================================================================

class KalmanFilter:
    """Kalman filter for dynamic hedge ratio estimation"""

    def __init__(self, delta: float = 0.0001, ve: float = 0.001):
        self.delta = delta  # Transition covariance
        self.ve = ve        # Observation noise
        self.beta = None    # Hedge ratio
        self.P = None       # Estimation error covariance
        self.initialized = False

    def update(self, y: float, x: float) -> float:
        """Update filter with new price observation"""
        if not self.initialized:
            # Initialize with OLS estimate
            self.beta = y / x if x != 0 else 1.0
            self.P = 1.0
            self.initialized = True
            return self.beta

        # Predict
        self.P = self.P + self.delta

        # Update
        e = y - self.beta * x  # Innovation
        Q = x * x * self.P + self.ve  # Innovation variance
        K = self.P * x / Q  # Kalman gain

        self.beta = self.beta + K * e
        self.P = self.P * (1 - K * x)

        return self.beta


# ============================================================================
# PAIR SELECTION
# ============================================================================

def test_cointegration(y: pd.Series, x: pd.Series) -> Tuple[bool, float, float]:
    """
    Test if two series are cointegrated
    Returns: (is_cointegrated, p_value, hedge_ratio)
    """
    if not HAS_STATSMODELS:
        # Fallback: use correlation as proxy
        corr = y.corr(x)
        is_coint = abs(corr) > CONFIG['min_correlation']
        hedge_ratio = (y.std() / x.std()) * np.sign(corr)
        return is_coint, 1 - abs(corr), hedge_ratio

    try:
        # Engle-Granger two-step method
        model = sm.OLS(y, sm.add_constant(x))
        result = model.fit()
        hedge_ratio = result.params[1]

        # Test residuals for stationarity
        residuals = y - hedge_ratio * x
        adf_result = adfuller(residuals, autolag='AIC')

        # Check if cointegrated (p-value < 0.05)
        p_value = adf_result[1]
        is_cointegrated = p_value < 0.05

        return is_cointegrated, p_value, hedge_ratio

    except Exception as e:
        return False, 1.0, 1.0


def select_pairs(prices: pd.DataFrame) -> List[Dict]:
    """Select cointegrated pairs for trading"""

    assets = list(prices.columns)
    pairs = []

    print(f"🔍 Testing {len(assets) * (len(assets) - 1) // 2} potential pairs...")

    for i in range(len(assets)):
        for j in range(i + 1, len(assets)):
            asset1, asset2 = assets[i], assets[j]

            # Get price series
            y = prices[asset1]
            x = prices[asset2]

            # Check correlation first (faster)
            corr = y.corr(x)
            if abs(corr) < CONFIG['min_correlation']:
                continue

            # Test cointegration
            is_coint, p_value, hedge_ratio = test_cointegration(y, x)

            if is_coint:
                pairs.append({
                    'asset1': asset1,
                    'asset2': asset2,
                    'correlation': corr,
                    'p_value': p_value,
                    'hedge_ratio': hedge_ratio,
                    'score': abs(corr) * (1 - p_value)  # Simple scoring
                })

    # Sort by score and select top pairs
    pairs.sort(key=lambda x: x['score'], reverse=True)
    selected = pairs[:CONFIG['max_pairs']]

    print(f"✅ Found {len(selected)} cointegrated pairs")

    return selected


# ============================================================================
# SIGNAL GENERATION
# ============================================================================

class PairTrader:
    """Manages trading for a single pair"""

    def __init__(self, asset1: str, asset2: str, lookback: int = 60):
        self.asset1 = asset1
        self.asset2 = asset2
        self.lookback = lookback

        self.kalman = KalmanFilter()
        self.spreads = []
        self.position = 0  # 1 = long spread, -1 = short spread, 0 = no position

    def update(self, price1: float, price2: float) -> int:
        """Update with new prices and return trading signal"""

        # Update Kalman filter
        hedge_ratio = self.kalman.update(price1, price2)

        # Calculate spread
        spread = price1 - hedge_ratio * price2
        self.spreads.append(spread)

        # Keep only lookback period
        if len(self.spreads) > self.lookback:
            self.spreads.pop(0)

        # Need minimum history
        if len(self.spreads) < 20:
            return 0

        # Calculate z-score
        spread_mean = np.mean(self.spreads)
        spread_std = np.std(self.spreads)

        if spread_std == 0:
            return self.position

        z_score = (spread - spread_mean) / spread_std

        # Generate signals
        if self.position == 0:  # No position
            if z_score > CONFIG['z_entry']:
                self.position = -1  # Short spread (expecting mean reversion)
            elif z_score < -CONFIG['z_entry']:
                self.position = 1   # Long spread

        else:  # Have position
            # Exit conditions
            if abs(z_score) < CONFIG['z_exit']:  # Converged to mean
                self.position = 0
            elif abs(z_score) > CONFIG['z_stop']:  # Stop loss
                self.position = 0
            elif (self.position == 1 and z_score > 0):  # Wrong direction
                self.position = 0
            elif (self.position == -1 and z_score < 0):  # Wrong direction
                self.position = 0

        return self.position

    def get_weights(self) -> Tuple[float, float]:
        """Get position weights for each asset"""
        if not self.kalman.initialized or self.position == 0:
            return 0.0, 0.0

        # Position size
        size = CONFIG['position_size']

        # Weights based on hedge ratio
        beta = self.kalman.beta
        total = abs(1) + abs(beta)

        w1 = size * (1 / total) * self.position
        w2 = size * (beta / total) * (-self.position)

        return w1, w2


# ============================================================================
# PORTFOLIO MANAGEMENT
# ============================================================================

class Portfolio:
    """Manages the overall portfolio"""

    def __init__(self, pairs: List[Dict]):
        self.pairs = pairs
        self.traders = {}

        # Create trader for each pair
        for pair in pairs:
            key = f"{pair['asset1']}/{pair['asset2']}"
            self.traders[key] = PairTrader(pair['asset1'], pair['asset2'])

        self.returns = []

    def update(self, prices: pd.Series) -> float:
        """Update portfolio and return daily P&L"""

        # Collect all positions
        asset_weights = {}

        for pair in self.pairs:
            asset1 = pair['asset1']
            asset2 = pair['asset2']
            key = f"{asset1}/{asset2}"

            if asset1 not in prices or asset2 not in prices:
                continue

            # Update pair trader
            trader = self.traders[key]
            signal = trader.update(prices[asset1], prices[asset2])

            # Get weights
            w1, w2 = trader.get_weights()

            # Aggregate weights
            if w1 != 0:
                if asset1 not in asset_weights:
                    asset_weights[asset1] = 0
                asset_weights[asset1] += w1

            if w2 != 0:
                if asset2 not in asset_weights:
                    asset_weights[asset2] = 0
                asset_weights[asset2] += w2

        # Apply leverage constraints
        total_exposure = sum(abs(w) for w in asset_weights.values())
        if total_exposure > CONFIG['max_leverage']:
            scale = CONFIG['max_leverage'] / total_exposure
            asset_weights = {k: v * scale for k, v in asset_weights.items()}

        return asset_weights


# ============================================================================
# BACKTEST
# ============================================================================

def run_backtest(prices: pd.DataFrame) -> Dict:
    """Run the actual v6 strategy backtest"""

    print("\n" + "="*60)
    print("RUNNING HONEST V6 BACKTEST")
    print("="*60)

    # Select pairs using lookback period
    lookback_prices = prices.iloc[:CONFIG['lookback_period']]
    selected_pairs = select_pairs(lookback_prices)

    if not selected_pairs:
        print("❌ No cointegrated pairs found")
        return None

    print(f"\n🏆 Top pairs selected:")
    for i, pair in enumerate(selected_pairs[:5]):
        print(f"   {i+1}. {pair['asset1']}/{pair['asset2']} - "
              f"Corr: {pair['correlation']:.3f}, P-value: {pair['p_value']:.3f}")

    # Initialize portfolio
    portfolio = Portfolio(selected_pairs)

    # Run simulation
    portfolio_returns = []
    weights_history = []

    # Start after lookback period
    for i in range(CONFIG['lookback_period'], len(prices)):
        current_prices = prices.iloc[i]
        prev_prices = prices.iloc[i-1]

        # Get portfolio weights
        weights = portfolio.update(current_prices)
        weights_history.append(weights)

        # Calculate returns
        returns = (current_prices - prev_prices) / prev_prices

        # Calculate portfolio return
        portfolio_return = sum(weights.get(asset, 0) * returns.get(asset, 0)
                              for asset in weights.keys())

        portfolio_returns.append(portfolio_return)

    # Convert to series
    portfolio_returns = pd.Series(
        portfolio_returns,
        index=prices.index[CONFIG['lookback_period']:]
    )

    # Apply volatility targeting
    if len(portfolio_returns) > 20:
        # Calculate rolling volatility
        rolling_vol = portfolio_returns.rolling(20).std() * np.sqrt(252)

        # Scale to target volatility
        vol_scalar = CONFIG['vol_target'] / (rolling_vol + 0.001)
        vol_scalar = vol_scalar.clip(0.5, 2.0)  # Limit scaling

        portfolio_returns = portfolio_returns * vol_scalar

    # Calculate performance metrics
    cumulative_returns = (1 + portfolio_returns).cumprod()
    total_return = cumulative_returns.iloc[-1] - 1

    days = len(portfolio_returns)
    years = days / 252
    annual_return = (1 + total_return) ** (1/years) - 1

    # Sharpe ratio
    sharpe = np.sqrt(252) * portfolio_returns.mean() / (portfolio_returns.std() + 1e-6)

    # Max drawdown
    peak = cumulative_returns.expanding().max()
    drawdown = (cumulative_returns - peak) / peak
    max_drawdown = drawdown.min()

    # Other metrics
    win_rate = (portfolio_returns > 0).mean()

    positive_returns = portfolio_returns[portfolio_returns > 0]
    negative_returns = portfolio_returns[portfolio_returns < 0]

    if len(negative_returns) > 0:
        profit_factor = positive_returns.sum() / abs(negative_returns.sum())
    else:
        profit_factor = np.inf

    return {
        'pairs': selected_pairs,
        'returns': portfolio_returns,
        'cumulative': cumulative_returns,
        'metrics': {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'num_trades': len(portfolio_returns)
        }
    }


# ============================================================================
# DATA FETCHING
# ============================================================================

def fetch_data():
    """Fetch cryptocurrency data"""

    symbols = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
        "ADA-USD", "AVAX-USD", "DOGE-USD", "DOT-USD", "MATIC-USD",
        "LINK-USD", "LTC-USD", "BCH-USD", "ALGO-USD", "ATOM-USD",
        "UNI-USD", "NEAR-USD", "FTM-USD", "SAND-USD", "MANA-USD"
    ]

    print(f"📥 Fetching data for {len(symbols)} cryptocurrencies...")

    start_date = "2022-01-01"
    end_date = "2024-02-12"

    data = yf.download(symbols, start=start_date, end=end_date, progress=False)

    # Extract closing prices
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']
    else:
        prices = data

    # Clean column names
    prices.columns = [col.replace('-USD', '') for col in prices.columns]

    # Forward fill and drop NaN
    prices = prices.ffill().dropna()

    print(f"✅ Data fetched: {len(prices.columns)} assets, {len(prices)} days")

    return prices


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution"""

    print("\n" + "="*80)
    print(" HONEST V6 STANDALONE BACKTEST ".center(80))
    print(" Real Implementation - No Artificial Boosting ".center(80))
    print("="*80)

    # Fetch data
    prices = fetch_data()

    # Run backtest
    results = run_backtest(prices)

    if results is None:
        print("\n❌ Backtest failed - no valid pairs found")
        return None

    # Display results
    metrics = results['metrics']

    print("\n" + "="*60)
    print(" BACKTEST RESULTS ".center(60))
    print("="*60)

    print(f"\n📈 Performance Metrics (REAL):")
    print(f"   {'Total Return:':20} {metrics['total_return']*100:>10.1f}%")
    print(f"   {'Annual Return:':20} {metrics['annual_return']*100:>10.1f}%")
    print(f"   {'Sharpe Ratio:':20} {metrics['sharpe_ratio']:>10.2f}")
    print(f"   {'Max Drawdown:':20} {metrics['max_drawdown']*100:>10.1f}%")
    print(f"   {'Win Rate:':20} {metrics['win_rate']*100:>10.1f}%")
    print(f"   {'Profit Factor:':20} {metrics['profit_factor']:>10.2f}")
    print(f"   {'Total Days:':20} {metrics['num_trades']:>10}")

    print(f"\n📊 Analysis:")
    if metrics['annual_return'] > 0.20:
        print("   ✅ Strategy is profitable with good returns")
    elif metrics['annual_return'] > 0:
        print("   ⚠️  Strategy is profitable but returns are modest")
    else:
        print("   ❌ Strategy is not profitable in this configuration")

    if metrics['sharpe_ratio'] > 1.0:
        print("   ✅ Risk-adjusted returns are good")
    elif metrics['sharpe_ratio'] > 0.5:
        print("   ⚠️  Risk-adjusted returns are acceptable")
    else:
        print("   ❌ Risk-adjusted returns are poor")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save metrics
    metrics_df = pd.DataFrame([metrics])
    metrics_file = f"v6_honest_results_{timestamp}.csv"
    metrics_df.to_csv(metrics_file, index=False)

    # Save returns
    returns_file = f"v6_honest_returns_{timestamp}.csv"
    results['returns'].to_csv(returns_file)

    print(f"\n💾 Results saved:")
    print(f"   - {metrics_file}")
    print(f"   - {returns_file}")

    print("\n" + "="*80)
    print("📌 NOTE: These are REAL results from actual strategy implementation")
    print("   No artificial boosting or calibration factors applied")
    print("="*80)

    return results


if __name__ == "__main__":
    results = main()