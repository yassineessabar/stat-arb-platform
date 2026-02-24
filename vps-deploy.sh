#!/bin/bash
set -e

echo "🚀 VPS Deployment Script for Statistical Arbitrage Platform"
echo "=========================================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Don't run as root. Create and use a regular user account."
    echo "Run: adduser trader && usermod -aG sudo trader && su trader"
    exit 1
fi

# Check location for Binance API access
echo "🌍 Checking VPS location and API access..."
IP_INFO=$(curl -s https://ipinfo.io/json 2>/dev/null || echo '{"country":"Unknown","city":"Unknown","ip":"Unknown"}')
COUNTRY=$(echo $IP_INFO | jq -r '.country // "Unknown"')
CITY=$(echo $IP_INFO | jq -r '.city // "Unknown"')
IP=$(echo $IP_INFO | jq -r '.ip // "Unknown"')

echo "📍 VPS Location: $COUNTRY - $CITY ($IP)"

# Test Binance API access
echo "🔌 Testing Binance API access..."
BINANCE_MAIN=$(curl -s "https://api.binance.com/api/v3/ping" 2>/dev/null || echo "failed")
BINANCE_TEST=$(curl -s "https://testnet.binance.vision/api/v3/ping" 2>/dev/null || echo "failed")

if echo "$BINANCE_MAIN" | grep -q '{}'; then
    echo "✅ Binance main API accessible"
    API_ACCESS=true
elif echo "$BINANCE_MAIN" | grep -q '"code":0'; then
    echo "❌ Binance main API blocked (geo-restriction)"
    echo "⚠️  This VPS location ($COUNTRY) is not supported by Binance"
    API_ACCESS=false
else
    echo "⚠️ Binance main API: Unknown response"
    API_ACCESS=false
fi

if echo "$BINANCE_TEST" | grep -q '{}'; then
    echo "✅ Binance testnet accessible"
else
    echo "⚠️ Binance testnet may be blocked"
fi

if [ "$API_ACCESS" = false ]; then
    echo ""
    echo "❌ ERROR: Binance APIs are blocked from this location!"
    echo "Recommended VPS locations:"
    echo "  - Singapore (DigitalOcean/Vultr)"
    echo "  - Frankfurt, Germany (Linode)"
    echo "  - Tokyo, Japan (Vultr)"
    echo "  - London, UK (All providers)"
    echo ""
    echo "Avoid: US, Canada, China"
    exit 1
fi

echo "🚀 Great! This VPS can access Binance APIs."
echo ""

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt install -y curl jq git python3 python3-pip python3-venv nodejs npm pm2 nginx

# Install Python packages
echo "🐍 Installing Python packages..."
pip3 install --user pandas numpy requests supabase yfinance statsmodels scikit-learn python-dotenv

# Clone repository if not already present
if [ ! -d "stat-arb-platform" ]; then
    echo "📂 Cloning repository..."
    git clone https://github.com/yassineessabar/stat-arb-platform.git
fi

cd stat-arb-platform

# Install dashboard dependencies
echo "🌐 Installing dashboard dependencies..."
cd dashboard
npm install --production

# Create environment configuration
echo "⚙️ Creating environment configuration..."
cat > .env.local << 'EOF'
# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=https://hfmcbyqdibxdbimwkcwi.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhmbWNieXFkaWJ4ZGJpbXdrY3dpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTgzMDU3MCwiZXhwIjoyMDg3NDA2NTcwfQ.lAAU3d_wcZVOPMhFVZ80RizUJturvnKtXj2hX5nX8o0

# VPS Configuration
VPS_LOCATION=$COUNTRY
VPS_IP=$IP
EOF

# Create strategy configuration template
echo "📋 Creating strategy configuration..."
cat > strategy_config.json << 'EOF'
{
  "strategy_name": "StatArb_v6_VPS",
  "trading_mode": "paper",
  "universe": [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "LTCUSDT", "BCHUSDT", "ETCUSDT", "XLMUSDT"
  ],
  "portfolio_value": 10000,
  "rebalance_frequency": 5,
  "deployment_id": "VPS_DEPLOYMENT",
  "api_key": "YOUR_BINANCE_API_KEY",
  "api_secret": "YOUR_BINANCE_API_SECRET",
  "testnet": true
}
EOF

# Create PM2 ecosystem file
echo "🔧 Creating PM2 configuration..."
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'stat-arb-strategy',
      script: 'python3',
      args: 'strategy_executor.py --config strategy_config.json',
      cwd: '/home/$USER/stat-arb-platform/dashboard',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '/home/$USER/stat-arb-platform'
      },
      error_file: '/home/$USER/.pm2/logs/strategy-error.log',
      out_file: '/home/$USER/.pm2/logs/strategy-out.log',
      log_file: '/home/$USER/.pm2/logs/strategy-combined.log',
      time: true
    },
    {
      name: 'stat-arb-dashboard',
      script: 'npm',
      args: 'run start',
      cwd: '/home/$USER/stat-arb-platform/dashboard',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      env: {
        NODE_ENV: 'production',
        PORT: 3000
      },
      error_file: '/home/$USER/.pm2/logs/dashboard-error.log',
      out_file: '/home/$USER/.pm2/logs/dashboard-out.log',
      log_file: '/home/$USER/.pm2/logs/dashboard-combined.log'
    }
  ]
};
EOF

# Build dashboard
echo "🏗️ Building dashboard..."
npm run build

echo ""
echo "✅ VPS Deployment Complete!"
echo "========================="
echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1. Edit strategy configuration:"
echo "   nano strategy_config.json"
echo "   - Add your Binance API keys"
echo "   - Set trading_mode to 'live' when ready"
echo ""
echo "2. Start the applications:"
echo "   pm2 start ecosystem.config.js"
echo "   pm2 save"
echo "   pm2 startup"
echo ""
echo "3. Check status:"
echo "   pm2 status"
echo "   pm2 logs stat-arb-strategy"
echo ""
echo "4. Access dashboard:"
echo "   http://$IP:3000"
echo "   (Configure nginx for domain/SSL if needed)"
echo ""
echo "5. Monitor execution logs in dashboard Execution tab"
echo ""
echo "🚀 Your VPS is ready for 24/7 statistical arbitrage trading!"