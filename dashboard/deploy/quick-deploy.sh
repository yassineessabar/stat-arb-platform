#!/bin/bash

# Quick Deploy Script for Statistical Arbitrage Platform
# One-click deployment to your VPS server

set -e

echo "🚀 Statistical Arbitrage Platform - Quick Deploy"
echo "================================================"
echo ""

# Prompt for server details
read -p "Enter your server IP address: " SERVER_IP
read -p "Enter SSH username (default: root): " SSH_USER
SSH_USER=${SSH_USER:-root}
read -p "Enter SSH port (default: 22): " SSH_PORT
SSH_PORT=${SSH_PORT:-22}

echo ""
echo "📋 Deployment Configuration:"
echo "  Server: $SSH_USER@$SERVER_IP:$SSH_PORT"
echo "  Location: /opt/trading-strategy"
echo ""
read -p "Continue with deployment? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ]; then
    echo "Deployment cancelled."
    exit 0
fi

# Create one-line installer script
cat > remote_install.sh << 'INSTALLER'
#!/bin/bash
set -e

echo "🔧 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y curl git build-essential

echo "📦 Installing Node.js 18..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "🐍 Installing Python 3..."
sudo apt-get install -y python3 python3-pip python3-venv

echo "⚙️ Installing PM2..."
sudo npm install -g pm2

echo "📁 Setting up deployment directory..."
sudo mkdir -p /opt/trading-strategy
sudo chown $USER:$USER /opt/trading-strategy
cd /opt/trading-strategy

echo "✅ Server preparation complete!"
INSTALLER

echo ""
echo "🔄 Connecting to server and installing dependencies..."
ssh -p $SSH_PORT $SSH_USER@$SERVER_IP 'bash -s' < remote_install.sh

echo "📤 Copying application files..."
rsync -avz -e "ssh -p $SSH_PORT" \
    --exclude node_modules \
    --exclude .next \
    --exclude .git \
    --exclude logs \
    ../ $SSH_USER@$SERVER_IP:/opt/trading-strategy/

echo "🔨 Building and starting application..."
ssh -p $SSH_PORT $SSH_USER@$SERVER_IP << 'REMOTE_COMMANDS'
cd /opt/trading-strategy
echo "📚 Installing Node.js dependencies..."
npm install --production

echo "📚 Installing Python dependencies..."
pip3 install -r requirements.txt

echo "🔨 Building Next.js application..."
npm run build

echo "⚙️ Starting services with PM2..."
pm2 delete all 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save
pm2 startup systemd -u $USER --hp /home/$USER | tail -1 | sudo bash

echo "✅ Application started successfully!"
pm2 status
REMOTE_COMMANDS

# Clean up
rm -f remote_install.sh

echo ""
echo "🎉 Deployment Complete!"
echo "=================================="
echo "✅ Your trading platform is now running 24/7!"
echo ""
echo "📊 Access your dashboard at: http://$SERVER_IP:3000"
echo "📝 View logs: ssh $SSH_USER@$SERVER_IP 'pm2 logs'"
echo "🔄 Restart: ssh $SSH_USER@$SERVER_IP 'pm2 restart all'"
echo "🛑 Stop: ssh $SSH_USER@$SERVER_IP 'pm2 stop all'"
echo ""
echo "💡 Tip: Set up a domain name and SSL certificate for secure access"