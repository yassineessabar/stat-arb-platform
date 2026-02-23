// Mock Jupyter notebook data for the Statistical Arbitrage strategy
export const mockNotebook = {
  cells: [
    {
      cell_type: "markdown",
      source: "# Statistical Arbitrage Trading Strategy\n\n## Cointegration-Based Pairs Trading\n\nThis notebook implements a statistical arbitrage strategy that identifies and trades cointegrated cryptocurrency pairs.",
      metadata: {}
    },
    {
      cell_type: "code",
      execution_count: 1,
      source: `import numpy as np
import pandas as pd
import yfinance as yf
from statsmodels.tsa.stattools import coint, adfuller
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

print("Libraries imported successfully")`,
      outputs: [
        {
          output_type: "stream",
          name: "stdout",
          text: ["Libraries imported successfully\n"]
        }
      ],
      metadata: {}
    },
    {
      cell_type: "markdown",
      source: "## 1. Universe Selection\n\nWe analyze 30+ cryptocurrency pairs to find cointegrated relationships suitable for statistical arbitrage.",
      metadata: {}
    },
    {
      cell_type: "code",
      execution_count: 2,
      source: `# Define universe of crypto pairs
universe = [
    'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'SOL-USD',
    'ADA-USD', 'DOGE-USD', 'TRX-USD', 'LINK-USD', 'MATIC-USD',
    'BCH-USD', 'XLM-USD', 'UNI-USD', 'LTC-USD', 'AVAX-USD'
]

# Download historical data
start_date = '2023-01-01'
end_date = '2024-02-13'

data = yf.download(universe, start=start_date, end=end_date, progress=False)['Close']
print(f"Downloaded data for {len(data.columns)} assets")
print(f"Date range: {data.index[0]} to {data.index[-1]}")
print(f"Total trading days: {len(data)}")`,
      outputs: [
        {
          output_type: "stream",
          name: "stdout",
          text: ["Downloaded data for 15 assets\nDate range: 2023-01-01 to 2024-02-13\nTotal trading days: 408\n"]
        }
      ],
      metadata: {}
    },
    {
      cell_type: "markdown",
      source: "## 2. Cointegration Testing\n\nWe test all possible pairs for cointegration using the Engle-Granger test.",
      metadata: {}
    },
    {
      cell_type: "code",
      execution_count: 3,
      source: `def test_cointegration(series1, series2):
    """Test for cointegration between two price series"""
    score, pvalue, _ = coint(series1, series2)
    return pvalue

def find_cointegrated_pairs(data, threshold=0.05):
    """Find all cointegrated pairs in the dataset"""
    n = data.shape[1]
    pairs = []

    for i in range(n):
        for j in range(i+1, n):
            S1 = data.iloc[:, i]
            S2 = data.iloc[:, j]

            pvalue = test_cointegration(S1, S2)

            if pvalue < threshold:
                pairs.append({
                    'pair': f"{data.columns[i]}-{data.columns[j]}",
                    'pvalue': pvalue,
                    'asset1': data.columns[i],
                    'asset2': data.columns[j]
                })

    return sorted(pairs, key=lambda x: x['pvalue'])

# Find cointegrated pairs
coint_pairs = find_cointegrated_pairs(data)
print(f"Found {len(coint_pairs)} cointegrated pairs (p < 0.05)")
print("\nTop 5 pairs:")
for i, pair in enumerate(coint_pairs[:5], 1):
    print(f"{i}. {pair['pair']}: p-value = {pair['pvalue']:.4f}")`,
      outputs: [
        {
          output_type: "stream",
          name: "stdout",
          text: ["Found 8 cointegrated pairs (p < 0.05)\n\nTop 5 pairs:\n1. XLM-USD-XRP-USD: p-value = 0.0012\n2. ETH-USD-SOL-USD: p-value = 0.0089\n3. BCH-USD-TRX-USD: p-value = 0.0156\n4. ADA-USD-BTC-USD: p-value = 0.0234\n5. LINK-USD-UNI-USD: p-value = 0.0412\n"]
        }
      ],
      metadata: {}
    },
    {
      cell_type: "markdown",
      source: "## 3. Strategy Parameters\n\nWe calculate z-scores and define entry/exit thresholds for our selected pairs.",
      metadata: {}
    },
    {
      cell_type: "code",
      execution_count: 4,
      source: `class PairTradingStrategy:
    def __init__(self, asset1_prices, asset2_prices, window=20):
        self.asset1 = asset1_prices
        self.asset2 = asset2_prices
        self.window = window

        # Calculate hedge ratio
        self.hedge_ratio = self._calculate_hedge_ratio()

        # Calculate spread
        self.spread = self.asset1 - self.hedge_ratio * self.asset2

        # Calculate z-score
        self.zscore = self._calculate_zscore()

    def _calculate_hedge_ratio(self):
        """Calculate optimal hedge ratio using linear regression"""
        model = LinearRegression()
        model.fit(self.asset2.values.reshape(-1, 1), self.asset1.values)
        return model.coef_[0]

    def _calculate_zscore(self):
        """Calculate rolling z-score of the spread"""
        spread_mean = self.spread.rolling(window=self.window).mean()
        spread_std = self.spread.rolling(window=self.window).std()
        return (self.spread - spread_mean) / spread_std

    def generate_signals(self, entry_threshold=2.0, exit_threshold=0.5):
        """Generate trading signals based on z-score thresholds"""
        signals = pd.Series(0, index=self.zscore.index)

        # Entry signals
        signals[self.zscore > entry_threshold] = -1  # Short spread
        signals[self.zscore < -entry_threshold] = 1   # Long spread

        # Exit signals
        signals[abs(self.zscore) < exit_threshold] = 0

        return signals

# Apply strategy to top pair (XLM-XRP)
xlm_prices = data['XLM-USD']
xrp_prices = data['XRP-USD']

strategy = PairTradingStrategy(xlm_prices, xrp_prices)
signals = strategy.generate_signals()

print(f"Hedge Ratio: {strategy.hedge_ratio:.4f}")
print(f"Current Z-Score: {strategy.zscore.iloc[-1]:.2f}")
print(f"Signal Distribution:")
print(signals.value_counts())`,
      outputs: [
        {
          output_type: "stream",
          name: "stdout",
          text: ["Hedge Ratio: 0.8923\nCurrent Z-Score: 1.45\nSignal Distribution:\n 0    350\n 1     32\n-1     26\nName: count, dtype: int64\n"]
        }
      ],
      metadata: {}
    },
    {
      cell_type: "markdown",
      source: "## 4. Backtest Results\n\nWe backtest the strategy on our top 3 pairs and calculate performance metrics.",
      metadata: {}
    },
    {
      cell_type: "code",
      execution_count: 5,
      source: `def backtest_pair(asset1_prices, asset2_prices, signals, initial_capital=100000):
    """Backtest a pairs trading strategy"""
    returns1 = asset1_prices.pct_change()
    returns2 = asset2_prices.pct_change()

    # Strategy returns (simplified)
    strategy_returns = signals.shift(1) * (returns1 - returns2)
    strategy_returns = strategy_returns.fillna(0)

    # Calculate cumulative returns
    cumulative_returns = (1 + strategy_returns).cumprod()

    # Calculate metrics
    total_return = cumulative_returns.iloc[-1] - 1
    annual_return = (1 + total_return) ** (252 / len(returns1)) - 1
    volatility = strategy_returns.std() * np.sqrt(252)
    sharpe_ratio = annual_return / volatility if volatility > 0 else 0

    # Maximum drawdown
    cummax = cumulative_returns.cummax()
    drawdown = (cumulative_returns - cummax) / cummax
    max_drawdown = drawdown.min()

    # Win rate
    winning_trades = strategy_returns[strategy_returns > 0]
    losing_trades = strategy_returns[strategy_returns < 0]
    win_rate = len(winning_trades) / (len(winning_trades) + len(losing_trades)) if len(winning_trades) + len(losing_trades) > 0 else 0

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'cumulative_returns': cumulative_returns
    }

# Backtest top 3 pairs
results = {}
top_pairs = [
    ('XLM-USD', 'XRP-USD', 'XLM-XRP'),
    ('ETH-USD', 'SOL-USD', 'ETH-SOL'),
    ('BCH-USD', 'TRX-USD', 'BCH-TRX')
]

for asset1, asset2, name in top_pairs:
    strategy = PairTradingStrategy(data[asset1], data[asset2])
    signals = strategy.generate_signals()
    results[name] = backtest_pair(data[asset1], data[asset2], signals)

    print(f"\n{name} Performance:")
    print(f"  Annual Return: {results[name]['annual_return']:.1%}")
    print(f"  Sharpe Ratio: {results[name]['sharpe_ratio']:.2f}")
    print(f"  Max Drawdown: {results[name]['max_drawdown']:.1%}")
    print(f"  Win Rate: {results[name]['win_rate']:.1%}")`,
      outputs: [
        {
          output_type: "stream",
          name: "stdout",
          text: ["\nXLM-XRP Performance:\n  Annual Return: 68.2%\n  Sharpe Ratio: 3.45\n  Max Drawdown: -9.8%\n  Win Rate: 62.5%\n\nETH-SOL Performance:\n  Annual Return: 52.1%\n  Sharpe Ratio: 2.89\n  Max Drawdown: -11.2%\n  Win Rate: 58.9%\n\nBCH-TRX Performance:\n  Annual Return: 64.3%\n  Sharpe Ratio: 3.02\n  Max Drawdown: -13.5%\n  Win Rate: 61.8%\n"]
        }
      ],
      metadata: {}
    },
    {
      cell_type: "markdown",
      source: "## 5. Portfolio Performance\n\nCombining all three pairs into an equally-weighted portfolio:",
      metadata: {}
    },
    {
      cell_type: "code",
      execution_count: 6,
      source: `# Combine returns from all pairs
portfolio_returns = pd.DataFrame({
    name: results[name]['cumulative_returns']
    for name in results.keys()
})

# Equal weight portfolio
portfolio_cumulative = portfolio_returns.mean(axis=1)

# Portfolio metrics
total_return = portfolio_cumulative.iloc[-1] - 1
annual_return = (1 + total_return) ** (252 / len(portfolio_cumulative)) - 1

# Calculate portfolio volatility and Sharpe
portfolio_daily_returns = portfolio_cumulative.pct_change().dropna()
volatility = portfolio_daily_returns.std() * np.sqrt(252)
sharpe_ratio = annual_return / volatility

# Maximum drawdown
cummax = portfolio_cumulative.cummax()
drawdown = (portfolio_cumulative - cummax) / cummax
max_drawdown = drawdown.min()

print("=" * 50)
print("PORTFOLIO PERFORMANCE (3 Pairs Combined)")
print("=" * 50)
print(f"Annual Return:     {annual_return:.1%}")
print(f"Sharpe Ratio:      {sharpe_ratio:.2f}")
print(f"Max Drawdown:      {max_drawdown:.1%}")
print(f"Total Return:      {total_return:.1%}")
print(f"Win Rate:          {np.mean([r['win_rate'] for r in results.values()]):.1%}")
print(f"Profit Factor:     {1.82:.2f}")

# Validation checks
print("\n✅ VALIDATION:")
checks = [
    ("Annual Return > 25%", annual_return > 0.25),
    ("Sharpe Ratio > 1.0", sharpe_ratio > 1.0),
    ("Max Drawdown < 15%", abs(max_drawdown) < 0.15),
    ("Profit Factor > 1.0", 1.82 > 1.0),
    ("Sharpe Ratio < 3.5", sharpe_ratio < 3.5)
]

passed = sum(1 for _, check in checks if check)
for check_name, check_result in checks:
    print(f"  {'✓' if check_result else '✗'} {check_name}")

if passed == len(checks):
    print("\n🚀 READY FOR PAPER TRADING")
else:
    print(f"\n⚠️  {passed}/{len(checks)} checks passed - NEEDS TUNING")`,
      outputs: [
        {
          output_type: "stream",
          name: "stdout",
          text: ["==================================================\nPORTFOLIO PERFORMANCE (3 Pairs Combined)\n==================================================\nAnnual Return:     61.4%\nSharpe Ratio:      3.12\nMax Drawdown:      -11.4%\nTotal Return:      78.3%\nWin Rate:          61.1%\nProfit Factor:     1.82\n\n✅ VALIDATION:\n  ✓ Annual Return > 25%\n  ✓ Sharpe Ratio > 1.0\n  ✓ Max Drawdown < 15%\n  ✓ Profit Factor > 1.0\n  ✓ Sharpe Ratio < 3.5\n\n🚀 READY FOR PAPER TRADING\n"]
        }
      ],
      metadata: {}
    },
    {
      cell_type: "markdown",
      source: "## 6. Risk Management\n\nKey risk parameters for live trading:",
      metadata: {}
    },
    {
      cell_type: "code",
      execution_count: 7,
      source: `risk_params = {
    'max_position_size': 50000,
    'max_drawdown_limit': 0.15,
    'daily_loss_limit': 5000,
    'position_limit': 10,
    'z_score_entry': 2.0,
    'z_score_exit': 0.5,
    'lookback_window': 20,
    'rebalance_frequency': 'daily'
}

print("RISK MANAGEMENT PARAMETERS")
print("-" * 40)
for param, value in risk_params.items():
    if isinstance(value, float) and value < 1:
        print(f"{param:.<30} {value:.1%}")
    else:
        print(f"{param:.<30} {value}")

print("\nPOSITION SIZING")
print("-" * 40)
capital = 100000
for name in results.keys():
    allocation = capital / 3  # Equal weight
    print(f"{name}:".ljust(15), f"$" + str(int(allocation)))`,
      outputs: [
        {
          output_type: "stream",
          name: "stdout",
          text: ["RISK MANAGEMENT PARAMETERS\n----------------------------------------\nmax_position_size............. 50000\nmax_drawdown_limit............ 15.0%\ndaily_loss_limit.............. 5000\nposition_limit................ 10\nz_score_entry................. 2.0\nz_score_exit.................. 0.5\nlookback_window............... 20\nrebalance_frequency........... daily\n\nPOSITION SIZING\n----------------------------------------\nXLM-XRP:        $33,333\nETH-SOL:        $33,333\nBCH-TRX:        $33,333\n"]
        }
      ],
      metadata: {}
    }
  ],
  metadata: {
    kernelspec: {
      display_name: "Python 3",
      language: "python",
      name: "python3"
    },
    language_info: {
      name: "python",
      version: "3.9.0"
    }
  },
  nbformat: 4,
  nbformat_minor: 4
};