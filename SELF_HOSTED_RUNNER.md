# 🌍 Self-Hosted GitHub Runner Setup

## Quick Setup (5 minutes)

### Step 1: Create VPS in Supported Region
```bash
# DigitalOcean Singapore
doctl compute droplet create github-runner \
  --region sgp1 \
  --size s-2vcpu-4gb \
  --image ubuntu-22-04-x64 \
  --ssh-keys YOUR_SSH_KEY_ID

# Linode Frankfurt
linode-cli linodes create \
  --type g6-standard-2 \
  --region eu-west \
  --image linode/ubuntu22.04 \
  --root_pass YOUR_PASSWORD
```

### Step 2: Setup Runner on VPS
```bash
# SSH into your VPS
ssh root@YOUR_VPS_IP

# Install dependencies
apt update && apt upgrade -y
apt install -y curl git

# Create runner user
adduser github-runner
usermod -aG sudo github-runner
su github-runner
cd /home/github-runner

# Download GitHub Actions runner
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# Configure runner (get token from GitHub)
./config.sh --url https://github.com/yassineessabar/stat-arb-platform --token YOUR_TOKEN
```

### Step 3: Get Registration Token
1. Go to: https://github.com/yassineessabar/stat-arb-platform/settings/actions/runners
2. Click "New self-hosted runner"
3. Select "Linux x64"
4. Copy the token from the configure command

### Step 4: Start Runner as Service
```bash
# Install as service
sudo ./svc.sh install
sudo ./svc.sh start

# Check status
sudo ./svc.sh status
```

### Step 5: Update Workflow to Use Self-Hosted Runner
```yaml
# In .github/workflows/strategy-executor.yml
jobs:
  execute-strategy:
    runs-on: self-hosted  # Change from ubuntu-latest
    steps:
      # ... rest of workflow
```

## Cost: ~$24/month for 2vCPU, 4GB RAM VPS
## Benefit: Full Binance API access from Singapore/EU