#!/bin/bash
set -e

echo "🚀 Setting up GitHub Actions Self-Hosted Runner"
echo "=============================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "❌ Don't run as root. Run as regular user with sudo access."
    exit 1
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt install -y curl jq git python3 python3-pip python3-venv

# Install Python packages for the strategy
echo "🐍 Installing Python packages..."
pip3 install --user pandas numpy requests supabase yfinance statsmodels scikit-learn

# Create runner directory
echo "📁 Setting up runner directory..."
mkdir -p ~/actions-runner
cd ~/actions-runner

# Download latest runner
echo "⬇️ Downloading GitHub Actions runner..."
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | cut -c 2-)
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
    https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Verify checksum
echo "✅ Verifying checksum..."
echo "$(curl -s https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz.sha256) actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" | shasum -a 256 -c

# Extract runner
echo "📂 Extracting runner..."
tar xzf ./actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Install additional dependencies
echo "⚙️ Installing runner dependencies..."
sudo ./bin/installdependencies.sh

# Test Binance API access
echo ""
echo "🌍 Testing Binance API access from this location..."
IP_INFO=$(curl -s https://ipinfo.io/json)
echo "Location: $(echo $IP_INFO | jq -r '.country + " - " + .city + " (" + .ip + ")"')"

BINANCE_MAIN=$(curl -s "https://api.binance.com/api/v3/ping" 2>/dev/null || echo "failed")
BINANCE_TEST=$(curl -s "https://testnet.binance.vision/api/v3/ping" 2>/dev/null || echo "failed")

if echo "$BINANCE_MAIN" | grep -q '{}'; then
    echo "✅ Binance main API accessible"
    API_ACCESS=true
elif echo "$BINANCE_MAIN" | grep -q '"code":0'; then
    echo "❌ Binance main API blocked (geo-restriction)"
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

echo ""
if [ "$API_ACCESS" = true ]; then
    echo "🚀 Great! This VPS location can access Binance APIs."
    echo "You can proceed with live trading setup."
else
    echo "⚠️ Warning: Binance APIs are blocked from this location."
    echo "Consider using a VPS in Singapore, EU, or other supported regions."
fi

echo ""
echo "📋 NEXT STEPS:"
echo "=============="
echo ""
echo "1. Get a registration token from GitHub:"
echo "   https://github.com/yassineessabar/stat-arb-platform/settings/actions/runners"
echo ""
echo "2. Click 'New self-hosted runner'"
echo ""
echo "3. Copy the token and run:"
echo "   ./config.sh --url https://github.com/yassineessabar/stat-arb-platform --token YOUR_TOKEN"
echo ""
echo "4. Start the runner:"
echo "   ./run.sh"
echo ""
echo "5. Or install as service:"
echo "   sudo ./svc.sh install"
echo "   sudo ./svc.sh start"
echo ""
echo "6. Update workflow to use 'self-hosted' runner"
echo ""
echo "✅ Setup complete! Configure your runner token to continue."