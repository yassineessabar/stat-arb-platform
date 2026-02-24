#!/bin/bash

# Statistical Arbitrage Platform Deployment Script
# Usage: ./deploy.sh <server_host> <server_user> [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVER_HOST=$1
SERVER_USER=$2
SERVER_PORT=${3:-22}
DEPLOYMENT_PATH="/opt/trading-strategy"
USE_PM2=${USE_PM2:-true}
USE_DOCKER=${USE_DOCKER:-false}

# Check arguments
if [ -z "$SERVER_HOST" ] || [ -z "$SERVER_USER" ]; then
    echo -e "${RED}Usage: ./deploy.sh <server_host> <server_user> [port]${NC}"
    exit 1
fi

echo -e "${GREEN}🚀 Starting deployment to $SERVER_USER@$SERVER_HOST:$SERVER_PORT${NC}"

# Step 1: Prepare deployment package
echo -e "${YELLOW}📦 Preparing deployment package...${NC}"
rm -rf deploy_package
mkdir -p deploy_package
cp -r ../dashboard/* deploy_package/
cp -r ../requirements.txt deploy_package/ 2>/dev/null || true
cp -r ../package.json deploy_package/ 2>/dev/null || true

# Create setup script for server
cat > deploy_package/setup_server.sh << 'EOF'
#!/bin/bash
set -e

echo "🔧 Setting up server environment..."

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Python 3.10+
sudo apt-get install -y python3 python3-pip python3-venv

# Install PM2 globally
sudo npm install -g pm2

# Install system dependencies
sudo apt-get install -y git build-essential curl wget

# Create deployment directory
sudo mkdir -p /opt/trading-strategy
sudo chown $USER:$USER /opt/trading-strategy

echo "✅ Server setup complete!"
EOF

# Step 2: Copy files to server
echo -e "${YELLOW}📤 Copying files to server...${NC}"
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "mkdir -p $DEPLOYMENT_PATH/logs"
scp -P $SERVER_PORT -r deploy_package/* $SERVER_USER@$SERVER_HOST:$DEPLOYMENT_PATH/

# Step 3: Setup server environment
echo -e "${YELLOW}🔧 Setting up server environment...${NC}"
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "cd $DEPLOYMENT_PATH && chmod +x setup_server.sh && ./setup_server.sh"

# Step 4: Install dependencies
echo -e "${YELLOW}📚 Installing dependencies...${NC}"
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "cd $DEPLOYMENT_PATH && npm install --production"
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "cd $DEPLOYMENT_PATH && pip3 install -r requirements.txt"

# Step 5: Build Next.js app
echo -e "${YELLOW}🔨 Building Next.js application...${NC}"
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "cd $DEPLOYMENT_PATH && npm run build"

# Step 6: Setup PM2
if [ "$USE_PM2" = true ]; then
    echo -e "${YELLOW}⚙️ Configuring PM2...${NC}"
    ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "cd $DEPLOYMENT_PATH && pm2 start ecosystem.config.js"
    ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "pm2 save"
    ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "pm2 startup systemd -u $SERVER_USER --hp /home/$SERVER_USER"
fi

# Step 7: Setup monitoring
echo -e "${YELLOW}📊 Setting up monitoring...${NC}"
cat > deploy_package/monitor.sh << 'MONITOR'
#!/bin/bash
# Health check script
while true; do
    # Check if strategy is running
    if pm2 list | grep -q "strategy-executor"; then
        echo "$(date): Strategy is running ✅"
    else
        echo "$(date): Strategy is down! Restarting... ❌"
        pm2 restart strategy-executor
    fi

    # Check memory usage
    MEMORY=$(free -m | awk 'NR==2{printf "%.1f", $3*100/$2}')
    if (( $(echo "$MEMORY > 90" | bc -l) )); then
        echo "$(date): High memory usage: $MEMORY% ⚠️"
        # Send alert (implement your alert method)
    fi

    sleep 60
done
MONITOR

scp -P $SERVER_PORT deploy_package/monitor.sh $SERVER_USER@$SERVER_HOST:$DEPLOYMENT_PATH/
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "chmod +x $DEPLOYMENT_PATH/monitor.sh"
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "nohup $DEPLOYMENT_PATH/monitor.sh > $DEPLOYMENT_PATH/logs/monitor.log 2>&1 &"

# Step 8: Start services
echo -e "${YELLOW}🎯 Starting services...${NC}"
ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "cd $DEPLOYMENT_PATH && pm2 start all"

# Step 9: Verify deployment
echo -e "${YELLOW}✔️ Verifying deployment...${NC}"
sleep 5
if ssh -p $SERVER_PORT $SERVER_USER@$SERVER_HOST "curl -s http://localhost:3000 > /dev/null"; then
    echo -e "${GREEN}✅ Deployment successful!${NC}"
    echo -e "${GREEN}🌐 Dashboard: http://$SERVER_HOST:3000${NC}"
    echo -e "${GREEN}📊 Monitoring: pm2 monit (on server)${NC}"
else
    echo -e "${RED}❌ Deployment verification failed!${NC}"
    exit 1
fi

# Cleanup
rm -rf deploy_package

echo -e "${GREEN}🎉 Deployment complete!${NC}"