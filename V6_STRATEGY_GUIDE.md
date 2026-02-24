# 📊 V6 Strategy Implementation Guide

## ✅ Strategy Alignment Complete!

Your deployed strategy now uses the **EXACT SAME** engine as your backtest, ensuring consistent performance.

## 🎯 Key Changes Made

### 1. New V6 Executor (`strategy_executor_v6.py`)
- Uses the exact `StatArbStrategyEngine` from backtesting
- Includes all v6 features:
  - ✅ Kalman filter for dynamic hedge ratios
  - ✅ Regime detection and filtering
  - ✅ Multi-pair trading (up to 30 pairs)
  - ✅ Dynamic position sizing based on z-score
  - ✅ Conviction weighting
  - ✅ Tiered pair quality system

### 2. Correct Parameters (from `params_v6.yaml`)
```python
# V6 BACKTEST PARAMETERS (Now in Production!)
entry_z_score = 1.0      # Was 2.0 in simple strategy
exit_z_score = 0.2       # Was 0.5 in simple strategy
stop_loss = 3.5          # Was 3.0 in simple strategy
max_pairs = 30           # Was 1 pair only
target_volatility = 20%  # Risk-adjusted sizing
```

### 3. Multi-Pair Universe Trading
Instead of single pair (ETH/BTC), now trades:
- Analyzes all combinations from universe
- Selects best 30 pairs based on cointegration
- Tier 1 pairs: Full weight (ADF p-value < 0.05)
- Tier 2 pairs: Half weight (ADF p-value < 0.10)

## 📈 Performance Expectations

### Backtest Results (v6):
- **Annual Return**: 63.7%
- **Sharpe Ratio**: 3.98
- **Max Drawdown**: -4.6%
- **Hit Rate**: >60%

### Live Trading Expectations:
- Similar returns with some slippage
- More trades due to lower entry threshold (1.0 vs 2.0)
- Better risk distribution across multiple pairs
- Smoother equity curve

## 🚀 How to Deploy

### Option 1: Use UI with V6 Engine
1. Go to Execution page
2. Check "**Use v6 Backtest Engine**" ✅
3. Parameters auto-update to v6 values
4. Click "Deploy Locally" or "Deploy to Server"

### Option 2: Command Line Test
```bash
cd dashboard

# Edit test script with your API keys
nano test_v6_strategy.py

# Run test
python3 test_v6_strategy.py
```

### Option 3: Direct Deployment
```bash
# Create config file
cat > v6_config.json << EOF
{
  "strategy_name": "StatArb_v6_Production",
  "trading_mode": "paper",
  "use_v6_engine": true,
  "universe": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"],
  "portfolio_value": 10000,
  "api_key": "YOUR_KEY",
  "api_secret": "YOUR_SECRET",
  "testnet": true,
  "rebalance_frequency": 5
}
EOF

# Run v6 executor
python3 strategy_executor_v6.py --config v6_config.json
```

## 📊 Comparison: Simple vs V6

| Feature | Simple Strategy | V6 Backtest Engine |
|---------|----------------|-------------------|
| **Entry Z-score** | 2.0 | 1.0 ✅ |
| **Exit Z-score** | 0.5 | 0.2 ✅ |
| **Pairs Traded** | 1 fixed | Up to 30 dynamic ✅ |
| **Hedge Ratio** | Rolling mean | Kalman filter ✅ |
| **Position Sizing** | Fixed | Dynamic by z-score ✅ |
| **Regime Filter** | None | Correlation & volatility ✅ |
| **Conviction Weight** | None | Historical performance ✅ |
| **Expected Sharpe** | ~1.5 | ~3.98 ✅ |

## 🔍 Monitoring

### Check Logs
```bash
# View strategy logs
tail -f strategy_logs/strategy_*.log

# Check for signals
grep "SIGNAL" strategy_logs/*.log

# Monitor positions
grep "POSITION" strategy_logs/*.log
```

### Database Queries
The v6 executor logs to database:
- Signal analysis
- Position entries/exits
- Performance metrics

## ⚠️ Important Notes

1. **Data Requirements**: V6 needs 180 periods of historical data (vs 24 for simple)
2. **Computation**: More CPU intensive due to Kalman filters and multi-pair analysis
3. **Capital**: Spreads capital across multiple pairs - ensure adequate funding
4. **Latency**: Rebalances every 5 minutes by default (configurable)

## 🎯 Next Steps

1. **Test with Paper Trading** first
   - Run for at least 24 hours
   - Verify signals match expectations
   - Check position sizing is correct

2. **Monitor Key Metrics**
   - Number of active pairs
   - Signal frequency
   - Position turnover
   - Realized P&L

3. **Gradual Scaling**
   - Start with small position sizes
   - Increase as confidence builds
   - Monitor slippage and costs

## 📞 Troubleshooting

### No Pairs Found
- Need more historical data (180+ periods)
- Universe assets not cointegrated
- Try expanding universe

### No Signals Generated
- Market conditions not favorable
- Regime filter blocking trades
- Check correlation thresholds

### Performance Differs from Backtest
- Transaction costs and slippage
- Market regime change
- Data quality differences

---

**Remember**: Always start with paper trading to verify the strategy behaves as expected before using real funds!