#!/usr/bin/env python3
"""
Test script for v6 strategy executor
Run this to verify the v6 engine works correctly
"""

import json
import sys
import os
from pathlib import Path

# Test configuration
test_config = {
    "strategy_name": "StatArb_v6_Test",
    "trading_mode": "paper",
    "use_v6_engine": True,
    "universe": [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
        "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT"
    ],
    "portfolio_value": 10000,
    "deployment_id": "test_v6_strategy",
    "lookback_period": 5,
    "entry_z_score": 1.0,
    "exit_z_score": 0.2,
    "stop_loss_z_score": 3.5,
    "position_size": 1000,
    "max_positions": 30,
    "rebalance_frequency": 1,  # 1 minute for testing
    "api_key": "YOUR_API_KEY",  # Replace with actual key
    "api_secret": "YOUR_API_SECRET",  # Replace with actual secret
    "testnet": True
}

def main():
    print("=" * 70)
    print("  V6 STRATEGY ENGINE TEST")
    print("=" * 70)
    print()
    print("This will test the v6 strategy executor with backtest engine.")
    print()
    print("Configuration:")
    print(f"  - Universe: {len(test_config['universe'])} assets")
    print(f"  - Entry Z-score: {test_config['entry_z_score']}")
    print(f"  - Exit Z-score: {test_config['exit_z_score']}")
    print(f"  - Max Pairs: {test_config['max_positions']}")
    print(f"  - Rebalance: Every {test_config['rebalance_frequency']} minutes")
    print()

    # Check if API credentials are set
    if test_config['api_key'] == 'YOUR_API_KEY':
        print("⚠️  Please set your Binance API credentials in this script first!")
        print("   Edit test_v6_strategy.py and add your testnet API key and secret.")
        return

    # Save test config
    config_path = Path("test_v6_config.json")
    with open(config_path, 'w') as f:
        json.dump(test_config, f, indent=2)

    print(f"✅ Config saved to: {config_path}")
    print()

    # Import and run the executor
    try:
        # Add parent directory to path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        # Import the v6 executor
        from dashboard.strategy_executor_v6 import V6StrategyExecutor

        print("Starting v6 strategy executor...")
        print("-" * 70)

        # Create and run executor
        executor = V6StrategyExecutor(str(config_path))

        # Run a few cycles for testing
        import asyncio

        async def test_run():
            executor.running = True

            # Build initial price history
            print("📊 Building initial price history...")
            for i in range(10):  # Just 10 data points for quick test
                executor.fetch_price_data()
                if i % 5 == 0:
                    print(f"  Collected {i+1} price points...")
                await asyncio.sleep(1)

            print(f"✅ Initial data collected: {len(executor.price_history)} periods")
            print()

            # Run 3 strategy cycles
            for cycle in range(1, 4):
                print(f"📍 TEST CYCLE {cycle}")
                print("-" * 40)
                executor.run_strategy_cycle()
                print()
                await asyncio.sleep(5)  # Wait 5 seconds between cycles

            print("✅ Test completed successfully!")
            print()
            print("Summary:")
            print(f"  - Data points collected: {len(executor.price_history)}")
            print(f"  - Pairs analyzed: {len(executor.active_pairs)}")
            print(f"  - Positions: {sum(1 for p in executor.positions.values() if abs(p) > 0)}")

        # Run the test
        asyncio.run(test_run())

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you're running this from the dashboard directory")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()