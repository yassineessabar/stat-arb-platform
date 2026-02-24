# 🚀 GitHub Actions Setup for 24/7 Automated Trading

This guide will help you set up GitHub Actions to run your statistical arbitrage strategy automatically, 24/7, without any server costs!

## 📋 Quick Setup (5 minutes)

### Step 1: Fork or Push to GitHub
```bash
# If not already on GitHub
git remote add origin https://github.com/YOUR_USERNAME/stat-arb-platform.git
git branch -M main
git push -u origin main
```

### Step 2: Add GitHub Secrets
Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `BINANCE_API_KEY` | Live trading API key | `your_live_api_key` |
| `BINANCE_API_SECRET` | Live trading API secret | `your_live_api_secret` |
| `BINANCE_TESTNET_KEY` | Paper trading API key | `your_testnet_api_key` |
| `BINANCE_TESTNET_SECRET` | Paper trading API secret | `your_testnet_api_secret` |
| `SUPABASE_URL` | Database URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Database service key | `eyJhbGc...` |
| `DISCORD_WEBHOOK` | (Optional) Discord alerts | `https://discord.com/api/webhooks/...` |

### Step 3: Enable GitHub Actions
1. Go to Actions tab in your repository
2. Click "I understand my workflows, go ahead and enable them"
3. The strategy will now run automatically every 5 minutes!

## 🎯 How It Works

### Automated Execution (Free!)
- **Runs every 5 minutes** via cron job
- **No server needed** - GitHub provides free compute
- **2000 minutes/month free** (enough for ~400 executions)
- **Auto-restarts** if strategy stops

### Workflow Files
```
.github/workflows/
├── strategy-executor.yml   # Main strategy execution (every 5 min)
└── monitoring.yml          # Performance monitoring (every hour)
```

## 🔧 Configuration Options

### Manual Trigger with Custom Settings
1. Go to Actions → Strategy Executor → Run workflow
2. Choose options:
   - Trading Mode: `paper` or `live`
   - Rebalance Frequency: Minutes between trades
   - Portfolio Value: Total USDT to trade

### Modify Schedule
Edit `.github/workflows/strategy-executor.yml`:
```yaml
schedule:
  - cron: '*/5 * * * *'  # Change this line
```

Examples:
- `'*/10 * * * *'` - Every 10 minutes
- `'0 * * * *'` - Every hour
- `'0 */4 * * *'` - Every 4 hours
- `'0 9,21 * * *'` - At 9 AM and 9 PM daily

## 📊 Monitoring

### View Execution Logs
1. Go to Actions tab
2. Click on any workflow run
3. Click on "Execute V6 Strategy"
4. View real-time logs

### Download Trading Logs
1. Click on completed workflow
2. Scroll to "Artifacts"
3. Download `strategy-logs-XXX.zip`

### Performance Reports
- Daily reports generated at midnight UTC
- Check Actions → Monitoring → performance-report
- Downloads available for 30 days

## 🔐 Security Best Practices

1. **Use Testnet First**
   - Always test with paper trading before live
   - Monitor for at least 24 hours

2. **API Key Restrictions**
   - Enable IP whitelist (GitHub IPs)
   - Limit to trading permissions only
   - No withdrawal permissions

3. **Position Limits**
   - Set max position size in strategy
   - Use stop-loss parameters
   - Monitor via Discord/Telegram alerts

## 🎬 Getting Your API Keys

### Binance Testnet (Paper Trading)
1. Go to https://testnet.binance.vision/
2. Register with any email (no verification needed)
3. Generate API keys
4. Fund with test coins (free)

### Binance Live (Real Trading)
1. Go to https://www.binance.com/en/my/settings/api-management
2. Create API key
3. Enable "Enable Futures" permission
4. Save API key and secret securely

### Supabase (Database)
1. Go to https://supabase.com/
2. Create free project
3. Settings → API → Copy URL and service_role key

## 📈 Verify It's Working

### Check Strategy is Running
```bash
# View latest workflow runs
gh run list --workflow=strategy-executor.yml

# View specific run logs
gh run view <run-id>

# Download artifacts
gh run download <run-id>
```

### Monitor in Real-Time
1. Go to Actions tab
2. Click on running workflow
3. Watch live execution logs

### Database Monitoring
```sql
-- Check recent positions
SELECT * FROM positions
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;

-- Check performance
SELECT
  DATE(exit_time) as date,
  COUNT(*) as trades,
  SUM(realized_pnl) as total_pnl
FROM trades
GROUP BY DATE(exit_time)
ORDER BY date DESC;
```

## 🚨 Alerts & Notifications

### Discord Webhook Setup
1. Discord Server Settings → Integrations → Webhooks
2. Create webhook
3. Copy webhook URL
4. Add as `DISCORD_WEBHOOK` secret

### What Gets Alerted
- ❌ Strategy failures
- 📉 Daily losses > $500
- ⚠️ Positions open > 24 hours
- 📊 Daily performance reports

## 🛠️ Troubleshooting

### Strategy Not Running
- Check Actions tab for errors
- Verify all secrets are set correctly
- Check workflow is enabled

### No Trades Happening
- Need 180+ periods of price data first
- Market conditions may not be favorable
- Check logs for "No viable pairs" message

### API Errors
- Verify API keys are correct
- Check testnet vs live settings
- Ensure API has trading permissions

## 💰 Cost Optimization

### GitHub Actions Limits (Free Tier)
- **2,000 minutes/month** for private repos
- **Unlimited** for public repos
- Each run uses ~2-3 minutes

### Optimize Usage
- Run less frequently (every 15-30 min)
- Use scheduled maintenance windows
- Combine monitoring into main workflow

### Calculate Your Usage
```
Runs per day = (24 * 60) / rebalance_frequency
Minutes per month = Runs per day * 30 * 3 minutes
```

Example: 5-min rebalance = 288 runs/day = 864 min/month (within free tier)

## 🎯 Next Steps

1. ✅ Start with paper trading
2. ✅ Monitor for 24-48 hours
3. ✅ Review performance reports
4. ✅ Adjust parameters if needed
5. ✅ Switch to live with small amount
6. ✅ Scale up gradually

## 📞 Support

### View Logs
```bash
# Recent executions
cat .github/workflows/logs/strategy-*.log

# Specific date
cat .github/workflows/logs/strategy-2024-01-15.log
```

### Common Issues
- **"No module named 'core'"** - Check Python path in workflow
- **"API key invalid"** - Verify secrets are set correctly
- **"Insufficient balance"** - Check testnet funding or reduce position size

---

## 🎉 Congratulations!

Your strategy is now running 24/7 on GitHub's infrastructure - completely free!

The v6 backtest engine with Kalman filters and multi-pair trading is actively:
- ✅ Analyzing market conditions every 5 minutes
- ✅ Trading up to 30 pairs simultaneously
- ✅ Using exact parameters from successful backtest
- ✅ Logging all trades to database
- ✅ Generating performance reports

No server required, no monthly costs, just pure algorithmic trading! 🚀