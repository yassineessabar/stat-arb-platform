#!/usr/bin/env python3
"""
Setup Validation Script
=======================

Validates that the statistical arbitrage platform is correctly installed
and configured. Runs comprehensive checks on all components.

Usage:
    python scripts/validate_setup.py
    python scripts/validate_setup.py --full
"""

import argparse
import sys
import logging
from pathlib import Path
import importlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_python_version():
    """Check Python version compatibility."""
    print("🐍 Checking Python version...")

    version = sys.version_info
    if version.major != 3 or version.minor < 8:
        print(f"   ❌ Python {version.major}.{version.minor} detected")
        print("   ⚠️  Requires Python 3.8+")
        return False

    print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Check required dependencies."""
    print("\n📦 Checking dependencies...")

    required_packages = [
        ('numpy', 'NumPy'),
        ('pandas', 'Pandas'),
        ('scipy', 'SciPy'),
        ('statsmodels', 'Statsmodels'),
        ('matplotlib', 'Matplotlib'),
        ('aiohttp', 'aiohttp'),
        ('yaml', 'PyYAML'),
        ('yfinance', 'yfinance'),
    ]

    missing_packages = []

    for package_name, display_name in required_packages:
        try:
            importlib.import_module(package_name)
            print(f"   ✅ {display_name}")
        except ImportError:
            print(f"   ❌ {display_name} - Not installed")
            missing_packages.append(package_name)

    if missing_packages:
        print(f"\n   ⚠️  Missing packages: {', '.join(missing_packages)}")
        print("   💡 Run: pip install -r requirements.txt")
        return False

    return True


def check_config_files():
    """Check configuration files."""
    print("\n⚙️  Checking configuration files...")

    config_path = Path(__file__).parent.parent / "config"
    required_configs = [
        'params_v6.yaml',
        'universe.yaml',
        'exchange.yaml',
        'risk_limits.yaml'
    ]

    missing_configs = []

    for config_file in required_configs:
        config_path_full = config_path / config_file

        if config_path_full.exists():
            print(f"   ✅ {config_file}")
        else:
            print(f"   ❌ {config_file} - Missing")
            missing_configs.append(config_file)

    if missing_configs:
        print(f"\n   ⚠️  Missing configs: {', '.join(missing_configs)}")
        return False

    return True


def check_core_modules():
    """Check core strategy modules."""
    print("\n🧠 Checking core modules...")

    core_modules = [
        ('core.strategy_engine', 'Strategy Engine'),
        ('core.pairs.kalman', 'Kalman Filter'),
        ('core.signals.zscore', 'Z-Score Signals'),
        ('core.signals.regime', 'Regime Detection'),
        ('core.portfolio.position_sizer', 'Position Sizer'),
    ]

    failed_imports = []

    for module_name, display_name in core_modules:
        try:
            importlib.import_module(module_name)
            print(f"   ✅ {display_name}")
        except ImportError as e:
            print(f"   ❌ {display_name} - Import error: {e}")
            failed_imports.append(module_name)

    if failed_imports:
        print(f"\n   ⚠️  Failed imports: {', '.join(failed_imports)}")
        return False

    return True


def check_live_modules():
    """Check live trading modules."""
    print("\n🚀 Checking live trading modules...")

    live_modules = [
        ('live.binance_client', 'Binance Client'),
        ('live.execution_engine', 'Execution Engine'),
        ('live.trading_bot', 'Trading Bot'),
        ('risk.position_risk', 'Risk Manager'),
        ('monitoring.metrics', 'Metrics'),
    ]

    failed_imports = []

    for module_name, display_name in live_modules:
        try:
            importlib.import_module(module_name)
            print(f"   ✅ {display_name}")
        except ImportError as e:
            print(f"   ❌ {display_name} - Import error: {e}")
            failed_imports.append(module_name)

    if failed_imports:
        print(f"\n   ⚠️  Failed imports: {', '.join(failed_imports)}")
        return False

    return True


def test_strategy_initialization():
    """Test strategy engine initialization."""
    print("\n🧪 Testing strategy initialization...")

    try:
        from core.strategy_engine import StatArbStrategyEngine

        # Try to initialize
        engine = StatArbStrategyEngine()

        if hasattr(engine, 'params') and engine.params:
            print("   ✅ Strategy engine initialization")
        else:
            print("   ❌ Strategy engine - Configuration not loaded")
            return False

        # Check key parameters
        target_vol = engine.params.get('portfolio', {}).get('target_vol')
        if target_vol == 0.20:
            print("   ✅ v6 parameters loaded correctly")
        else:
            print(f"   ❌ v6 parameters - Expected 0.20 vol target, got {target_vol}")
            return False

        return True

    except Exception as e:
        print(f"   ❌ Strategy engine test failed: {e}")
        return False


def test_data_fetching():
    """Test data fetching capability."""
    print("\n📊 Testing data fetching...")

    try:
        import yfinance as yf
        import pandas as pd

        # Try to fetch small amount of data
        ticker = yf.Ticker("BTC-USD")
        data = ticker.history(period="5d")

        if not data.empty and len(data) >= 3:
            print("   ✅ Data fetching works")
            return True
        else:
            print("   ❌ Data fetching - Insufficient data received")
            return False

    except Exception as e:
        print(f"   ❌ Data fetching failed: {e}")
        return False


def test_paper_trading():
    """Test paper trading simulation."""
    print("\n💰 Testing paper trading...")

    try:
        from live.binance_client import BinanceClient, PaperTradingSimulator

        # Test paper trading simulator
        simulator = PaperTradingSimulator(10000)
        account_info = simulator.get_account_info()

        if account_info and account_info['totalWalletBalance'] == '10000':
            print("   ✅ Paper trading simulation")
        else:
            print("   ❌ Paper trading simulation - Incorrect balance")
            return False

        # Test Binance client in paper mode
        client = BinanceClient(paper_trading=True)
        if hasattr(client, 'paper_state'):
            print("   ✅ Binance paper client")
        else:
            print("   ❌ Binance paper client - Paper state not initialized")
            return False

        return True

    except Exception as e:
        print(f"   ❌ Paper trading test failed: {e}")
        return False


def run_full_validation():
    """Run comprehensive validation including mini backtest."""
    print("\n🔬 Running full validation with mini backtest...")

    try:
        import pandas as pd
        import numpy as np
        from core.strategy_engine import StatArbStrategyEngine

        # Generate synthetic data
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')

        # Create synthetic price data
        returns_btc = np.random.normal(0, 0.02, len(dates))
        returns_eth = 0.8 * returns_btc + 0.6 * np.random.normal(0, 0.02, len(dates))

        prices = pd.DataFrame({
            'BTC': 100 * np.exp(np.cumsum(returns_btc)),
            'ETH': 200 * np.exp(np.cumsum(returns_eth))
        }, index=dates)

        # Initialize engine
        engine = StatArbStrategyEngine()

        # Run mini backtest
        print("   📈 Running mini backtest...")
        results = engine.run_backtest(prices)

        # Check results
        if 'performance_metrics' in results:
            perf = results['performance_metrics']

            if 'error' not in perf:
                print(f"   ✅ Mini backtest completed")
                print(f"      Sharpe: {perf['sharpe_ratio']:.2f}")
                print(f"      Return: {perf['annual_return']:.1%}")
                print(f"      Max DD: {perf['max_drawdown']:.1%}")
                return True
            else:
                print(f"   ❌ Mini backtest - Performance error: {perf['error']}")
                return False
        else:
            print("   ❌ Mini backtest - No performance metrics")
            return False

    except Exception as e:
        print(f"   ❌ Full validation failed: {e}")
        return False


def check_directory_structure():
    """Check project directory structure."""
    print("\n📁 Checking directory structure...")

    project_root = Path(__file__).parent.parent
    required_dirs = [
        'config',
        'core',
        'core/pairs',
        'core/signals',
        'core/portfolio',
        'live',
        'risk',
        'monitoring',
        'tests',
        'scripts'
    ]

    missing_dirs = []

    for dir_name in required_dirs:
        dir_path = project_root / dir_name

        if dir_path.exists() and dir_path.is_dir():
            print(f"   ✅ {dir_name}/")
        else:
            print(f"   ❌ {dir_name}/ - Missing")
            missing_dirs.append(dir_name)

    if missing_dirs:
        print(f"\n   ⚠️  Missing directories: {', '.join(missing_dirs)}")
        return False

    return True


def print_summary(results: dict):
    """Print validation summary."""
    print("\n" + "="*70)
    print("  VALIDATION SUMMARY")
    print("="*70)

    total_checks = len(results)
    passed_checks = sum(1 for result in results.values() if result)

    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {check_name:<30} {status}")

    print(f"\n  Overall: {passed_checks}/{total_checks} checks passed")

    if passed_checks == total_checks:
        print("\n🎉 ALL CHECKS PASSED - PLATFORM READY!")
        print("\n💡 Next steps:")
        print("   1. Run a backtest: python scripts/run_backtest.py")
        print("   2. Start paper trading: python scripts/paper_trade.py")
        print("   3. Monitor performance and validate strategy")
    else:
        print(f"\n⚠️  {total_checks - passed_checks} CHECKS FAILED")
        print("\n💡 Fix the issues above before proceeding")


def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate Statistical Arbitrage Platform Setup')

    parser.add_argument('--full', action='store_true',
                       help='Run full validation including mini backtest')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress detailed output')

    args = parser.parse_args()

    if not args.quiet:
        print("="*70)
        print("  STATISTICAL ARBITRAGE v6 — SETUP VALIDATION")
        print("="*70)

    # Suppress logging unless needed
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)

    # Run validation checks
    results = {}

    results['Python Version'] = check_python_version()
    results['Dependencies'] = check_dependencies()
    results['Directory Structure'] = check_directory_structure()
    results['Config Files'] = check_config_files()
    results['Core Modules'] = check_core_modules()
    results['Live Modules'] = check_live_modules()
    results['Strategy Init'] = test_strategy_initialization()
    results['Data Fetching'] = test_data_fetching()
    results['Paper Trading'] = test_paper_trading()

    if args.full:
        results['Full Validation'] = run_full_validation()

    # Print summary
    if not args.quiet:
        print_summary(results)

    # Exit with appropriate code
    if all(results.values()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()