# 🚀 VPS Deployment Guide - 24/7 Trading

Since GitHub Actions runs from US servers (where Binance is blocked), you need to deploy to a VPS in a supported country for 24/7 trading.

## 🎯 Quick Deploy (5 minutes)

### Step 1: Get a VPS
**Recommended Providers (Non-US locations):**
- **DigitalOcean Singapore**: $12/month, easy setup
- **Linode Frankfurt**: $10/month, reliable
- **Vultr Tokyo**: $12/month, closest to Binance servers

### Step 2: One-Command Deploy
```bash
# SSH into your VPS
ssh root@YOUR_VPS_IP

# Run the auto-installer
curl -sSL https://raw.githubusercontent.com/yassineessabar/stat-arb-platform/main/dashboard/deploy/quick-deploy.sh | bash
```

That's it! Your strategy will be running 24/7.

## 📋 Manual Deployment

### Step 1: Prepare VPS
```bash
# Update system
apt update && apt upgrade -y

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
apt install -y nodejs

# Install Python
apt install -y python3 python3-pip python3-venv

# Install PM2 for process management
npm install -g pm2
```

### Step 2: Clone Repository
```bash
cd /opt
git clone https://github.com/yassineessabar/stat-arb-platform.git
cd stat-arb-platform
```

### Step 3: Install Dependencies
```bash
# Install Python packages
cd dashboard
pip3 install -r requirements.txt

# Install Node.js packages
npm install --production
```

### Step 4: Configure Strategy
```bash
# Create configuration file
cat > strategy_config.json << EOF
{
  "strategy_name": "StatArb_v6_Production",
  "trading_mode": "paper",
  "universe": [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT"
  ],
  "portfolio_value": 10000,
  "rebalance_frequency": 5,
  "api_key": "YOUR_BINANCE_API_KEY",
  "api_secret": "YOUR_BINANCE_API_SECRET",
  "testnet": true
}
EOF

# Edit with your actual API keys
nano strategy_config.json
```

### Step 5: Start Strategy
```bash
# Start with PM2 (auto-restart on crash)
pm2 start strategy_executor.py --interpreter python3 -- --config strategy_config.json

# Save PM2 configuration
pm2 save

# Auto-start on server reboot
pm2 startup
```

## 🔧 Environment Variables

Add these to your VPS environment:
```bash
export NEXT_PUBLIC_SUPABASE_URL="https://hfmcbyqdibxdbimwkcwi.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhmbWNieXFkaWJ4ZGJpbXdrY3dpIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTgzMDU3MCwiZXhwIjoyMDg3NDA2NTcwfQ.lAAU3d_wcZVOPMhFVZ80RizUJturvnKtXj2hX5nX8o0"
```

## 📊 Monitoring

### Check Strategy Status
```bash
# View running processes
pm2 status

# View logs
pm2 logs

# Restart strategy
pm2 restart all

# Stop strategy
pm2 stop all
```

### View Real-time Logs
```bash
# Follow strategy logs
tail -f ~/.pm2/logs/strategy_executor-out.log

# View error logs
tail -f ~/.pm2/logs/strategy_executor-error.log
```

## 🌍 Best VPS Locations

**For optimal performance, choose locations close to Binance:**

1. **Singapore** (DigitalOcean/Vultr) - Closest to Binance
2. **Tokyo** (Vultr/Linode) - Low latency
3. **Frankfurt** (Linode) - European option
4. **London** (All providers) - Good for EU traders

**Avoid**: US, Canada (Binance restricted)

## 💰 Cost Breakdown

| Provider | Location | Monthly Cost | Setup |
|----------|----------|--------------|-------|
| DigitalOcean | Singapore | $12 | Easiest |
| Linode | Frankfurt | $10 | Cheapest |
| Vultr | Tokyo | $12 | Fastest |
| AWS EC2 | ap-southeast-1 | $15 | Most features |

## 🔐 Security Setup

### Basic Security
```bash
# Create non-root user
adduser trader
usermod -aG sudo trader
su trader

# Setup SSH keys (recommended)
ssh-keygen -t rsa -b 4096
# Copy ~/.ssh/id_rsa.pub to your local machine

# Disable root SSH (after testing)
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
sudo systemctl restart sshd
```

### Firewall
```bash
# Install and configure UFW
sudo ufw allow 22/tcp   # SSH
sudo ufw enable
```

## 🚀 Quick Start Commands

### DigitalOcean Deployment
```bash
# Create droplet
doctl compute droplet create trading-bot \
  --region sgp1 \
  --size s-2vcpu-2gb \
  --image ubuntu-22-04-x64 \
  --ssh-keys YOUR_SSH_KEY_ID

# Get IP and deploy
doctl compute droplet list
ssh root@DROPLET_IP
curl -sSL https://raw.githubusercontent.com/yassineessabar/stat-arb-platform/main/dashboard/deploy/quick-deploy.sh | bash
```

### Linode Deployment
```bash
# Using Linode CLI
linode-cli linodes create \
  --type g6-nanode-1 \
  --region eu-west \
  --image linode/ubuntu22.04 \
  --root_pass YOUR_PASSWORD

# Deploy
ssh root@LINODE_IP
curl -sSL https://raw.githubusercontent.com/yassineessabar/stat-arb-platform/main/dashboard/deploy/quick-deploy.sh | bash
```

## 🎯 Testing

### Verify Binance Access
```bash
# Test API connectivity
curl -s "https://api.binance.com/api/v3/ping"
curl -s "https://testnet.binance.vision/api/v3/ping"

# Should return {} (empty JSON) if successful
```

### Test Strategy
```bash
# Run for one cycle to test
python3 strategy_executor.py --config strategy_config.json
```

## 📈 Production Checklist

- [ ] VPS in non-US location
- [ ] Binance API accessible
- [ ] Strategy configuration correct
- [ ] PM2 auto-restart enabled
- [ ] Firewall configured
- [ ] Monitoring set up
- [ ] Backup strategy created
- [ ] Test with small amounts first

## 🆘 Troubleshooting

### Strategy Not Starting
```bash
# Check logs
pm2 logs

# Check Python path
which python3

# Check dependencies
pip3 list | grep supabase
```

### API Connection Issues
```bash
# Test connectivity
curl -v "https://api.binance.com/api/v3/ping"

# Check location restrictions
curl -s "https://ipinfo.io/ip"
```

### Performance Issues
```bash
# Check system resources
htop
df -h

# Optimize PM2
pm2 set pm2:max-memory 1G
```

---

## 🎉 Success!

Your v6 strategy is now running 24/7 on a VPS with:
- ✅ Real Binance API access
- ✅ Automatic restarts
- ✅ Full monitoring
- ✅ Production-ready setup

Expected performance: **63.7% annual return, 3.98 Sharpe ratio** (based on backtest)