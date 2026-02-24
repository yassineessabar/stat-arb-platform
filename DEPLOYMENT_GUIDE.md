# 🚀 Deployment Guide - Statistical Arbitrage Platform

Deploy your trading strategy to run 24/7 on a server with this comprehensive guide.

## 📋 Table of Contents
- [Quick Start](#quick-start)
- [Server Recommendations](#server-recommendations)
- [Deployment Methods](#deployment-methods)
- [Post-Deployment](#post-deployment)
- [Monitoring & Maintenance](#monitoring--maintenance)

## 🎯 Quick Start

### Option 1: One-Click Deploy (Recommended)
```bash
cd dashboard/deploy
chmod +x quick-deploy.sh
./quick-deploy.sh
```

### Option 2: Using the Web Interface
1. Open your dashboard at `http://localhost:3000/execution`
2. Click "Deploy to Server (24/7)"
3. Select your VPS provider
4. Enter server credentials
5. Click "Deploy Strategy"

## 💻 Server Recommendations

### Best VPS Providers for Trading Bots

| Provider | Price/mo | Specs | Free Credit | Best For |
|----------|----------|-------|-------------|----------|
| **DigitalOcean** | $12 | 2GB RAM, 2 vCPU | $200 | Beginners, great docs |
| **Linode** | $10 | 2GB RAM, 1 vCPU | $100 | Budget-friendly |
| **Vultr** | $12 | 2GB RAM, 2 vCPU | $100 | Global locations |
| **AWS EC2** | $15 | t3.small | 750hr free | Enterprise scale |
| **Google Cloud** | $13 | e2-micro | $300 | Advanced features |

### Minimum Requirements
- **OS**: Ubuntu 22.04 LTS (recommended)
- **RAM**: 2GB minimum, 4GB recommended
- **CPU**: 2 vCPU cores
- **Storage**: 20GB SSD
- **Network**: Stable internet connection
- **Location**: Choose closest to exchange servers (Tokyo for Binance)

## 🛠️ Deployment Methods

### Method 1: VPS Deployment (Recommended)

#### Step 1: Create VPS Instance
```bash
# Example for DigitalOcean
doctl compute droplet create trading-bot \
  --region sgp1 \
  --size s-2vcpu-2gb \
  --image ubuntu-22-04-x64
```

#### Step 2: Initial Server Setup
```bash
# SSH into your server
ssh root@your_server_ip

# Update system
apt update && apt upgrade -y

# Create non-root user (optional but recommended)
adduser trading
usermod -aG sudo trading
```

#### Step 3: Deploy Application
```bash
# From your local machine
cd dashboard/deploy
./deploy.sh your_server_ip root
```

### Method 2: Docker Deployment

#### Step 1: Build Docker Image
```bash
cd dashboard
docker build -t stat-arb-platform .
```

#### Step 2: Run with Docker Compose
```bash
docker-compose up -d
```

#### Step 3: Deploy to Docker Host
```bash
# Push to registry
docker tag stat-arb-platform your-registry/stat-arb-platform
docker push your-registry/stat-arb-platform

# On server
docker pull your-registry/stat-arb-platform
docker run -d -p 3000:3000 --restart unless-stopped \
  --name trading-bot your-registry/stat-arb-platform
```

### Method 3: AWS EC2 Deployment

#### Step 1: Launch EC2 Instance
```bash
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.small \
  --key-name your-key \
  --security-groups trading-bot-sg
```

#### Step 2: Configure Security Group
```bash
# Allow HTTP/HTTPS and SSH
aws ec2 authorize-security-group-ingress \
  --group-name trading-bot-sg \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
  --group-name trading-bot-sg \
  --protocol tcp \
  --port 3000 \
  --cidr 0.0.0.0/0
```

## ⚙️ Configuration

### Environment Variables
Create `.env.production` file:
```env
NODE_ENV=production
DATABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key
```

### PM2 Configuration
The platform uses PM2 for process management. Configuration is in `ecosystem.config.js`.

### Nginx Reverse Proxy (Optional)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### SSL Certificate (Recommended)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## 📊 Post-Deployment

### Verify Deployment
```bash
# Check if services are running
pm2 status

# Check application logs
pm2 logs

# Test API endpoint
curl http://your-server-ip:3000/api/health
```

### Security Hardening
```bash
# Configure firewall
ufw allow 22/tcp
ufw allow 3000/tcp
ufw enable

# Disable root SSH (after creating user)
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd

# Set up fail2ban
apt install fail2ban
systemctl enable fail2ban
```

## 🔍 Monitoring & Maintenance

### Health Monitoring
```bash
# View real-time logs
pm2 logs --lines 100

# Monitor system resources
pm2 monit

# Check strategy status
curl http://your-server:3000/api/strategy/status
```

### Automated Backups
```bash
# Create backup script
cat > /opt/backup.sh << 'EOF'
#!/bin/bash
tar -czf /backups/trading-$(date +%Y%m%d).tar.gz /opt/trading-strategy
find /backups -name "*.tar.gz" -mtime +7 -delete
EOF

# Add to crontab
crontab -e
# Add: 0 3 * * * /opt/backup.sh
```

### Updates and Maintenance
```bash
# Update application
cd /opt/trading-strategy
git pull
npm install
npm run build
pm2 restart all

# System updates
apt update && apt upgrade -y
```

## 🚨 Troubleshooting

### Common Issues

#### Port 3000 Already in Use
```bash
# Find process using port
lsof -i :3000
# Kill process
kill -9 <PID>
```

#### PM2 Not Starting
```bash
# Reset PM2
pm2 kill
pm2 start ecosystem.config.js
```

#### Database Connection Issues
- Check Supabase credentials in `.env`
- Verify network connectivity
- Check Supabase service status

## 📞 Support

- **Documentation**: Check `/docs` folder
- **Issues**: GitHub Issues
- **Logs**: `pm2 logs` for debugging
- **Health Check**: `http://your-server:3000/api/health`

## 🎯 Best Practices

1. **Always use testnet first** before deploying with real funds
2. **Set up monitoring alerts** for critical errors
3. **Regular backups** of your configuration and database
4. **Keep dependencies updated** for security
5. **Use environment variables** for sensitive data
6. **Monitor resource usage** to prevent overload
7. **Implement rate limiting** for API calls
8. **Set up DDoS protection** (Cloudflare recommended)

## 🚀 Next Steps

After successful deployment:

1. ✅ Test strategy with paper trading
2. ✅ Set up monitoring dashboards
3. ✅ Configure alerts for critical events
4. ✅ Implement backup strategy
5. ✅ Document your configuration
6. ✅ Test emergency stop procedures

---

**Remember**: Always start with paper trading and thoroughly test your strategy before using real funds!