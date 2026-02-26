import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Helper function to execute command with timeout
const execWithTimeout = async (command: string, timeout: number = 10000) => {
  return Promise.race([
    execAsync(command),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Command timeout')), timeout)
    )
  ]);
};

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      strategy_name,
      trading_mode,
      universe,
      lookback_period,
      entry_z_score,
      exit_z_score,
      stop_loss_z_score,
      position_size,
      max_positions,
      rebalance_frequency,
      api_key,
      api_secret,
      testnet
    } = body;

    // EC2 connection details from environment variables
    const EC2_HOST = process.env.EC2_HOST;
    const EC2_USER = process.env.EC2_USER || 'ubuntu';
    const EC2_KEY_PATH = process.env.EC2_KEY_PATH;
    const EC2_PROJECT_PATH = process.env.EC2_PROJECT_PATH || 'stat-arb-platform';

    if (!EC2_HOST || !EC2_KEY_PATH) {
      return NextResponse.json({
        success: false,
        error: 'EC2 connection configuration not found in environment variables'
      }, { status: 400 });
    }

    if (!api_key || !api_secret) {
      return NextResponse.json({
        success: false,
        error: 'API credentials are required'
      }, { status: 400 });
    }

    // SSH command to connect to EC2
    const sshCommand = `ssh -i "${EC2_KEY_PATH}" -o ConnectTimeout=10 -o StrictHostKeyChecking=no ${EC2_USER}@${EC2_HOST}`;

    // Create strategy configuration with proper key mapping
    const strategyConfig = {
      strategy_name,
      trading_mode,
      trading_pairs: universe, // Map universe to trading_pairs for strategy compatibility
      universe,
      lookback_period,
      entry_z_score,
      exit_z_score,
      stop_loss_z_score,
      entry_threshold: entry_z_score, // Map entry_z_score to entry_threshold
      exit_threshold: exit_z_score, // Map exit_z_score to exit_threshold
      stop_loss: 0.035, // Add default stop loss percentage
      take_profit: 0.05, // Add default take profit
      position_size,
      max_positions,
      rebalance_frequency,
      update_interval: rebalance_frequency || 5, // Add missing update_interval
      enable_trading: true, // Enable trading
      risk_per_trade: 0.02, // Risk per trade
      max_daily_loss: 0.15, // Max daily loss
      use_testnet: testnet, // Map testnet to use_testnet
      v6_parameters: { // Add V6 parameters for enhanced trading logic
        z_entry: entry_z_score,
        z_exit_long: exit_z_score,
        z_exit_short: exit_z_score * 0.5, // Tighter exit for shorts
        z_stop: stop_loss_z_score,
        min_correlation: 0.40,
        min_half_life: 2,
        max_half_life: 120,
        target_vol: 0.20,
        max_portfolio_leverage: 6.0
      },
      api_key,
      api_secret,
      testnet
    };

    console.log('🚀 Deploying strategy to EC2 server...');
    console.log('Strategy config:', JSON.stringify(strategyConfig, null, 2));

    // Execute deployment in multiple steps to avoid command length issues
    let processRunning = false;
    try {
      // Step 1: Stop any existing processes and clean logs (simplified to avoid SSH issues)
      console.log('Step 1: Stopping existing processes and cleaning logs...');
      try {
        const stopCommand = `${sshCommand} 'cd ${EC2_PROJECT_PATH} && (pkill -f enhanced_strategy_executor 2>/dev/null || true) && rm -f strategy_logs.txt && echo "Cleaned"'`;
        await execWithTimeout(stopCommand, 5000);
      } catch (stopError) {
        console.log('Note: Stop command had issues but continuing with deployment');
      }

      // Step 2: Create configuration file (using echo to avoid heredoc issues)
      console.log('Step 2: Creating configuration file...');
      const configJson = JSON.stringify(strategyConfig).replace(/'/g, "'\\''");
      const configCommand = `${sshCommand} 'cd ${EC2_PROJECT_PATH} && echo '"'"'${configJson}'"'"' > strategy_config.json'`;
      await execWithTimeout(configCommand, 5000);

      // Step 3: Start the strategy with log output
      console.log('Step 3: Starting strategy with fresh logs...');
      const startCommand = `${sshCommand} 'cd ${EC2_PROJECT_PATH} && nohup python3 src/enhanced_strategy_executor_fixed.py > strategy_logs.txt 2>&1 & echo "Started"'`;
      await execWithTimeout(startCommand, 5000);

      // Step 4: Wait and check if process is running
      console.log('Step 4: Verifying deployment...');
      await new Promise(resolve => setTimeout(resolve, 3000)); // Wait 3 seconds for process to start

      let stdout = '';
      try {
        const checkCommand = `${sshCommand} 'cd ${EC2_PROJECT_PATH} && ps aux | grep enhanced_strategy_executor | grep -v grep'`;
        const result = await execWithTimeout(checkCommand, 5000) as any;
        stdout = result.stdout;
      } catch (checkError) {
        console.log('Process check had issues');
      }

      processRunning = stdout && !stdout.includes('Process not found');

      console.log('✅ Strategy deployment completed');
      console.log('Process running:', processRunning);
      console.log('Check output:', stdout);

    } catch (execError: any) {
      console.error('SSH command execution failed:', execError);
      return NextResponse.json({
        success: false,
        error: `SSH command failed: ${execError.message}`,
        details: {
          stdout: execError.stdout || '',
          stderr: execError.stderr || '',
          code: execError.code
        }
      }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      message: 'Strategy deployed to EC2 server',
      processRunning,
      output: 'Deployment completed successfully',
      errors: '',
      config: strategyConfig
    });

  } catch (error) {
    console.error('❌ Error deploying strategy to EC2:', error);

    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to deploy strategy to EC2',
      details: error instanceof Error ? error.stack : undefined
    }, { status: 500 });
  }
}