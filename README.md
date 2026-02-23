# Statistical Arbitrage Trading Platform

A professional-grade statistical arbitrage trading platform with real-time strategy deployment, paper trading, and live execution capabilities.

## 🚀 Features

### Core Platform
- **Real-time Statistical Arbitrage** - Automated mean reversion trading strategies
- **Paper & Live Trading** - Safe testing environment with live market data
- **Professional UI** - Institutional-grade execution interface
- **24/7 Strategy Deployment** - Server-side Python strategy execution
- **Real-time Monitoring** - Live P&L, positions, and signal tracking

### Trading Features
- **Binance Futures Integration** - Testnet and live trading support
- **Z-Score Signal Detection** - Statistical mean reversion signals
- **Risk Management** - Stop-loss, position sizing, and exposure limits
- **Emergency Stop** - Instant position closure and strategy termination
- **Multi-pair Support** - Trade any futures pairs (ETH/BTC, etc.)

### Technical Features
- **Next.js Frontend** - Modern React-based interface
- **Python Strategy Engine** - Robust execution with pandas/numpy
- **Real-time API Integration** - Live market data and order execution
- **Process Management** - Background strategy deployment and monitoring
- **Comprehensive Logging** - Full audit trail of all trading activity

## 📋 Prerequisites

- **Node.js 18+** and npm
- **Python 3.8+** with pip
- **Binance Futures Account** (Testnet recommended for testing)

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone https://github.com/yassineessabar/stat-arb-platform.git
cd stat-arb-platform/dashboard
```

### 2. Install Frontend Dependencies
```bash
npm install
```

### 3. Install Python Dependencies
```bash
pip3 install requests pandas numpy
```

### 4. Environment Setup
Create `.env.local` in the dashboard directory:
```env
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_API_SECRET=your_secret_here
```

## 🚀 Quick Start

### 1. Start Development Server
```bash
cd dashboard
npm run dev
```
Access the platform at `http://localhost:3000/execution`

### 2. Configure API Credentials
- Click "API Settings" in the top right
- Enter your Binance API key and secret
- Enable "Use Testnet" for safe testing
- Click "Save & Connect"

### 3. Deploy Strategy
- Click "Deploy" button
- Configure strategy parameters:
  - **Symbols**: ETHUSDT / BTCUSDT (or any pair)
  - **Entry Z-Score**: 2.0 (signal threshold)
  - **Exit Z-Score**: 0.5 (mean reversion exit)
  - **Position Size**: $1000 USDT
  - **Max Positions**: 3
- Click "Deploy Paper Strategy"

### 4. Monitor Execution
- View real-time logs in the "Logs & Risk Events" section
- Monitor positions in the "Open Positions" table
- Track P&L in the "Live Metrics" dashboard

## 📊 Strategy Parameters

### Statistical Parameters
- **Lookback Period**: Hours of historical data for z-score calculation (default: 24)
- **Entry Z-Score**: Threshold for opening positions (default: 2.0)
- **Exit Z-Score**: Threshold for closing positions (default: 0.5)
- **Stop Loss Z-Score**: Emergency exit threshold (default: 3.0)

### Risk Parameters
- **Position Size**: USDT amount per trade (minimum: $100)
- **Max Positions**: Maximum concurrent positions (1-10)
- **Rebalance Frequency**: Minutes between strategy cycles (1-60)

## 🔧 Advanced Usage

### Manual Strategy Deployment
```bash
python3 strategy_executor.py --config config.json --mode paper
```

### API Endpoints
- `POST /api/strategy/deploy` - Deploy new strategy
- `POST /api/strategy/stop` - Stop running strategy
- `GET /api/binance/account` - Get account information
- `GET /api/binance/positions` - Get open positions

### Log Monitoring
Strategy logs are stored in `strategy_logs/` directory:
```bash
tail -f strategy_logs/strategy_[ID].log
```

## 🔒 Security Notes

- **API Keys**: Store securely in `.env.local` (never commit to git)
- **Testnet First**: Always test strategies on Binance Testnet
- **Paper Trading**: Use paper mode for strategy development
- **Risk Management**: Set appropriate position sizes and stop-losses

## ⚠️ Disclaimer

This software is provided "as is" without warranty. Trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred through use of this software.

---

🔥 **Built with Claude Code** - AI-powered development platform
