#!/bin/bash

# Stat-Arb Platform Deployment Script for sshx environment
# Run this in your sshx terminal session

set -e

echo "🚀 Starting Stat-Arb Platform deployment..."

# Update system packages
echo "📦 Updating system packages..."
apt-get update -qq
apt-get install -y git curl nodejs npm python3 python3-pip -qq

# Clone the repository
echo "📥 Cloning repository..."
cd /root
rm -rf stat-arb-platform
git clone https://github.com/yassineessabar/sigmaticv2.git
cd sigmaticv2/stat-arb-platform

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install -r requirements.txt

# Install PM2 globally
echo "📦 Installing PM2..."
npm install -g pm2

# Create strategy config if it doesn't exist
if [ ! -f strategy_config.json ]; then
    echo "⚙️ Creating strategy_config.json..."
    cat > strategy_config.json << 'EOF'
{
  "exchange": "binance",
  "trading_pairs": [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT"
  ],
  "lookback_period": 20,
  "entry_threshold": 2.0,
  "exit_threshold": 0.5,
  "position_size": 100,
  "max_positions": 3,
  "update_interval": 60,
  "stop_loss": 0.02,
  "take_profit": 0.03,
  "api_key": "YOUR_BINANCE_API_KEY",
  "api_secret": "YOUR_BINANCE_API_SECRET"
}
EOF
    echo "⚠️  Please update API keys in strategy_config.json"
fi

# Create PM2 ecosystem file
echo "⚙️ Creating PM2 ecosystem file..."
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'stat-arb-bot',
    script: 'python3',
    args: 'src/enhanced_strategy_executor.py',
    cwd: '/root/sigmaticv2/stat-arb-platform',
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    env: {
      NODE_ENV: 'production'
    },
    error_file: '/root/stat-arb-logs/error.log',
    out_file: '/root/stat-arb-logs/out.log',
    log_file: '/root/stat-arb-logs/combined.log',
    time: true
  }]
};
EOF

# Create log directory
mkdir -p /root/stat-arb-logs

# Build the dashboard
echo "🔨 Building dashboard..."
npm run build || echo "Dashboard build skipped (optional)"

echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit strategy_config.json and add your Binance API keys:"
echo "   nano strategy_config.json"
echo ""
echo "2. Start the trading bot:"
echo "   pm2 start ecosystem.config.js"
echo ""
echo "3. View logs:"
echo "   pm2 logs stat-arb-bot"
echo ""
echo "4. Monitor status:"
echo "   pm2 status"
echo ""
echo "5. Save PM2 config for auto-restart:"
echo "   pm2 save"
echo "   pm2 startup"