import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';

const execAsync = promisify(exec);

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      provider,
      serverHost,
      serverPort,
      serverUser,
      serverPassword,
      useSSHKey,
      sshKeyPath,
      deploymentPath,
      usePM2,
      useDocker,
      autoRestart,
      monitoringEnabled,
      alertEmail,
      strategy
    } = body;

    // Validate inputs
    if (!serverHost || !serverUser) {
      return NextResponse.json(
        { error: 'Server host and user are required' },
        { status: 400 }
      );
    }

    // Create deployment configuration
    const deployConfig = {
      host: serverHost,
      port: serverPort || 22,
      user: serverUser,
      deploymentPath: deploymentPath || '/opt/trading-strategy',
      timestamp: new Date().toISOString(),
      strategy: strategy
    };

    // Generate deployment ID
    const deploymentId = `deploy_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Create deployment script
    const deployScript = `
#!/bin/bash
set -e

echo "🚀 Initiating remote deployment..."

# SSH connection string
SSH_CMD="ssh -o StrictHostKeyChecking=no -p ${deployConfig.port} ${deployConfig.user}@${deployConfig.host}"
SCP_CMD="scp -o StrictHostKeyChecking=no -P ${deployConfig.port}"

# Create remote directory
$SSH_CMD "sudo mkdir -p ${deployConfig.deploymentPath} && sudo chown $USER:$USER ${deployConfig.deploymentPath}"

# Install dependencies on remote server
$SSH_CMD "which node || (curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt-get install -y nodejs)"
$SSH_CMD "which python3 || sudo apt-get install -y python3 python3-pip"
${usePM2 ? '$SSH_CMD "which pm2 || sudo npm install -g pm2"' : ''}
${useDocker ? '$SSH_CMD "which docker || (curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER)"' : ''}

# Copy files
echo "📦 Copying files to server..."
$SCP_CMD -r ./* ${deployConfig.user}@${deployConfig.host}:${deployConfig.deploymentPath}/

# Install dependencies
echo "📚 Installing dependencies..."
$SSH_CMD "cd ${deployConfig.deploymentPath} && npm install --production"
$SSH_CMD "cd ${deployConfig.deploymentPath} && pip3 install -r requirements.txt"

# Build application
echo "🔨 Building application..."
$SSH_CMD "cd ${deployConfig.deploymentPath} && npm run build"

${usePM2 ? `
# Setup PM2
echo "⚙️ Configuring PM2..."
$SSH_CMD "cd ${deployConfig.deploymentPath} && pm2 delete all || true"
$SSH_CMD "cd ${deployConfig.deploymentPath} && pm2 start ecosystem.config.js"
$SSH_CMD "pm2 save"
$SSH_CMD "pm2 startup systemd -u ${deployConfig.user} --hp /home/${deployConfig.user} | tail -1 | sudo bash"
` : ''}

${useDocker ? `
# Setup Docker
echo "🐳 Building Docker containers..."
$SSH_CMD "cd ${deployConfig.deploymentPath} && docker-compose down || true"
$SSH_CMD "cd ${deployConfig.deploymentPath} && docker-compose build"
$SSH_CMD "cd ${deployConfig.deploymentPath} && docker-compose up -d"
` : ''}

${monitoringEnabled ? `
# Setup monitoring
echo "📊 Setting up monitoring..."
cat > monitor.sh << 'MONITOR'
#!/bin/bash
while true; do
  # Check service health
  if curl -f http://localhost:3000/health > /dev/null 2>&1; then
    echo "$(date): Service healthy ✅"
  else
    echo "$(date): Service unhealthy! ❌"
    ${alertEmail ? `echo "Service down at $(date)" | mail -s "Trading Platform Alert" ${alertEmail}` : ''}
    ${autoRestart ? 'pm2 restart all' : ''}
  fi
  sleep 60
done
MONITOR

$SCP_CMD monitor.sh ${deployConfig.user}@${deployConfig.host}:${deployConfig.deploymentPath}/
$SSH_CMD "chmod +x ${deployConfig.deploymentPath}/monitor.sh"
$SSH_CMD "nohup ${deployConfig.deploymentPath}/monitor.sh > ${deployConfig.deploymentPath}/logs/monitor.log 2>&1 &"
` : ''}

echo "✅ Deployment complete!"
    `;

    // Write deployment script to temp file
    const tempScriptPath = path.join(process.cwd(), `temp_deploy_${deploymentId}.sh`);
    await fs.writeFile(tempScriptPath, deployScript, 'utf-8');
    await fs.chmod(tempScriptPath, '755');

    // Execute deployment based on provider
    let deploymentResult;

    if (provider === 'docker') {
      // Docker deployment
      const dockerCommands = `
        docker build -t stat-arb-platform .
        docker run -d --name stat-arb-platform -p 3000:3000 --restart unless-stopped stat-arb-platform
      `;
      deploymentResult = await execAsync(dockerCommands);
    } else if (provider === 'local') {
      // Local deployment
      const localCommands = `
        npm install --production
        npm run build
        ${usePM2 ? 'pm2 start ecosystem.config.js' : 'npm start &'}
      `;
      deploymentResult = await execAsync(localCommands);
    } else {
      // Remote server deployment (VPS, AWS)
      if (useSSHKey) {
        // Add SSH key to agent
        await execAsync(`ssh-add ${sshKeyPath}`);
      } else {
        // Note: In production, use proper SSH key authentication
        console.warn('Password authentication not recommended for production');
      }

      // Execute deployment script
      deploymentResult = await execAsync(`bash ${tempScriptPath}`);
    }

    // Clean up temp files
    await fs.unlink(tempScriptPath).catch(() => {});

    // Save deployment record to database
    // TODO: Add database integration

    return NextResponse.json({
      success: true,
      deploymentId,
      message: 'Deployment initiated successfully',
      details: {
        provider,
        host: serverHost,
        deploymentPath: deployConfig.deploymentPath,
        features: {
          pm2: usePM2,
          docker: useDocker,
          monitoring: monitoringEnabled,
          autoRestart
        }
      }
    });
  } catch (error: any) {
    console.error('Deployment error:', error);
    return NextResponse.json(
      {
        error: 'Deployment failed',
        details: error.message,
        stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
      },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  // Get deployment status
  const deploymentId = request.nextUrl.searchParams.get('id');

  if (!deploymentId) {
    return NextResponse.json({ error: 'Deployment ID required' }, { status: 400 });
  }

  // TODO: Implement deployment status tracking
  return NextResponse.json({
    deploymentId,
    status: 'in_progress',
    message: 'Deployment is running...'
  });
}