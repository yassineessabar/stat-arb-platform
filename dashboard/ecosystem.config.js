module.exports = {
  apps: [
    {
      name: 'trading-dashboard',
      script: 'npm',
      args: 'start',
      cwd: '/opt/trading-strategy',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '2G',
      env: {
        NODE_ENV: 'production',
        PORT: 3000
      },
      error_file: './logs/dashboard-error.log',
      out_file: './logs/dashboard-out.log',
      log_file: './logs/dashboard-combined.log',
      time: true
    },
    {
      name: 'strategy-executor',
      script: 'python3',
      args: 'strategy_executor.py',
      cwd: '/opt/trading-strategy',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        PYTHONUNBUFFERED: 1
      },
      error_file: './logs/strategy-error.log',
      out_file: './logs/strategy-out.log',
      log_file: './logs/strategy-combined.log',
      time: true,
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
      kill_timeout: 5000
    }
  ],

  deploy: {
    production: {
      user: 'root',
      host: process.env.DEPLOY_HOST || 'your-server-ip',
      ref: 'origin/main',
      repo: 'git@github.com:yourusername/stat-arb-platform.git',
      path: '/opt/trading-strategy',
      'pre-deploy-local': '',
      'post-deploy': 'npm install && npm run build && pm2 reload ecosystem.config.js --env production',
      'pre-setup': ''
    }
  }
};