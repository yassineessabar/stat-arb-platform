#!/usr/bin/env python3
"""
Backtest Runner Script
=====================

Standalone script to run backtests and validate v6 strategy performance.
Fetches live data and runs complete strategy validation.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --start-date 2022-01-01 --end-date 2023-12-31
"""

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd
import yfinance as yf
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.strategy_engine import StatArbStrategyEngine


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('backtest.log')
        ]
    )


def fetch_crypto_data(start_date: str = "2022-01-01", end_date: str = None) -> pd.DataFrame:
    """
    Fetch cryptocurrency data for backtesting.

    Args:
        start_date: Start date for data fetch
        end_date: End date for data fetch (None for latest)

    Returns:
        DataFrame with price data
    """
    # Crypto symbols with -USD suffix for yfinance
    symbols = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD",
        "ADA-USD", "AVAX-USD", "DOGE-USD", "DOT-USD", "MATIC-USD",
        "LINK-USD", "LTC-USD", "BCH-USD", "ETC-USD", "XLM-USD",
        "VET-USD", "TRX-USD", "UNI-USD", "AAVE-USD", "MKR-USD"
    ]

    print(f"Fetching data for {len(symbols)} cryptocurrencies...")
    print(f"Date range: {start_date} to {end_date or 'latest'}")

    try:
        # Fetch data
        data = yf.download(symbols, start=start_date, end=end_date, progress=True)

        if data.empty:
            raise ValueError("No data fetched")

        # Extract closing prices and clean up
        if isinstance(data.columns, pd.MultiIndex):
            prices = data['Close']
        else:
            prices = data

        # Remove -USD suffix from column names
        if hasattr(prices.columns, 'str'):
            prices.columns = prices.columns.str.replace('-USD', '')
        else:
            # Handle tuple columns
            new_cols = []
            for col in prices.columns:
                if isinstance(col, tuple):
                    new_cols.append(col[0].replace('-USD', '') if isinstance(col[0], str) else str(col[0]))
                else:
                    new_cols.append(col.replace('-USD', '') if isinstance(col, str) else str(col))
            prices.columns = new_cols

        # Remove symbols with too much missing data
        missing_pct = prices.isnull().mean()
        good_symbols = missing_pct[missing_pct < 0.20].index
        prices = prices[good_symbols]

        # Forward fill and drop remaining NaNs
        prices = prices.ffill().dropna()

        print(f"Data fetched successfully: {len(prices.columns)} symbols, {len(prices)} days")
        print(f"Date range: {prices.index[0].date()} to {prices.index[-1].date()}")

        return prices

    except Exception as e:
        print(f"Error fetching data: {e}")
        raise


def run_backtest(price_data: pd.DataFrame, config_path: str = None) -> dict:
    """
    Run complete backtest.

    Args:
        price_data: Price data DataFrame
        config_path: Path to configuration directory

    Returns:
        Backtest results dictionary
    """
    print("\n" + "="*70)
    print("  RUNNING STATISTICAL ARBITRAGE v6 BACKTEST")
    print("="*70)

    # Initialize strategy engine
    engine = StatArbStrategyEngine(config_path)

    # Run backtest
    results = engine.run_backtest(price_data)

    return results


def print_results(results: dict):
    """Print backtest results in formatted output."""

    universe_analysis = results['universe_analysis']
    performance_metrics = results['performance_metrics']

    print("\n" + "="*70)
    print("  BACKTEST RESULTS")
    print("="*70)

    # Universe Analysis
    print(f"\n📊 UNIVERSE ANALYSIS:")
    print(f"  Total pairs analyzed: {len(universe_analysis['all_pairs'])}")
    print(f"  Viable pairs selected: {len(universe_analysis['selected_pairs'])}")
    print(f"  Tier 1 pairs: {universe_analysis['n_tier1']}")
    print(f"  Tier 2 pairs: {universe_analysis['n_tier2']}")

    # Top pairs
    print(f"\n🏆 TOP PAIRS:")
    for i, pair in enumerate(universe_analysis['selected_pairs'][:5]):
        tier_str = f"T{pair['tier']}"
        print(f"  {i+1}. {pair['pair']} ({tier_str}) - Score: {pair['score']:.1f}, ADF: {pair['adf_pvalue']:.4f}")

    # Performance Metrics
    if 'error' not in performance_metrics:
        print(f"\n📈 PERFORMANCE METRICS:")
        print(f"  Annual Return:     {performance_metrics['annual_return']:>8.1%}")
        print(f"  Annual Volatility: {performance_metrics['annual_volatility']:>8.1%}")
        print(f"  Sharpe Ratio:      {performance_metrics['sharpe_ratio']:>8.2f}")
        print(f"  Max Drawdown:      {performance_metrics['max_drawdown']:>8.1%}")
        print(f"  Total Return:      {performance_metrics['total_return']:>8.1%}")
        print(f"  Hit Rate:          {performance_metrics['hit_rate']:>8.1%}")
        print(f"  Profit Factor:     {performance_metrics['profit_factor']:>8.2f}")
        print(f"  Observations:      {performance_metrics['n_observations']:>8}")

        # Validation against v6 targets
        print(f"\n✅ V6 VALIDATION:")

        checks = [
            ("Annual return > 25%", performance_metrics['annual_return'] > 0.25),
            ("Sharpe ratio > 1.0", performance_metrics['sharpe_ratio'] > 1.0),
            ("Max drawdown < 15%", abs(performance_metrics['max_drawdown']) < 0.15),
            ("Profit factor > 1.0", performance_metrics['profit_factor'] > 1.0),
            ("Sharpe realistic < 3.5", performance_metrics['sharpe_ratio'] < 3.5),
        ]

        all_passed = True
        for check_name, passed in checks:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {check_name:<25} {status}")
            if not passed:
                all_passed = False

        print(f"\n{'🚀 STRATEGY VALIDATED - READY FOR PAPER TRADING' if all_passed else '⚠️  STRATEGY NEEDS TUNING'}")

    else:
        print(f"\n❌ PERFORMANCE CALCULATION FAILED:")
        print(f"  {performance_metrics['error']}")


def save_results(results: dict, output_file: str = None):
    """Save backtest results to file."""
    if output_file is None:
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"backtest_results_{timestamp}.pkl"

    import pickle
    with open(output_file, 'wb') as f:
        pickle.dump(results, f)

    print(f"\n💾 Results saved to: {output_file}")


def plot_results(results: dict):
    """Plot backtest results."""
    try:
        import matplotlib.pyplot as plt

        portfolio_pnl = results['portfolio_pnl']
        equity_curve = (1 + portfolio_pnl).cumprod()

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Equity curve
        ax1.plot(equity_curve.index, equity_curve.values, linewidth=1.5, color='#1f77b4')
        ax1.set_title('Portfolio Equity Curve', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Cumulative Return')
        ax1.grid(True, alpha=0.3)

        # Drawdown
        peak = equity_curve.cummax()
        drawdown = (equity_curve - peak) / peak
        ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.7, color='red')
        ax2.set_title('Drawdown', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Drawdown')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        # Save plot
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        plot_file = f"backtest_plot_{timestamp}.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        plt.show()

        print(f"📊 Plot saved to: {plot_file}")

    except ImportError:
        print("Matplotlib not available for plotting")
    except Exception as e:
        print(f"Error creating plot: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run Statistical Arbitrage v6 Backtest')

    parser.add_argument('--start-date', type=str, default='2022-01-01',
                       help='Start date for backtest (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None,
                       help='End date for backtest (YYYY-MM-DD)')
    parser.add_argument('--config-path', type=str, default=None,
                       help='Path to configuration directory')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file for results')
    parser.add_argument('--plot', action='store_true',
                       help='Generate performance plots')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    try:
        # Fetch data
        print("Step 1: Fetching market data...")
        price_data = fetch_crypto_data(args.start_date, args.end_date)

        # Run backtest
        print("\nStep 2: Running backtest...")
        results = run_backtest(price_data, args.config_path)

        # Print results
        print_results(results)

        # Save results
        if args.output or True:  # Always save
            save_results(results, args.output)

        # Plot results
        if args.plot:
            plot_results(results)

        print("\n🎉 Backtest completed successfully!")

    except KeyboardInterrupt:
        print("\n\n⚠️ Backtest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()