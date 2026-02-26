import { NextRequest, NextResponse } from 'next/server';
import { NodeSSH } from 'node-ssh';

// This endpoint fetches real-time logs from the EC2 instance running enhanced_strategy_executor_fixed.py
export async function GET(request: NextRequest) {
  try {
    // EC2 connection details - these should be in environment variables in production
    const EC2_HOST = process.env.EC2_HOST || 'your-ec2-instance.amazonaws.com';
    const EC2_USER = process.env.EC2_USER || 'ubuntu';
    const EC2_KEY_PATH = process.env.EC2_KEY_PATH || '/path/to/your-key.pem';
    const EC2_PROJECT_PATH = process.env.EC2_PROJECT_PATH || '/home/ubuntu/stat-arb-platform';

    // For development/demo, we'll fall back to simulated logs if EC2 connection fails
    let logs: any[] = [];

    try {
      // Attempt to connect to EC2 and fetch real logs
      const ssh = new NodeSSH();

      await ssh.connect({
        host: EC2_HOST,
        username: EC2_USER,
        privateKeyPath: EC2_KEY_PATH,
        readyTimeout: 10000
      });

      // Get the process ID of the running strategy
      const psResult = await ssh.execCommand(
        `ps aux | grep "python3 src/enhanced_strategy_executor_fixed.py" | grep -v grep | awk '{print $2}'`
      );

      let strategyLogs = '';
      if (psResult.stdout.trim()) {
        // Strategy is running, try multiple log file locations
        const logResult = await ssh.execCommand(
          `cd ${EC2_PROJECT_PATH} && (tail -n 50 strategy_logs.txt 2>/dev/null || tail -n 50 *.log 2>/dev/null | head -50 || echo "No readable log files found")`
        );
        strategyLogs = logResult.stdout;

        // If no log files or empty log files, create informative message about setting up logging
        if (strategyLogs === "No readable log files found" || strategyLogs.trim() === "") {
          const processInfo = await ssh.execCommand(
            `cd ${EC2_PROJECT_PATH} && ps aux | grep enhanced_strategy_executor_fixed.py | grep -v grep`
          );

          strategyLogs = `Strategy is running (PID: ${psResult.stdout.trim()}) but no log files found.

To enable live log streaming to this dashboard:

1. Add logging to your enhanced_strategy_executor_fixed.py:

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('strategy_logs.txt'),
        logging.StreamHandler()
    ]
)

2. In your strategy loop, replace print() with logging.info():
logging.info("🔄 ITERATION #%d - %s", iteration, time.strftime("%H:%M:%S"))
logging.info("📊 MARKET ANALYSIS (V6 PARAMETERS)")
logging.info("🟢 BTC/USDT: $%.2f | Z-Score: %.2f | Signal: %s", price, zscore, signal)

3. Restart your strategy script to create log files.

Process info: ${processInfo.stdout}`;
        }
      } else {
        // Try to get logs from the most recent run
        const logResult = await ssh.execCommand(
          `cd ${EC2_PROJECT_PATH} && (tail -n 20 strategy_logs.txt 2>/dev/null || tail -n 20 *.log 2>/dev/null | head -20 || echo "No strategy currently running and no log files found")`
        );
        strategyLogs = logResult.stdout;
      }

      // Parse logs into structured format
      if (strategyLogs &&
          strategyLogs.trim() !== "" &&
          strategyLogs !== "No log file found" &&
          strategyLogs !== "Strategy not currently running" &&
          strategyLogs !== "No readable log files found" &&
          strategyLogs !== "No strategy currently running and no log files found") {

        const logLines = strategyLogs.split('\n').filter(line => line.trim());
        logs = logLines.map((line, index) => {
          // Extract timestamp from log line if present, or use estimated time
          let timestamp;
          let cleanMessage = line.trim();

          // Check if line has timestamp format: "2026-02-26 01:14:47,615 - message"
          const timestampMatch = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (.*)$/);
          if (timestampMatch) {
            // Parse the actual timestamp from the log
            const logTime = timestampMatch[1].replace(',', '.');
            timestamp = new Date(logTime).toISOString();
            cleanMessage = timestampMatch[2];
          } else {
            // Use estimated timestamp for lines without timestamps
            timestamp = new Date(Date.now() - (logLines.length - index) * 1000).toISOString();
          }

          // Clean up ANSI color codes and other terminal formatting
          cleanMessage = cleanMessage
            .replace(/\x1b\[[0-9;]*m/g, '') // Remove ANSI color codes
            .replace(/\[[0-9;]*m/g, '') // Remove remaining color codes
            .trim();

          // Determine log level based on content
          let level = 'INFO';
          if (cleanMessage.includes('ERROR') || cleanMessage.includes('❌') || cleanMessage.includes('Order failed')) level = 'ERROR';
          else if (cleanMessage.includes('SUCCESS') || cleanMessage.includes('✅') || cleanMessage.includes('ORDER EXECUTED')) level = 'SUCCESS';
          else if (cleanMessage.includes('WARNING') || cleanMessage.includes('⚠️')) level = 'WARNING';
          else if (cleanMessage.includes('Strategy is running') || cleanMessage.includes('To enable live log streaming')) level = 'WARNING';

          return {
            timestamp,
            level,
            message: cleanMessage
          };
        }).filter(log => log.message.length > 0); // Filter out empty messages
      }

      ssh.dispose();

      if (logs.length > 0) {
        return NextResponse.json({
          success: true,
          logs,
          source: 'ec2_live',
          debug: {
            psOutput: psResult.stdout,
            logContent: strategyLogs.substring(0, 200) + '...'
          }
        });
      }
    } catch (sshError) {
      console.warn('EC2 SSH connection failed, falling back to simulated logs:', sshError);
      console.warn('SSH Error details:', {
        host: EC2_HOST,
        user: EC2_USER,
        keyPath: EC2_KEY_PATH,
        error: sshError.message
      });
    }

    // Fallback: Generate simulated logs if EC2 connection fails
    const now = new Date();
    const iterationNum = Math.floor(Date.now() / 300000) % 99;

    // Generate realistic price data
    const btcPrice = 68800 + (Math.random() - 0.5) * 2000;
    const ethPrice = 2100 + (Math.random() - 0.5) * 200;
    const bnbPrice = 634 + (Math.random() - 0.5) * 50;

    // Generate z-scores
    const btcZScore = (Math.random() - 0.5) * 4;
    const ethZScore = (Math.random() - 0.5) * 4;
    const bnbZScore = (Math.random() - 0.5) * 4;

    const getSignal = (zScore: number) => {
      if (Math.abs(zScore) > 1.0) return zScore > 0 ? 'LONG' : 'SHORT';
      return 'HOLD';
    };

    // Create logs in the correct order matching EC2 terminal output
    logs = [
      // Crypto signals first (newest to oldest in display)
      {
        timestamp: new Date(now.getTime() - 7000).toISOString(),
        level: 'INFO',
        message: `${getSignal(bnbZScore) === 'HOLD' ? '⏸️' : getSignal(bnbZScore) === 'LONG' ? '🟢' : '🔴'} BNB/USDT: $${bnbPrice.toFixed(2)} | Z-Score: ${bnbZScore.toFixed(2)} | Signal: ${getSignal(bnbZScore)}`
      },
      {
        timestamp: new Date(now.getTime() - 6000).toISOString(),
        level: 'INFO',
        message: `${getSignal(ethZScore) === 'HOLD' ? '⏸️' : getSignal(ethZScore) === 'LONG' ? '🟢' : '🔴'} ETH/USDT: $${ethPrice.toFixed(2)} | Z-Score: ${ethZScore.toFixed(2)} | Signal: ${getSignal(ethZScore)}`
      },
      {
        timestamp: new Date(now.getTime() - 5000).toISOString(),
        level: 'INFO',
        message: `${getSignal(btcZScore) === 'HOLD' ? '⏸️' : getSignal(btcZScore) === 'LONG' ? '🟢' : '🔴'} BTC/USDT: $${btcPrice.toFixed(2)} | Z-Score: ${btcZScore.toFixed(2)} | Signal: ${getSignal(btcZScore)}`
      },
      // Separator
      {
        timestamp: new Date(now.getTime() - 4000).toISOString(),
        level: 'INFO',
        message: '------------------------------------------------------------'
      },
      // Market analysis header
      {
        timestamp: new Date(now.getTime() - 3000).toISOString(),
        level: 'INFO',
        message: '📊 MARKET ANALYSIS (V6 PARAMETERS)'
      },
      // Separator
      {
        timestamp: new Date(now.getTime() - 2000).toISOString(),
        level: 'INFO',
        message: '------------------------------------------------------------'
      },
      // Iteration header last (most recent)
      {
        timestamp: new Date(now.getTime() - 1000).toISOString(),
        level: 'INFO',
        message: `🔄 ITERATION #${iterationNum} - ${now.toLocaleTimeString()} (SIMULATED - EC2 CONNECTION NEEDED)`
      }
    ];

    return NextResponse.json({
      success: true,
      logs: logs // Display in chronological order like terminal
    });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: 'Failed to fetch EC2 logs' },
      { status: 500 }
    );
  }
}

// WebSocket endpoint for real-time streaming (future enhancement)
export async function POST(request: NextRequest) {
  // This would establish a WebSocket connection to stream logs
  // For now, return a message indicating the feature
  return NextResponse.json({
    message: 'WebSocket streaming not yet implemented. Use GET for polling.'
  });
}