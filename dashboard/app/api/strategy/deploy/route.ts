import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';

interface StrategyConfig {
  strategy_name: string;
  trading_mode: 'paper' | 'live';
  symbol_1: string;
  symbol_2: string;
  lookback_period: number;
  entry_z_score: number;
  exit_z_score: number;
  stop_loss_z_score: number;
  position_size: number;
  max_positions: number;
  rebalance_frequency: number;
  api_key: string;
  api_secret: string;
  testnet: boolean;
}

// Store active strategy processes
const activeStrategies = new Map<string, any>();

export async function POST(request: Request) {
  try {
    const config: StrategyConfig = await request.json();

    // Validate configuration
    if (!config.api_key || !config.api_secret) {
      return NextResponse.json({
        success: false,
        error: 'API credentials are required'
      }, { status: 400 });
    }

    if (!config.symbol_1 || !config.symbol_2) {
      return NextResponse.json({
        success: false,
        error: 'Trading symbols are required'
      }, { status: 400 });
    }

    // Generate unique process ID
    const processId = `strategy_${Date.now()}_${Math.random().toString(36).substring(7)}`;

    // Create config file for the strategy
    const configDir = path.join(process.cwd(), 'strategy_configs');
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }

    const configPath = path.join(configDir, `${processId}.json`);
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));

    // Get the Python executable path
    const pythonPath = process.platform === 'win32' ? 'python' : 'python3';

    // Path to the strategy executor script
    const scriptPath = path.join(process.cwd(), 'strategy_executor.py');

    // Check if script exists
    if (!fs.existsSync(scriptPath)) {
      return NextResponse.json({
        success: false,
        error: 'Strategy executor script not found. Please ensure strategy_executor.py is in the project root.'
      }, { status: 500 });
    }

    // Spawn the Python process
    const strategyProcess = spawn(pythonPath, [
      scriptPath,
      '--config', configPath,
      '--mode', config.trading_mode
    ], {
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    // Store process reference
    activeStrategies.set(processId, {
      process: strategyProcess,
      config: config,
      startTime: new Date(),
      pid: strategyProcess.pid
    });

    // Log output
    const logDir = path.join(process.cwd(), 'strategy_logs');
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }

    const logPath = path.join(logDir, `${processId}.log`);
    const logStream = fs.createWriteStream(logPath, { flags: 'a' });

    strategyProcess.stdout?.pipe(logStream);
    strategyProcess.stderr?.pipe(logStream);

    // Handle process events
    strategyProcess.on('error', (error) => {
      console.error(`Strategy process error: ${error}`);
      activeStrategies.delete(processId);
    });

    strategyProcess.on('exit', (code, signal) => {
      console.log(`Strategy process exited with code ${code} and signal ${signal}`);
      activeStrategies.delete(processId);
    });

    // Log initial deployment
    logStream.write(`[${new Date().toISOString()}] Strategy deployed: ${config.strategy_name}\n`);
    logStream.write(`[${new Date().toISOString()}] Mode: ${config.trading_mode}\n`);
    logStream.write(`[${new Date().toISOString()}] Symbols: ${config.symbol_1} / ${config.symbol_2}\n`);
    logStream.write(`[${new Date().toISOString()}] Process ID: ${processId}\n`);
    logStream.write(`[${new Date().toISOString()}] System PID: ${strategyProcess.pid}\n`);

    // Don't wait for the subprocess (let it run in background)
    strategyProcess.unref();

    return NextResponse.json({
      success: true,
      processId: processId,
      pid: strategyProcess.pid,
      message: `Strategy deployed successfully in ${config.trading_mode} mode`,
      logFile: `strategy_logs/${processId}.log`,
      configFile: `strategy_configs/${processId}.json`
    });

  } catch (error) {
    console.error('Strategy deployment error:', error);
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to deploy strategy'
    }, { status: 500 });
  }
}

export async function GET() {
  // Get list of active strategies
  const strategies = Array.from(activeStrategies.entries()).map(([id, data]) => ({
    processId: id,
    pid: data.pid,
    strategy_name: data.config.strategy_name,
    trading_mode: data.config.trading_mode,
    symbols: `${data.config.symbol_1}/${data.config.symbol_2}`,
    startTime: data.startTime,
    status: data.process.killed ? 'stopped' : 'running'
  }));

  return NextResponse.json({
    strategies,
    count: strategies.length
  });
}